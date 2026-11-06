from dataclasses import asdict
import json
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder

from project_management.app.api import ProjectActor, ProjectError
from project_management.app.api.project_runs import (
    ProjectRunWorker,
    RunError,
    RunRequest,
    build_project_runtime,
    build_run_read_service,
    get_project_runtime,
)
from project_management.app.api.report_factories import build_report_preparation_for_run
from project_management.app.api.reports import PublicationRef, ReportError, TemplateSelection, UserTemplateSelection


class Command(BaseCommand):
    help = 'Inspect and explicitly run project report operations.'

    def add_arguments(self, parser):
        commands = parser.add_subparsers(dest='operation', required=True)
        start = commands.add_parser('start')
        start.add_argument('project_id')
        start.add_argument('stage_id')
        start.add_argument('--command-id', default='')
        start.add_argument('--expected-stage-hash', required=True)
        start.add_argument('--timezone', default='Asia/Shanghai')
        start.add_argument('--execute-local', action='store_true')
        preview = commands.add_parser('preview')
        preview.add_argument('project_id')
        preview.add_argument('stage_id')
        preview.add_argument('--series-id', required=True)
        preview.add_argument('--meeting-date', required=True)
        self._template_arguments(preview)
        prepare = commands.add_parser('prepare')
        prepare.add_argument('project_id')
        prepare.add_argument('stage_id')
        self._daily_arguments(prepare)
        reprepare = commands.add_parser('reprepare')
        reprepare.add_argument('project_id')
        reprepare.add_argument('stage_id')
        reprepare.add_argument('preparation_id')
        reprepare.add_argument('--expected-operation-revision', type=int)
        reprepare.add_argument('--expected-draft-revision', type=int)
        reprepare.add_argument('--expected-draft-revision-hash', default='')
        self._daily_arguments(reprepare, reprepare=True)
        status = commands.add_parser('status')
        status.add_argument('project_id')
        status.add_argument('stage_id')
        status.add_argument('operation_id')
        for name in ('cancel', 'resume'):
            parser_value = commands.add_parser(name)
            parser_value.add_argument('project_id')
            parser_value.add_argument('stage_id')
            parser_value.add_argument('operation_id')
            parser_value.add_argument('--expected-revision', type=int, required=True)

    def _template_arguments(self, parser):
        parser.add_argument('--template-id', required=True)
        parser.add_argument('--template-revision', type=int, required=True)
        parser.add_argument('--template-revision-hash', required=True)

    def _daily_arguments(self, parser, *, reprepare=False):
        parser.add_argument('--command-id', required=True)
        if not reprepare:
            parser.add_argument('--series-id', required=True)
            parser.add_argument('--meeting-date', required=True)
            parser.add_argument('--expected-series-policy-hash', required=True)
        parser.add_argument('--baseline-publication-id', default='')
        parser.add_argument('--baseline-manifest-hash', default='')
        parser.add_argument('--baseline-commit', default='')
        self._template_arguments(parser)
        parser.add_argument('--source-mode', choices=('saved_capture', 'refresh'), required=True)
        parser.add_argument('--capture-id', default='')
        parser.add_argument('--analysis-mode', choices=('manual_only', 'changed_items'), required=True)
        parser.add_argument('--acknowledge-gap-draft-id', action='append', default=[])
        parser.add_argument('--execute-local', action='store_true')

    def handle(self, *args, **options):
        actor = ProjectActor('local_operator')
        try:
            runtime = get_project_runtime()
            daily_local = options['operation'] in {'prepare', 'reprepare'} and options.get('execute_local')
            if runtime is not None and daily_local:
                raise RunError('RUN_BUSY')
            needs_local = options['operation'] == 'start' or options.get('source_mode') == 'refresh'
            if runtime is None and options.get('execute_local') and needs_local:
                runtime = build_project_runtime()
            service = runtime.run_service if runtime is not None else build_run_read_service()
            if options.get('source_mode') == 'refresh' and runtime is None:
                raise RunError('RUN_UNAVAILABLE')
            if daily_local and runtime is not None and service.notifier is None:
                service.notifier = lambda *args: None
            result = self._execute(service, runtime, actor, options)
        except (RunError, ReportError, ProjectError) as error:
            raise CommandError(json.dumps({'schema_version': 1, 'result': None, 'error': {
                'code': error.code,
                'message': error.message,
            }}), returncode=1) from None
        self.stdout.write(json.dumps({'schema_version': 1, 'result': asdict(result), 'error': None},
                                     cls=DjangoJSONEncoder))

    def _execute(self, service, runtime, actor, options):
        operation = options['operation']
        if operation == 'start':
            if runtime is None and not options['execute_local']:
                raise RunError('RUN_UNAVAILABLE')
            if options['execute_local'] and service.notifier is None:
                service.notifier = lambda *args: None
            request = RunRequest(
                options['command_id'] or str(uuid.uuid4()),
                options['expected_stage_hash'],
                TemplateSelection('daily-standup', '1', {}),
                options['timezone'],
            )
            submitted = service.submit(actor, options['project_id'], options['stage_id'], request)
            if runtime is None and options['execute_local']:
                return ProjectRunWorker(service).execute(actor, options['project_id'], options['stage_id'],
                                                         submitted.operation_id)
            if options['execute_local']:
                return runtime.worker.execute(actor, options['project_id'], options['stage_id'],
                                              submitted.operation_id)
            return submitted
        if operation == 'prepare':
            preparation = self._preparation(service, runtime)
            result = self._prepare_daily(preparation, actor, options)
            return self._finish_daily(preparation, runtime, actor, options, result)
        if operation == 'reprepare':
            preparation = self._preparation(service, runtime)
            result = self._reprepare_daily(preparation, actor, options)
            return self._finish_daily(preparation, runtime, actor, options, result)
        if operation == 'preview':
            return self._preparation(service, runtime).continuity.preview(
                actor, options['project_id'], options['stage_id'],
                series_id=options['series_id'], meeting_date=options['meeting_date'],
                template_selection=self._template(options),
            )
        if operation == 'status':
            return service.get(actor, options['project_id'], options['stage_id'], options['operation_id'])
        if operation == 'cancel':
            return service.cancel(actor, options['project_id'], options['stage_id'], options['operation_id'],
                                  expected_revision=options['expected_revision'])
        return service.resume(actor, options['project_id'], options['stage_id'], options['operation_id'],
                              expected_revision=options['expected_revision'])

    def _preparation(self, service, runtime):
        if runtime is None:
            return build_report_preparation_for_run(service)
        preparation = runtime.worker.daily_preparation_service
        if preparation is None:
            raise RunError('RUN_UNAVAILABLE')
        return preparation

    def _finish_daily(self, preparation, runtime, actor, options, result):
        if not options.get('execute_local') or options['source_mode'] != 'refresh' or result.operation_id is None:
            return result
        runtime.worker.execute(actor, options['project_id'], options['stage_id'], result.operation_id)
        return preparation.get(actor, options['project_id'], options['stage_id'], result.preparation_id).result

    def _prepare_daily(self, preparation, actor, options):
        return preparation.prepare(
            actor,
            options['project_id'],
            options['stage_id'],
            command_id=options['command_id'],
            series_id=options['series_id'],
            meeting_date=options['meeting_date'],
            expected_series_policy_hash=options['expected_series_policy_hash'],
            expected_baseline_ref=self._baseline(options),
            template_selection=self._template(options),
            source_mode=options['source_mode'],
            capture_id=options['capture_id'] or None,
            analysis_mode=options['analysis_mode'],
            acknowledge_gap_draft_ids=tuple(options['acknowledge_gap_draft_id']),
        )

    def _reprepare_daily(self, preparation, actor, options):
        return preparation.reprepare(
            actor,
            options['project_id'],
            options['stage_id'],
            command_id=options['command_id'],
            preparation_id=options['preparation_id'],
            expected_operation_revision=options.get('expected_operation_revision'),
            expected_draft_revision=options.get('expected_draft_revision'),
            expected_draft_revision_hash=options.get('expected_draft_revision_hash') or None,
            expected_baseline_ref=self._baseline(options),
            template_selection=self._template(options),
            source_mode=options['source_mode'],
            capture_id=options['capture_id'] or None,
            analysis_mode=options['analysis_mode'],
        )

    def _template(self, options):
        return UserTemplateSelection(
            options['template_id'],
            options['template_revision'],
            options['template_revision_hash'],
        )

    def _baseline(self, options):
        values = (
            options.get('baseline_publication_id') or '',
            options.get('baseline_manifest_hash') or '',
            options.get('baseline_commit') or '',
        )
        if values == ('', '', ''):
            return None
        if not all(values):
            raise RunError('RUN_INVALID')
        return PublicationRef(*values)
