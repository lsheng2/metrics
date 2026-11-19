import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ai_host.admission import RuntimeCandidateError, admit_runtime_candidate


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
    assert record['version'] == '0.1.1.dev4'
    assert record['wheelSha256'] == 'b332f338f77bf2e966de7495eea6b5968606eb670287588d97a3a4d82905ec94'


def test_shouldRejectTamperedRuntimeArtifact(tmp_path):
    artifact = tmp_path / 'runtime_artifact.json'
    record = json.loads(Path('ai_host/runtime_artifact.json').read_text(encoding='utf-8'))
    record['version'] = '0.0.0'
    artifact.write_text(json.dumps(record), encoding='utf-8')

    with pytest.raises(RuntimeCandidateError):
        admit_runtime_candidate(artifact)

@pytest.mark.parametrize('mutation', ['missing-files', 'empty-files', 'missing-entry', 'wrong-wheel'])
def test_candidate_admission_rejects_incomplete_or_rebound_artifact_identity(tmp_path, mutation):
    value = json.loads(Path('ai_host/runtime_artifact.json').read_text(encoding='utf-8'))
    if mutation == 'missing-files':
        value.pop('packageFiles')
    elif mutation == 'empty-files':
        value['packageFiles'] = {}
    elif mutation == 'missing-entry':
        value['packageFiles'].pop(next(iter(value['packageFiles'])))
    else:
        value['wheelSha256'] = 'f' * 64
    artifact = tmp_path / 'runtime_artifact.json'
    artifact.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(RuntimeCandidateError):
        admit_runtime_candidate(artifact)
