from dataclasses import asdict
import json
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder

from project_management.app.api import ProjectActor
from project_management.app.api.project_runs import (
    RunError,
    RunRequest,
    build_project_runtime,
    build_run_read_service,
    get_project_runtime,
)
from project_management.app.api.reports import TemplateSelection
from project_management.services.project_run_worker import ProjectRunWorker


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

    def handle(self, *args, **options):
        actor = ProjectActor('local_operator')
        runtime = get_project_runtime()
        if runtime is None and options['operation'] == 'start' and options.get('execute_local'):
            runtime = build_project_runtime()
        service = runtime.run_service if runtime is not None else build_run_read_service()
        try:
            result = self._execute(service, runtime, actor, options)
        except RunError as error:
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
        if operation == 'status':
            return service.get(actor, options['project_id'], options['stage_id'], options['operation_id'])
        if operation == 'cancel':
            return service.cancel(actor, options['project_id'], options['stage_id'], options['operation_id'],
                                  expected_revision=options['expected_revision'])
        return service.resume(actor, options['project_id'], options['stage_id'], options['operation_id'],
                              expected_revision=options['expected_revision'])
