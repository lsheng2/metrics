from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json


ERROR_MESSAGES = {
    'PROJECT_NOT_FOUND': 'Project is not available.',
    'PROJECT_ARCHIVED': 'Archived projects cannot accept new stages.',
    'PROJECT_KEY_CONFLICT': 'Project key is already used with different details.',
    'STAGE_RULE_IMMUTABLE': 'Stage key is already bound to a different definition.',
    'INVALID_PROJECT': 'Project request is invalid.',
    'INVALID_SELECTION': 'Source selection is invalid.',
    'SOURCE_UNAVAILABLE': 'The selected source is not available.',
    'SOURCE_CHANGED': 'Source changed during stage preparation.',
    'PROJECT_LIMIT': 'Project stage limit has been reached.',
    'PROJECT_BUSY': 'Project storage is busy. Retry the same request later.',
}


class ProjectError(Exception):
    def __init__(self, code):
        self.code = code
        self.message = ERROR_MESSAGES[code]
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class ProjectActor:
    subject: str


@dataclass(frozen=True, slots=True)
class ScopeSelection:
    profile_id: str
    scope_id: int | None = None


@dataclass(frozen=True, slots=True)
class ScopeDescriptor:
    provider_id: str
    profile_id: str
    endpoint: str
    source_ref: str
    query_kind: str
    query: str
    source_version: str

    def definition_hash(self) -> str:
        return document_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class ProjectSummary:
    id: str
    key: str
    name: str
    archived: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StageSummary:
    id: str
    key: str
    name: str
    selection: ScopeSelection
    descriptor: ScopeDescriptor
    definition_hash: str
    created_at: datetime
    source_status: str = 'unchecked'


@dataclass(frozen=True, slots=True)
class StagePreview:
    project_id: str
    key: str
    name: str
    selection: ScopeSelection
    descriptor: ScopeDescriptor
    definition_hash: str


@dataclass(frozen=True, slots=True)
class ProjectDetail:
    project: ProjectSummary
    stages: tuple[StageSummary, ...]


def document_hash(document) -> str:
    encoded = json.dumps(document, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()
