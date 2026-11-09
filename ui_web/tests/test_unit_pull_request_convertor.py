import unittest
from typing import List, Optional

from pull_requests.app.domain.model.pull_request import (
    Author, GatewayBlocker, GatewayResult, GatewayState, PullRequest, ReviewState
)
from tasks.app.domain.model.task import Assignment, Release, SystemMetadata, Task, TimeTracking
from ui_web.convertors.pull_request_convertor import PullRequestConvertor


def pull_request_with_gateway(gateway: GatewayResult) -> PullRequest:
    return PullRequest(
        id="1", title="Improve checkout", author=Author(id="a", display_name="Author"),
        status="active", review=ReviewState(gateway=gateway)
    )


def pull_request_linked_to(task_id: str) -> PullRequest:
    return PullRequest(
        id="1", title="Improve checkout", author=Author(id="a", display_name="Author"),
        status="active", linked_task_id=task_id
    )


def task_with_status(task_id: str, original_status: str, iteration: Optional[str] = None,
                      releases: Optional[List[Release]] = None) -> Task:
    return Task(
        id=task_id, title="Speed up checkout",
        system_metadata=SystemMetadata(original_status=original_status, project_key="PROJ",
                                        url=f"https://tracker.example.com/{task_id}"),
        assignment=Assignment(), time_tracking=TimeTracking(),
        iteration=iteration, releases=releases
    )


class TestGatewayDisplay(unittest.TestCase):

    def test_shouldShowSingleGreenReadyChipWhenGatewayIsReady(self):
        # given
        pull_request = pull_request_with_gateway(GatewayResult(state=GatewayState.READY))

        # when
        policies = PullRequestConvertor().convert_review_details(pull_request).policies

        # then
        self.assertEqual([("Ready", "is-success")], [(policy.name, policy.css_class) for policy in policies])

    def test_shouldShowOneRedChipPerBlockerWhenGatewayIsBlocked(self):
        # given
        pull_request = pull_request_with_gateway(GatewayResult(
            state=GatewayState.BLOCKED,
            blockers=[GatewayBlocker.CI, GatewayBlocker.CHANGES_REQUESTED]
        ))

        # when
        policies = PullRequestConvertor().convert_review_details(pull_request).policies

        # then
        self.assertEqual(["CI", "Changes requested"], [policy.name for policy in policies])

    def test_shouldMarkBlockerChipsAsDangerWhenGatewayIsBlocked(self):
        # given
        pull_request = pull_request_with_gateway(GatewayResult(state=GatewayState.BLOCKED, blockers=[GatewayBlocker.CI]))

        # when
        policies = PullRequestConvertor().convert_review_details(pull_request).policies

        # then
        self.assertEqual("is-danger", policies[0].css_class)

    def test_shouldShowMutedInReviewChipWhenGatewayIsInReview(self):
        # given
        pull_request = pull_request_with_gateway(GatewayResult(state=GatewayState.IN_REVIEW))

        # when
        policies = PullRequestConvertor().convert_review_details(pull_request).policies

        # then
        self.assertEqual([("In review", "")], [(policy.name, policy.css_class) for policy in policies])

    def test_shouldShowNoPolicyChipsWhenGatewayIsUnknown(self):
        # given
        pull_request = pull_request_with_gateway(None)

        # when
        policies = PullRequestConvertor().convert_review_details(pull_request).policies

        # then
        self.assertEqual([], policies)


class TestLinkedTaskDisplay(unittest.TestCase):

    def test_shouldShowTicketTrackerStatusWhenTaskIsLinked(self):
        # given
        pull_request = pull_request_linked_to("PROJ-42")
        linked_task = task_with_status("PROJ-42", "Code Review")

        # when
        linked_task_data = PullRequestConvertor().convert_to_data(pull_request, linked_task).linked_task

        # then
        self.assertEqual("Code Review", linked_task_data.status)

    def test_shouldShowNoTrackerStatusWhenLinkedTicketCannotBeResolved(self):
        # given
        pull_request = pull_request_linked_to("PROJ-42")

        # when
        linked_task_data = PullRequestConvertor().convert_to_data(pull_request, None).linked_task

        # then
        self.assertIsNone(linked_task_data.status)

    def test_shouldShowIterationAndReleasesWhenLinkedTaskHasThem(self):
        # given
        pull_request = pull_request_linked_to("PROJ-42")
        linked_task = task_with_status("PROJ-42", "Code Review", iteration="Sprint 12",
                                        releases=[Release(id="rel-1", name="2026.015")])

        # when
        linked_task_data = PullRequestConvertor().convert_to_data(pull_request, linked_task).linked_task

        # then
        self.assertEqual("Sprint 12", linked_task_data.iteration)
        self.assertEqual([("rel-1", "2026.015")], [(r.id, r.name) for r in linked_task_data.releases])

    def test_shouldShowNoIterationOrReleasesWhenLinkedTicketCannotBeResolved(self):
        # given
        pull_request = pull_request_linked_to("PROJ-42")

        # when
        linked_task_data = PullRequestConvertor().convert_to_data(pull_request, None).linked_task

        # then
        self.assertIsNone(linked_task_data.iteration)
        self.assertIsNone(linked_task_data.releases)


if __name__ == '__main__':
    unittest.main()
