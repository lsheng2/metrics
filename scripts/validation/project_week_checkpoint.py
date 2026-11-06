import argparse
from hashlib import sha256
import os
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.validation.project_full_stack import trusted_manifest
from scripts.validation.project_full_stack_support import require_owned_run_dir, write_json
from scripts.validation.project_week_scenarios import settings_for


def checkpoint(run_dir, draft_id, label, publication_id=None):
    if re.fullmatch(r'[A-Za-z0-9_-]{1,80}', label) is None:
        raise ValueError('Invalid evidence label.')
    manifest = trusted_manifest(run_dir)
    if manifest.get('scenario') != 'full-week':
        raise ValueError('Readback requires the owned full-week scenario.')
    os.environ['DJANGO_SETTINGS_MODULE'] = settings_for('full-week')
    os.environ['METRICS_PROJECT_FULL_STACK_RUN_DIR'] = str(run_dir)
    os.environ.pop('METRICS_PROJECT_FULL_STACK_BOOTSTRAP', None)
    import django
    django.setup()
    from project_management.app.api import ProjectActor
    from project_management.app.api.report_factories import build_report_service

    actor = ProjectActor(manifest['catalog']['actor'])
    args = (actor, manifest['catalog']['project_id'], manifest['catalog']['stage_id'])
    service = build_report_service()
    draft = service.get(*args, draft_id)
    directory = run_dir / 'evidence' / 'canonical' / label
    directory.mkdir(parents=True, exist_ok=False)
    value = {
        'draft_id': draft.draft_id, 'revision': draft.revision, 'revision_hash': draft.revision_hash,
        'state': draft.state, 'snapshot_hash': draft.snapshot_hash,
        'snapshot': draft.snapshot, 'context': draft.authoring_context, 'edits': draft.authored_edits,
    }
    if publication_id is not None:
        publication = service.get_publication(*args, publication_id)
        if publication.manifest.draft_id != draft_id:
            raise AssertionError('Publication does not belong to the selected draft.')
        files = {}
        for name in ('snapshot.json', 'template.json', 'edits.json', 'report.html', 'report.txt', 'manifest.json'):
            data = service.read_artifact(*args, publication_id, name)
            (directory / name).write_bytes(data)
            files[name] = sha256(data).hexdigest()
        value.update(publication=publication, file_hashes=files)
    write_json(directory / 'checkpoint.json', value)
    return directory / 'checkpoint.json'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--draft-id', required=True)
    parser.add_argument('--publication-id')
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    result = checkpoint(require_owned_run_dir(args.run_dir), args.draft_id, args.label, args.publication_id)
    print(str(result))


if __name__ == '__main__':
    main()
