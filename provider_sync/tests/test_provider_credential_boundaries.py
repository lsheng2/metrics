import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from django.db import DatabaseError, connection
from django.test import TestCase as DatabaseTestCase

from bug_metrics.app.api.provider_credentials import CredentialAdoptionService
from bug_metrics.app.api.provider_profile_config import ProviderProfileConfigService, provider_profile_config_from_dict
from bug_metrics.models import ProviderProfileConfig
from bug_metrics.provider_connections.contracts import ConnectionError
from bug_metrics.provider_connections.protected_store import ProtectedCredentialStore
from bug_metrics.provider_connections.windows_files import validate_named_path_protection
from provider_sync.tests.test_provider_connections import SyntheticSettings
from provider_sync.tests.test_provider_credentials_native import create_protected_source_toml, write_protected_file


class TestProtectedStorageBoundaries(TestCase):
    def test_every_created_directory_is_protected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "secrets"
            store = ProtectedCredentialStore(root, 65536)
            credential = store.create_candidate(
                provider_id="jira", profile_id="alpha", endpoint_id="site-a",
                auth_mode="server_pat", token="synthetic-secret",
            )
            secret_directory = root / "jira" / "alpha" / credential.reference.split(":")[1]
            for path in (root, root / "jira", root / "jira" / "alpha", secret_directory):
                with self.subTest(path=path.name):
                    validate_named_path_protection(path)

    def test_dot_segments_cannot_select_a_different_profile_directory(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "secrets"
            store = ProtectedCredentialStore(root, 65536)
            for profile in (".", "..", "CON", "aux.txt", "alpha."):
                with self.subTest(profile=profile), self.assertRaises(ConnectionError):
                    store.create_candidate(
                        provider_id="jira", profile_id=profile, endpoint_id="site-a",
                        auth_mode="server_pat", token="synthetic-secret",
                    )
            self.assertFalse(root.exists())

    def test_inventory_cannot_accept_metadata_disagreeing_with_its_path(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "secrets"
            store = ProtectedCredentialStore(root, 65536)
            store.create_candidate(
                provider_id="jira", profile_id="alpha", endpoint_id="site-a",
                auth_mode="server_pat", token="synthetic-secret",
            )
            intent = next(root.glob("*/*/*/*.intent.json"))
            payload = json.loads(intent.read_text(encoding="utf-8"))
            payload["profile_id"] = "other-profile"
            write_protected_file(intent, json.dumps(payload))
            with self.assertRaises(ConnectionError):
                store.list_unreferenced(frozenset())

    def test_duplicate_metadata_and_hardlinked_secret_are_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "secrets"
            store = ProtectedCredentialStore(root, 65536)
            credential = store.create_candidate(
                provider_id="jira", profile_id="alpha", endpoint_id="site-a",
                auth_mode="server_pat", token="synthetic-secret",
            )
            args = dict(reference=credential.reference, revision=credential.revision,
                        provider_id="jira", profile_id="alpha", endpoint_id="site-a", auth_mode="server_pat")
            secret = next(root.glob("*/*/*/*.secret"))
            alias = Path(directory) / "alias"
            os.link(secret, alias)
            with self.assertRaises(ConnectionError):
                store.read_selected(**args)
            alias.unlink()
            metadata = next(root.glob("*/*/*/*.meta.json"))
            original = metadata.read_text(encoding="utf-8")
            write_protected_file(metadata, '{"schema_version":1,' + original[1:])
            with self.assertRaises(ConnectionError):
                store.read_selected(**args)


class TestAdoptionTransactionBoundaries(DatabaseTestCase):
    def test_profile_and_audit_save_roll_back_together(self):
        api = ProviderProfileConfigService()
        saved = api.save_provider_profile_config(provider_profile_config_from_dict({
            "profile_id": "editor-audit", "provider_id": "jira", "display_name": "Original",
        }))
        saved.display_name = "Uncommitted"

        def fail_audit(execute, sql, params, many, context):
            if sql.startswith('INSERT INTO "bug_metrics_bugtrendauditevent"'):
                raise DatabaseError("synthetic audit write failure")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(fail_audit), self.assertRaises(DatabaseError):
            api.save_provider_profile_config(saved)
        self.assertEqual("Original", ProviderProfileConfig.objects.get(pk=saved.id).display_name)

    def test_editor_never_replaces_protected_revision_or_reintroduces_inline_secrets(self):
        api = ProviderProfileConfigService()
        saved = api.save_provider_profile_config(provider_profile_config_from_dict({
            "profile_id": "editor-protected", "provider_id": "jira", "display_name": "Protected",
            "connection_settings": {"credential_storage": "protected_file",
                                    "credential_ref": "protected:pcred_" + "a" * 32,
                                    "credential_revision": "original"},
        }))
        saved.connection_settings.update({"credential_revision": "forged", "token": "secret-canary",
                                          "credentials": {"api_token": "secret-canary"}})
        api.save_provider_profile_config(saved)
        stored = ProviderProfileConfig.objects.get(pk=saved.id).connection_settings
        self.assertEqual("original", stored["credential_revision"])
        self.assertNotIn("secret-canary", json.dumps(stored))

    def test_database_race_after_private_observation_is_checked_by_update(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = create_protected_source_toml(root / "source.toml", "new-token")
            service = CredentialAdoptionService(SyntheticSettings(), ProtectedCredentialStore(root / "secrets", 65536))
            saved = ProviderProfileConfigService().save_provider_profile_config(provider_profile_config_from_dict({
                "profile_id": "race-cas", "provider_id": "jira", "display_name": "Race",
                "connection_settings": {"base_url": "https://jira.settings.example/jira",
                                        "auth_mode": "server_pat", "credentials": {"api_token": "old-token"}},
            }))
            preview = service.preview(saved.profile_id, source).to_dict()
            injected = []

            def race(execute, sql, params, many, context):
                if not injected and sql.startswith('UPDATE "bug_metrics_providerprofileconfig"'):
                    injected.append(True)
                    changed = dict(ProviderProfileConfig.objects.get(pk=saved.id).connection_settings)
                    changed["credentials"] = {"api_token": "concurrent-token"}
                    ProviderProfileConfig.objects.filter(pk=saved.id).update(connection_settings=changed)
                return execute(sql, params, many, context)

            with connection.execute_wrapper(race), self.assertRaises(ConnectionError) as caught:
                service.apply(saved.profile_id, source, expected_preview=preview, replace=True)
            self.assertEqual("PROVIDER_CREDENTIAL_CAS_MISMATCH", caught.exception.code)
            self.assertTrue(injected)
            self.assertFalse((root / "secrets").exists())


class TestCredentialParserBoundaries(TestCase):
    def test_missing_cli_arguments_are_one_safe_json_envelope(self):
        result = subprocess.run(
            [sys.executable, "manage.py", "provider_credentials", "apply"],
            cwd=Path(__file__).resolve().parents[2],
            env={**os.environ, "DJANGO_SETTINGS_MODULE": "provider_sync.tests.connection_test_settings"},
            capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertEqual("INVALID_ARGUMENTS", json.loads(result.stderr)["error"]["code"])
