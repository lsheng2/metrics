import json
import shutil
from pathlib import Path

import pytest

from scripts.tests.test_qualify_ai_runtime import _sha, _write_json
from scripts.tests.test_windows_migration_admission import migration_case
from scripts.validation.windows_qualification_inputs import QualificationError


def _history_declaration(root: Path, *, repository: str | None = None, marker_payload: dict | None = None) -> dict:
    repository = repository or "C:/retired/dashboard/moonfish"
    payload = {
        "schema_version": 1,
        "owner": "mdb2-windows-closure",
        "purpose": "Owned synthetic Windows artifact and rollback qualification",
        "repository": repository,
        "root": str(root),
        "real_user_data_allowed": False,
        "external_provider_model_calls_allowed": False,
    }
    if marker_payload:
        payload.update(marker_payload)
    marker = _write_json(root / "owner.json", payload)
    return {"root": str(root), "repository": repository, "marker": {"path": str(marker), "sha256": _sha(marker)}}


def _historical_case(tmp_path, monkeypatch):
    history = tmp_path / "history" / "artifacts" / "mdb2-windows-20261117"
    case = migration_case(tmp_path, monkeypatch, historical_root=history)
    case["manifest"]["migration"]["historical_inputs"] = _history_declaration(history)
    _write_json(case["inputs"], case["manifest"])
    return {**case, "history": history}


def test_declared_short_disjoint_historical_root_is_validated_structurally(monkeypatch):
    from scripts.validation import windows_migration_history as history

    root = Path("C:/history")
    marker = root / "owner.json"
    current_repo = Path("D:/repo")
    owned_root = Path("E:/owned")
    original_is_dir = Path.is_dir

    def canonical(value, *, must_exist=True):
        return Path(value)

    def is_dir(path):
        return path == root or original_is_dir(path)

    monkeypatch.setattr(history.common, "canonical", canonical)
    monkeypatch.setattr(Path, "is_dir", is_dir)
    monkeypatch.setattr(history.common, "require_hash", lambda path, expected, label: None)
    monkeypatch.setattr(history, "read_json", lambda path: {
        "schema_version": 1,
        "owner": "mdb2-windows-closure",
        "repository": "C:/retired/dashboard/moonfish",
        "root": str(root),
        "real_user_data_allowed": False,
        "external_provider_model_calls_allowed": False,
    })

    result = history.from_migration({
        "historical_inputs": {
            "root": str(root),
            "repository": "C:/retired/dashboard/moonfish",
            "marker": {"path": str(marker), "sha256": "a" * 64},
        },
    }, current_repo=current_repo, owned_root=owned_root)

    assert result.root == root
    assert result.marker == marker


