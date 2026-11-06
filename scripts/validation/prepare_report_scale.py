import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter
import traceback


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.validation.project_full_stack_support import (
    DEFAULT_DATA_ROOT, create_run_dir, ensure_data_root, initialize_run_dir, require_owned_run_dir, write_json,
)
from scripts.validation.profile_report_reads import denied_network
from scripts.validation.report_read_identity import preflight_run_manifest


def main():
    parser = argparse.ArgumentParser(description='Create a durable synthetic S1 read fixture without model calls.')
    parser.add_argument('--manifest-from', type=Path, required=True)
    parser.add_argument('--count', type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.count <= 100:
        raise ValueError('Fixture count must be between 1 and 100.')
    source = require_owned_run_dir(args.manifest_from)
    manifest = preflight_run_manifest(source)
    root = ensure_data_root(DEFAULT_DATA_ROOT)
    run = create_run_dir(root)
    initialize_run_dir(run, root)
    manifest.update(run_dir=str(run), scenario='read-scale', fixture_state='building')
    write_json(run / 'runtime-manifest.json', manifest)
    os.environ['METRICS_PROJECT_FULL_STACK_RUN_DIR'] = str(run)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'scripts.validation.project_week_settings'
    import django
    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from django.urls import reverse
    from project_management.app.domain.captures import ArchiveStorageConfig
    from project_management.models import Project
    from project_management.tests.history_persistence_fixtures import archive_limits
    from scripts.validation.report_read_fixtures import create_standalone_scale_fixture

    started = perf_counter()
    try:
        with denied_network() as attempts:
            call_command('migrate', interactive=False, verbosity=0)

            def progress(count):
                project = Project.objects.get(owner_subject='basic:SYNTHETIC_ALICE')
                stage = project.stages.get()
                manifest['catalog'] = {
                    'actor': project.owner_subject, 'project_id': str(project.id), 'stage_id': str(stage.id),
                }
                manifest['routes'] = {'project_stage_reports': reverse('ui_web:project_stage_reports', kwargs={
                    'project_id': project.id, 'stage_id': stage.id,
                })}
                manifest['cookies'] = {
                    'session': settings.SESSION_COOKIE_NAME,
                    'csrf': settings.CSRF_COOKIE_NAME, 'language': settings.LANGUAGE_COOKIE_NAME,
                }
                write_json(run / 'runtime-manifest.json', manifest, replace=True)
                print(json.dumps({'run_dir': str(run), 'drafts_built': count}), flush=True)

            fixture = create_standalone_scale_fixture(
                run, captures=args.count, publications=args.count, revisions_per_draft=5,
                actor_subject='basic:SYNTHETIC_ALICE', progress=progress,
                archive_config=ArchiveStorageConfig(
                    run / 'archive', 'Synthetic Validation', 'validation@example.test', archive_limits(),
                ),
            )
        manifest['fixture_state'] = 'ready'
        manifest['fixture_counts'] = {'captures': args.count, 'drafts': args.count, 'publications': args.count,
                                      'revisions_per_draft': 5, 'tickets_per_snapshot': 3}
        write_json(run / 'runtime-manifest.json', manifest, replace=True)
        receipt = {
            'created_at': datetime.now(UTC).isoformat(), 'run_dir': str(run),
            'elapsed_seconds': perf_counter() - started, 'counts': manifest['fixture_counts'],
            'source_commit': fixture.source_commit, 'fixture_digest': fixture.fixture_digest,
            'network_attempts': len(attempts),
            'setup_only_stubs': ['repeated archive identity checks', 'quota scans', 'buffered Git publication appends'],
            'qualification': 'real source reader, original runtime files, native Git and full publication validation',
            'publication_files': {
                packet.publication.manifest.publication_id: {
                    'commit': packet.publication.commit_id,
                    'hashes': {name: hashlib.sha256(data).hexdigest() for name, data in packet.files.items()},
                } for packet in fixture.publication_packets
            },
        }
        write_json(run / 'evidence' / 'scale-fixture.json', receipt)
        print(json.dumps({'run_dir': str(run), 'ready': True, 'seconds': receipt['elapsed_seconds']}), flush=True)
        return 0
    except Exception as error:
        write_json(run / 'evidence' / 'scale-failure.json', {
            'run_dir': str(run), 'elapsed_seconds': perf_counter() - started, 'error': type(error).__name__,
            'traceback': traceback.format_exception(error),
        })
        print(json.dumps({'run_dir': str(run), 'ready': False, 'error': type(error).__name__}), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
