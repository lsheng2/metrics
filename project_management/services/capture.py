from datetime import UTC, datetime

from bug_metrics.app.api.provider_connections import ConnectionError
from project_management.app.domain.capture_values import content_hash
from project_management.app.domain.captures import ArchiveError, CaptureIntent, MembershipInput, PartCoverage
from project_management.app.domain.contracts import ProjectError
from provider_sync.app.api.access import ArchivePageSink
from provider_sync.app.api.access_contracts import AccessError, validate_context


class ProjectCaptureService:
    def __init__(self, project_api, provider_access, archive, clock=None, *, required_parts=('facts', 'comments', 'history')):
        self.project_api = project_api
        self.provider_access = provider_access
        self.archive = archive
        self.clock = clock or (lambda: datetime.now(UTC))
        self.required_parts = required_parts

    def capture(self, context, *, cancel_requested=None):
        validate_context(context)
        self.project_api.get_project(context.actor, context.project_id)
        if context.deadline_at <= self.clock():
            raise AccessError('CAPTURE_DEADLINE_EXPIRED')
        with self.provider_access.open_capture(context, online=True, cancel_requested=cancel_requested) as lease:
            self.archive.bind_source_resolution(context.actor, context.project_id, context.stage_id, lease.resolved_scope)
            intent = CaptureIntent(
                context.project_id, context.stage_id, context.capture_id, context.request_id, lease.source_identity,
                content_hash({'context': context, 'resolution': lease.resolved_scope, 'required_parts': self.required_parts}),
                self.required_parts, context.deadline_at,
            )
            self.archive.prepare(context.actor, intent)
            membership = MembershipInput((), PartCoverage('partial', None, 0, None, 'CAPTURE_NOT_STARTED'), ())
            failure = None
            try:
                lease.attach_archive_sink(ArchivePageSink(intent, lambda page: self.archive.append_page(context.actor, intent, page)))
                observed = lease.enumerate()
                membership = MembershipInput(tuple(row.identity for row in observed.members),
                                             observed.coverage, observed.raw_page_ids)
                failure = observed.coverage.reason_code if observed.coverage.state != 'complete' else None
                if observed.coverage.state != 'complete':
                    failure = failure or 'PROVIDER_PAGE_INVALID'
                else:
                    failure = self._capture_details(context, intent, lease, observed)
                    if failure is None:
                        lease.verify_final()
            except (AccessError, ConnectionError, ProjectError, ArchiveError) as error:
                failure = error.code
            if failure is not None:
                return self.archive.finalize_partial(
                    context.actor, context.project_id, context.stage_id, context.capture_id,
                    failure_code=failure, membership=membership,
                )
            return self.archive.finalize(context.actor, intent, membership, complete=True)

    def _capture_details(self, context, intent, lease, membership):
        failure = 'CAPTURE_DETAILS_PENDING' if len(membership.members) > context.limits.max_details else None
        for marker in membership.members[:context.limits.max_details]:
            result = lease.capture_item(marker)
            if result.snapshot is not None:
                self.archive.append_snapshot(context.actor, intent, result.snapshot)
            complete = (result.snapshot is not None and result.snapshot.consistent
                        and all(getattr(result.coverage, part).state == 'complete' for part in self.required_parts))
            if not complete and failure is None:
                failure = next(iter(result.failures), 'PROVIDER_RESPONSE_INVALID')
        return failure
