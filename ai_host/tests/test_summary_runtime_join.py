from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
import threading
import time
import unittest

from ai_base_runtime import start_blocking
from ai_base_runtime.spi import HostConfig, LifecycleLimits, PROVIDER_OPENAI_COMPATIBLE
from ai_base_runtime.testkit import InMemoryHost, scripted_model_endpoint

from ai_host.package import METRICS_APP
from ai_host.settings import RUNTIME_START_SECONDS, build_runtime_settings
from ai_host.task_runs import RuntimeTaskRunPort
from project_management.services.summary_analysis import SummaryAnalysisService
from project_management.tests.summary_fixtures import SummaryScenario


def completion(content):
    return {
        'id': 'joined-summary', 'object': 'chat.completion', 'created': 1794780000,
        'model': 'scripted', 'choices': [{
            'index': 0, 'message': {'role': 'assistant', 'content': json.dumps(content)},
            'finish_reason': 'stop',
        }],
        'usage': {'prompt_tokens': 101, 'completion_tokens': 37, 'total_tokens': 138},
    }


class TestSummaryRuntimeJoin(SummaryScenario, unittest.TestCase):
    def test_real_archive_and_installed_runtime_accept_one_summary_without_legacy_wire(self):
        threads = {thread.ident for thread in threading.enumerate()}
        with self.archive_service() as (root, archive):
            source_key = self.capture_source(archive)
            service = SummaryAnalysisService(archive, self.contract, None)
            prepared = service.prepare(
                self.actor, self.project.id, self.stage.id, source_key,
                principal=self.principal(), deadline_at=datetime.now(UTC) + timedelta(minutes=5),
            )
            request = prepared.attempt.request
            state_dir = root.parent / 'joined-runtime-state'
            state_dir.mkdir()
            with scripted_model_endpoint([completion(self.output(prepared.attempt.prepared))]) as endpoint:
                config = HostConfig(
                    state_dir=state_dir, allowed_hosts=('127.0.0.1',),
                    lifecycle=LifecycleLimits(stop_timeout_seconds=1.0),
                    model=replace(endpoint.model, provider=PROVIDER_OPENAI_COMPATIBLE),
                )
                context = start_blocking(
                    build_runtime_settings(), InMemoryHost(config), [METRICS_APP],
                    start_timeout=RUNTIME_START_SECONDS,
                )
                with context as handle:
                    service = SummaryAnalysisService(
                        archive, self.contract, RuntimeTaskRunPort(handle.blocking.task_runs),
                    )
                    deadline = time.monotonic() + 60
                    while True:
                        step = service.advance(
                            self.actor, self.project.id, self.stage.id, prepared.attempt.attempt_id,
                            principal=self.principal(),
                        )
                        if step.state not in {'queued', 'running'}:
                            break
                        self.assertLess(time.monotonic(), deadline)
                    self.assertEqual('accepted', step.state)
                    self.assertEqual(prepared.attempt.prepared.input_hash, step.accepted.input_hash)
                    self.assertEqual('succeeded', step.accepted.run_result['status'])
                    self.assertNotIn('contractVersion', step.accepted.run_result)
                    self.assertNotIn('runStoreId', step.accepted.run_result)
                    self.assertNotIn('acceptedAt', step.accepted.run_result)
                    reopened = type(archive)(archive.project_api, archive.repository_factory, archive.config)
                    recovered = SummaryAnalysisService(reopened, self.contract, service.task_run_port)
                    repeat = recovered.advance(
                        self.actor, self.project.id, self.stage.id, prepared.attempt.attempt_id,
                        principal=self.principal(),
                    )
                    self.assertEqual(step.accepted.summary_id, repeat.accepted.summary_id)
                    stored = reopened.read_analysis_attempt(
                        self.actor, self.project.id, self.stage.id, prepared.attempt.attempt_id,
                    )
                    self.assertEqual(request, stored.request)
                    self.assertEqual(1, len(endpoint.requests))
                self.assertTrue(handle.stop_result.completed)
                self.assertTrue(handle.stop_result.persistent_state_flushed)
                self.assertEqual((), handle.stop_result.unclosed_resources)
            self.assertEqual([], [thread.name for thread in threading.enumerate()
                                  if thread.ident not in threads])
