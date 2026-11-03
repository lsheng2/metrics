import json
import time
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings

from bug_metrics.app.api.provider_connections import create_provider_connection_resolver
from bug_metrics.app.api.provider_credentials import CredentialAdoptionService
from bug_metrics.app.api.provider_profile_config import ProviderProfileConfigService, provider_profile_config_from_dict
from bug_metrics.models import BugTrendAuditEvent, ProviderProfileConfig
from bug_metrics.provider_connections.contracts import ConnectionError
from bug_metrics.provider_connections.protected_store import ProtectedCredentialStore
from provider_sync.tests.test_provider_connections import CapturingJiraFactory, SyntheticSettings
from provider_sync.tests.test_provider_credentials_native import create_protected_source_toml, write_protected_file


class FailingAfterIntentStore(ProtectedCredentialStore):
    def create_candidate(self, **kwargs):
        result = super().create_candidate(**kwargs)
        raise ConnectionError("INTERNAL_ERROR")


@override_settings(METRICS_PROVIDER_SECRET_MAX_BYTES=65536)
class TestProviderCredentialAdoption(TestCase):
    def test_shouldPreviewCredentialAdoptionWithoutDatabaseFileAuditOrSecretDisclosure(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = create_protected_source_toml(root / "source.toml", "preview-token")
            service = self._service(root)
            profile = self._save_jira_profile("preview-jira", token="old-token")
            profile_count = ProviderProfileConfig.objects.count()
            audit_count = BugTrendAuditEvent.objects.count()

            preview = service.preview(profile.profile_id, source_file)

            self.assertEqual(profile_count, ProviderProfileConfig.objects.count())
            self.assertEqual(audit_count, BugTrendAuditEvent.objects.count())
            self.assertEqual([], list((root / "secrets").glob("**/*")))
            self.assertEqual("preview-jira", preview.profile_id)
            self.assertEqual("jira", preview.provider_id)
            self.assertTrue(preview.conflict)
            self.assertNotIn("preview-token", str(preview.to_dict()))
            self.assertNotIn(str(source_file), str(preview.to_dict()))
            self.assertNotIn("old-token", repr(preview))
            self.assertNotIn("old-token", str(asdict(preview)))

    def test_shouldPreviewEmptyCredentialProfileWithoutResolvingExistingSecret(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = create_protected_source_toml(root / "source.toml", "new-token")
            service = CredentialAdoptionService(
                settings_source=SyntheticSettings(METRICS_JIRA_API_TOKEN=""),
                protected_store=ProtectedCredentialStore(root / "secrets", 65536),
            )
            profile = self._save_jira_profile("empty-credential-jira", token=None)

            preview = service.preview(profile.profile_id, source_file)

            self.assertEqual("empty-credential-jira", preview.profile_id)
            self.assertFalse(preview.conflict)

    def test_shouldTreatSettingsCredentialAsPreviewConflict(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = create_protected_source_toml(root / "source.toml", "settings-replacement")
            service = self._service(root)
            profile = self._save_jira_profile("settings-conflict-jira", token=None, credential_ref="settings:METRICS_JIRA_EMAIL/METRICS_JIRA_API_TOKEN")

            preview = service.preview(profile.profile_id, source_file)

            self.assertTrue(preview.conflict)

    def test_shouldRejectUnsupportedProviderOrAuthBeforeReadingSourceFile(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            missing_source = root / "missing.toml"
            service = self._service(root)
            profile = self._save_jira_profile("cloud-basic-jira", token="old-token")
            record = ProviderProfileConfig.objects.get(profile_id=profile.profile_id)
            record.connection_settings["auth_mode"] = "cloud_basic"
            record.save()

            with self.assertRaises(ConnectionError) as context:
                service.preview(profile.profile_id, missing_source)

            self.assertEqual("PROVIDER_UNSUPPORTED", context.exception.code)

    def test_shouldApplyPreviewIntoProtectedReferenceAndResolveThroughDefaultStore(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = create_protected_source_toml(root / "source.toml", "applied-token")
            service = self._service(root)
            profile = self._save_jira_profile("apply-jira", token="old-token")
            preview = service.preview(profile.profile_id, source_file)

            result = service.apply(profile.profile_id, source_file, expected_preview=preview, replace=True)

            updated = ProviderProfileConfig.objects.get(profile_id=profile.profile_id)
            self.assertEqual("applied", result.status)
            self.assertEqual("protected_file", updated.connection_settings["credential_storage"])
            self.assertTrue(updated.connection_settings["credential_ref"].startswith("protected:pcred_"))
            self.assertNotIn("credentials", updated.connection_settings)
            self.assertNotIn("api_token", updated.connection_settings)
            self.assertNotIn("token", updated.connection_settings)
            self.assertNotIn("password", updated.connection_settings)
            resolved = create_provider_connection_resolver(
                SyntheticSettings(), self._registry(updated), ProtectedCredentialStore(root / "secrets", 65536)
            ).resolve_profile(profile.profile_id)
            factory = CapturingJiraFactory()
            resolved.open_jira_client(factory)
            self.assertEqual("applied-token", factory.kwargs["token"])
            audit_payload = str(BugTrendAuditEvent.objects.latest("created_at").request_summary)
            self.assertNotIn("applied-token", audit_payload)
            self.assertNotIn(str(source_file), audit_payload)

    def test_shouldResolveAdoptedCredentialThroughPublicDefaultStoreFactory(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = create_protected_source_toml(root / "source.toml", "default-store-token")
            service = self._service(root)
            profile = self._save_jira_profile("default-store-jira", token="old-token")
            preview = service.preview(profile.profile_id, source_file)
            service.apply(profile.profile_id, source_file, expected_preview=preview, replace=True)
            updated = ProviderProfileConfig.objects.get(profile_id=profile.profile_id)
            settings_source = type("SettingsWithStore", (), {
                **{name: getattr(SyntheticSettings(), name) for name in SyntheticSettings.__dataclass_fields__},
                "METRICS_PROVIDER_SECRET_DIR": str(root / "secrets"),
                "METRICS_PROVIDER_SECRET_MAX_BYTES": 65536,
            })()

            resolved = create_provider_connection_resolver(settings_source, self._registry(updated)).resolve_profile(profile.profile_id)
            factory = CapturingJiraFactory()
            resolved.open_jira_client(factory)

            self.assertEqual("protected", resolved.info.credential.kind)
            self.assertEqual("default-store-token", factory.kwargs["token"])

    def test_shouldRejectApplyWhenProfileChangedAfterPreviewWithoutWritingSuccessResult(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = create_protected_source_toml(root / "source.toml", "race-token")
            service = self._service(root)
            profile = self._save_jira_profile("race-jira", token="old-token")
            preview = service.preview(profile.profile_id, source_file)
            record = ProviderProfileConfig.objects.get(profile_id=profile.profile_id)
            record.connection_settings["credentials"]["api_token"] = "changed-token"
            record.save()

            with self.assertRaises(ConnectionError) as context:
                service.apply(profile.profile_id, source_file, expected_preview=preview, replace=True)

            self.assertEqual("PROVIDER_CREDENTIAL_CAS_MISMATCH", context.exception.code)
            current = ProviderProfileConfig.objects.get(profile_id=profile.profile_id)
            self.assertEqual("changed-token", current.connection_settings["credentials"]["api_token"])

    def test_shouldApplySerializedPreviewUsingAFreshServiceWithoutRememberedSecrets(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = create_protected_source_toml(root / "source.toml", "race-token")
            service = self._service(root)
            profile = self._save_jira_profile("json-race-jira", token="old-token")
            preview = json.loads(json.dumps(service.preview(profile.profile_id, source_file).to_dict()))
            fresh_service = self._service(root)

            result = fresh_service.apply(profile.profile_id, source_file, expected_preview=preview, replace=True)

            self.assertEqual("applied", result.status)
            self.assertNotIn("old-token", json.dumps(preview))
            self.assertEqual(1, len(list((root / "secrets").glob("*/*/*/*.intent.json"))))

    def test_shouldRejectApplyWhenSourceFileChangedAfterPreview(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = create_protected_source_toml(root / "source.toml", "preview-token")
            service = self._service(root)
            profile = self._save_jira_profile("source-race-jira", token="old-token")
            preview = service.preview(profile.profile_id, source_file)
            time.sleep(0.05)
            write_protected_file(source_file, '[jira]\ntoken="changed-token"\n')

            with self.assertRaises(ConnectionError) as context:
                service.apply(profile.profile_id, source_file, expected_preview=preview, replace=True)

            self.assertEqual("PROVIDER_CREDENTIAL_CAS_MISMATCH", context.exception.code)
            current = ProviderProfileConfig.objects.get(profile_id=profile.profile_id)
            self.assertEqual("old-token", current.connection_settings["credentials"]["api_token"])

    def test_shouldLeavePendingIntentWhenSecretWriteFailsWithoutChangingProfile(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = create_protected_source_toml(root / "source.toml", "orphan-token")
            store = FailingAfterIntentStore(root / "secrets", 65536)
            service = self._service(root, store=store)
            profile = self._save_jira_profile("orphan-jira", token="old-token")
            preview = service.preview(profile.profile_id, source_file)

            with self.assertRaises(ConnectionError):
                service.apply(profile.profile_id, source_file, expected_preview=preview, replace=True)

            current = ProviderProfileConfig.objects.get(profile_id=profile.profile_id)
            self.assertEqual("old-token", current.connection_settings["credentials"]["api_token"])
            pending = store.list_unreferenced(frozenset())
            self.assertEqual(1, len(pending))
            self.assertEqual("pending_cleanup", pending[0].status)

    def test_shouldPreventStaleProfileEditorFromDiscardingProtectedReference(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = create_protected_source_toml(root / "source.toml", "protected-token")
            adoption_service = self._service(root)
            profile = self._save_jira_profile("stale-editor-jira", token="old-token")
            stale_form = ProviderProfileConfigService().get_provider_profile_config(profile.profile_id)
            preview = adoption_service.preview(profile.profile_id, source_file)
            adoption_service.apply(profile.profile_id, source_file, expected_preview=preview, replace=True)
            stale_form.connection_settings = {
                "base_url": "https://jira.settings.example/jira",
                "auth_mode": "server_pat",
                "credentials": {"api_token": "stale-inline-token"},
            }

            ProviderProfileConfigService().save_provider_profile_config(stale_form)

            current = ProviderProfileConfig.objects.get(profile_id=profile.profile_id)
            self.assertEqual("protected_file", current.connection_settings["credential_storage"])
            self.assertNotIn("credentials", current.connection_settings)

    def _service(self, root: Path, store=None):
        secret_root = root / "secrets"
        return CredentialAdoptionService(settings_source=SyntheticSettings(), protected_store=store or ProtectedCredentialStore(secret_root, 65536))

    def _save_jira_profile(self, profile_id: str, token: str | None, credential_ref: str | None = None):
        connection_settings = {
            "base_url": "https://jira.settings.example/jira",
            "auth_mode": "server_pat",
        }
        if token is not None:
            connection_settings.update({
                "api_token": "top-level-token",
                "token": "top-level-bearer",
                "password": "top-level-password",
                "credentials": {"api_token": token},
            })
        if credential_ref is not None:
            connection_settings["credential_ref"] = credential_ref
        if token is None and credential_ref is None:
            connection_settings["credential_ref"] = ""
        return ProviderProfileConfigService().save_provider_profile_config(provider_profile_config_from_dict({
            "profile_id": profile_id,
            "provider_id": "jira",
            "display_name": profile_id,
            "lifecycle_state": ProviderProfileConfig.LIFECYCLE_ENABLED,
            "connection_settings": connection_settings,
            "source_population": {"native_query_text": f"project = {profile_id}"},
            "field_bindings": {"status": {"native_field": "status"}},
            "chart_bindings": {"open_bug_trend": {"support_status": "supported"}},
        }))

    def _registry(self, profile_record):
        class Registry:
            def resolve_profile(self, profile_id):
                return type("Resolution", (), {
                    "profile": type("Profile", (), {
                        "profile_id": profile_record.profile_id,
                        "provider_id": profile_record.provider_id,
                        "connection_settings": profile_record.connection_settings,
                    })(),
                    "provider_id": profile_record.provider_id,
                    "blockers": [],
                })()

        return Registry()
