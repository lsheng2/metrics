import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.validation import project_full_stack
from scripts.validation.project_full_stack_support import json_lines, read_json, require_owned_run_dir, write_json
from scripts.validation.project_runtime_join_http import RuntimeJoinHttp, operation_id
from scripts.validation.project_validation_identity import source_identity
from scripts.validation.run_report_authoring_tests import guarded_connect, guarded_create_connection, guarded_getaddrinfo


def run_case(run_dir, manifest, directory):
    from project_management.app.api import ProjectActor
    from project_management.app.api.report_factories import build_report_service
    from project_management.app.api.run_factories import build_run_read_service
    from project_management.app.api.reports import AuthoringTemplateSelection
    from project_management.app.domain.report_contracts import ReportSelection

    catalog = manifest['catalog']
    actor = ProjectActor(catalog['actor'])
    project_id, stage_id = catalog['project_id'], catalog['stage_id']
    prefix = f'/projects/{project_id}/stages/{stage_id}/reports'
    client = RuntimeJoinHttp(manifest, directory)
    try:
        assert client.request('GET', manifest['routes']['project_stage_reports']).status_code == 200
        command = {
            'command_id': str(uuid4()), 'expected_stage_hash': catalog['stage_hash'],
            'template_id': 'daily-standup', 'template_version': '1', 'timezone': 'Asia/Shanghai',
        }
        run_id, run_url = operation_id(client.request('POST', prefix + '/runs/', data=command))
        assert client.wait_run(run_url) == 'draft_ready'
        operation = build_run_read_service().get(actor, project_id, stage_id, run_id)
        admission_path = (
            run_dir / 'archive/projects' / project_id / 'stages' / stage_id /
            'runtime/operations' / run_id / 'request.json'
        )
        admission = read_json(admission_path)
        assert admission['schema_version'] == 3
        assert admission['task_binding']['principal']['subject'] == actor.subject
        assert admission['task_binding']['model_identity']['model'] == 'scripted'
        assert admission['task_binding']['runtime_version']
        repeated_id, _ = operation_id(client.request('POST', prefix + '/runs/', data=command))
        assert repeated_id == run_id
        drafts = build_report_service()
        draft = drafts.create_authored(
            actor, project_id, stage_id, command_id=str(uuid4()),
            selection=ReportSelection(capture_id=operation.capture_id),
            template=AuthoringTemplateSelection('builtin', 'daily-standup', '2', {}),
        )
        assist_path = prefix + f'/drafts/{draft.draft_id}/assists/'
        description = client.json_result('GET', assist_path)
        assert description['available'] and description['targets']
        target = description['targets'][0]['target_id']
        request = {
            'command_id': str(uuid4()), 'expected_revision': draft.revision,
            'expected_revision_hash': draft.revision_hash, 'target_ids': [target],
            'instruction': 'Summarize the retained synthetic evidence.',
        }
        assist = client.json_result('POST', assist_path, payload=request)
        observed = client.wait_assist(assist_path + assist['assist_id'] + '/')
        assert observed['state'] == 'candidate_ready', observed
        candidate = client.json_result('GET', assist_path + assist['assist_id'] + '/candidate/')
        assert candidate['targets'][0]['target_id'] == target
        assert candidate['targets'][0]['status'] == 'filled'
        repeated = client.json_result('POST', assist_path, payload=request)
        assert repeated['assist_id'] == assist['assist_id']
        observations = json_lines(run_dir / 'model/executor-observations.jsonl')
        assert len(observations) == 2
        assert {item['kind'] for item in observations} == {'project_summary', 'report_authoring'}
        return {
            'operation_id': run_id, 'run_url': run_url, 'capture_id': operation.capture_id,
            'produced_draft_id': operation.draft_id, 'authored_draft_id': draft.draft_id,
            'assist_id': assist['assist_id'], 'assist_path': assist_path,
            'model_dispatch_count': len(observations),
            'admission_sha256': hashlib.sha256(admission_path.read_bytes()).hexdigest(),
            'task_binding': admission['task_binding'], 'state': 'passed',
        }
    finally:
        client.close()


def reopen_case(run_dir, manifest, directory):
    previous = read_json(run_dir / 'evidence/runtime-join.json')['result']
    client = RuntimeJoinHttp(manifest, directory)
    try:
        assert client.wait_run(previous['run_url']) == 'draft_ready'
        result = client.json_result('GET', previous['assist_path'] + previous['assist_id'] + '/')
        assert result['state'] == 'candidate_ready'
        candidate = client.json_result('GET', previous['assist_path'] + previous['assist_id'] + '/candidate/')
        assert candidate['targets']
        assert len(json_lines(run_dir / 'model/executor-observations.jsonl')) == previous['model_dispatch_count']
        return {'state': 'passed', 'operation_id': previous['operation_id'], 'assist_id': previous['assist_id']}
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description='Validate served project-run and report-assist runtime consumers.')
    parser.add_argument('action', choices=('run', 'reopen'))
    parser.add_argument('--run-dir', type=Path, required=True)
    args = parser.parse_args()
    run_dir = require_owned_run_dir(args.run_dir)
    manifest = project_full_stack.trusted_manifest(run_dir)
    if args.action == 'run' and (run_dir / 'evidence/runtime-join.json').exists():
        raise ValueError('A completed runtime join cannot be relabeled or repeated.')
    directory = run_dir / 'evidence' / f'runtime-{args.action}-{uuid4()}'
    directory.mkdir()
    os.environ['DJANGO_SETTINGS_MODULE'] = project_full_stack.settings_for(manifest.get('scenario', 'single'))
    os.environ['METRICS_PROJECT_FULL_STACK_RUN_DIR'] = str(run_dir)
    os.environ.pop('METRICS_PROJECT_FULL_STACK_BOOTSTRAP', None)
    receipt = {'action': args.action, 'started_at': datetime.now(UTC).isoformat(), 'source': source_identity()}
    try:
        with patch.object(socket.socket, 'connect', guarded_connect(socket.socket.connect)), \
                patch.object(socket, 'create_connection', guarded_create_connection(socket.create_connection)), \
                patch.object(socket, 'getaddrinfo', guarded_getaddrinfo(socket.getaddrinfo)):
            import django
            django.setup()
            from ai_host.admission import admit_runtime_candidate
            record = admit_runtime_candidate()
            receipt['runtime'] = {key: record[key] for key in ('version', 'wheelSha256', 'sourceCommit')}
            receipt['result'] = (
                run_case(run_dir, manifest, directory) if args.action == 'run'
                else reopen_case(run_dir, manifest, directory)
            )
        receipt['status'] = 'passed'
        if args.action == 'run':
            write_json(run_dir / 'evidence/runtime-join.json', receipt)
    except Exception as error:
        receipt.update(status='failed', error=type(error).__name__)
        write_json(directory / 'receipt.json', receipt)
        raise
    write_json(directory / 'receipt.json', receipt)
    print(json.dumps({'status': 'passed', 'evidence': str(directory / 'receipt.json')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
