import shutil
import sys
from pathlib import Path

import pytest

from ai_host.admission import RuntimeCandidateError, admit_runtime_candidate


def test_shouldAdmitPinnedInstalledRuntimeWithoutImportingRuntimePackage(tmp_path):
    artifact = tmp_path / 'runtime_artifact.json'
    shutil.copyfile('ai_host/runtime_artifact.json', artifact)
    sys.modules.pop('ai_base_runtime', None)

    record = admit_runtime_candidate(artifact)

    assert record['distribution'] == 'ai-base-runtime'
    assert record['version'] == '0.1.1.dev1'
    assert record['wheelSha256'] == '4bf24df5927cdcd36f9675948967c3894a4c66e252db5b9b8dffda9223e2b6b6'
    assert 'ai_base_runtime' not in sys.modules


def test_shouldRejectTamperedRuntimeArtifact(tmp_path):
    artifact = tmp_path / 'runtime_artifact.json'
    text = Path('ai_host/runtime_artifact.json').read_text(encoding='utf-8')
    artifact.write_text(text.replace('"version": "0.1.1.dev1"', '"version": "0.1.1"'), encoding='utf-8')

    with pytest.raises(RuntimeCandidateError):
        admit_runtime_candidate(artifact)
import json


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
