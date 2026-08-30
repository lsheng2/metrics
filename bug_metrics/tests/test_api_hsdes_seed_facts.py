import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase

from bug_metrics.app.api.hsdes_seed_facts import HsdesSeedFactRepository


class TestHsdesSeedFacts(TestCase):
    def test_shouldPreferLocalPreviewSeedWhenItExists(self):
        # Given
        with TemporaryDirectory() as directory:
            fallback_path = Path(directory) / 'fallback.json'
            preview_path = Path(directory) / 'preview.json'
            fallback_path.write_text(json.dumps(self._seed_payload('fallback-id')), encoding='utf-8')
            preview_path.write_text(json.dumps(self._seed_payload('preview-id')), encoding='utf-8')

            repository = HsdesSeedFactRepository(seed_path=fallback_path, preview_seed_path=preview_path)

            # When
            facts = repository.facts_for_profile('nvu-ttl-hsdes')

            # Then
            self.assertEqual('preview-id', facts[0]['source_item_id'])

    def _seed_payload(self, article_id):
        return {
            'profile_id': 'nvu-ttl-hsdes',
            'seeded_from_query_id': '15017652869',
            'articles': [
                {
                    'id': article_id,
                    'rev': '1',
                    'fieldValues': {
                        'HSD_type': 'bug',
                        'status': 'open',
                        'component': 'fwsw',
                        'submitted_date': '2026-08-03T08:00:00Z',
                    },
                }
            ],
        }
