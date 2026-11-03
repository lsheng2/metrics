from dataclasses import asdict
import json

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder

from project_management.app.api import ProjectActor, ProjectError, ScopeSelection
from project_management.container import build_project_api


class Command(BaseCommand):
    help = 'Manage local projects and immutable Jira or HSD-ES stage definitions.'

    def add_arguments(self, parser):
        commands = parser.add_subparsers(dest='operation', required=True)
        create = commands.add_parser('create')
        create.add_argument('--key', required=True)
        create.add_argument('--name', required=True)
        listing = commands.add_parser('list')
        listing.add_argument('--limit', type=int, default=50)
        listing.add_argument('--offset', type=int, default=0)
        for name in ('show', 'archive'):
            commands.add_parser(name).add_argument('project_id')
        stage = commands.add_parser('add-stage')
        stage.add_argument('project_id')
        stage.add_argument('--key', required=True)
        stage.add_argument('--name', required=True)
        stage.add_argument('--profile-id', required=True)
        stage.add_argument('--scope-id', type=int)

    def handle(self, *args, **options):
        api = build_project_api()
        actor = ProjectActor('local_operator')
        try:
            result = self._execute(api, actor, options)
        except ProjectError as error:
            envelope = {'schema_version': 1, 'result': None, 'error': {
                'code': error.code, 'message': error.message,
            }}
            raise CommandError(json.dumps(envelope), returncode=1) from None
        payload = [asdict(row) for row in result] if isinstance(result, tuple) else asdict(result)
        self.stdout.write(json.dumps(
            {'schema_version': 1, 'result': payload, 'error': None}, cls=DjangoJSONEncoder,
        ))

    def _execute(self, api, actor, options):
        operation = options['operation']
        if operation == 'create':
            return api.create_project(actor, key=options['key'], name=options['name'])
        if operation == 'list':
            return api.list_projects(actor, limit=options['limit'], offset=options['offset'])
        if operation == 'show':
            return api.get_project(actor, options['project_id'])
        if operation == 'archive':
            return api.archive_project(actor, options['project_id'])
        return api.add_stage(
            actor, options['project_id'], key=options['key'], name=options['name'],
            selection=ScopeSelection(options['profile_id'], options['scope_id']),
        )
