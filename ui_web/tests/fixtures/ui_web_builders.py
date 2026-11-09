from datetime import datetime
from typing import List, Optional

from sd_metrics_lib.utils.enums import HealthStatus
from sd_metrics_lib.utils.time import Duration, TimeUnit

from tasks.app.domain.model.config import SortingConfig
from tasks.app.domain.model.task import Task, Assignment, Assignee, TimeTracking, SystemMetadata, TaskStatus, MemberGroup
from ui_web.data.task_data import TaskData, AssignmentData, AssigneeData, TimeTrackingData, SystemMetadataData, ForecastData
from ui_web.data.member_data import MemberGroupData


class TaskDataBuilder:
    
    def __init__(self, task_id: str, title: str):
        self._id = task_id
        self._title = title
        self._story_points: Optional[float] = None
        self._priority: Optional[int] = None
        self._assignee_data: Optional[AssigneeData] = None
        self._member_group_data: Optional[MemberGroupData] = None
        self._total_spent_time_days: Optional[float] = None
        self._current_assignee_spent_time_days: Optional[float] = None
        self._stage: Optional[str] = None
        self._original_status = "To Do"
        self._url: Optional[str] = None
        self._child_tasks: List[TaskData] = []
        self._child_tasks_count = 0
        self._forecast_data: Optional[ForecastData] = None
        self._custom_sort_fields: dict = {}
    
    @classmethod
    def sprint_dashboard_task(cls) -> 'TaskDataBuilder':
        return cls("PROJ-123", "Implement user authentication dashboard")
    
    @classmethod
    def team_velocity_task(cls) -> 'TaskDataBuilder':
        return cls("PROJ-456", "Optimize database queries for reporting")
    
    @classmethod
    def capacity_planning_epic(cls) -> 'TaskDataBuilder':
        return cls("PROJ-001", "Customer Management Epic")
    
    @classmethod
    def retrospective_analysis_task(cls) -> 'TaskDataBuilder':
        return cls("PROJ-789", "Refactor legacy authentication system")
    
    @classmethod
    def health_monitoring_task(cls) -> 'TaskDataBuilder':
        return cls("PROJ-321", "Set up application monitoring")
    
    def with_story_points(self, points: float) -> 'TaskDataBuilder':
        self._story_points = points
        return self

    def with_priority(self, priority: int) -> 'TaskDataBuilder':
        self._priority = priority
        return self

    def assigned_to(self, assignee_id: str) -> 'TaskDataBuilder':
        self._assignee_data = AssigneeData(
            id=assignee_id,
            display_name=f"{assignee_id} (Developer)",
            avatar_url=f"https://company.com/avatars/{assignee_id}.jpg"
        )
        return self
    
    def assigned_to_frontend_team_senior(self) -> 'TaskDataBuilder':
        self._assignee_data = AssigneeData(
            id="alice.frontend",
            display_name="Alice Johnson (Senior Frontend Developer)",
            avatar_url="https://company.com/avatars/alice.jpg"
        )
        self._member_group_data = MemberGroupData(
            id="frontend-team",
            name="Frontend Development Team"
        )
        return self
    
    def assigned_to_backend_team_junior(self) -> 'TaskDataBuilder':
        self._assignee_data = AssigneeData(
            id="bob.backend",
            display_name="Bob Smith (Junior Backend Developer)",
            avatar_url="https://company.com/avatars/bob.jpg"
        )
        self._member_group_data = MemberGroupData(
            id="backend-team",
            name="Backend Development Team"
        )
        return self
    
    def assigned_to_devops_team_lead(self) -> 'TaskDataBuilder':
        self._assignee_data = AssigneeData(
            id="charlie.devops",
            display_name="Charlie Wilson (DevOps Team Lead)",
            avatar_url="https://company.com/avatars/charlie.jpg"
        )
        self._member_group_data = MemberGroupData(
            id="devops-team",
            name="DevOps Team"
        )
        return self
    
    def with_no_assignee(self) -> 'TaskDataBuilder':
        self._assignee_data = None
        self._member_group_data = None
        return self
    
    def with_time_spent_days(self, days: float) -> 'TaskDataBuilder':
        self._total_spent_time_days = days
        self._current_assignee_spent_time_days = days
        return self
    
    def with_stage(self, stage: str) -> 'TaskDataBuilder':
        self._stage = stage
        return self
    
    def in_development_stage(self) -> 'TaskDataBuilder':
        return self.with_stage("development")
    
    def in_qa_stage(self) -> 'TaskDataBuilder':
        return self.with_stage("qa")
    
    def in_done_stage(self) -> 'TaskDataBuilder':
        return self.with_stage("done")
    
    def with_green_health_forecast(self) -> 'TaskDataBuilder':
        self._forecast_data = ForecastData(
            health_status=HealthStatus.GREEN,
            estimation_time_days=2.5,
            start_date=datetime.now().isoformat(),
            velocity=8.5
        )
        return self
    
    def with_yellow_health_forecast(self) -> 'TaskDataBuilder':
        self._forecast_data = ForecastData(
            health_status=HealthStatus.YELLOW,
            estimation_time_days=5.0,
            start_date=datetime.now().isoformat(),
            velocity=6.2
        )
        return self
    
    def with_red_health_forecast(self) -> 'TaskDataBuilder':
        self._forecast_data = ForecastData(
            health_status=HealthStatus.RED,
            estimation_time_days=10.0,
            start_date=datetime.now().isoformat(),
            velocity=3.1
        )
        return self
    
    def with_child_tasks(self, *child_tasks: TaskData) -> 'TaskDataBuilder':
        self._child_tasks = list(child_tasks)
        self._child_tasks_count = len(child_tasks)
        return self
    
    def with_original_status(self, status: str) -> 'TaskDataBuilder':
        self._original_status = status
        return self
    
    def with_url(self, url: str) -> 'TaskDataBuilder':
        self._url = url
        return self

    def with_custom_sort_field(self, field_name: str, value: str) -> 'TaskDataBuilder':
        self._custom_sort_fields[field_name] = value
        return self
    
    def build(self) -> TaskData:
        assignment = AssignmentData(
            assignee=self._assignee_data,
            member_group=self._member_group_data
        )
        
        time_tracking = TimeTrackingData(
            total_spent_time_days=self._total_spent_time_days,
            current_assignee_spent_time_days=self._current_assignee_spent_time_days
        )
        
        system_metadata = SystemMetadataData(
            original_status=self._original_status,
            url=self._url
        )
        
        return TaskData(
            id=self._id,
            title=self._title,
            assignment=assignment,
            time_tracking=time_tracking,
            system_metadata=system_metadata,
            story_points=self._story_points,
            priority=self._priority,
            child_tasks=self._child_tasks if self._child_tasks else None,
            child_tasks_count=self._child_tasks_count,
            stage=self._stage,
            forecast=self._forecast_data,
            custom_sort_fields=self._custom_sort_fields if self._custom_sort_fields else None
        )


