"""Frozen source, snapshot and interpreter inputs for the migration driver."""
from dataclasses import dataclass
from pathlib import Path
import re
from string import Template
from uuid import UUID

from project_management.app.domain.report_publication_contracts import PUBLICATION_FILES
from scripts.validation import windows_qualification_inputs as common
from scripts.validation.project_full_stack_support import read_json
from scripts.validation.qualify_ai_runtime import run_command, source_identity
from scripts.validation.windows_migration_history import HistoricalInputs
from scripts.validation import windows_migration_history
from scripts.validation.windows_migration_inventory import MigrationSnapshot, SourceIdentity, validate_snapshot
from scripts.validation.windows_qualification_inputs import QualificationError
from scripts.validation.windows_install_smoke import LEGACY_SDK_MODULES, installer_environment, validate_import_probe


ROOT = Path(__file__).resolve().parents[2]
IDENTITY_FIELDS = ("repository", "commit", "app_python", "base_python", "base_source", "pack_root", "environment_digest")
ENVIRONMENT_ROLES = ("candidate", "old_app", "old_base")
ENVIRONMENT_PROBE = Template("""
import hashlib, importlib.metadata as metadata, importlib.util, json, re, sys
from pathlib import Path
def fingerprint(distribution):
    records = [item for item in distribution.files or ()
               if len(item.parts) == 2 and item.parts[0].endswith('.dist-info') and item.name == 'RECORD']
    if len(records) != 1:
        raise RuntimeError('distribution RECORD is missing or ambiguous')
    return {
        'version': distribution.version,
        'location': str(Path(distribution.locate_file('')).resolve()),
        'record_sha256': hashlib.sha256(Path(distribution.locate_file(records[0])).read_bytes()).hexdigest(),
    }
candidates = {}
for distribution in metadata.distributions():
    name = re.sub(r'[-_.]+', '-', distribution.metadata['Name']).lower()
    record = fingerprint(distribution)
    if record not in candidates.setdefault(name, []):
        candidates[name].append(record)
packages = {name: fingerprint(metadata.distribution(name)) for name in candidates}
if any(packages[name] not in rows for name, rows in candidates.items()):
    raise RuntimeError('selected distribution was not inventoried')
imports = {}
for name in ('ai_base_runtime', $legacy_modules):
    spec = importlib.util.find_spec(name)
    imports[name] = spec.origin if spec else None
print(json.dumps({
    'executable': sys.executable, 'python': sys.version.split()[0], 'packages': packages,
    'shadowed_distributions': {name: rows for name, rows in candidates.items() if len(rows) > 1},
    'selected_imports': imports, 'sys_path': sys.path,
}, sort_keys=True))
""").substitute(legacy_modules=", ".join(repr(name) for name in sorted(LEGACY_SDK_MODULES)))


@dataclass(frozen=True, slots=True)
class MigrationRequest:
    data: dict
    snapshot: MigrationSnapshot
    seed: dict
    old: SourceIdentity
    current: SourceIdentity
    environments: dict
    references: tuple[tuple[Path, str], ...]
    historical: HistoricalInputs | None = None

    @property
    def paths(self):
        return self.data["_paths"]


def _reference(value: dict, root: Path, label: str, references: list, *,
               historical: HistoricalInputs | None = None) -> tuple[Path, dict]:
    path = windows_migration_history.input_file(value["path"], root, label, historical)
    common.require_hash(path, value["sha256"], label)
    references.append((path, value["sha256"]))
    return path, read_json(path)


