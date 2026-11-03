import tomllib
import re
from pathlib import Path

import win32con
import win32api
import win32file
import win32security

from .contracts import ConnectionError
from .protected_store import SourceFileReceipt


TOKEN_MAX_CHARS = 8192
INHERITED_ACE = 0x10
RESERVED_NAME = re.compile(r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.IGNORECASE)


def protected_security_attributes():
    attributes = win32security.SECURITY_ATTRIBUTES()
    attributes.SECURITY_DESCRIPTOR = protected_security_descriptor()
    return attributes


def protected_security_descriptor():
    current_user, system, admins = allowed_sids()
    dacl = win32security.ACL()
    for sid in [current_user, system, admins]:
        dacl.AddAccessAllowedAce(win32security.ACL_REVISION, win32con.GENERIC_ALL, sid)
    descriptor = win32security.SECURITY_DESCRIPTOR()
    descriptor.SetSecurityDescriptorOwner(current_user, False)
    descriptor.SetSecurityDescriptorDacl(True, dacl, False)
    descriptor.SetSecurityDescriptorControl(win32security.SE_DACL_PROTECTED, win32security.SE_DACL_PROTECTED)
    return descriptor


def ensure_protected_directory(path: Path, *, root: Path | None = None) -> None:
    check_ancestors(path)
    root = path if root is None else Path(root)
    try:
        path.relative_to(root)
    except ValueError:
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID") from None
    if path.exists():
        if not path.is_dir() or _reparse(path):
            raise ConnectionError("PROVIDER_CREDENTIAL_UNPROTECTED")
        validate_named_path_protection(path)
        return
    if path != root:
        ensure_protected_directory(path.parent, root=root)
    elif not path.parent.is_dir():
        raise ConnectionError("PROVIDER_CREDENTIAL_UNAVAILABLE")
    try:
        win32file.CreateDirectory(str(path), protected_security_attributes())
    except OSError:
        if not path.is_dir() or _reparse(path):
            raise ConnectionError("PROVIDER_CREDENTIAL_UNAVAILABLE") from None
    validate_named_path_protection(path)


def validate_named_path_protection(path: Path) -> None:
    check_ancestors(path)
    if _reparse(path):
        raise ConnectionError("PROVIDER_CREDENTIAL_UNPROTECTED")
    try:
        descriptor = win32security.GetNamedSecurityInfo(
            str(path),
            win32security.SE_FILE_OBJECT,
            win32security.OWNER_SECURITY_INFORMATION | win32security.DACL_SECURITY_INFORMATION,
        )
    except Exception:
        raise ConnectionError("PROVIDER_CREDENTIAL_UNPROTECTED") from None
    validate_security_descriptor(descriptor)


def validate_handle_protection(handle) -> None:
    descriptor = win32security.GetSecurityInfo(
        handle,
        win32security.SE_FILE_OBJECT,
        win32security.OWNER_SECURITY_INFORMATION | win32security.DACL_SECURITY_INFORMATION,
    )
    validate_security_descriptor(descriptor)


def validate_security_descriptor(descriptor) -> None:
    current_user, system, admins = allowed_sids()
    allowed_sid_values = {str(current_user), str(system), str(admins)}
    owner = descriptor.GetSecurityDescriptorOwner()
    if str(owner) not in allowed_sid_values:
        raise ConnectionError("PROVIDER_CREDENTIAL_UNPROTECTED")
    control, _ = descriptor.GetSecurityDescriptorControl()
    if not control & win32security.SE_DACL_PROTECTED:
        raise ConnectionError("PROVIDER_CREDENTIAL_UNPROTECTED")
    dacl_value = descriptor.GetSecurityDescriptorDacl()
    dacl = dacl_value[1] if isinstance(dacl_value, tuple) else dacl_value
    if dacl is None:
        raise ConnectionError("PROVIDER_CREDENTIAL_UNPROTECTED")
    for index in range(dacl.GetAceCount()):
        ace = dacl.GetAce(index)
        ace_type = ace[0][0]
        ace_flags = ace[0][1]
        if ace_flags & INHERITED_ACE:
            raise ConnectionError("PROVIDER_CREDENTIAL_UNPROTECTED")
        if ace_type == win32security.ACCESS_DENIED_ACE_TYPE:
            continue
        if ace_type != win32security.ACCESS_ALLOWED_ACE_TYPE or str(ace[-1]) not in allowed_sid_values:
            raise ConnectionError("PROVIDER_CREDENTIAL_UNPROTECTED")


