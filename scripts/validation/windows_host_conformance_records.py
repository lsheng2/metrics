"""Read native child logs without substituting a different run's output."""
import json

from scripts.validation.project_full_stack_support import read_json
from scripts.validation import windows_qualification_inputs as inputs
from scripts.validation.windows_qualification_inputs import QualificationError


def require_matching_producer_input(reference, request):
    if not isinstance(reference, dict):
        raise QualificationError("native conformance producer input reference is missing")
    path = inputs.canonical(reference.get("path", ""), must_exist=True)
    roots = (inputs.canonical(request["source"]["repository"]), request["_paths"]["owned_root"])
    if not inputs.path_in_allowed_roots(path, roots):
        raise QualificationError("native conformance producer input is outside allowed roots")
    inputs.require_hash(path, reference.get("sha256", ""), "native conformance producer input")
    producer = read_json(path)
    if (not isinstance(producer, dict) or type(producer.get("schema_version")) is not int
            or producer["schema_version"] != 1 or producer.get("acceptance_profile") != "functional"):
        raise QualificationError("native conformance producer input schema or profile mismatch")
    # Producer inputs predate receipts; aggregate inputs bind those receipt hashes.
    for key in ("source", "candidate", "owned_root", "fixtures", "native_conformance"):
        if key not in producer or producer[key] != request.get(key):
            raise QualificationError(f"native conformance producer input differs: {key}")
    python = producer.get("python")
    if not isinstance(python, dict) or python.get("candidate") != request["python"]["candidate"]:
        raise QualificationError("native conformance producer input differs: candidate interpreter")
    environments = python.get("environments")
    expected = request["python"].get("environments", {}).get("candidate")
    if (not isinstance(environments, dict) or not environments.get("candidate")
            or environments["candidate"] != expected):
        raise QualificationError("native conformance producer input differs: candidate environment")


def server_log(reference, root, case_directory):
    if not isinstance(reference, dict):
        raise QualificationError("native server log reference is missing")
    path = inputs.owned_file(reference["path"], root)
    if path != case_directory / "serve.log":
        raise QualificationError("native server log belongs to a different case")
    inputs.require_hash(path, reference["sha256"], "native server log")
    text = path.read_text(encoding="utf-8", errors="replace")
    records = []
    for line in text.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return text, records


def require_matching_server_log(reference, payload, root, case_directory):
    _, records = server_log(reference, root, case_directory)
    if records != payload.get("server"):
        raise QualificationError("native server log and observation disagree")


def require_terminal_exits(pids, exits):
    if not isinstance(exits, dict) or set(exits) != set(pids):
        raise QualificationError("native descendant exit inventory is incomplete")
    if any(type(code) is not int or not 0 <= code <= 0xFFFFFFFF for code in exits.values()):
        raise QualificationError("native descendant termination is unproven")


def validate_descendant_exits(payload):
    descendants, exits = payload.get("descendants"), payload.get("descendant_exit_codes")
    if not isinstance(descendants, list) or not isinstance(exits, dict):
        raise QualificationError("native descendant inventory is missing")
    if any(not isinstance(row, (list, tuple)) or len(row) != 2
           or type(row[0]) is not int or row[0] <= 0 for row in descendants):
        raise QualificationError("native descendant identity is invalid")
    pids = {str(row[0]) for row in descendants}
    if len(pids) != len(descendants):
        raise QualificationError("native descendant exit inventory is incomplete")
    # Helpers have independent outcomes. The host's exit code and cleanup
    # result govern success; every observed child still needs a terminal code.
    require_terminal_exits(pids, exits)