class DomainTaskBuilder:
    
    def __init__(self, task_id: str, title: str):
        self._id = task_id
        self._title = title
        self._story_points: Optional[float] = None
        self._assignee: Optional[Assignee] = None
        self._member_group: Optional[MemberGroup] = None
        self._total_spent_time: Optional[Duration] = None
        self._child_tasks: List[Task] = []
        self._status: Optional[TaskStatus] = None
        self._stage: Optional[str] = None
        self._original_status = "To Do"
        self._project_key = "PROJ"
        self._url: Optional[str] = None
    
    @classmethod
    def domain_task_for_ui_conversion(cls) -> 'DomainTaskBuilder':
        return (cls("PROJ-123", "Domain task for UI conversion testing")
                .assigned_to("default.developer"))
    
    def with_story_points(self, points: float) -> 'DomainTaskBuilder':
        self._story_points = points
        return self
    
    def assigned_to(self, assignee_id: str) -> 'DomainTaskBuilder':
        self._assignee = Assignee(
            id=assignee_id,
            display_name=f"{assignee_id} (Developer)",
            avatar_url=f"https://company.com/avatars/{assignee_id.replace('.', '_')}.jpg"
        )
        return self
    
    def with_member_group(self, member_group_id: str, member_group_name: str) -> 'DomainTaskBuilder':
        self._member_group = MemberGroup(id=member_group_id, name=member_group_name)
        return self

    def assigned_to_senior_developer(self) -> 'DomainTaskBuilder':
        self._assignee = Assignee(
            id="alice.senior",
            display_name="Alice Thompson (Senior Developer)",
            avatar_url="https://company.com/avatars/alice.jpg"
        )
        self._member_group = MemberGroup(id="backend-team", name="Backend Team")
        return self
    
    def with_time_spent_hours(self, hours: float) -> 'DomainTaskBuilder':
        self._total_spent_time = Duration.of(hours, TimeUnit.HOUR)
        return self
    
    def with_stage(self, stage: str) -> 'DomainTaskBuilder':
        self._stage = stage
        return self
    
    def build(self) -> Task:
        assignment = Assignment(
            assignee=self._assignee,
            member_group=self._member_group
        )
        
        time_tracking = TimeTracking(
            total_spent_time=self._total_spent_time
        )
        
        system_metadata = SystemMetadata(
            original_status=self._original_status,
            project_key=self._project_key,
            url=self._url
        )
        
        return Task(
            id=self._id,
            title=self._title,
            system_metadata=system_metadata,
            assignment=assignment,
            time_tracking=time_tracking,
            status=self._status,
            stage=self._stage,
            story_points=self._story_points,
            child_tasks=self._child_tasks if self._child_tasks else None
        )


def sorting_config(criteria: str = '-health,-spent_time') -> SortingConfig:
    return SortingConfig(stage_sort_overrides={}, default_sort_criteria=criteria)
