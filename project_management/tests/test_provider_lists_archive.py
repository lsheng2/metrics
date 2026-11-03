from io import BytesIO
import re
import stat
import struct
from unittest import TestCase
from unittest.mock import patch
from zipfile import ZIP_BZIP2, ZipFile, ZipInfo

from project_management.app.api.spreadsheet import SpreadsheetBounds, SpreadsheetError, extract_workbook, inspect_workbook
from project_management.tests.spreadsheet_fixtures import rewrite_workbook, workbook_bytes


class TestProviderWorkbookArchive(TestCase):
    def test_shouldRejectEncryptionSymlinksAndUnsupportedCompression(self):
        raw = self.raw()
        with ZipFile(BytesIO(raw)) as book:
            local = book.infolist()[0].header_offset
            central = book.start_dir
        encrypted = bytearray(raw)
        struct.pack_into('<H', encrypted, local + 6, struct.unpack_from('<H', raw, local + 6)[0] | 1)
        struct.pack_into('<H', encrypted, central + 8, struct.unpack_from('<H', raw, central + 8)[0] | 1)
        symlink = ZipInfo('xl/link.xml')
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        compressed = ZipInfo('customXml/other.xml')
        compressed.compress_type = ZIP_BZIP2
        cases = [bytes(encrypted), rewrite_workbook(raw, extras=[(symlink, b'target')]),
                 rewrite_workbook(raw, extras=[(compressed, b'<root/>')])]
        for number, data in enumerate(cases):
            with self.subTest(number=number), self.assertRaises(SpreadsheetError) as caught:
                inspect_workbook(data)
            self.assertEqual('SPREADSHEET_ARCHIVE_INVALID', caught.exception.code)

    def raw(self):
        return workbook_bytes([['ID'], ['ALPHA-1'], ['ALPHA-2']])

    def extract(self, raw, **kwargs):
        return extract_workbook(raw, provider_id='jira', sheet='Scope', column='A', **kwargs)

    def test_shouldIgnoreForgedSmallDimensionsAndKeepAllSelectedRows(self):
        raw = self.raw()
        with ZipFile(BytesIO(raw)) as book:
            sheet = re.sub(rb'<dimension ref="[^"]+"', b'<dimension ref="A1:A1"', book.read('xl/worksheets/sheet1.xml'))
        self.assertEqual(('ALPHA-1', 'ALPHA-2'),
                         self.extract(rewrite_workbook(raw, {'xl/worksheets/sheet1.xml': sheet}))['tokens'])

    def test_shouldRefuseUnsafeDuplicateAndEncryptedArchiveEntries(self):
        for name in ('../outside.xml', '/absolute.xml', 'C:/outside.xml', 'xl\\escape.xml'):
            stored = name.replace('\\', '/')
            raw = rewrite_workbook(self.raw(), extras=[(stored, b'<root/>')])
            if name != stored:
                raw = raw.replace(stored.encode(), name.encode())
            with self.subTest(name=name), self.assertRaises(SpreadsheetError) as caught:
                inspect_workbook(raw)
            self.assertEqual('SPREADSHEET_ARCHIVE_INVALID', caught.exception.code)
        with self.assertWarns(UserWarning):
            raw = rewrite_workbook(self.raw(), extras=[('xl/workbook.xml', b'<wrong/>')])
        with self.assertRaises(SpreadsheetError):
            inspect_workbook(raw)

    def test_shouldRefuseXmlEntitiesBeforeWorkbookLibraryLoads(self):
        for encoding in ('utf-8', 'utf-16'):
            xml = (f'<?xml version="1.0" encoding="{encoding}"?>'
                   '<!DOCTYPE root [<!ENTITY repeated "ALPHA-999">]><root>&repeated;</root>').encode(encoding)
            raw = rewrite_workbook(self.raw(), {'xl/workbook.xml': xml})
            with self.subTest(encoding=encoding), patch(
                'openpyxl.load_workbook', side_effect=AssertionError('Unsafe XML reached workbook loading')
            ), self.assertRaises(SpreadsheetError) as caught:
                inspect_workbook(raw)
            self.assertEqual('SPREADSHEET_XML_INVALID', caught.exception.code)

    def test_shouldRejectInputExpansionEntryDepthAndElementOverflow(self):
        cases = [
            (b'x' * 524289, 'SPREADSHEET_INPUT_LIMIT'),
            (rewrite_workbook(self.raw(), extras=[('large.bin', b'x' * (8 * 1024**2 + 1))]), 'SPREADSHEET_EXPANSION_LIMIT'),
            (rewrite_workbook(self.raw(), extras=[(f'extra/{i}.bin', b'') for i in range(129)]), 'SPREADSHEET_ARCHIVE_LIMIT'),
            (rewrite_workbook(self.raw(), {'xl/workbook.xml': b'<x>' * 65 + b'</x>' * 65}), 'SPREADSHEET_XML_LIMIT'),
            (rewrite_workbook(self.raw(), extras=[('customXml/large.xml', b'<root>' + b'<x/>' * 100001 + b'</root>')]), 'SPREADSHEET_XML_LIMIT'),
        ]
        for raw, code in cases:
            with self.subTest(code=code), self.assertRaises(SpreadsheetError) as caught:
                inspect_workbook(raw)
            self.assertEqual(code, caught.exception.code)

    def test_shouldRefuseUnsupportedOrCorruptContainers(self):
        for raw in (b'', b'not a workbook', b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
            with self.subTest(raw=raw), self.assertRaises(SpreadsheetError) as caught:
                inspect_workbook(raw)
            self.assertEqual('SPREADSHEET_FORMAT_UNSUPPORTED', caught.exception.code)
        raw = rewrite_workbook(self.raw(), extras=[('bad.bin', b'x' * 128)])
        with ZipFile(BytesIO(raw)) as book:
            entry = book.getinfo('bad.bin')
            name_size, extra_size = struct.unpack_from('<HH', raw, entry.header_offset + 26)
            offset = entry.header_offset + 30 + name_size + extra_size
        changed = bytearray(raw)
        changed[offset] = 6
        with self.assertRaises(SpreadsheetError) as caught:
            inspect_workbook(bytes(changed))
        self.assertEqual('SPREADSHEET_ARCHIVE_INVALID', caught.exception.code)

    def test_shouldRejectAmbiguousRowsAndCells(self):
        rows = [
            b'<row r="2"><c r="A2" t="inlineStr"><is><t>ALPHA-1</t></is></c></row>'
            b'<row r="2"><c r="A2" t="inlineStr"><is><t>ALPHA-2</t></is></c></row>',
            b'<row r="2"><c r="B2" t="inlineStr"><is><t>ALPHA-1</t></is></c>'
            b'<c r="A2" t="inlineStr"><is><t>ALPHA-2</t></is></c></row>',
            b'<row r="2"><c r="A3" t="inlineStr"><is><t>ALPHA-1</t></is></c></row>',
        ]
        raw = self.raw()
        for replacement in rows:
            with ZipFile(BytesIO(raw)) as book:
                sheet = re.sub(rb'<sheetData>.*?</sheetData>', b'<sheetData>' + replacement + b'</sheetData>',
                               book.read('xl/worksheets/sheet1.xml'))
            with self.subTest(replacement=replacement), self.assertRaises(SpreadsheetError) as caught:
                self.extract(rewrite_workbook(raw, {'xl/worksheets/sheet1.xml': sheet}))
            self.assertEqual('SPREADSHEET_WORKBOOK_INVALID', caught.exception.code)

    def test_shouldBoundSparseRowsAndDiagnosticCounts(self):
        raw = self.raw()
        with ZipFile(BytesIO(raw)) as book:
            sheet = book.read('xl/worksheets/sheet1.xml').replace(b'r="3"', b'r="20000"').replace(b'r="A3"', b'r="A20000"')
        with self.assertRaises(SpreadsheetError) as caught:
            self.extract(rewrite_workbook(raw, {'xl/worksheets/sheet1.xml': sheet}))
        self.assertEqual('SPREADSHEET_ROW_LIMIT', caught.exception.code)
        with self.assertRaises(SpreadsheetError) as caught:
            self.extract(workbook_bytes([['ID'], ['bad'], ['wrong']]), limits=SpreadsheetBounds(diagnostics=1))
        self.assertEqual('SPREADSHEET_DIAGNOSTIC_LIMIT', caught.exception.code)

    def test_shouldReadMacroWorkbookAsDataWithoutExecutingOrPreservingVba(self):
        raw = self.raw()
        with ZipFile(BytesIO(raw)) as book:
            types = book.read('[Content_Types].xml').replace(
                b'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml',
                b'application/vnd.ms-excel.sheet.macroEnabled.main+xml')
        result = self.extract(rewrite_workbook(raw, {'[Content_Types].xml': types},
                                               [('xl/vbaProject.bin', b'UNEXECUTED')]))
        self.assertEqual(('ALPHA-1', 'ALPHA-2'), result['tokens'])
