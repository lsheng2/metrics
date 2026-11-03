from project_management.app.domain.capture_values import canonical_bytes, decode_json, sha256_bytes


def report_hash(value) -> str:
    return sha256_bytes(canonical_bytes(value))


def frozen_json(value):
    return decode_json(canonical_bytes(value))