def allowed_sids():
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        current_user = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    finally:
        token.Close()
    system = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid)
    admins = win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid)
    return current_user, system, admins


def check_ancestors(path: Path) -> None:
    path = Path(path)
    if (not path.is_absolute() or path.drive.startswith("\\\\")
            or any(not safe_component(part) for part in path.parts[1:])):
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
    for ancestor in path.parents:
        if ancestor.exists():
            attrs = win32file.GetFileAttributes(str(ancestor))
            if attrs & win32con.FILE_ATTRIBUTE_REPARSE_POINT or not attrs & win32con.FILE_ATTRIBUTE_DIRECTORY:
                raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")


def safe_component(value: str) -> bool:
    return (bool(value) and value not in {".", ".."} and not value.endswith((".", " "))
            and not RESERVED_NAME.match(value)
            and not any(ord(char) < 32 or char in '<>:"/\\|?*' for char in value))


def _reparse(path: Path) -> bool:
    return path.is_symlink() or bool(win32file.GetFileAttributes(str(path)) & win32con.FILE_ATTRIBUTE_REPARSE_POINT)


def read_source_toml_same_handle(path: Path, *, max_bytes: int) -> tuple[str, SourceFileReceipt]:
    data, receipt = read_protected_bytes(path, max_bytes=max_bytes)
    return _token_from_toml(data), receipt


def read_protected_bytes(path: Path, *, max_bytes: int) -> tuple[bytes, SourceFileReceipt]:
    if type(max_bytes) is not int or not 0 < max_bytes <= 16 * 1024**2:
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
    check_ancestors(path)
    handle = _open_existing_file(path)
    try:
        info = win32file.GetFileInformationByHandle(handle)
        if info[0] & (win32con.FILE_ATTRIBUTE_DIRECTORY | win32con.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        if info[7] != 1:
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        validate_handle_protection(handle)
        size = win32file.GetFileSize(handle)
        if size <= 0 or size > max_bytes:
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        _, data = win32file.ReadFile(handle, size)
        if len(data) != size:
            raise ConnectionError("PROVIDER_CREDENTIAL_UNAVAILABLE")
        receipt = SourceFileReceipt(_file_identity(info), str(info[3]), "protected")
    finally:
        handle.Close()
    return data, receipt


def create_new_protected_file(path: Path, content: bytes, *, root: Path | None = None) -> None:
    check_ancestors(path)
    ensure_protected_directory(path.parent, root=root)
    handle = win32file.CreateFile(
        str(path),
        win32con.GENERIC_WRITE | win32con.GENERIC_READ | win32con.READ_CONTROL,
        0,
        protected_security_attributes(),
        win32con.CREATE_NEW,
        win32con.FILE_ATTRIBUTE_NORMAL | win32file.FILE_FLAG_WRITE_THROUGH,
        None,
    )
    try:
        win32file.WriteFile(handle, content)
        win32file.FlushFileBuffers(handle)
        validate_handle_protection(handle)
        win32file.SetFilePointer(handle, 0, win32con.FILE_BEGIN)
        _, verified = win32file.ReadFile(handle, len(content))
        if verified != content:
            raise ConnectionError("PROVIDER_CREDENTIAL_UNAVAILABLE")
    finally:
        handle.Close()


def _open_existing_file(path: Path):
    try:
        return win32file.CreateFile(
            str(path),
            win32con.GENERIC_READ | win32con.READ_CONTROL,
            win32con.FILE_SHARE_READ,
            None,
            win32con.OPEN_EXISTING,
            win32file.FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
    except Exception:
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID") from None


def _token_from_toml(data: bytes) -> str:
    try:
        payload = tomllib.loads(data.decode("utf-8"))
    except Exception:
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID") from None
    jira = payload.get("jira")
    token = jira.get("token") if isinstance(jira, dict) else None
    if not isinstance(token, str) or not 1 <= len(token) <= TOKEN_MAX_CHARS:
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
    if any(ord(character) < 33 or ord(character) > 126 for character in token):
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
    return token


def _file_identity(info) -> str:
    return f"{info[4]}:{info[8]}:{info[9]}"
