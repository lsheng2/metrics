from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_publication_contracts import (
    PublicationManifest, ReportPublication, ReportPublicationArtifacts, manifest_payload,
)
from project_management.reporting.report_audit import compile_audit_bundle


def artifacts():
    files = {
        'snapshot.json': canonical_bytes({'source_evidence': '<script>hostile</script>', 'status': 'Fixed'}),
        'template.json': b'{"template":"retained"}',
        'edits.json': canonical_bytes({'human': 'Keep color', 'deleted': '', 'revisions': [1, 2]}),
        'report.html': b'<!doctype html><html><body>Saved report</body></html>',
        'report.txt': b'Saved report',
    }
    manifest = PublicationManifest(
        1, '99000000-0000-4000-8000-000000000001', '99000000-0000-4000-8000-000000000002',
        2, '1' * 64, 'standup', None, None, '2026-11-06T01:00:00Z', '2026-11-06T02:00:00Z',
        'synthetic-owner', '2' * 64, '3' * 64, {name: sha256(data).hexdigest() for name, data in files.items()},
    )
    files['manifest.json'] = canonical_bytes(manifest_payload(manifest))
    publication = ReportPublication(manifest, sha256(files['manifest.json']).hexdigest(), 'a' * 40, 'current')
    return ReportPublicationArtifacts(publication, files)


def test_shouldExportOriginalFilesAndEscapedReadableAuditWithDeterministicHashes():
    original = artifacts()
    exported = compile_audit_bundle(original)
    with ZipFile(BytesIO(exported.content)) as archive:
        assert len(archive.namelist()) == 8
        assert set(archive.namelist()) == set(original.files) | {'audit.html', 'audit-manifest.json'}
        for name, data in original.files.items():
            assert archive.read(name) == data
        audit = archive.read('audit.html').decode()
        assert '&lt;script&gt;hostile&lt;/script&gt;' in audit and '<script>' not in audit
        assert 'Source snapshot' in audit and 'Editorial history' in audit
        assert 'Keep color' in audit
        inventory = json.loads(archive.read('audit-manifest.json'))
        assert inventory['publication_id'] == original.publication.manifest.publication_id
        assert inventory['commit_id'] == 'a' * 40
        for name, digest in inventory['files'].items():
            assert sha256(archive.read(name)).hexdigest() == digest
    assert exported.sha256 == sha256(exported.content).hexdigest()
    assert exported.source_sha256 == original.publication.manifest_sha256
    newer_view = replace(original, publication=replace(original.publication, checkout_state='stale'))
    assert compile_audit_bundle(newer_view).content == exported.content


@pytest.mark.parametrize('mutation', ['missing', 'tampered', 'wrong-manifest'])
def test_shouldRefuseIncompleteOrInconsistentAuditBytes(mutation):
    original = artifacts()
    files = dict(original.files)
    if mutation == 'missing':
        files.pop('edits.json')
    elif mutation == 'tampered':
        files['report.html'] += b'changed'
    else:
        files['manifest.json'] += b' '
    with pytest.raises(ReportError) as error:
        compile_audit_bundle(replace(original, files=files))
    assert error.value.code == 'REPORT_ARTIFACT_INVALID'


def test_shouldRejectOversizedAuditWithoutReturningPartialZip(monkeypatch):
    import project_management.reporting.report_audit as module
    monkeypatch.setattr(module, 'MAX_EXPORT_BYTES', 32)
    with pytest.raises(ReportError) as error:
        compile_audit_bundle(artifacts())
    assert error.value.code == 'REPORT_LIMIT'
