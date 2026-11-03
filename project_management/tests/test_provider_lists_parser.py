from datetime import datetime
from hashlib import sha256
from io import BytesIO
import inspect
from unittest import TestCase
from unittest.mock import patch

import openpyxl
from openpyxl.worksheet._read_only import ReadOnlyWorksheet

from project_management.app.api.spreadsheet import SpreadsheetBounds, SpreadsheetError, extract_workbook, inspect_workbook
from project_management.tests.spreadsheet_fixtures import workbook_bytes


class TestProviderWorkbookParser(TestCase):
    def extract(self, raw, provider_id='jira', **options):
        return extract_workbook(raw, provider_id=provider_id, sheet='Scope', column='A', **options)

    def test_shouldExtractOnlySelectedColumnAndKeepOriginalRows(self):
        raw = workbook_bytes([['Title', 'ID'], ['one', ' ALPHA-2 '], ['two', 101],
                              ['blank', None], ['repeat', 'ALPHA-2']])
        result = extract_workbook(raw, provider_id='jira', sheet='Scope', column='b')
        self.assertEqual(('ALPHA-2', '101'), result['tokens'])
        self.assertEqual(sha256(raw).hexdigest(), result['source_sha256'])
        self.assertEqual([('B2', ' ALPHA-2 '), ('B3', 101), ('B5', 'ALPHA-2')],
                         [(row['cell'], row['raw_value']) for row in result['selected_rows']])
        self.assertEqual((1, 1, False, True),
                         (result['blank_rows'], result['duplicate_rows'], result['resolved'], result['can_confirm']))
        self.assertEqual([('B5', 'DUPLICATE')], [(row['cell'], row['code']) for row in result['diagnostics']])

    def test_shouldInspectSheetsWithoutChoosingAMembership(self):
        raw = workbook_bytes([['ID'], ['ALPHA-1']])
        result = inspect_workbook(raw)
        self.assertEqual(('Scope', 'Unselected'), result['sheets'])
        self.assertNotIn('tokens', result)

    def test_shouldUseHsdArticleSyntaxWithoutJiraFallback(self):
        result = self.extract(workbook_bytes([['ID'], ['15017652869'], ['12345678901234567890'], ['ALPHA-1']]), 'hsdes')
        self.assertEqual(('15017652869', '12345678901234567890'), result['tokens'])
        self.assertEqual((False, 'INVALID_TOKEN'), (result['can_confirm'], result['diagnostics'][0]['code']))

    def test_shouldRejectUnknownProviderBeforeReadingWorkbook(self):
        with self.assertRaises(SpreadsheetError) as caught:
            self.extract(b'not even a workbook', 'unknown')
        self.assertEqual('SPREADSHEET_PROVIDER_UNSUPPORTED', caught.exception.code)

    def test_shouldRejectInvalidCellsWithoutApprovingTheValidSubset(self):
        raw = workbook_bytes([['ID'], ['ALPHA-1'], ['=HYPERLINK("https://invalid.example","ALPHA-2")'],
                              [True], [datetime(2026, 10, 28)], ['not an ID'], [0], [1.5],
                              [1000000000000000], ['<script>bad</script>']])
        result = self.extract(raw)
        self.assertEqual(('ALPHA-1',), result['tokens'])
        self.assertFalse(result['can_confirm'])
        self.assertEqual(list(range(3, 11)), [row['row'] for row in result['diagnostics']])
        self.assertEqual('FORMULA', result['diagnostics'][0]['code'])

    def test_shouldPreserveLongStringIdsAndKeyCase(self):
        result = self.extract(workbook_bytes([['ID'], ['123456789012345678901234567890'], ['Mixed_Key-4'], [42.0]]))
        self.assertEqual(('123456789012345678901234567890', 'Mixed_Key-4', '42'), result['tokens'])

    def test_shouldRejectInvalidExplicitSelection(self):
        raw = workbook_bytes([['ID'], ['ALPHA-1']])
        for selection in [
            {'sheet': 'missing', 'column': 'A', 'first_row': 2},
            {'sheet': 'Scope', 'column': 'A0', 'first_row': 2},
            {'sheet': 'Scope', 'column': 'XFE', 'first_row': 2},
            {'sheet': 'Scope', 'column': True, 'first_row': 2},
            {'sheet': 'Scope', 'column': 'A', 'first_row': True},
            {'sheet': 'Scope', 'column': 'A', 'first_row': 0},
            {'sheet': 'Scope', 'column': 'A', 'first_row': 1048577},
        ]:
            with self.subTest(selection=selection), self.assertRaises(SpreadsheetError) as caught:
                extract_workbook(raw, provider_id='jira', **selection)
            self.assertEqual('SPREADSHEET_SELECTION_INVALID', caught.exception.code)

    def test_shouldRefuseLimitsInsteadOfTruncatingScope(self):
        raw = workbook_bytes([['ID'], ['ALPHA-1'], ['ALPHA-2'], ['ALPHA-3']])
        with self.assertRaises(SpreadsheetError) as caught:
            self.extract(raw, max_items=2)
        self.assertEqual('SPREADSHEET_ITEM_LIMIT', caught.exception.code)
        for value in (0, 501, True):
            with self.subTest(value=value), self.assertRaises(SpreadsheetError):
                self.extract(raw, max_items=value)
        for overrides in ({'input_bytes': 524289}, {'scan_rows': 0}, {'diagnostics': True}, {'worksheets': 33}):
            with self.subTest(overrides=overrides), self.assertRaises(SpreadsheetError):
                SpreadsheetBounds(**overrides)

    def test_shouldNotTreatEmptyRangeAsApprovedEmptyScope(self):
        result = self.extract(workbook_bytes([['ID'], [None]], others=False))
        self.assertEqual(((), False, 'EMPTY_SCOPE'),
                         (result['tokens'], result['can_confirm'], result['diagnostics'][0]['code']))

    def test_shouldCloseActualWorkbookAndIteratorWhenCancelledDuringRows(self):
        raw = workbook_bytes([['ID'], ['ALPHA-1'], ['ALPHA-2']])
        original_load = openpyxl.load_workbook
        original_rows = ReadOnlyWorksheet.iter_rows
        books, iterators, closed = [], [], []
        failure = RuntimeError('Controlled cancellation')

        def load(*args, **kwargs):
            book = original_load(*args, **kwargs)
            close = book.close

            def close_book():
                close()
                closed.append(True)

            book.close = close_book
            books.append(book)
            return book

        def rows(worksheet, *args, **kwargs):
            iterator = original_rows(worksheet, *args, **kwargs)
            iterators.append(iterator)
            return iterator

        def check():
            if iterators and inspect.getgeneratorstate(iterators[-1]) == 'GEN_SUSPENDED':
                raise failure

        with patch('openpyxl.load_workbook', load), patch.object(ReadOnlyWorksheet, 'iter_rows', rows):
            with self.assertRaises(RuntimeError) as caught:
                self.extract(raw, check=check)
        self.assertIs(failure, caught.exception)
        self.assertEqual([True], closed)
        self.assertEqual('GEN_CLOSED', inspect.getgeneratorstate(iterators[-1]))

    def test_shouldAcceptSupportedSheetCountAndRefuseTheNextSheet(self):
        book = openpyxl.Workbook()
        for index in range(1, 32):
            book.create_sheet(f'Sheet{index}')
        output = BytesIO()
        book.save(output)
        self.assertEqual(32, len(inspect_workbook(output.getvalue())['sheets']))
        book.create_sheet('Sheet32')
        output = BytesIO()
        book.save(output)
        book.close()
        with self.assertRaises(SpreadsheetError) as caught:
            inspect_workbook(output.getvalue())
        self.assertEqual('SPREADSHEET_SHEET_LIMIT', caught.exception.code)