def _old_identity(source: dict, rollback: dict, root: Path, historical: HistoricalInputs | None) -> SourceIdentity:
    values = {key: source[key] for key in IDENTITY_FIELDS}
    for key in ("repository", "app_python", "base_python", "base_source", "pack_root"):
        if not values[key]:
            raise QualificationError(f"missing old source binding: {key}")
        values[key] = windows_migration_history.input_file(values[key], root, key, historical)
    identity = SourceIdentity(**values)
    expected = {
        "source_repository": str(identity.repository), "source_commit": identity.commit,
        "app_python": str(identity.app_python), "base_python": str(identity.base_python),
    }
    for key, value in expected.items():
        candidate = rollback.get(key)
        if key != "source_commit":
            candidate = str(common.canonical(candidate))
        if candidate != value:
            raise QualificationError(f"old source binding mismatch: {key}")
    return identity


def validate_seed(seed: dict, old_commit: str) -> dict:
    if seed.get("kind") != "synthetic-retained-publication-fixture" or seed.get("old_source_commit") != old_commit:
        raise QualificationError("retained publication source mismatch")
    for key in ("project_id", "stage_id"):
        if str(UUID(seed[key])) != seed[key]:
            raise QualificationError("retained publication identity is not canonical")
    packets = seed.get("packets")
    if not isinstance(packets, list) or not packets:
        raise QualificationError("retained publication packets are missing")
    ids = []
    for packet in packets:
        identifier = packet["publication_id"]
        if str(UUID(identifier)) != identifier or not re.fullmatch("[0-9a-f]{40}", packet["commit"]):
            raise QualificationError("retained publication identity is invalid")
        if set(packet["files"]) != set(PUBLICATION_FILES):
            raise QualificationError("retained publication file set is incomplete")
        if any(not re.fullmatch("[0-9a-f]{64}", digest) for digest in packet["files"].values()):
            raise QualificationError("retained publication digest is invalid")
        ids.append(identifier)
    if len(set(ids)) != len(ids) or seed.get("publications") != ids:
        raise QualificationError("retained publication inventory is inconsistent")
    route = f'/projects/{seed["project_id"]}/stages/{seed["stage_id"]}/reports/'
    if seed.get("route", route) != route:
        raise QualificationError("retained publication route mismatch")
    return {**seed, "route": route}


def _environments(data: dict, root: Path, executables: dict, references: list,
                  historical: HistoricalInputs | None) -> dict:
    selected = data["python"]["environments"]
    if set(selected) != set(ENVIRONMENT_ROLES):
        raise QualificationError("complete interpreter environment roles are required")
    result = {}
    for role, executable in executables.items():
        read_root = historical if role in {"old_app", "old_base"} else None
        _, record = _reference(selected[role], root, f"{role} environment", references, historical=read_root)
        if common.canonical(record["executable"]) != executable:
            raise QualificationError(f"{role} environment interpreter mismatch")
        if not record.get("python") or not isinstance(record.get("packages"), dict) or not record["packages"]:
            raise QualificationError(f"{role} environment inventory is incomplete")
        if (not isinstance(record.get("shadowed_distributions"), dict)
                or not isinstance(record.get("selected_imports"), dict) or not isinstance(record.get("sys_path"), list)):
            raise QualificationError(f"{role} environment resolution inventory is incomplete")
        result[role] = record
    return result


def load_request(input_arg: str | Path, output_arg: str | Path) -> MigrationRequest:
    data = common.load_request(input_arg, output_arg, profile="functional")
    return from_validated_input(data)


