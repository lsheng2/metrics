import json

from project_management.app.domain import report_draft_values


def verified_revision(repository, value):
    # Values come from strict JSON decoding; cache only the pure shape validation.
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    key = ('revision-decode/1', report_draft_values.bytes_hash(data))
    return repository.validated(key, lambda: report_draft_values.revision_from_mapping(value))
