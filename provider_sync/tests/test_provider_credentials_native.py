from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import win32con
import win32api
import win32file
import win32security

from bug_metrics.provider_connections.contracts import ConnectionError
from bug_metrics.provider_connections.protected_store import ProtectedCredentialStore, read_source_toml
from bug_metrics.provider_connections.windows_files import allowed_sids
from bug_metrics.provider_connections.windows_files import validate_named_path_protection


def create_protected_source_toml(path: Path, token: str) -> Path:
    write_protected_file(path, f'[jira]\ntoken="{token}"\n')
    return path


def write_protected_file(path: Path, text: str, protect_dacl: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not protect_dacl:
        path.write_text(text, encoding="utf-8")
        descriptor = protected_descriptor(protect_dacl=False)
        win32security.SetNamedSecurityInfo(
            str(path),
            win32security.SE_FILE_OBJECT,
            win32security.DACL_SECURITY_INFORMATION,
            None,
            None,
            descriptor.GetSecurityDescriptorDacl(),
            None,
        )
        return
    security_attributes = win32security.SECURITY_ATTRIBUTES()
    security_attributes.SECURITY_DESCRIPTOR = protected_descriptor(protect_dacl=protect_dacl)
    handle = win32file.CreateFile(
        str(path),
        win32con.GENERIC_WRITE,
        0,
        security_attributes,
        win32con.CREATE_ALWAYS,
        win32con.FILE_ATTRIBUTE_NORMAL,
        None,
    )
    try:
        win32file.WriteFile(handle, text.encode("utf-8"))
    finally:
        handle.Close()


def protected_descriptor(protect_dacl: bool = True):
    current_user, system, admins = allowed_sids()
    dacl = win32security.ACL()
    for sid in [current_user, system, admins]:
        dacl.AddAccessAllowedAce(win32security.ACL_REVISION, win32con.GENERIC_ALL, sid)
    descriptor = win32security.SECURITY_DESCRIPTOR()
    descriptor.SetSecurityDescriptorOwner(current_user, False)
    descriptor.SetSecurityDescriptorDacl(True, dacl, False)
    if protect_dacl:
        descriptor.SetSecurityDescriptorControl(win32security.SE_DACL_PROTECTED, win32security.SE_DACL_PROTECTED)
    return descriptor


class TestProviderCredentialNativeStore(unittest.TestCase):
    def test_shouldReadProtectedTomlThroughSameHandleAndReturnStableReceipt(self):
        with TemporaryDirectory() as temp_dir:
            source_file = create_protected_source_toml(Path(temp_dir) / "source.toml", "native-token")

            token, receipt = read_source_toml(source_file, max_bytes=65536)

            self.assertEqual("native-token", token)
            self.assertTrue(receipt.file_identity)
            self.assertTrue(receipt.last_write)
            self.assertEqual("protected", receipt.owner_class)

    def test_shouldRejectUnprotectedTomlAndDirectories(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            unprotected = root / "source.toml"
            unprotected.write_text('[jira]\ntoken="native-token"\n', encoding="utf-8")

            with self.assertRaises(ConnectionError) as context:
                read_source_toml(unprotected, max_bytes=65536)
            self.assertEqual("PROVIDER_CREDENTIAL_UNPROTECTED", context.exception.code)

            with self.assertRaises(ConnectionError):
                read_source_toml(root, max_bytes=65536)

    def test_shouldRejectAllowlistedDaclWhenInheritanceIsEnabled(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "source.toml"
            write_protected_file(path, '[jira]\ntoken="native-token"\n', protect_dacl=False)

            with self.assertRaises(ConnectionError) as context:
                validate_named_path_protection(path)

            self.assertEqual("PROVIDER_CREDENTIAL_UNPROTECTED", context.exception.code)

    def test_shouldWriteProtectedIntentSecretAndMetadataWithoutChangingSource(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = create_protected_source_toml(root / "source.toml", "native-secret")
            before = source_file.read_bytes()
            store = ProtectedCredentialStore(root / "secrets", 65536)

            credential = store.create_candidate(
                provider_id="jira",
                profile_id="profile-a",
                endpoint_id="endpoint-a",
                auth_mode="server_pat",
                token="native-secret",
            )

            self.assertTrue(credential.reference.startswith("protected:pcred_"))
            self.assertTrue(credential.revision.startswith("rev_"))
            self.assertEqual(before, source_file.read_bytes())
            self.assertEqual(
                "native-secret",
                store.read_selected(
                    reference=credential.reference,
                    revision=credential.revision,
                    provider_id="jira",
                    profile_id="profile-a",
                    endpoint_id="endpoint-a",
                    auth_mode="server_pat",
                ),
            )
            pending = store.list_unreferenced(frozenset())
            self.assertEqual(1, len(pending))

    def test_shouldFailInventoryWhenProtectedIntentIsCorrupt(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = ProtectedCredentialStore(root / "secrets", 65536)
            credential = store.create_candidate(
                provider_id="jira",
                profile_id="profile-a",
                endpoint_id="endpoint-a",
                auth_mode="server_pat",
                token="native-secret",
            )
            intent = next((root / "secrets").glob("*/*/*/*.intent.json"))
            write_protected_file(intent, "{not-json")

            with self.assertRaises(ConnectionError) as context:
                store.list_unreferenced(frozenset({(credential.reference, credential.revision)}))

            self.assertEqual("PROVIDER_CREDENTIAL_INVALID", context.exception.code)


if __name__ == "__main__":
    unittest.main()