def test_declared_historical_inputs_admit_only_old_read_side_paths(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_admission as admission

    case = _historical_case(tmp_path, monkeypatch)
    request = admission.load_request(case["inputs"], case["output"])

    assert request.snapshot.run_dir == str(case["source_run"])
    assert request.old.repository.is_relative_to(case["history"])
    assert request.old.app_python.is_relative_to(case["history"])
    assert request.environments["old_app"]["executable"] == str(request.old.app_python)
    assert not request.current.app_python.is_relative_to(case["history"])
    assert {path for path, _ in request.references if path == case["history"] / "owner.json"}


def test_declared_historical_inputs_still_admit_new_owned_old_metadata(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_admission as admission

    case = _historical_case(tmp_path, monkeypatch)
    owned_snapshot = case["owned"] / "migration-metadata" / "snapshot.json"
    owned_snapshot.parent.mkdir(parents=True)
    shutil.copy2(case["manifest"]["migration"]["snapshot"]["path"], owned_snapshot)
    case["manifest"]["migration"]["snapshot"] = {"path": str(owned_snapshot), "sha256": _sha(owned_snapshot)}
    _write_json(case["inputs"], case["manifest"])

    request = admission.load_request(case["inputs"], case["output"])

    assert request.snapshot.run_dir == str(case["source_run"])
    assert any(path == owned_snapshot for path, _ in request.references)


def test_no_declaration_keeps_old_paths_inside_the_current_owned_root(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_admission as admission

    history = tmp_path / "history" / "artifacts" / "mdb2-windows-20261117"
    case = migration_case(tmp_path, monkeypatch, historical_root=history)

    with pytest.raises(QualificationError, match="owned root"):
        admission.load_request(case["inputs"], case["output"])
    assert not (case["owned"] / "migration-runs").exists()


def test_declared_historical_inputs_reject_undeclared_sibling_old_metadata(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_admission as admission

    case = _historical_case(tmp_path, monkeypatch)
    sibling = case["history"].parent / "undeclared-sibling"
    sibling.mkdir()
    sibling_snapshot = sibling / "snapshot.json"
    shutil.copy2(case["manifest"]["migration"]["snapshot"]["path"], sibling_snapshot)
    case["manifest"]["migration"]["snapshot"] = {"path": str(sibling_snapshot), "sha256": _sha(sibling_snapshot)}
    _write_json(case["inputs"], case["manifest"])

    with pytest.raises(QualificationError):
        admission.load_request(case["inputs"], case["output"])


@pytest.mark.parametrize("mutation", [
    "marker-hash", "repository", "owner", "schema", "schema-bool", "payload-type", "root", "flags",
    "marker-path", "marker-type", "declaration-type",
])
def test_historical_inputs_reject_unbound_or_wrong_owner_marker(tmp_path, monkeypatch, mutation):
    from scripts.validation import windows_migration_admission as admission

    case = _historical_case(tmp_path, monkeypatch)
    declaration = case["manifest"]["migration"]["historical_inputs"]
    marker = case["history"] / "owner.json"
    if mutation == "marker-hash":
        declaration["marker"]["sha256"] = "0" * 64
    elif mutation == "repository":
        declaration["repository"] = "C:/retired/dashboard/other"
    elif mutation == "owner":
        payload = json.loads(marker.read_text(encoding="utf-8"))
        payload["owner"] = "other-owner"
        _write_json(marker, payload)
        declaration["marker"]["sha256"] = _sha(marker)
    elif mutation == "schema":
        payload = json.loads(marker.read_text(encoding="utf-8"))
        payload["schema_version"] = 2
        _write_json(marker, payload)
        declaration["marker"]["sha256"] = _sha(marker)
    elif mutation == "schema-bool":
        payload = json.loads(marker.read_text(encoding="utf-8"))
        payload["schema_version"] = True
        _write_json(marker, payload)
        declaration["marker"]["sha256"] = _sha(marker)
    elif mutation == "payload-type":
        marker.write_text("[]\n", encoding="utf-8")
        declaration["marker"]["sha256"] = _sha(marker)
    elif mutation == "root":
        payload = json.loads(marker.read_text(encoding="utf-8"))
        payload["root"] = str(case["history"] / "child")
        _write_json(marker, payload)
        declaration["marker"]["sha256"] = _sha(marker)
    elif mutation == "flags":
        payload = json.loads(marker.read_text(encoding="utf-8"))
        payload["external_provider_model_calls_allowed"] = True
        _write_json(marker, payload)
        declaration["marker"]["sha256"] = _sha(marker)
    elif mutation == "marker-path":
        other = _write_json(case["history"] / "other-owner.json", json.loads(marker.read_text(encoding="utf-8")))
        declaration["marker"] = {"path": str(other), "sha256": _sha(other)}
    elif mutation == "marker-type":
        declaration["marker"] = "not-an-object"
    elif mutation == "declaration-type":
        case["manifest"]["migration"]["historical_inputs"] = ["not", "an", "object"]
    _write_json(case["inputs"], case["manifest"])

    with pytest.raises(QualificationError):
        admission.load_request(case["inputs"], case["output"])


@pytest.mark.parametrize("mutation", ["current-repo", "owned-root", "broad-root"])
def test_historical_inputs_reject_overlap_or_broad_roots(tmp_path, monkeypatch, mutation):
    from scripts.validation import windows_migration_admission as admission

    case = _historical_case(tmp_path, monkeypatch)
    if mutation == "current-repo":
        root = case["root"] / "nested-history"
    elif mutation == "owned-root":
        root = case["owned"] / "nested-history"
    else:
        root = Path(case["history"].anchor) / "AIGC"
    if mutation == "broad-root":
        marker = _write_json(tmp_path / "broad-root-owner.json", {
            "schema_version": 1,
            "owner": "mdb2-windows-closure",
            "repository": "C:/retired/dashboard/moonfish",
            "root": str(root),
            "real_user_data_allowed": False,
            "external_provider_model_calls_allowed": False,
        })
        case["manifest"]["migration"]["historical_inputs"] = {
            "root": str(root),
            "repository": "C:/retired/dashboard/moonfish",
            "marker": {"path": str(marker), "sha256": _sha(marker)},
        }
    else:
        root.mkdir(parents=True, exist_ok=True)
        case["manifest"]["migration"]["historical_inputs"] = _history_declaration(root)
    _write_json(case["inputs"], case["manifest"])

    with pytest.raises(QualificationError):
        admission.load_request(case["inputs"], case["output"])


@pytest.mark.parametrize("role", ["candidate-env", "output"])
def test_new_side_paths_cannot_target_the_historical_root(tmp_path, monkeypatch, role):
    from scripts.validation import windows_migration_admission as admission

    case = _historical_case(tmp_path, monkeypatch)
    if role == "candidate-env":
        candidate_environment = _write_json(case["history"] / "environments" / "candidate.json", {
            "executable": str(Path(case["manifest"]["python"]["candidate"])),
            "python": "3.13.7",
            "packages": {"synthetic": {"version": "1", "record_sha256": "c" * 64, "location": str(case["owned"])}},
            "shadowed_distributions": {},
            "sys_path": [],
            "selected_imports": {"ai_base_runtime": None, "ai_base_application_sdk": None},
        })
        case["manifest"]["python"]["environments"]["candidate"] = {
            "path": str(candidate_environment), "sha256": _sha(candidate_environment),
        }
        _write_json(case["inputs"], case["manifest"])
        target = case["output"]
    else:
        target = case["history"] / "migration-runs" / "receipt.json"

    with pytest.raises(QualificationError):
        admission.load_request(case["inputs"], target)


@pytest.mark.parametrize("mutation", ["marker", "snapshot", "seed", "environment"])
def test_historical_inputs_are_rechecked_after_admission(tmp_path, monkeypatch, mutation):
    from scripts.validation import windows_migration_admission as admission

    case = _historical_case(tmp_path, monkeypatch)
    request = admission.load_request(case["inputs"], case["output"])
    if mutation == "marker":
        (case["history"] / "owner.json").write_text("{}", encoding="utf-8")
    elif mutation == "snapshot":
        Path(case["manifest"]["migration"]["snapshot"]["path"]).write_text("{}", encoding="utf-8")
    elif mutation == "seed":
        Path(case["manifest"]["migration"]["seed"]["path"]).write_text("{}", encoding="utf-8")
    else:
        Path(case["manifest"]["python"]["environments"]["old_app"]["path"]).write_text("{}", encoding="utf-8")

    with pytest.raises(QualificationError, match="hash"):
        admission.recheck_inputs(request)
