from hashlib import sha256
from html import escape
from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_exports import MAX_EXPORT_BYTES, ReportExport
from project_management.app.domain.report_publication_contracts import PUBLICATION_FILES, manifest_payload


GENERATOR_REVISION = 'report-audit/1'


def compile_audit_bundle(artifacts):
    publication, files = artifacts.publication, artifacts.files
    if set(files) != set(PUBLICATION_FILES) or any(type(data) is not bytes for data in files.values()):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if sum(map(len, files.values())) > MAX_EXPORT_BYTES:
        raise ReportError('REPORT_LIMIT')
    manifest = publication.manifest
    if (sha256(files['manifest.json']).hexdigest() != publication.manifest_sha256
            or canonical_bytes(manifest_payload(manifest)) != files['manifest.json']
            or any(sha256(files[name]).hexdigest() != digest for name, digest in manifest.file_hashes.items())):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Report audit</title></head>',
        '<body style="font-family:Segoe UI,Arial,sans-serif;margin:24px;">',
        '<h1>Report audit</h1>',
        f'<p>Publication: {escape(manifest.publication_id)}<br>Commit: {escape(publication.commit_id)}</p>',
    ]
    labels = (('snapshot.json', 'Source snapshot'), ('template.json', 'Pinned template'),
              ('edits.json', 'Editorial history'), ('manifest.json', 'Publication manifest'))
    try:
        for name, label in labels:
            value = json.loads(files[name])
            text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
            parts.append(f'<h2>{label}</h2><pre style="white-space:pre-wrap;overflow-wrap:anywhere;">{escape(text)}</pre>')
    except (ValueError, UnicodeError, TypeError):
        raise ReportError('REPORT_ARTIFACT_INVALID') from None
    parts.append('</body></html>')
    included = {**files, 'audit.html': ''.join(parts).encode('utf-8')}
    inventory = {
        'schema_version': 1, 'generator_revision': GENERATOR_REVISION,
        'publication_id': manifest.publication_id, 'commit_id': publication.commit_id,
        'manifest_sha256': publication.manifest_sha256,
        'files': {name: sha256(data).hexdigest() for name, data in included.items()},
    }
    included['audit-manifest.json'] = canonical_bytes(inventory)
    if sum(map(len, included.values())) > MAX_EXPORT_BYTES:
        raise ReportError('REPORT_LIMIT')
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        for name, data in sorted(included.items()):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0o600 << 16
            archive.writestr(info, data)
    content = stream.getvalue()
    if len(content) > MAX_EXPORT_BYTES:
        raise ReportError('REPORT_LIMIT')
    return ReportExport('audit_zip', 'application/zip', f'publication-{manifest.publication_id}-audit.zip',
                        content, sha256(content).hexdigest(), publication.manifest_sha256,
                        GENERATOR_REVISION, ())
