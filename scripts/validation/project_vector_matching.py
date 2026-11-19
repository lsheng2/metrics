from __future__ import annotations

import hashlib
import json

from project_management.app.domain.capture_values import canonical_bytes


def summary_output(vector, value):
    if vector.get('schema_version') == 2:
        cases = vector.get('cases')
        if not isinstance(cases, list):
            raise ValueError('Week vector cases are invalid.')
        matches = [case for case in cases if case['input_template']['binding'] == value['binding']]
        if len(matches) != 1:
            raise ValueError('Summary input does not match a registered week vector.')
        vector = matches[0]
    capture_id = dynamic_capture_id(value)
    normalized = normalize_capture_id(value, capture_id, vector['capture_placeholder'])
    if normalized != vector['input_template']:
        raise ValueError('Summary input does not match the registered validation vector.')
    return adapt_summary_output(vector['output_template'], value, capture_id), value['binding']['stable_id']


def dynamic_capture_id(value):
    ids = [value['target_capture_id'], value['delta']['to_capture_id']]
    ids.extend(row['capture_id'] for row in value['evidence'])
    if len(set(ids)) != 1:
        raise ValueError('Dynamic capture IDs must match.')
    return str(ids[0])


def normalize_capture_id(value, capture_id, placeholder):
    normalized = json.loads(json.dumps(value, ensure_ascii=False))
    if normalized['target_capture_id'] != capture_id or normalized['delta']['to_capture_id'] != capture_id:
        raise ValueError('Unexpected dynamic capture binding.')
    normalized['target_capture_id'] = placeholder
    normalized['delta']['to_capture_id'] = placeholder
    for row in normalized['evidence']:
        if row['capture_id'] != capture_id:
            raise ValueError('Unexpected evidence capture binding.')
        row['capture_id'] = placeholder
        expected = hashlib.sha256(canonical_bytes(row['value'])).hexdigest()
        if row['source_hash'] != expected:
            raise ValueError('Evidence source hash mismatch.')
    return normalized


def adapt_summary_output(template, input_value, capture_id):
    output = json.loads(json.dumps(template, ensure_ascii=False))
    output['binding'] = input_value['binding']
    output['target_capture_id'] = capture_id
    output['profile_revision'] = input_value['profile_revision']
    return output
