from typing import List, Optional

from pull_requests.app.domain.model.pull_request import (
    Approval, ApprovalVote, GatewayResult, GatewayState, PullRequest
)
from tasks.app.domain.model.task import Task
from ..data.pull_request_data import ApprovalData, LinkedTaskData, PolicyResultData, PullRequestData
from .task_convertor import to_release_data_list

_STALE_APPROVAL_STATE = "stale_approved"


class PullRequestConvertor:

    def convert_to_data(self, pull_request: PullRequest, linked_task: Optional[Task]) -> PullRequestData:
        return PullRequestData(
            id=pull_request.id,
            title=pull_request.title,
            author_name=pull_request.author.display_name,
            status=pull_request.status,
            internal_gate=pull_request.review.internal_gate_met,
            url=pull_request.url,
            repository=pull_request.repository,
            repository_id=pull_request.repository_id,
            project_id=pull_request.project_id,
            project_name=pull_request.project_name,
            is_draft=pull_request.is_draft,
            approvals=self._convert_visible_approvals(pull_request.review.approvals),
            linked_task=self._convert_linked_task(pull_request.linked_task_id, linked_task)
        )

    def convert_review_details(self, pull_request: PullRequest) -> PullRequestData:
        review = pull_request.review
        approvals = self._convert_visible_approvals(review.approvals)
        approvals += [self._convert_reset_approval(approval) for approval in review.reset_approvals]
        return PullRequestData(
            id=pull_request.id,
            approvals=approvals,
            policies=self._convert_gateway(review.gateway)
        )

    def _convert_gateway(self, gateway: Optional[GatewayResult]) -> List[PolicyResultData]:
        if gateway is None:
            return []
        if gateway.state is GatewayState.BLOCKED:
            return [self._blocker_tag(blocker.value) for blocker in gateway.blockers]
        if gateway.state is GatewayState.READY:
            return [self._ready_tag()]
        return [self._in_review_tag()]

    @staticmethod
    def _ready_tag() -> PolicyResultData:
        return PolicyResultData(name="Ready", status="ready", css_class="is-success", icon="iconoir-check")

    @staticmethod
    def _in_review_tag() -> PolicyResultData:
        return PolicyResultData(name="In review", status="in_review", css_class="", icon="iconoir-clock")

    @staticmethod
    def _blocker_tag(name: str) -> PolicyResultData:
        return PolicyResultData(name=name, status="blocked", css_class="is-danger", icon="iconoir-xmark")

    @staticmethod
    def _convert_reset_approval(approval: Approval) -> ApprovalData:
        return ApprovalData(
            display_name=approval.reviewer.display_name,
            state=_STALE_APPROVAL_STATE,
            tier=approval.reviewer.tier.value,
            is_approval=False
        )

    @staticmethod
    def _convert_visible_approvals(approvals: List[Approval]) -> List[ApprovalData]:
        visible_approvals = []
        for approval in approvals:
            if approval.vote is ApprovalVote.NO_VOTE:
                continue
            visible_approvals.append(ApprovalData(
                display_name=approval.reviewer.display_name,
                state=approval.vote.value,
                tier=approval.reviewer.tier.value,
                is_approval=approval.vote.is_positive
            ))
        return visible_approvals

    @staticmethod
    def _convert_linked_task(linked_task_id: Optional[str], linked_task: Optional[Task]) -> Optional[LinkedTaskData]:
        if not linked_task_id:
            return None
        if linked_task:
            return LinkedTaskData(
                id=linked_task.id,
                url=linked_task.system_metadata.url if linked_task.system_metadata else None,
                status=linked_task.system_metadata.original_status if linked_task.system_metadata else None,
                iteration=linked_task.iteration,
                releases=to_release_data_list(linked_task.releases)
            )
        return LinkedTaskData(id=linked_task_id)
