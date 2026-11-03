from copy import deepcopy
import json
import unittest

from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario
from provider_sync.out.jira_consistency import consistent_responses
from provider_sync.tests.capture_gateway_fixtures import JiraFixture, attach_sink


PLUGIN = 'com.atlassian.jira.plugins.jira-development-integration-plugin:devsummary'
ROOT = 'com.atlassian.jira.plugin.devstatus.rest.SummaryBean'
ITEM = 'com.atlassian.jira.plugin.devstatus.rest.SummaryItemBean'
BRANCH = 'com.atlassian.jira.plugin.devstatus.summary.beans.BranchOverallBean'
FIELD = 'customfield_8080'


def rendered(address='ab12', *, count=1, json_count=1):
    prefix = (f'{{summaryBean={ROOT}@{address}[summary={{branch='
              f'{ITEM}@{address}[overall={BRANCH}@{address}[count={count}],byInstanceType={{}}]}}]')
    embedded = json.dumps({'cachedValue': {'branch': json_count}, 'isStale': False}, separators=(',', ':'))
    return prefix + ', devSummaryJson=' + embedded + '}'


def payload(address='ab12'):
    return {
        'id': '101', 'key': 'ALPHA-101', 'fields': {FIELD: rendered(address), 'summary': 'Business text'},
        'schema': {FIELD: {'type': 'any', 'custom': PLUGIN, 'customId': 8080}},
        'names': {FIELD: 'Development'},
    }


class TestJiraConsistency(unittest.TestCase):
    def test_shouldCompareKnownBeanAddressesWithoutChangingOriginals(self):
        before, after = payload(), payload('cd34')
        original = deepcopy((before, after))
        self.assertTrue(consistent_responses(before, after))
        self.assertEqual(original, (before, after))

    def test_shouldPreserveQuotedBusinessProperties(self):
        before, after = payload(), payload('cd34')
        before['fields'][FIELD] = rendered().replace('count=1', "count=1,state='UNKNOWN'")
        after['fields'][FIELD] = rendered('cd34').replace('count=1', "count=1,state='UNKNOWN'")
        self.assertTrue(consistent_responses(before, after))
        after['fields'][FIELD] = after['fields'][FIELD].replace("'UNKNOWN'", "'DONE'")
        self.assertFalse(consistent_responses(before, after))

    def test_shouldRejectUnprovenOrBusinessChangesAcrossTheDonorFailureFamily(self):
        cases = ('missing_schema', 'wrong_schema', 'wrong_id', 'schema_changed', 'prefix_count',
                 'json_value', 'unknown_class', 'unknown_hex', 'ordinary_text', 'json_identity',
                 'invalid_json', 'duplicate_json', 'trailing_text', 'other_field', 'quoted_prefix')
        for case in cases:
            before, after = payload(), payload('cd34')
            if case == 'missing_schema':
                before.pop('schema')
                after.pop('schema')
            elif case == 'wrong_schema':
                before['schema'][FIELD]['custom'] = after['schema'][FIELD]['custom'] = 'other:devsummary'
            elif case == 'wrong_id':
                before['schema'][FIELD]['customId'] = after['schema'][FIELD]['customId'] = 999
            elif case == 'schema_changed':
                after['schema'][FIELD]['extra'] = 'changed'
            elif case == 'prefix_count':
                after['fields'][FIELD] = rendered('cd34', count=2)
            elif case == 'json_value':
                after['fields'][FIELD] = rendered('cd34', json_count=2)
            elif case == 'unknown_class':
                before['fields'][FIELD] = rendered().replace('BranchOverallBean', 'UnknownBean')
                after['fields'][FIELD] = rendered('cd34').replace('BranchOverallBean', 'UnknownBean')
            elif case == 'unknown_hex':
                after['fields'][FIELD] = rendered('not_hex')
            elif case == 'ordinary_text':
                before['fields'][FIELD] = ROOT + '@ab12[ordinary note]'
                after['fields'][FIELD] = ROOT + '@cd34[ordinary note]'
            elif case == 'json_identity':
                before['fields'][FIELD] = rendered().replace('"branch":1', f'"branch":"{ROOT}@ab12["')
                after['fields'][FIELD] = rendered('cd34').replace('"branch":1', f'"branch":"{ROOT}@cd34["')
            elif case == 'invalid_json':
                after['fields'][FIELD] = rendered('cd34').replace('"isStale":false', '"isStale":invalid')
            elif case == 'duplicate_json':
                after['fields'][FIELD] = rendered('cd34').replace('"isStale":false', '"isStale":false,"isStale":false')
            elif case == 'trailing_text':
                after['fields'][FIELD] += ' unknown'
            elif case == 'other_field':
                before['fields']['description'] = ROOT + '@ab12['
                after['fields']['description'] = ROOT + '@cd34['
            else:
                before['fields'][FIELD] = rendered().replace('count=1', f'count=1,note="{ROOT}@ab12["')
                after['fields'][FIELD] = rendered('cd34').replace('count=1', f'count=1,note="{ROOT}@cd34["')
            with self.subTest(case=case):
                self.assertFalse(consistent_responses(before, after))


class TestJiraComparisonCapture(CaptureArchiveScenario, unittest.TestCase):
    def test_shouldKeepBothRawAddressesWhileAcceptingSchemaProvenConsistency(self):
        fixture = JiraFixture(self)
        fixture.rows[0]['fields'][FIELD] = rendered()
        fixture.rows[0]['schema'] = payload()['schema']
        original = fixture.respond
        count = []

        def respond(path, params):
            status, value = original(path, params)
            if path.endswith('/issue/101'):
                value = deepcopy(value)
                value['fields'][FIELD] = rendered('ab12' if not count else 'cd34')
                count.append(path)
            return status, value

        fixture.transport.responder = respond
        with fixture.service.open_capture(fixture.context(), online=True) as lease:
            raw = attach_sink(lease)
            observed = lease.capture_item(lease.enumerate().members[0])
            self.assertTrue(observed.snapshot.consistent)
            self.assertEqual(rendered(), observed.snapshot.facts[FIELD])
            addresses = [json.loads(row.payload)['fields'][FIELD] for row in raw if row.page_key.startswith('detail:')]
            self.assertEqual([rendered(), rendered('cd34')], addresses)
