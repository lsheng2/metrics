"""Exercise the retirement command against small real Windows/Git workspaces."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "maintenance" / "archive_workspace.ps1"
PWSH = shutil.which("pwsh")
pytestmark = pytest.mark.skipif(os.name != "nt" or not PWSH, reason="Windows maintenance contract")


def git(root, *args):
    result = subprocess.run(
        ["git", "-C", str(root), "-c", "core.autocrlf=false",
         "-c", "user.name=Retirement Test", "-c", "user.email=synthetic@example.test",
         *args],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def invoke(action, archive, source=None):
    command = [PWSH, "-NoProfile", "-File", str(SCRIPT),
               "-Action", action, "-ArchiveRoot", str(archive)]
    if source is not None:
        command += ["-SourceRoot", str(source)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    assert result.stdout.strip().startswith("{"), result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert "synthetic-retirement-secret" not in result.stdout + result.stderr
    assert output["schema"] == "workspace-retirement/1"
    return result, output


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    git(root, "init", "--initial-branch=main")
    (root / ".gitignore").write_text("private/\n", encoding="utf-8")
    (root / "tracked.txt").write_bytes(b"first\n")
    git(root, "add", ".gitignore", "tracked.txt")
    git(root, "commit", "-m", "initial synthetic source")
    (root / "tracked.txt").write_bytes(b"second\n")
    git(root, "commit", "-am", "unpublished synthetic change")
    git(root, "tag", "synthetic-tag")
    (root / "tracked.txt").write_bytes(b"uncommitted\n")
    (root / "new.txt").write_bytes(b"untracked\n")
    private = root / "private"
    private.mkdir()
    (private / "secret.txt").write_bytes(b"synthetic-retirement-secret")
    (private / "binary.dat").write_bytes(bytes(range(256)))
    (root / "empty").mkdir()
    return root


def capture(source, tmp_path):
    archive = tmp_path / "archive"
    process, receipt = invoke("Capture", archive, source)
    assert process.returncode == 0, receipt
    assert receipt["result"] == "verified"
    return archive


def test_preserves_dirty_ignored_git_history_and_private_bytes(source, tmp_path):
    status = git(source, "status", "--porcelain", "--untracked-files=all")
    head = git(source, "rev-parse", "HEAD")
    index_before = (source / ".git" / "index").read_bytes()
    archive = capture(source, tmp_path)
    snapshot = archive / "snapshot"
    assert (snapshot / "tracked.txt").read_bytes() == b"uncommitted\n"
    assert (snapshot / "new.txt").read_bytes() == b"untracked\n"
    assert (snapshot / "private" / "secret.txt").read_bytes() == b"synthetic-retirement-secret"
    assert (snapshot / "private" / "binary.dat").read_bytes() == bytes(range(256))
    assert (snapshot / "empty").is_dir()
    assert (snapshot / ".git" / "index").read_bytes() == index_before
    assert (source / ".git" / "index").read_bytes() == index_before
    assert git(source, "status", "--porcelain", "--untracked-files=all") == status
    restored = tmp_path / "restored-history"
    git(tmp_path, "clone", "--mirror", str(archive / "history.bundle"), str(restored))
    assert git(restored, "rev-parse", "HEAD") == head
    assert git(restored, "for-each-ref", "--format=%(refname) %(objectname)") == git(
        source, "for-each-ref", "--format=%(refname) %(objectname)")
    git(restored, "fsck", "--full")
    process, receipt = invoke("Verify", archive, source)
    assert process.returncode == 0, receipt
    assert receipt["fileCount"] >= 6
    assert receipt["linkCount"] == 0


@pytest.mark.parametrize("damage", ["replace", "remove", "extra", "manifest", "bundle"])
def test_detects_archive_damage_without_rewriting_receipt(source, tmp_path, damage):
    archive = capture(source, tmp_path)
    before = (archive / "capture.json").read_bytes()
    if damage == "replace":
        (archive / "snapshot" / "tracked.txt").write_bytes(b"changed\n")
    elif damage == "remove":
        (archive / "snapshot" / "new.txt").unlink()
    elif damage == "extra":
        (archive / "snapshot" / "extra.txt").write_bytes(b"unrecorded")
    elif damage == "manifest":
        (archive / "inventory.json").write_bytes(b"{}")
    else:
        (archive / "history.bundle").write_bytes(b"not a bundle")
    process, receipt = invoke("Verify", archive)
    assert process.returncode != 0
    assert receipt["result"] == "failed"
    assert (archive / "capture.json").read_bytes() == before


def test_source_drift_does_not_invalidate_preserved_archive(source, tmp_path):
    archive = capture(source, tmp_path)
    (source / "tracked.txt").write_bytes(b"new work after capture\n")
    process, result = invoke("Verify", archive, source)
    assert process.returncode != 0 and result["result"] == "failed"
    process, result = invoke("Verify", archive)
    assert process.returncode == 0 and result["result"] == "verified"


@pytest.mark.parametrize("kind", ["existing", "nested", "git-contained", "relative"])
def test_refuses_unsafe_target_without_overwriting(source, tmp_path, kind):
    if kind == "existing":
        target = tmp_path / "existing"
        target.mkdir()
        (target / "keep.txt").write_bytes(b"keep")
    elif kind == "nested":
        target = source / "nested"
    elif kind == "git-contained":
        other = tmp_path / "other-code"
        other.mkdir()
        git(other, "init")
        target = other / "ignored-archive"
    else:
        target = Path("relative-retirement-target")
    process, result = invoke("Capture", target, source)
    assert process.returncode != 0 and result["result"] == "failed"
    if kind == "existing":
        assert (target / "keep.txt").read_bytes() == b"keep"
        assert not (target / "capture.json").exists()
    else:
        assert not target.exists()
    assert (source / "tracked.txt").read_bytes() == b"uncommitted\n"


def junction(path, target):
    result = subprocess.run(
        [PWSH, "-NoProfile", "-Command",
         "New-Item -ItemType Junction -Path $env:RETIRE_LINK -Target $env:RETIRE_TARGET | Out-Null"],
        env={**os.environ, "RETIRE_LINK": str(path), "RETIRE_TARGET": str(target)},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_records_links_without_following_shared_target(source, tmp_path):
    outside = tmp_path / "shared"
    outside.mkdir()
    (outside / "never-copy.txt").write_bytes(b"shared target")
    junction(source / "external-cache", outside)
    junction(source / "internal-alias", source / "private")
    archive = capture(source, tmp_path)
    inventory = json.loads((archive / "inventory.json").read_text(encoding="utf-8-sig"))
    links = {entry["path"]: entry for entry in inventory["links"]}
    assert set(links) == {"external-cache", "internal-alias"}
    assert links["external-cache"]["targets"] == [str(outside)]
    assert links["internal-alias"]["targets"] == [str(source / "private")]
    assert not (archive / "snapshot" / "external-cache").exists()
    assert not (archive / "snapshot" / "internal-alias").exists()
    assert (outside / "never-copy.txt").read_bytes() == b"shared target"
    assert not any(entry["path"].endswith("never-copy.txt") for entry in inventory["files"])


def test_refuses_reparse_target_ancestor(source, tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    junction(tmp_path / "alias", actual)
    process, result = invoke("Capture", tmp_path / "alias" / "archive", source)
    assert process.returncode != 0 and result["result"] == "failed"
    assert not (actual / "archive").exists()


def test_archive_acl_is_private_and_broadening_fails_verification(source, tmp_path):
    archive = capture(source, tmp_path)
    secret = archive / "snapshot" / "private" / "secret.txt"
    result = subprocess.run(
        [PWSH, "-NoProfile", "-Command",
         "$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;"
         "$acl=Get-Acl -LiteralPath $env:RETIRE_SECRET;"
         "$bad=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | "
         "Where-Object { $_.AccessControlType -eq 'Allow' -and "
         "$_.IdentityReference.Value -notin @($sid,'S-1-5-18') });"
         "if($bad.Count){exit 9}"],
        env={**os.environ, "RETIRE_SECRET": str(secret)},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    widened = subprocess.run(
        ["icacls", str(secret), "/grant", "*S-1-1-0:(R)"],
        capture_output=True, text=True, timeout=20,
    )
    assert widened.returncode == 0, widened.stderr
    process, receipt = invoke("Verify", archive)
    assert process.returncode != 0 and receipt["result"] == "failed"


def test_manifest_hash_matches_capture_receipt(source, tmp_path):
    archive = capture(source, tmp_path)
    receipt = json.loads((archive / "capture.json").read_text(encoding="utf-8-sig"))
    assert receipt["inventorySha256"] == hashlib.sha256(
        (archive / "inventory.json").read_bytes()).hexdigest()
    assert receipt["bundleSha256"] == hashlib.sha256(
        (archive / "history.bundle").read_bytes()).hexdigest()


@pytest.mark.parametrize("damage", ["evidence-acl", "unexpected-root-file"])
def test_verifies_privacy_and_allowed_entries_outside_snapshot(source, tmp_path, damage):
    archive = capture(source, tmp_path)
    if damage == "evidence-acl":
        evidence = archive / "evidence" / "robocopy.log"
        changed = subprocess.run(
            ["icacls", str(evidence), "/grant", "*S-1-1-0:(R)"],
            capture_output=True, text=True, timeout=20,
        )
        assert changed.returncode == 0, changed.stderr
    else:
        (archive / "unexpected.txt").write_bytes(b"not part of the capture")
    process, result = invoke("Verify", archive)
    assert process.returncode != 0
    assert result["result"] == "failed"
