import json
import shutil
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

from ai_host.admission import RuntimeCandidateError, admit_runtime_candidate


class FakeDistributionPath:
    def __init__(self, value):
        self.value = value
        self.parts = tuple(Path(value).parts)

    def __str__(self):
        return self.value


class FakeDistribution:
    def __init__(self, site_root, record):
        self.site_root = site_root
        self.record = record
        self.files = [FakeDistributionPath(name) for name in record['packageFiles']]

    def read_text(self, name):
        if name != 'direct_url.json':
            return None
        return json.dumps({'archive_info': {'hashes': {'sha256': self.record['wheelSha256']}}})

    def locate_file(self, relative):
        return self.site_root / relative


def admit_synthetic_record(tmp_path, monkeypatch, record):
    import ai_host.admission as admission

    site_root = tmp_path / 'site-packages'
    for relative, digest in record['packageFiles'].items():
        path = site_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == 'ai_base_runtime/__init__.py':
            payload = b'# synthetic runtime\n'
            assert __import__('hashlib').sha256(payload).hexdigest() == digest
            path.write_bytes(payload)
        else:
            path.write_bytes(b'')

    monkeypatch.setattr(admission, 'version', lambda name: record['version'])
    monkeypatch.setattr(admission, 'distribution', lambda name: FakeDistribution(site_root, record))
    monkeypatch.setattr(admission, 'find_spec', lambda name: SimpleNamespace(
        origin=str(site_root / 'ai_base_runtime/__init__.py'),
    ))
    artifact = tmp_path / 'runtime_artifact.json'
    artifact.write_text(json.dumps(record), encoding='utf-8')
    return admit_runtime_candidate(artifact)


def test_shouldAdmitPinnedInstalledRuntimeWithoutImportingRuntimePackage(tmp_path):
    artifact = tmp_path / 'runtime_artifact.json'
    shutil.copyfile('ai_host/runtime_artifact.json', artifact)
    probe = """
import json
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from ai_host.admission import admit_runtime_candidate
assert 'ai_base_runtime' not in sys.modules
record = admit_runtime_candidate(Path(sys.argv[2]))
assert 'ai_base_runtime' not in sys.modules
print(json.dumps({key: record[key] for key in ('distribution', 'version', 'wheelSha256')}))
"""
    result = subprocess.run(
        [sys.executable, '-I', '-c', probe, str(Path.cwd()), str(artifact)],
        check=True, capture_output=True, text=True, timeout=15,
    )
    record = json.loads(result.stdout)

    assert record['distribution'] == 'ai-base-runtime'
    assert record['version'] == '0.1.1.dev6'
    assert record['wheelSha256'] == 'e8279a3d987da1ef84d1f3f267f04c2b1c2ffd7822f6b3dc70ae10323dc99f1c'


def test_shouldRejectTamperedRuntimeArtifact(tmp_path):
    artifact = tmp_path / 'runtime_artifact.json'
    record = json.loads(Path('ai_host/runtime_artifact.json').read_text(encoding='utf-8'))
    record['version'] = '0.0.0'
    artifact.write_text(json.dumps(record), encoding='utf-8')

    with pytest.raises(RuntimeCandidateError):
        admit_runtime_candidate(artifact)

@pytest.mark.parametrize('mutation', [
    'missing-files', 'empty-files', 'missing-entry', 'wrong-wheel',
    'missing-generic-capabilities', 'nonempty-generic-capabilities',
])
def test_candidate_admission_rejects_incomplete_or_rebound_artifact_identity(tmp_path, mutation):
    value = json.loads(Path('ai_host/runtime_artifact.json').read_text(encoding='utf-8'))
    if mutation == 'missing-files':
        value.pop('packageFiles')
    elif mutation == 'empty-files':
        value['packageFiles'] = {}
    elif mutation == 'missing-entry':
        value['packageFiles'].pop(next(iter(value['packageFiles'])))
    elif mutation == 'wrong-wheel':
        value['wheelSha256'] = 'f' * 64
    elif mutation == 'missing-generic-capabilities':
        value.pop('genericCapabilities')
    else:
        value['genericCapabilities'] = [{'kind': 'rag'}]
    artifact = tmp_path / 'runtime_artifact.json'
    artifact.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(RuntimeCandidateError):
        admit_runtime_candidate(artifact)


@pytest.mark.parametrize('generic_capabilities', [None, [{'kind': 'rag'}]])
def test_candidate_admission_rejects_missing_or_nonempty_generic_capabilities(tmp_path, monkeypatch, generic_capabilities):
    payload = b'# synthetic runtime\n'
    record = {
        'distribution': 'ai-base-runtime',
        'version': '0.1.1.dev6',
        'wheelSha256': '4' * 64,
        'packageFiles': {
            'ai_base_runtime/__init__.py': __import__('hashlib').sha256(payload).hexdigest(),
        },
    }
    if generic_capabilities is not None:
        record['genericCapabilities'] = generic_capabilities

    with pytest.raises(RuntimeCandidateError):
        admit_synthetic_record(tmp_path, monkeypatch, record)
