from dataclasses import asdict, replace
from datetime import UTC, datetime
import json
import sys
import uuid

from django.core.management.base import BaseCommand, CommandParser
from django.core.serializers.json import DjangoJSONEncoder

from bug_metrics.app.api.provider_connections import ConnectionError
from project_management.app.api import ProjectActor, ProjectError
from project_management.app.api.capture_archive import ArchiveError
from provider_sync.app.api.access_contracts import AccessContext, AccessError
from provider_sync.app.api.access_factory import capture_limits_from_settings, create_provider_access_service


def envelope(result=None, error=None):
    return json.dumps({'schema_version': 1, 'result': result, 'error': error},
                      cls=DjangoJSONEncoder, sort_keys=True, allow_nan=False)


def invalid_arguments():
    return {'code': 'INVALID_ARGUMENTS', 'message': str(AccessError('INVALID_ARGUMENTS'))}


class JsonArgumentParser(CommandParser):
    def error(self, message):
        print(envelope(error=invalid_arguments()), file=sys.stderr)
        raise SystemExit(2)


class Command(BaseCommand):
    help = 'Inspect provider profiles, frozen scopes and retained work items.'
    requires_system_checks = []

    def create_parser(self, prog_name, subcommand, **kwargs):
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.error = self._argument_error
        return parser

    def _argument_error(self, message):
        self.stderr.write(envelope(error=invalid_arguments()))
        raise SystemExit(2)

    def add_arguments(self, parser):
        commands = parser.add_subparsers(dest='action', required=True, parser_class=JsonArgumentParser)
        commands.add_parser('profiles').add_argument('--provider-id', choices=('jira', 'hsdes'))
        commands.add_parser('status').add_argument('--profile-id', required=True)
        for name in ('scope', 'verify', 'item'):
            command = commands.add_parser(name)
            command.add_argument('--project-id', required=True)
            command.add_argument('--stage-id', required=True)
            if name == 'item':
                command.add_argument('--capture-id', required=True)
                command.add_argument('--item-id', required=True)
            else:
                command.add_argument('--online', action='store_true')
                command.add_argument('--deadline-at')
                for limit in ('requests', 'download-bytes', 'members'):
                    command.add_argument('--max-' + limit, type=int)
        for name in ('capture', 'operation'):
            command = commands.add_parser(name)
            command.add_argument('--project-id')
            command.add_argument('--stage-id')
            command.add_argument('--operation-id')

    def handle(self, *args, **options):
        try:
            self.stdout.write(envelope(self._dispatch(options)))
        except (AccessError, ProjectError, ArchiveError, ConnectionError) as error:
            self.stderr.write(envelope(error={'code': error.code, 'message': str(error)}))
            raise SystemExit(1) from None
        except Exception:
            self.stderr.write(envelope(error={'code': 'INTERNAL_ERROR', 'message': 'Provider access failed.'}))
            raise SystemExit(1) from None

    def _dispatch(self, options):
        action = options['action']
        if action in {'capture', 'operation'} or (action == 'verify' and not options['online']):
            raise AccessError('CAPABILITY_UNAVAILABLE')
        context = self._context(options) if options.get('online') else None
        service = create_provider_access_service()
        if action == 'profiles':
            return [asdict(profile) for profile in service.profiles(provider_id=options.get('provider_id'))]
        if action == 'status':
            return asdict(service.status(options['profile_id']))
        actor = ProjectActor('local_operator')
        if action == 'item':
            return asdict(service.read_item(actor, options['project_id'], options['stage_id'],
                                           options['capture_id'], options['item_id']))
        if context is None:
            if options.get('deadline_at') or any(options.get(key) is not None for key in (
                    'max_requests', 'max_download_bytes', 'max_members')):
                raise AccessError('INVALID_ARGUMENTS')
            return asdict(service.scope(actor, options['project_id'], options['stage_id']))
        with service.open_capture(context, online=True) as lease:
            result = {'principal': asdict(lease.principal), 'archived': False}
            if action == 'scope':
                observation = lease.enumerate()
                result['membership'] = asdict(observation)
                if observation.coverage.state == 'complete':
                    lease.verify_final()
            result['usage'] = asdict(lease.usage)
            return result

    def _context(self, options):
        try:
            deadline = datetime.fromisoformat(options['deadline_at'].replace('Z', '+00:00'))
            if deadline.tzinfo is None or deadline.utcoffset() is None or deadline.utcoffset().total_seconds() != 0:
                raise ValueError
        except (AttributeError, TypeError, ValueError):
            raise AccessError('INVALID_ARGUMENTS') from None
        limits = capture_limits_from_settings()
        overrides = {}
        for key in ('max_requests', 'max_download_bytes', 'max_members'):
            value = options.get(key)
            if value is not None:
                if value <= 0 or value > getattr(limits, key):
                    raise AccessError('INVALID_ARGUMENTS')
                overrides[key] = value
        return AccessContext(ProjectActor('local_operator'), options['project_id'], options['stage_id'],
                             str(uuid.uuid4()), str(uuid.uuid4()), deadline.astimezone(UTC), replace(limits, **overrides))
