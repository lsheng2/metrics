import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from ai_base_application_sdk import TaskRunClient
import httpx

from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.summary_contracts import AiBackendTarget
from project_management.app.domain.summary_delta import build_analysis_input
from project_management.services.summary_analysis import SummaryAnalysisService
from project_management.tests.report_source_fixtures import ReportSourceScenario
from project_management.tests.summary_fixtures import PACK_ROOT
from scripts.validation.project_summary_support import (
    ai_base_python, child_environment, probe_base_imports, stop_owned_fixture, verify_base_source, wait_connection,
)


def test_shouldAcceptCumulativeDeltaThroughInstalledSdkAndRealBaseHttp():
    root = Path(__file__).resolve().parents[2]
    selected = root / '.tmp/sdk-020-join-20261105'
    base_python = ai_base_python()
    evidence = root / '.tmp/dashboard-delta-20261105' / f'http-{uuid4()}'
    evidence.mkdir(parents=True)
    provenance = verify_base_source(selected, selected / 'base-source')
    fixture = ReportSourceScenario()
    fixture.setUp()
    with fixture.archive_service() as (archive_root, archive):
        probe_base_imports(base_python, selected / 'base-source', archive_root.parent, evidence)
        first = fixture.capture_summary_source(archive)
        original, accepted1 = fixture.accept_summary(archive, first.source_key)
        second = fixture.capture_summary_source(archive, snapshot=replace(
            first.snapshot, facts=dict(first.snapshot.facts, status='In Analysis'),
        ))
        chain = tuple(archive.read_capture(fixture.actor, fixture.project.id, fixture.stage.id, item.capture_id).snapshots[0]
                      for item in (first, second))
        prepared = build_analysis_input(
            fixture.project.id, fixture.stage, first.source_key, chain, (first.snapshot, second.snapshot),
            'project-reporting.summary@review-1', accepted1,
        )
        output = {
            **fixture.output(prepared), 'base_summary_id': accepted1.summary_id,
            'current_position': 'The item is In Analysis. A validation rerun on build r8 is requested.',
        }
        vector = {
            'scope_key': fixture.backend().scope_key,
            'input': json.loads(prepared.input_content),
            'input_sha256': prepared.input_hash,
            'output': output,
        }
        vector_path = evidence / 'vector.json'
        vector_path.write_bytes(canonical_bytes(vector))
        directory = archive_root.parent / 'delta-base'
        environment_root = archive_root.parent / 'base-environment'
        environment_root.mkdir()
        process, connection = None, None
        # The input-bound intent must use the real joined endpoint on first admission.
        with (evidence / 'base.log').open('xb') as log:
            try:
                process = subprocess.Popen(
                    [str(base_python), '-I', '-B', str(root / 'scripts/validation/project_summary_base_fixture.py'),
                     '--data-dir', str(directory), '--source-root', str(selected / 'base-source'),
                     '--pack-root', str(PACK_ROOT), '--fixture', str(vector_path)],
                    cwd=archive_root.parent, env=child_environment(environment_root),
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                )
                connection = wait_connection(process, directory, vector['scope_key'])
                backend = AiBackendTarget(
                    connection['baseUrl'], connection['sourceAppId'], connection['runStoreId'],
                    connection['scopeKey'], connection['grantRevision'], connection['limitPolicyRevision'],
                )
                clients = []

                def client(target):
                    clients.append(target.run_store_id)
                    return TaskRunClient(
                        base_url=target.base_url, source_app_id=target.source_app_id,
                        run_store_id=target.run_store_id, credential_ref=connection['credentialRef'],
                        token=connection['token'], transport=httpx.AsyncHTTPTransport(retries=0, trust_env=False),
                    )

                service = SummaryAnalysisService(archive, fixture.contract, client)
                attempt = service.prepare(
                    fixture.actor, fixture.project.id, fixture.stage.id, first.source_key,
                    backend=backend, deadline_at=datetime.now(UTC) + timedelta(minutes=5),
                ).attempt
                accepted2 = asyncio.run(advance_to_acceptance(service, fixture, attempt, backend, time.monotonic() + 300))
                report = fixture.read_report_source(archive, second.capture_id)
                assert accepted2.revision == 2
                assert report.rows[0].summary_ref.summary_id == accepted2.summary_id
                assert report.rows[0].status == 'In Analysis'
                before = len(clients)
                reused = service.prepare(
                    fixture.actor, fixture.project.id, fixture.stage.id, first.source_key,
                    backend=backend, deadline_at=datetime.now(UTC) + timedelta(minutes=5),
                )
                assert reused.kind == 'no_work' and len(clients) == before
                events = [json.loads(line) for line in (directory / 'executor-observations.jsonl').read_text().splitlines()]
                assert len(events) == 1
                assert events[0]['inputSha256'] == prepared.input_hash
                (evidence / 'accepted.json').write_bytes(canonical_bytes(accepted2))
                (evidence / 'result.json').write_bytes(canonical_bytes({
                    'status': 'passed', 'sdk_version': '0.2.0a1', 'base_provenance': provenance,
                    'baseline_summary_id': accepted1.summary_id, 'accepted_summary_id': accepted2.summary_id,
                    'revision': accepted2.revision, 'input_hash': prepared.input_hash,
                    'base_dispatches': len(events), 'report_revision': report.rows[0].summary_ref.revision,
                    'initial_attempt': original.attempt_id,
                }))
            finally:
                cleanup = stop_owned_fixture(process, connection, directory)
                (evidence / 'cleanup.json').write_bytes(canonical_bytes(cleanup))
                assert cleanup['normal'], cleanup


async def advance_to_acceptance(service, source, attempt, backend, end):
    for _ in range(8):
        if time.monotonic() >= end:
            raise TimeoutError('The joint validation window expired.')
        step = await service.advance(source.actor, source.project.id, source.stage.id, attempt.attempt_id,
                                     backend=backend)
        if step.state == 'accepted':
            return step.accepted
        if step.state not in {'queued', 'running'}:
            raise RuntimeError(f'Analysis did not progress: {step.state}.')
        await asyncio.sleep(0.1)
    raise RuntimeError('The joint observation limit was reached.')