def from_validated_input(data: dict) -> MigrationRequest:
    paths, references = data["_paths"], []
    root = paths["owned_root"]
    references.append((paths["inputs"], common.digest_file(paths["inputs"])))
    historical = windows_migration_history.from_migration(
        data["migration"], current_repo=ROOT.resolve(), owned_root=root,
    )
    if historical is not None:
        references.append((historical.marker, historical.marker_sha256))
    snapshot_path, payload = _reference(data["migration"]["snapshot"], root, "snapshot", references, historical=historical)
    payload["files"], payload["directories"] = tuple(payload["files"]), tuple(payload["directories"])
    snapshot = MigrationSnapshot(**payload)
    old = _old_identity(snapshot.source, data["rollback"], root, historical)
    validate_snapshot(snapshot, old.as_record())
    source_run = windows_migration_history.input_file(snapshot.run_dir, root, "source run", historical)
    source_data = windows_migration_history.input_file(snapshot.data_root, root, "source data root", historical)
    if source_run.parent != source_data:
        raise QualificationError("source run does not belong to the source data root")
    seed_path, seed = _reference(data["migration"]["seed"], root, "seed", references, historical=historical)
    if not seed_path.is_relative_to(source_run / "evidence"):
        raise QualificationError("seed does not belong to the source run")
    seed = validate_seed(seed, old.commit)
    current = SourceIdentity(repository=ROOT, commit=data["source"]["commit"], app_python=paths["python"])
    executables = {"candidate": paths["python"], "old_app": old.app_python, "old_base": old.base_python}
    environments = _environments(data, root, executables, references, historical)
    protected = [
        ROOT, source_run, old.repository, snapshot_path, seed_path,
        *(python.parent.parent for python in executables.values()),
    ]
    if historical is not None:
        protected.append(historical.root)
    if any(common.overlaps(paths["output"], path) for path in protected):
        raise QualificationError("output overlaps protected source, data or environment")
    return MigrationRequest(data, snapshot, seed, old, current, environments, tuple(references), historical)


def recheck_inputs(request: MigrationRequest) -> None:
    for path, digest in request.references:
        common.require_hash(path, digest, "frozen migration input")
    common.validate_frozen_hashes(
        ROOT.resolve(), request.data["source"], request.data["fixtures"],
        (ROOT.resolve(), request.paths["owned_root"]),
    )


def capture_environment(python: Path, directory: Path) -> tuple[dict, dict]:
    command = run_command(
        [str(python), "-I", "-c", ENVIRONMENT_PROBE], cwd=ROOT, log_dir=directory,
        label="environment", timeout=30, env=installer_environment(directory / "private"),
    )
    path = Path(command["stdout"])
    return read_json(path), {
        "path": str(path), "sha256": common.digest_file(path),
        "command": {"path": command["receipt"], "sha256": common.digest_file(Path(command["receipt"]))},
    }


def preflight(request: MigrationRequest, directory: Path) -> dict:
    recheck_inputs(request)
    sources = {
        "dashboard": source_identity(request.current.repository, request.current.commit),
        "old_dashboard": source_identity(request.old.repository, request.old.commit),
    }
    executables = {
        "candidate": request.current.app_python, "old_app": request.old.app_python,
        "old_base": request.old.base_python,
    }
    environments, commands = {}, []
    for role, python in executables.items():
        observed, reference = capture_environment(python, directory / role)
        if observed != request.environments[role]:
            raise QualificationError(f"{role} environment changed")
        if role == "candidate" and (
            observed["shadowed_distributions"]
            or any(observed["selected_imports"].get(name) is not None for name in LEGACY_SDK_MODULES)
        ):
            raise QualificationError("candidate environment is not an isolated modern runtime")
        environments[role] = reference
    private = installer_environment(directory / "private")
    probe = run_command(
        [str(request.current.app_python), "-I", str(ROOT / "scripts/validation/windows_install_smoke.py"), "--probe"],
        cwd=ROOT, log_dir=directory, label="runtime-admission", timeout=30, env=private,
    )
    value = read_json(Path(probe["stdout"]))
    validate_import_probe(value, request.current.app_python.parent.parent, ROOT)
    commands.append(probe)
    commands.append(run_command(
        [str(request.current.app_python), "-I", "-m", "pip", "check"], cwd=ROOT, log_dir=directory,
        label="candidate-pip-check", timeout=60, env=private,
    ))
    return {
        "sources": sources, "environments": environments,
        "commands": [
            {"path": item["receipt"], "sha256": common.digest_file(Path(item["receipt"]))}
            for item in commands
        ],
    }
