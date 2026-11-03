from dataclasses import asdict, replace

from project_management.app.api.capture_archive import CaptureSourceIdentity
from provider_sync.app.api.access_contracts import AccessError
from provider_sync.app.spi.capture import ArchivePageSink
from provider_sync.services.capture_session import fingerprint


def same_members(left, right):
    def keys(observation):
        return sorted((row.identity.stable_id, row.identity.display_key, row.updated, row.fields_hash)
                      for row in observation.members)
    return keys(left) == keys(right)


class ProviderCaptureLease:
    def __init__(self, context, stage, connection, adapter, session, principal, resolved_scope):
        self.context = context
        self.stage = stage
        self.connection = connection
        self.adapter = adapter
        self.session = session
        self.principal = principal
        self.resolved_scope = resolved_scope
        self.membership = None
        self._closed = False
        self._attached = False
        self._detail_attempts = 0
        self._captured = set()
        self._final = False

    @property
    def usage(self):
        return self.session.usage

    @property
    def source_identity(self):
        info = self.connection.info
        return CaptureSourceIdentity(self.principal.provider_id, self.principal.endpoint_id,
                                     self.stage.descriptor.endpoint, self.principal.principal_id,
                                     info.credential.revision, self.stage.definition_hash)

    def attach_archive_sink(self, sink):
        self._require_open()
        if not isinstance(sink, ArchivePageSink) or sink.intent.source != self.source_identity:
            raise AccessError('CAPTURE_SINK_CONFLICT')
        self.session.attach_archive_sink(sink)
        self._attached = True
        self.principal = replace(self.principal, evidence_page_id=self.session.page_id('identity:1'))

    def enumerate(self):
        self._require_open()
        if self.membership is not None:
            raise AccessError('CAPTURE_PAGE_CONFLICT')
        self.membership = self.adapter.enumerate(self.stage.descriptor, self.principal, self.session)
        return self.membership

    def capture_item(self, marker):
        self._require_open()
        if not self._attached:
            raise AccessError('CAPTURE_SINK_CONFLICT')
        if self._final:
            raise AccessError('CAPTURE_CLOSED')
        if (self.membership is None or marker not in self.membership.members
                or marker.identity.provider_id != self.principal.provider_id
                or marker.identity.endpoint_id != self.principal.endpoint_id):
            raise AccessError('INVALID_ARGUMENTS')
        if marker.identity.stable_id in self._captured:
            raise AccessError('CAPTURE_PAGE_CONFLICT')
        if self._detail_attempts >= self.context.limits.max_details:
            raise AccessError('CAPTURE_DETAILS_PENDING')
        self._detail_attempts += 1
        self._captured.add(marker.identity.stable_id)
        return self.adapter.capture(marker, self.stage.descriptor, self.principal, self.session)

    def verify_final(self):
        self._require_open()
        if self.membership is None or self.membership.coverage.state != 'complete':
            raise AccessError('SOURCE_UNSTABLE')
        observed = self.adapter.enumerate(self.stage.descriptor, self.principal, self.session)
        if observed.coverage.state != 'complete' or not same_members(self.membership, observed):
            raise AccessError('SOURCE_UNSTABLE')
        definition = self.adapter.resolve(self.stage.descriptor, self.principal, self.session)
        if fingerprint(asdict(definition)) != fingerprint(asdict(self.resolved_scope)):
            raise AccessError('SOURCE_CHANGED')
        principal = self.adapter.verify(self.connection, self.session)
        if (principal.provider_id, principal.endpoint_id, principal.principal_id) != (
                self.principal.provider_id, self.principal.endpoint_id, self.principal.principal_id):
            raise AccessError('PRINCIPAL_CHANGED')
        self._final = True

    def close(self):
        if not self._closed:
            self._closed = True
            self.session.close()

    def _require_open(self):
        if self._closed:
            raise AccessError('CAPTURE_CLOSED')

    def __enter__(self):
        self._require_open()
        return self

    def __exit__(self, exc_type, error, traceback):
        self.close()
