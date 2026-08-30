import io
import json

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase


class TestLiveHsdesSmoke(TestCase):
    def test_shouldSyncConfiguredHsdesProfileThroughLiveSmokeCommand(self):
        # Given
        if not getattr(settings, 'METRICS_HSDES_LIVE_SYNC_ENABLED', False):
            self.skipTest('Live HSD-ES smoke test requires METRICS_HSDES_LIVE_SYNC_ENABLED=true.')
        output = io.StringIO()

        # When
        call_command('sync_hsdes_profile', '--begin-ww', '26WW32', '--end-ww', '26WW32', '--force-refresh', stdout=output)

        # Then
        payload = json.loads(output.getvalue())
        self.assertEqual('success', payload['status'])
        self.assertEqual('nvu-ttl-hsdes', payload['profile_id'])
        self.assertGreater(payload['fact_count'], 0)
        self.assertGreater(payload['artifact_count'], 0)
        self.assertNotIn('token', json.dumps(payload).lower())
        self.assertNotIn('password', json.dumps(payload).lower())
