from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Set


@dataclass(slots=True)
class JiraConfig:
    jira_server_url: Optional[str]
    jira_email: Optional[str]
    jira_api_token: Optional[str]
    story_point_custom_field_id: str
    auth_mode: str = 'cloud_basic'
    verify_ssl: bool = True
    release_field: Optional[str] = None
    iteration_field: Optional[str] = None

    def uses_server_pat(self) -> bool:
        return self.auth_mode == 'server_pat'

    def has_authentication(self) -> bool:
        if self.uses_server_pat():
            return bool(self.jira_server_url and self.jira_api_token)
        return bool(self.jira_server_url and self.jira_email and self.jira_api_token)

@dataclass(slots=True)
class AzureConfig:
    azure_organization_url: Optional[str]
    azure_pat: Optional[str]
    release_field: Optional[str] = None
    iteration_field: Optional[str] = None

@dataclass(slots=True)
class ProjectConfig:
    project_keys: List[str]
    task_tracker: str

@dataclass(slots=True)
class WorkflowConfig:
    stages: Dict[str, List[str]]
    in_progress_status_codes: List[str]
    pending_status_codes: List[str]
    done_status_codes: List[str]
    recently_finished_tasks_days: int

@dataclass(slots=True)
class TaskFilterConfig:
    global_task_types_filter: List[str]
    global_team_filter: Optional[List[str]]

@dataclass(slots=True)
class MemberGroupConfig:
    members: Dict[str, Dict[str, Any]]
    default_member_group_when_missing: Optional[str]
    custom_filters: Optional[Dict[str, str]] = None
    merge_unassigned_into_filtered_group: bool = False

    def get_members_by_stage(self, stage_name: str) -> Set[str]:
        return {
            member_id for member_id, member_data in self.members.items()
            if stage_name in member_data.get('stages', [])
        }

    def get_members_in_stages(self, stage_names: List[str]) -> Set[str]:
        members = set()
        for stage_name in stage_names:
            members |= self.get_members_by_stage(stage_name)
        return members

    def get_available_member_groups(self) -> Dict[str, str]:
        member_groups = {}
        for member_data in self.members.values():
            member_groups_of_member = member_data.get('member_groups', [])
            for member_group_name in member_groups_of_member:
                member_groups[member_group_name] = member_group_name

        if self.default_member_group_when_missing:
            member_groups[self.default_member_group_when_missing] = self.default_member_group_when_missing

        return member_groups

@dataclass(slots=True)
class EstimationConfig:
    working_days_per_month: int
    default_story_points_value_when_missing: float
    ideal_hours_per_day: float
    story_points_to_ideal_hours_convertion_ratio: float
    default_seniority_level_when_missing: str
    default_health_status_when_missing: str

BUILTIN_SORT_CRITERIA = frozenset({'priority', 'health', 'spent_time', 'assignee', 'story_points'})

@dataclass(slots=True)
class SortingConfig:
    stage_sort_overrides: Dict[str, str]
    default_sort_criteria: str

    def custom_sort_field_names(self) -> List[str]:
        field_names = []
        for criteria_string in [self.default_sort_criteria, *self.stage_sort_overrides.values()]:
            for token in criteria_string.split(','):
                field_name = token.strip().lstrip('-').strip()
                if field_name and field_name not in BUILTIN_SORT_CRITERIA and field_name not in field_names:
                    field_names.append(field_name)
        return field_names

@dataclass(slots=True)
class TasksConfig:
    jira: JiraConfig
    azure: AzureConfig
    project: ProjectConfig
    workflow: WorkflowConfig
    task_filter: TaskFilterConfig
    member_group: MemberGroupConfig
    estimation: EstimationConfig
    sorting: SortingConfig

    def get_available_member_group_ids(self) -> List[str]:
        return sorted(self.member_group.get_available_member_groups().keys())
    
    def get_assignee_member_groups(self, assignee_id: str) -> List[str]:
        member_data = self.member_group.members.get(assignee_id, {})
        return member_data.get('member_groups', [])
    
    def get_assignee_level(self, assignee_id: str) -> Optional[str]:
        member_data = self.member_group.members.get(assignee_id, {})
        return member_data.get('level')
    
    def get_assignee_stages(self, assignee_id: str) -> List[str]:
        member_data = self.member_group.members.get(assignee_id, {})
        return member_data.get('stages', [])
