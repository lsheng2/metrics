from typing import List

from tasks.app.domain.model.task import Task
from ui_web.data.task_data import TaskData
from ui_web.tests.fixtures.ui_web_builders import DomainTaskBuilder, TaskDataBuilder


class BusinessScenarios:
    """
    Business-focused test scenarios that represent real stakeholder concerns.

    Each scenario provides:
    - Realistic business context for stakeholders (PMs, Scrum Masters, Developers)
    - Test data that reflects actual work patterns and team dynamics
    - Scenarios that inform business decisions about capacity, performance, and health
    """

    @staticmethod
    def critical_production_incident_response() -> List[TaskData]:
        """
        Scenario: Critical production bug requiring immediate team response

        Business Context: High-priority incident affecting customer experience
        Stakeholder Value: Helps identify response time and resource allocation for incidents
        Decision Impact: Informs escalation policies and incident response team capacity
        """
        return [
            TaskDataBuilder.sprint_dashboard_task()
                .with_story_points(8.0)
                .assigned_to_backend_team_junior()
                .with_time_spent_days(2.0)
                .in_development_stage()
                .with_red_health_forecast()
                .with_original_status("In Progress")
                .build(),

            TaskDataBuilder.health_monitoring_task()
                .with_story_points(5.0)
                .assigned_to_devops_team_lead()
                .with_time_spent_days(1.5)
                .in_qa_stage()
                .with_yellow_health_forecast()
                .with_original_status("Testing")
                .build()
        ]

    @staticmethod
    def successful_sprint_completion() -> List[TaskData]:
        """
        Scenario: Successful sprint with all tasks completed on schedule

        Business Context: Team delivering on commitments for stakeholder confidence
        Stakeholder Value: Demonstrates team reliability and predictable delivery capacity
        Decision Impact: Supports sprint planning accuracy and velocity forecasting
        """
        return [
            TaskDataBuilder.sprint_dashboard_task()
                .with_story_points(5.0)
                .assigned_to_frontend_team_senior()
                .with_time_spent_days(2.0)
                .in_done_stage()
                .with_green_health_forecast()
                .with_original_status("Done")
                .build(),

            TaskDataBuilder.team_velocity_task()
                .with_story_points(3.0)
                .assigned_to_backend_team_junior()
                .with_time_spent_days(1.5)
                .in_done_stage()
                .with_green_health_forecast()
                .with_original_status("Done")
                .build()
        ]

    @staticmethod
    def capacity_planning_scenario() -> List[TaskData]:
        """
        Scenario: Mixed workload requiring capacity planning decisions
        Business Context: Product manager needs to allocate resources effectively
        """
        return [
            TaskDataBuilder.capacity_planning_epic()
                .with_story_points(13.0)
                .assigned_to_frontend_team_senior()
                .with_time_spent_days(8.0)
                .in_development_stage()
                .with_yellow_health_forecast()
                .build(),

            TaskDataBuilder.retrospective_analysis_task()
                .with_story_points(2.0)
                .assigned_to_backend_team_junior()
                .with_time_spent_days(1.0)
                .in_qa_stage()
                .with_green_health_forecast()
                .build(),

            TaskDataBuilder.health_monitoring_task()
                .with_story_points(5.0)
                .with_no_assignee()  # Unassigned - needs capacity allocation
                .with_time_spent_days(0.0)
                .with_stage("backlog")
                .with_original_status("To Do")
                .build()
        ]

    @staticmethod
    def one_on_one_performance_review() -> List[TaskData]:
        """
        Scenario: Individual developer performance data for one-on-one reviews
        Business Context: Manager preparing for performance discussions
        """
        return [
            TaskDataBuilder.sprint_dashboard_task()
                .with_story_points(8.0)
                .assigned_to("alice.senior.developer")
                .with_time_spent_days(3.0)  # Efficient completion
                .in_done_stage()
                .with_green_health_forecast()
                .build(),

            TaskDataBuilder.team_velocity_task()
                .with_story_points(5.0)
                .assigned_to("alice.senior.developer")
                .with_time_spent_days(2.5)  # Good velocity
                .in_done_stage()
                .with_green_health_forecast()
                .build(),

            TaskDataBuilder.retrospective_analysis_task()
                .with_story_points(3.0)
                .assigned_to("alice.senior.developer")
                .with_time_spent_days(1.5)  # Consistent performance
                .in_done_stage()
                .with_green_health_forecast()
                .build()
        ]

    @staticmethod
    def technical_debt_prioritization() -> List[TaskData]:
        """
        Scenario: Technical debt tasks competing with feature development
        Business Context: Engineering manager balancing debt vs features
        """
        return [
            TaskDataBuilder.retrospective_analysis_task()
                .with_story_points(8.0)
                .assigned_to_backend_team_junior()
                .with_time_spent_days(5.0)  # High effort, important refactoring
                .in_development_stage()
                .with_yellow_health_forecast()
                .with_original_status("In Progress")
                .build(),

            TaskDataBuilder("TECH-DEBT-001", "Upgrade legacy authentication system")
                .with_story_points(13.0)
                .assigned_to_devops_team_lead()
                .with_time_spent_days(10.0)  # Significant technical debt
                .in_qa_stage()
                .with_red_health_forecast()
                .with_original_status("Testing")
                .build()
        ]

    @staticmethod
    def cross_team_collaboration_epic() -> List[TaskData]:
        """
        Scenario: Epic requiring coordination across multiple teams
        Business Context: Product owner tracking cross-functional delivery
        """
        return [
            TaskDataBuilder("EPIC-COLLAB-001", "Multi-tenant Architecture Implementation")
                .with_story_points(21.0)
                .assigned_to_backend_team_junior()
                .with_time_spent_days(12.0)
                .in_development_stage()
                .with_yellow_health_forecast()
                .build(),

            TaskDataBuilder("EPIC-COLLAB-002", "Frontend Multi-tenant UI Components")
                .with_story_points(13.0)
                .assigned_to_frontend_team_senior()
                .with_time_spent_days(8.0)
                .in_development_stage()
                .with_green_health_forecast()
                .build(),

            TaskDataBuilder("EPIC-COLLAB-003", "DevOps Multi-tenant Deployment Pipeline")
                .with_story_points(8.0)
                .assigned_to_devops_team_lead()
                .with_time_spent_days(4.0)
                .in_qa_stage()
                .with_green_health_forecast()
                .build()
        ]

    @staticmethod
    def new_team_member_onboarding() -> List[TaskData]:
        """
        Scenario: Onboarding tasks for new team member evaluation
        Business Context: Team lead assessing onboarding progress and support needs
        """
        return [
            TaskDataBuilder("ONBOARD-001", "Set up development environment")
                .with_story_points(2.0)
                .assigned_to("junior.new.developer")
                .with_time_spent_days(1.0)
                .in_done_stage()
                .with_green_health_forecast()
                .build(),

            TaskDataBuilder("ONBOARD-002", "First code contribution - bug fix")
                .with_story_points(3.0)
                .assigned_to("junior.new.developer")
                .with_time_spent_days(2.5)  # Slower pace expected
                .in_qa_stage()
                .with_yellow_health_forecast()
                .build(),

            TaskDataBuilder("ONBOARD-003", "Code review learning task")
                .with_story_points(1.0)
                .assigned_to("junior.new.developer")
                .with_time_spent_days(0.5)
                .in_development_stage()
                .with_green_health_forecast()
                .build()
        ]

    @staticmethod
    def sprint_dashboard_tasks() -> List[TaskData]:
        return [
            TaskDataBuilder.sprint_dashboard_task()
                .with_story_points(5.0)
                .assigned_to_frontend_team_senior()
                .with_time_spent_days(1.5)
                .in_development_stage()
                .with_green_health_forecast()
                .build(),

            TaskDataBuilder.team_velocity_task()
                .with_story_points(8.0)
                .assigned_to_backend_team_junior()
                .with_time_spent_days(3.0)
                .in_qa_stage()
                .with_yellow_health_forecast()
                .build(),

            TaskDataBuilder.health_monitoring_task()
                .with_story_points(3.0)
                .assigned_to_devops_team_lead()
                .with_time_spent_days(0.5)
                .in_development_stage()
                .with_green_health_forecast()
                .build()
        ]

    @staticmethod
    def team_capacity_analysis_tasks() -> List[TaskData]:
        return [
            TaskDataBuilder.capacity_planning_epic()
                .with_story_points(10.0)
                .assigned_to_frontend_team_senior()
                .with_time_spent_days(5.0)
                .in_done_stage()
                .with_green_health_forecast()
                .build(),

            TaskDataBuilder.retrospective_analysis_task()
                .with_story_points(2.0)
                .assigned_to_backend_team_junior()
                .with_time_spent_days(4.0)
                .in_qa_stage()
                .with_red_health_forecast()
                .build()
        ]

    @staticmethod
    def mixed_member_group_tasks() -> List[TaskData]:
        return [
            TaskDataBuilder.sprint_dashboard_task()
                .assigned_to_frontend_team_senior()
                .in_development_stage()
                .with_green_health_forecast()
                .build(),

            TaskDataBuilder.team_velocity_task()
                .assigned_to_backend_team_junior()
                .in_qa_stage()
                .with_yellow_health_forecast()
                .build(),

            TaskDataBuilder.health_monitoring_task()
                .assigned_to_devops_team_lead()
                .in_development_stage()
                .with_green_health_forecast()
                .build()
        ]

    @staticmethod
    def mixed_stage_tasks() -> List[TaskData]:
        return [
            TaskDataBuilder.sprint_dashboard_task()
                .assigned_to_frontend_team_senior()
                .in_development_stage()
                .with_green_health_forecast()
                .build(),

            TaskDataBuilder.team_velocity_task()
                .assigned_to_frontend_team_senior()
                .in_qa_stage()
                .with_yellow_health_forecast()
                .build(),

            TaskDataBuilder.health_monitoring_task()
                .assigned_to_frontend_team_senior()
                .in_done_stage()
                .with_green_health_forecast()
                .build()
        ]

    @staticmethod
    def tasks_for_sorting_by_spent_time() -> List[TaskData]:
        return [
            TaskDataBuilder.sprint_dashboard_task().with_time_spent_days(1.0).build(),
            TaskDataBuilder.team_velocity_task().with_time_spent_days(5.0).build(),
            TaskDataBuilder.health_monitoring_task().with_time_spent_days(3.0).build()
        ]

    @staticmethod
    def unassigned_tasks() -> List[TaskData]:
        return [
            TaskDataBuilder.sprint_dashboard_task().with_no_assignee().build(),
            TaskDataBuilder.team_velocity_task().with_no_assignee().build()
        ]

    @staticmethod
    def hierarchical_epic_with_children() -> TaskData:
        child1 = (TaskDataBuilder("PROJ-002", "Epic Child 1")
                  .with_story_points(3.0)
                  .assigned_to_frontend_team_senior()
                  .in_development_stage()
                  .build())

        child2 = (TaskDataBuilder("PROJ-003", "Epic Child 2")
                  .with_story_points(5.0)
                  .assigned_to_backend_team_junior()
                  .in_qa_stage()
                  .build())

        return (TaskDataBuilder.capacity_planning_epic()
                .with_story_points(10.0)
                .assigned_to_devops_team_lead()
                .with_child_tasks(child1, child2)
                .in_development_stage()
                .build())

    @staticmethod
    def active_sprint_tasks() -> List[Task]:
        return [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .with_story_points(5.0)
                .assigned_to("alice.johnson")
                .with_time_spent_hours(16.0)
                .with_stage("development")
                .build(),

            DomainTaskBuilder.domain_task_for_ui_conversion()
                .with_story_points(8.0)
                .assigned_to("bob.smith")
                .with_time_spent_hours(12.0)
                .with_stage("qa")
                .build(),

            DomainTaskBuilder.domain_task_for_ui_conversion()
                .with_story_points(3.0)
                .assigned_to("charlie.brown")
                .with_time_spent_hours(8.0)
                .with_stage("development")
                .build()
        ]

    @staticmethod
    def recently_completed_tasks() -> List[Task]:
        return [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .with_story_points(3.0)
                .assigned_to("charlie.brown")
                .with_time_spent_hours(32.0)
                .with_stage("done")
                .build(),

            DomainTaskBuilder.domain_task_for_ui_conversion()
                .with_story_points(2.0)
                .assigned_to("alice.johnson")
                .with_time_spent_hours(8.0)
                .with_stage("done")
                .build()
        ]
