from dataclasses import asdict
from datetime import UTC, datetime

from bug_metrics.app.api.provider_connections import ConnectionError, source_endpoint_matches
from project_management.app.api import ProjectError
from project_management.app.api.capture_archive import SourceChainKey
from provider_sync.app.api.access_contracts import AccessError, AccessStatus, FrozenScopeStatus, PublicProfile, validate_context
from provider_sync.out.capture_reader import BoundCaptureReader
from provider_sync.services.capture_lease import ProviderCaptureLease
from provider_sync.services.capture_session import CaptureSession, fingerprint
from provider_sync.app.spi.capture import ArchivePageSink


class ProviderAccessService:
    def __init__(self, project_api, connection_resolver, adapter_registry, archive, *, clock=None,
                 reader_factory=BoundCaptureReader, profile_registry=None):
        self.project_api = project_api
        self.connection_resolver = connection_resolver
        self.adapter_registry = adapter_registry
        self.archive = archive
        self.clock = clock or (lambda: datetime.now(UTC))
        self.reader_factory = reader_factory
        self.profile_registry = profile_registry

    def profiles(self, *, provider_id=None):
        if self.profile_registry is None:
            raise AccessError('CAPABILITY_UNAVAILABLE')
        return tuple(PublicProfile(p.profile_id, p.provider_id, p.display_name, p.enabled)
                     for p in self.profile_registry.list_profiles(include_disabled=True)
                     if provider_id is None or p.provider_id == provider_id)

    def status(self, profile_id):
        try:
            info = self.connection_resolver.describe_profile(profile_id)
        except ConnectionError as error:
            return AccessStatus(profile_id, '', 'blocked', False, (error.code,))
        blockers = () if info.endpoint.provider_id in self.adapter_registry else ('PART_CONTRACT_UNQUALIFIED',)
        return AccessStatus(profile_id, info.endpoint.provider_id, 'configured' if not blockers else 'blocked',
                            False, blockers)

    def scope(self, actor, project_id, stage_id):
        _, stage = self._stage(actor, project_id, stage_id)
        resolution = self.archive.read_source_resolution(actor, project_id, stage_id) if self.archive else None
        return FrozenScopeStatus(project_id, stage_id, stage.definition_hash,
                                 stage.source_status, stage.descriptor,
                                 fingerprint(asdict(resolution)) if resolution else None,
                                 resolution.principal_id if resolution else None)

    def open_capture(self, context, *, online=False, cancel_requested=None):
        if online is not True:
            raise AccessError('CAPABILITY_UNAVAILABLE')
        validate_context(context)
        _, stage = self._writable_stage(context)
        if context.deadline_at <= self.clock():
            raise AccessError('CAPTURE_DEADLINE_EXPIRED')
        self._cancel_if_requested(cancel_requested)
        adapter = self.adapter_registry.get(stage.descriptor.provider_id)
        if adapter is None:
            raise AccessError('PART_CONTRACT_UNQUALIFIED')
        known = self.archive.read_source_resolution(context.actor, context.project_id, context.stage_id) if self.archive else None
        info = self.connection_resolver.describe_profile(stage.descriptor.profile_id,
                                                        expected_provider_id=stage.descriptor.provider_id)
        if not source_endpoint_matches(info, stage.descriptor.endpoint):
            raise AccessError('PROVIDER_ENDPOINT_INVALID')
        connection = self.connection_resolver.resolve_profile(stage.descriptor.profile_id,
                                                             expected_provider_id=stage.descriptor.provider_id)
        if connection.info.endpoint != info.endpoint:
            raise AccessError('PROVIDER_ENDPOINT_INVALID')
        reader = connection.open_capture_reader(self.reader_factory)
        session = CaptureSession(context, reader, timeout_seconds=info.endpoint.timeout_seconds,
                                 authorize=lambda: self._authorize_capture(context, cancel_requested),
                                 clock=self.clock)
        try:
            principal = adapter.verify(connection, session)
            resolution = adapter.resolve(stage.descriptor, principal, session)
            if known is not None and known != resolution:
                raise ProjectError('SOURCE_CHANGED')
            return ProviderCaptureLease(context, stage, connection, adapter, session, principal, resolution)
        except BaseException:
            session.close()
            raise

    def verify(self, context, *, online=False):
        with self.open_capture(context, online=online) as lease:
            return lease.principal

    def enumerate(self, lease):
        return lease.enumerate()

    def capture_item(self, lease, marker):
        return lease.capture_item(marker)

    def read_item(self, actor, project_id, stage_id, capture_id, source_key):
        self._stage(actor, project_id, stage_id)
        if self.archive is None:
            raise AccessError('CAPABILITY_UNAVAILABLE')
        if isinstance(source_key, str):
            manifest = self.archive.read_capture(actor, project_id, stage_id, capture_id)
            matched = next((row for row in manifest.snapshots if row.identity.stable_id == source_key), None)
            if matched is None:
                raise AccessError('CAPABILITY_UNAVAILABLE')
            source_key = SourceChainKey(matched.identity.provider_id, matched.identity.endpoint_id,
                                       matched.identity.stable_id, manifest.intent.source.principal_id,
                                       manifest.intent.source.rule_hash)
        return self.archive.read_snapshot(actor, project_id, stage_id, capture_id, source_key)

    def _stage(self, actor, project_id, stage_id):
        detail = self.project_api.get_project(actor, project_id)
        for stage in detail.stages:
            if stage.id == stage_id:
                return detail.project, stage
        raise ProjectError('PROJECT_NOT_FOUND')

    def _writable_stage(self, context):
        project, stage = self._stage(context.actor, context.project_id, context.stage_id)
        if project.archived:
            raise ProjectError('PROJECT_ARCHIVED')
        if stage.source_status != 'current':
            raise ProjectError('SOURCE_UNAVAILABLE' if stage.source_status == 'unavailable' else 'SOURCE_CHANGED')
        return project, stage

    def _authorize_capture(self, context, cancel_requested):
        self._cancel_if_requested(cancel_requested)
        return self._writable_stage(context)

    def _cancel_if_requested(self, cancel_requested):
        if cancel_requested is not None and cancel_requested():
            raise AccessError('CAPTURE_CANCELED')
