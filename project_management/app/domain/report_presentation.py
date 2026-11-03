from dataclasses import dataclass, field
from typing import Literal, Mapping


@dataclass(frozen=True, slots=True)
class TemplateSelection:
    template_id: str
    version: str
    options: Mapping = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReportEdit:
    edit_id: str
    kind: Literal['note', 'narrative_override']
    target: Mapping
    text: str
    expected_original_hash: str | None = None
    author: str | None = None
    edited_at: str | None = None


@dataclass(frozen=True, slots=True)
class TemplateDefinition:
    template_id: str
    version: str
    options: Mapping
    template_hash: str
    renderer_version: str


@dataclass(frozen=True, slots=True)
class RenderedReport:
    draft_id: str
    revision: int
    revision_hash: str | None
    snapshot_hash: str
    template_hash: str
    html_document: bytes
    html_fragment: str
    plain_text: str
    html_document_sha256: str
    html_document_bytes: int
    html_fragment_sha256: str
    html_fragment_bytes: int
    plain_text_sha256: str
    plain_text_bytes: int
    content_language: str = 'en'
    clipboard_available: bool = True
