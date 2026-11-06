from dataclasses import dataclass


GENERATOR_REVISION = 'report-derived/1'
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_EXPORT_BYTES = 32 * 1024 * 1024
MAX_TABLES = 64
MAX_CELLS = 100000
MAX_TEXT_LINES = 100000


@dataclass(frozen=True, slots=True)
class ReportExport:
    format: str
    media_type: str
    filename: str
    content: bytes
    sha256: str
    source_sha256: str
    generator_revision: str
    warnings: tuple[str, ...]
