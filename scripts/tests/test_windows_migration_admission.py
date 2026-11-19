from dataclasses import asdict
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from scripts.tests.test_qualify_ai_runtime import _base_case, _sha, _write_json
from scripts.tests.test_windows_migration_rehearsal import _fixture
from scripts.validation.windows_migration_rehearsal import snapshot_source_run
from scripts.validation.windows_qualification_inputs import QualificationError


def migration_case(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_admission as admission

    case = _base_case(tmp_path, monkeypatch)
    candidate_python = case["owned"] / "candidate-env/Scripts/python.exe"
    candidate_python.parent.mkdir(parents=True)
    candidate_python.write_text("synthetic interpreter", encoding="utf-8")
    case["manifest"]["python"]["candidate"] = str(candidate_python)
    materialized = case["owned"] / "rollback"
    materialized.mkdir()
    old, _, _, run = _fixture(materialized)
    snapshot = snapshot_source_run(run, old)
    snapshot_path = _write_json(case["owned"] / "snapshot.json", asdict(snapshot))
    project_id = "11111111-1111-4111-8111-111111111111"
    stage_id = "22222222-2222-4222-8222-222222222222"
    publication_id = "33333333-3333-4333-8333-333333333333"
    seed = {
        "kind": "synthetic-retained-publication-fixture", "old_source_commit": old.commit,
        "project_id": project_id, "stage_id": stage_id, "publications": [publication_id],
        "packets": [{"publication_id": publication_id, "commit": "a" * 40, "files": {
            name: "b" * 64 for name in ("edits.json", "manifest.json", "report.html", "report.txt", "snapshot.json", "template.json")
        }}],
    }
    seed_path = _write_json(run / "evidence/retained-publication.json", seed)
    data = case["manifest"]
    data["migration"] = {
        "snapshot": {"path": str(snapshot_path), "sha256": _sha(snapshot_path)},
        "seed": {"path": str(seed_path), "sha256": _sha(seed_path)},
    }
    data["rollback"] = {
        "source_repository": str(old.repository), "source_commit": old.commit,
        "app_python": str(old.app_python), "base_python": str(old.base_python),
    }
    environments = {}
    for role, python in (("candidate", Path(data["python"]["candidate"])), ("old_app", old.app_python), ("old_base", old.base_python)):
        path = _write_json(case["owned"] / "environments" / f"{role}.json", {
            "executable": str(python), "python": "3.13.7",
            "packages": {"synthetic": {"version": "1", "record_sha256": "c" * 64, "location": str(python.parent)}},
            "shadowed_distributions": {}, "sys_path": [],
            "selected_imports": {"ai_base_runtime": None, "ai_base_application_sdk": None},
        })
        environments[role] = {"path": str(path), "sha256": _sha(path)}
    data["python"]["environments"] = environments
    _write_json(case["inputs"], data)
    monkeypatch.setattr(admission, "ROOT", case["root"])
    return {**case, "old": old, "source_run": run, "snapshot": snapshot_path}


def test_migration_admission_binds_distinct_sources_and_environment_roles(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_admission as admission

    case = migration_case(tmp_path, monkeypatch)
    request = admission.load_request(case["inputs"], case["output"])
    assert request.old.commit == "e" * 40
    assert request.current.commit == "dashboard-1dbdd338"
    assert request.snapshot.run_dir == str(case["source_run"])
    assert set(request.environments) == {"candidate", "old_app", "old_base"}
    assert not case["output"].exists()


@pytest.mark.parametrize("mutation", ["snapshot", "seed", "environment", "working-tree"])
def test_migration_rejects_changed_or_unfrozen_inputs_before_copy(tmp_path, monkeypatch, mutation):
    from scripts.validation import windows_migration_admission as admission

    case = migration_case(tmp_path, monkeypatch)
    data = case["manifest"]
    if mutation == "working-tree":
        data["source"]["kind"] = "working-tree"
        _write_json(case["inputs"], data)
    else:
        ref = data["python"]["environments"]["candidate"] if mutation == "environment" else data["migration"][mutation]
        Path(ref["path"]).write_text("{}", encoding="utf-8")
    with pytest.raises((QualificationError, ValueError)):
        admission.load_request(case["inputs"], case["output"])
    assert not case["output"].exists()
    assert not (case["owned"] / "migration-runs").exists()


def test_migration_output_cannot_modify_original_snapshot_run(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_admission as admission

    case = migration_case(tmp_path, monkeypatch)
    target = case["source_run"] / "evidence/receipt.json"
    with pytest.raises(QualificationError, match="protected"):
        admission.load_request(case["inputs"], target)
    assert not target.exists()


def test_migration_environment_cannot_name_a_different_interpreter(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_admission as admission

    case = migration_case(tmp_path, monkeypatch)
    reference = case["manifest"]["python"]["environments"]["candidate"]
    path = Path(reference["path"])
    record = json.loads(path.read_text(encoding="utf-8"))
    record["executable"] = str(case["old"].app_python)
    _write_json(path, record)
    reference["sha256"] = _sha(path)
    _write_json(case["inputs"], case["manifest"])
    with pytest.raises(QualificationError, match="interpreter"):
        admission.load_request(case["inputs"], case["output"])


def test_migration_rechecks_bound_inputs_after_execution(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_admission as admission

    case = migration_case(tmp_path, monkeypatch)
    request = admission.load_request(case["inputs"], case["output"])
    case["snapshot"].write_text("{}", encoding="utf-8")
    with pytest.raises(QualificationError, match="hash"):
        admission.recheck_inputs(request)


def test_command_runner_preserves_explicit_environment_and_expected_negative_exit(tmp_path):
    from scripts.validation.qualify_ai_runtime import run_command

    result = run_command(
        [sys.executable, "-I", "-c", "import os,sys; print(os.environ['MIGRATION_TEST_VALUE']); sys.exit(1)"],
        cwd=tmp_path, log_dir=tmp_path / "logs", label="negative",
        env={"MIGRATION_TEST_VALUE": "isolated"}, expected_returncode=1, timeout=15,
    )
    assert result["returncode"] == result["expected_returncode"] == 1
    assert Path(result["stdout"]).read_text(encoding="utf-8").strip() == "isolated"
    assert result["stdout_sha256"] == _sha(Path(result["stdout"]))
    assert result["stderr_sha256"] == _sha(Path(result["stderr"]))


def test_environment_capture_observes_the_selected_interpreter_and_record_bytes(tmp_path):
    from scripts.validation.windows_migration_admission import capture_environment

    observed, reference = capture_environment(Path(sys.executable), tmp_path / "capture")
    distribution = metadata.distribution("ai-base-runtime")
    record = next(item for item in distribution.files if str(item).endswith(".dist-info/RECORD"))
    expected_digest = hashlib.sha256(Path(distribution.locate_file(record)).read_bytes()).hexdigest()
    assert Path(observed["executable"]).resolve() == Path(sys.executable).resolve()
    assert observed["packages"]["ai-base-runtime"]["record_sha256"] == expected_digest
    assert observed["packages"]["ai-base-runtime"]["version"] == distribution.version
    assert _sha(Path(reference["path"])) == reference["sha256"]


def test_preflight_rejects_environment_drift_before_any_service_command(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_admission as admission

    case = migration_case(tmp_path, monkeypatch)
    request = admission.load_request(case["inputs"], case["output"])
    monkeypatch.setattr(admission, "source_identity", lambda repo, commit: {"commit": commit, "status": ""})
    monkeypatch.setattr(admission, "capture_environment", lambda python, root: ({"changed": True}, {}))
    commands = []
    monkeypatch.setattr(admission, "run_command", lambda *args, **kwargs: commands.append(args))
    with pytest.raises(QualificationError, match="environment changed"):
        admission.preflight(request, case["owned"] / "preflight")
    assert commands == []


def test_environment_probe_records_shadowing_and_the_effective_selection(tmp_path, monkeypatch, capsys):
    from scripts.validation.windows_migration_admission import ENVIRONMENT_PROBE

    distributions = []
    for role, version in (("local", "0.2.0a1"), ("shared", "0.1.0a2")):
        location = tmp_path / role
        record = metadata.PackagePath(f"sdk-{version}.dist-info/RECORD")
        (location / record).parent.mkdir(parents=True)
        (location / record).write_text(role, encoding="utf-8")
        vendored = metadata.PackagePath("sdk/_vendor/vendor-1.dist-info/RECORD")
        (location / vendored).parent.mkdir(parents=True)
        (location / vendored).write_text("vendored package metadata", encoding="utf-8")
        distributions.append(SimpleNamespace(
            metadata={"Name": "ai-base-application-sdk"}, version=version, files=[record, vendored],
            locate_file=lambda item, location=location: location / str(item),
        ))
    monkeypatch.setattr(metadata, "distributions", lambda: distributions)
    monkeypatch.setattr(metadata, "distribution", lambda name: distributions[0])
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    exec(ENVIRONMENT_PROBE, {})
    value = json.loads(capsys.readouterr().out)
    assert value["packages"]["ai-base-application-sdk"]["version"] == "0.2.0a1"
    assert [row["version"] for row in value["shadowed_distributions"]["ai-base-application-sdk"]] == ["0.2.0a1", "0.1.0a2"]
    assert isinstance(value["sys_path"], list)


def test_clean_install_gate_applies_to_candidate_not_historical_optional_providers(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_admission as admission
    from scripts.validation.windows_install_smoke import PINS

    case = migration_case(tmp_path, monkeypatch)
    request = admission.load_request(case["inputs"], case["output"])
    monkeypatch.setattr(admission, "source_identity", lambda repo, commit: {"commit": commit, "status": ""})
    selected = {Path(value["executable"]): value for value in request.environments.values()}
    monkeypatch.setattr(admission, "capture_environment", lambda python, root: (selected[python], {}))
    prefix = request.current.app_python.parent.parent
    probe = {
        "prefix": str(prefix), "base_prefix": str(tmp_path / "stdlib"), "user_site": False,
        "paths": [str(prefix)], "versions": PINS,
        "modules": {name: str(prefix / f"{name}.py") for name in PINS},
        "distributions": {name: str(prefix / "Lib/site-packages") for name in PINS},
        "legacy_sdk": False, "unowned_pth": [],
    }
    labels = []

    def run(argv, **kwargs):
        assert argv[0] == str(request.current.app_python), "new clean-install rule must not reinterpret the historical environment"
        labels.append(kwargs["label"])
        output = kwargs["log_dir"] / f'{kwargs["label"]}.stdout'
        _write_json(output, probe if kwargs["label"] == "runtime-admission" else {})
        receipt = _write_json(output.with_suffix(".command.json"), {"argv": argv})
        return {"stdout": str(output), "receipt": str(receipt)}

    monkeypatch.setattr(admission, "run_command", run)
    admission.preflight(request, case["owned"] / "preflight")
    assert labels == ["runtime-admission", "candidate-pip-check"]
