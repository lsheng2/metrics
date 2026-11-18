"""Read native child logs without substituting a different run's output."""
import json

from scripts.validation import windows_qualification_inputs as inputs
from scripts.validation.windows_qualification_inputs import QualificationError


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
