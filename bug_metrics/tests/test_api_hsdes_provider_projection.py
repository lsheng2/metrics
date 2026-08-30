from django.test import TestCase

from bug_metrics.app.api import bug_trend_api


class TestHsdesProviderProjection(TestCase):
    def test_shouldNormalizeHsdesSearchPageIntoProviderNeutralFacts(self):
        # Given
        payload = {
            'start_at': 0,
            'max_results': 1,
            'total': 2,
            'articles': [
                {
                    'id': '16000000001',
                    'rev': '7',
                    'fieldValues': {
                        'HSD_type': 'bug',
                        'status': 'open',
                        'component': 'fwsw',
                        'release': 'NVU-FW.trunk',
                        'target_MS': 'NVU_TTL_FWSW0.8',
                        'owner': 'alice',
                        'priority': 'high',
                        'submitted_by': 'bob',
                        'submitted_date': '2026-08-03T08:00:00Z',
                        'updated_date': '2026-08-04T09:30:00Z',
                    },
                }
            ],
            'errors': [{'code': 'partial_lookup_timeout', 'message': 'lookup timeout'}],
        }

        # When
        projection = bug_trend_api.normalize_hsdes_search_page('nvu-ttl-hsdes', payload)

        # Then
        fact = projection['facts'][0]
        self.assertEqual('hsdes', fact['provider_id'])
        self.assertEqual('16000000001', fact['source_item_id'])
        self.assertEqual('7', fact['source_item_revision'])
        self.assertEqual('ip_fw_sw_sensing.tenant', fact['tenant'])
        self.assertEqual('ip_fw_sw_sensing.bug', fact['subject'])
        self.assertEqual('open', fact['canonical_fields']['source_state'])
        self.assertEqual('fwsw', fact['canonical_fields']['component_or_area'])
        self.assertEqual('NVU-FW.trunk', fact['canonical_fields']['release_target'])
        self.assertEqual('NVU_TTL_FWSW0.8', fact['canonical_fields']['milestone'])
        self.assertEqual('alice', fact['canonical_fields']['owner'])
        self.assertEqual(payload['articles'][0]['fieldValues'], fact['field_values'])
        self.assertEqual({'start_at': 0, 'max_results': 1, 'total': 2, 'next_start_at': 1, 'has_more': True}, projection['pagination'])
        self.assertEqual(payload['errors'], projection['errors'])

    def test_shouldNormalizeHsdesSearchPageWithFlatFieldValuesFromLiveApi(self):
        # Given
        payload = {
            'start_at': 1,
            'max_results': 1,
            'total': 1,
            'data': [
                {
                    'id': '14028237321',
                    'rev': '16',
                    'HSD_type': 'bug',
                    'status': 'implemented',
                    'component': 'ip.ish.fw.bsp',
                    'release': 'NVU-FW1.0_TTL',
                    'target_MS': 'NVU_TTL_FWSW0.8',
                    'owner': 'wchew',
                    'priority': 'p3-medium',
                    'exposure': '3-medium',
                    'submitted_by': 'wchew',
                    'submitted_date': '2026-07-13 12:52:08.18',
                    'updated_date': '2026-07-29 16:55:10.673',
                    'implemented_date': '2026-07-22 13:59:22.0',
                    'team_found': 'Non COE',
                },
            ],
        }

        # When
        projection = bug_trend_api.normalize_hsdes_search_page('nvu-ttl-hsdes', payload)

        # Then
        fact = projection['facts'][0]
        self.assertEqual('bug', fact['canonical_fields']['source_item_type'])
        self.assertEqual('implemented', fact['canonical_fields']['source_state'])
        self.assertEqual('ip.ish.fw.bsp', fact['canonical_fields']['component_or_area'])
        self.assertEqual('3-medium', fact['canonical_fields']['severity_or_priority'])
        self.assertEqual('2026-07-13 12:52:08.18', fact['canonical_fields']['created_at'])
        self.assertEqual('Non COE', fact['project_fields']['team_found'])
        self.assertEqual('bug', fact['field_values']['HSD_type'])

    def test_shouldNormalizeHsdesDetailLinksCommentsAndErrors(self):
        # Given
        payload = {
            'id': '16000000001',
            'rev': '8',
            'fieldValues': {
                'HSD_type': 'bug',
                'status': 'implemented',
                'component': 'fwsw',
                'closed_date': '2026-08-05T10:00:00Z',
            },
            'comments': [
                {
                    'id': 'comment-1',
                    'subject': 'comments',
                    'fieldValues': {'comment': 'fixed in build', 'submitted_by': 'alice'},
                }
            ],
            'links': [{'relationship': 'relates_to', 'target_id': 'JIRA-123'}],
            'children': [{'id': '16000000002', 'rev': '1'}],
            'errors': [{'code': 'link_permission_denied', 'message': 'links unavailable'}],
        }

        # When
        detail = bug_trend_api.normalize_hsdes_article_detail('nvu-ttl-hsdes', payload)

        # Then
        self.assertEqual('16000000001', detail['fact']['source_item_id'])
        self.assertEqual('8', detail['fact']['source_item_revision'])
        self.assertEqual('implemented', detail['fact']['canonical_fields']['source_state'])
        self.assertEqual(payload['comments'], detail['comments'])
        self.assertEqual(payload['links'], detail['links'])
        self.assertEqual(payload['children'], detail['children'])
        self.assertEqual(payload['errors'], detail['errors'])
