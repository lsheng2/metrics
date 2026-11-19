from dataclasses import dataclass

from .capture_values import canonical_bytes, content_hash, decode_json, sha256_bytes


@dataclass(frozen=True, slots=True)
class TaskProfileDefinition:
    definition_json: str

    def __post_init__(self):
        raw = self.definition_json.encode('utf-8')
        value = decode_json(raw)
        if (type(value) is not dict or canonical_bytes(value) != raw
                or set(value) != {'id', 'version', 'instructions', 'input_schema', 'output_schema', 'limits'}
                or type(value['id']) is not str or not value['id'].startswith('metrics.')
                or type(value['version']) is not str or value['version'] in {'', 'latest'}
                or type(value['instructions']) is not str or not value['instructions']
                or any(type(value[key]) is not dict for key in ('input_schema', 'output_schema', 'limits'))):
            raise ValueError('Invalid Metrics task profile')

    @property
    def definition(self):
        return decode_json(self.definition_json.encode('utf-8'))

    @property
    def id(self):
        return self.definition['id']

    @property
    def version(self):
        return self.definition['version']

    @property
    def instructions(self):
        return self.definition['instructions']

    @property
    def input_schema(self):
        return self.definition['input_schema']

    @property
    def output_schema(self):
        return self.definition['output_schema']

    @property
    def limits(self):
        return self.definition['limits']

    @property
    def definition_sha256(self):
        return sha256_bytes(self.definition_json.encode('utf-8'))

    @property
    def output_schema_sha256(self):
        return content_hash(self.output_schema)
