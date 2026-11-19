import asyncio
from typing import Union, List

from django.utils.http import urlencode
from django.views.generic import TemplateView

from pull_requests.app.domain.model.pull_request import PullRequestRef
from tasks.container import tasks_container
from ..container import ui_web_container
from ..data.hierarchical_item_data import HierarchicalItemData
from ..data.task_data import TaskData
from ..utils.task_grouping_utils import TaskGroupingUtils
from ..utils.task_sort_utils import TaskSortUtils
from .graceful_template_view import GracefulTemplateView


class CurrentTasksView(GracefulTemplateView):
    template_name = "current_tasks.html"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks_facade = ui_web_container.tasks_facade
        self.task_filter_facade = ui_web_container.task_filter_facade
        self.members_facade = ui_web_container.members_facade
        self.workflow_config = tasks_container.get_workflow_config()
        self.sorting_config = tasks_container.get_sorting_config()

    def get_template_names(self):
        if self.request.headers.get('HX-Target') == 'current-tasks-board':
            return ["partials/current_tasks_board.html"]
        if self.request.headers.get('HX-Request'):
            return ["partials/current_tasks_content.html"]
        return [self.template_name]

    def populate_context(self, context, **kwargs):
        group_id = self.request.GET.get('member_group_id')
        selections = self.task_filter_facade.parse_selections(self.request.GET)
        view_mode = self.request.GET.get('view', 'list')

        lazy_loading_enabled = self.tasks_facade.is_lazy_loading_enabled()
        expand_all = self.request.GET.get('expand_all') == 'true'
        needs_full_fetch = self.task_filter_facade.requires_full_fetch(selections)
        lazy_loading = lazy_loading_enabled and not expand_all and not needs_full_fetch and view_mode != 'board'

        context["view_mode"] = view_mode
        context["expand_all"] = expand_all
        context["view_queries"] = self._view_queries(view_mode)
        context["lazy_loading_enabled"] = lazy_loading_enabled
        context["lazy_loading"] = lazy_loading
        context["release_column_enabled"] = self.tasks_facade.is_release_column_enabled()
        context["pr_gateway_column_enabled"] = self.tasks_facade.is_pull_request_gateway_column_enabled()
        context["task_table_colspan"] = self.tasks_facade.task_table_colspan()
        context["success"] = False

        if lazy_loading:
            tasks = asyncio.run(self.tasks_facade.get_task_structure(group_id))
        else:
            tasks = asyncio.run(self.tasks_facade.get_tasks(group_id))

        context["task_filter_panel"] = self.task_filter_facade.get_panel(tasks, selections)

        if not lazy_loading_enabled:
            self._populate_available_members(context, tasks, group_id)

        tasks = self.task_filter_facade.filter_tasks(tasks, selections)
        grouped_tasks = self._group_tasks(tasks, view_mode)

        context["tasks"] = grouped_tasks
        context["task_count"] = len(tasks)
        context["selected_member_group_id"] = group_id
        context["has_groups"] = self._determine_has_groups(grouped_tasks)
        context["success"] = True

    def _view_queries(self, view_mode: str) -> dict:
        """Query strings for the layout switch (keeping applied filters) and for clearing the filters."""
        applied = {key: value for key, value in self.request.GET.items()
                   if value and key not in ('view', 'expand_all')}
        member_group = {key: value for key, value in applied.items() if key == 'member_group_id'}
        return {
            'list': urlencode({**applied, 'view': 'list'}),
            'board': urlencode({**applied, 'view': 'board'}),
            'clear': urlencode({**member_group, 'view': view_mode}),
        }

    def _populate_available_members(self, context, tasks, group_id):
        available_members = asyncio.run(self.members_facade.get_available_members(tasks, group_id))
        context["available_members"] = available_members
        context["show_available_members"] = len(available_members) > 0

    @staticmethod
    def _determine_has_groups(tasks: Union[List[HierarchicalItemData], List[TaskData]]) -> bool:
        return isinstance(tasks, list) and len(tasks) > 0 and isinstance(tasks[0], HierarchicalItemData)

    def _group_tasks(self, ui_tasks: List[TaskData], view_mode: str) -> Union[List[HierarchicalItemData], List[TaskData]]:
        if view_mode == 'board':
            return TaskGroupingUtils.group_tasks_by_all_stage_columns(
                ui_tasks,
                self.workflow_config,
                self.sorting_config
            )
        return TaskGroupingUtils.group_ui_tasks_by_member_group_and_stage(
            ui_tasks,
            self.workflow_config,
            self.sorting_config
        )


class CurrentTasksStageView(GracefulTemplateView):
    template_name = "partials/task_table.html"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks_facade = ui_web_container.tasks_facade
        self.sorting_config = tasks_container.get_sorting_config()

    def populate_context(self, context, **kwargs):
        context["release_column_enabled"] = self.tasks_facade.is_release_column_enabled()
        context["pr_gateway_column_enabled"] = self.tasks_facade.is_pull_request_gateway_column_enabled()
        context["task_table_colspan"] = self.tasks_facade.task_table_colspan()
        context["tasks"] = []

        task_ids = [task_id for task_id in self.request.GET.get('task_ids', '').split(',') if task_id]

        tasks = asyncio.run(self.tasks_facade.get_tasks_by_ids(task_ids))
        context["tasks"] = TaskSortUtils.sort_tasks(tasks, self.sorting_config)
        context["success"] = True


class AvailableMembersView(GracefulTemplateView):
    template_name = "partials/available_members_table.html"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks_facade = ui_web_container.tasks_facade
        self.members_facade = ui_web_container.members_facade

    def populate_context(self, context, **kwargs):
        context["available_members"] = []

        group_id = self.request.GET.get('member_group_id')
        tasks = asyncio.run(self.tasks_facade.get_task_structure(group_id))
        available_members = asyncio.run(self.members_facade.get_available_members(tasks, group_id))

        context["available_members"] = available_members
        context["show_available_members"] = len(available_members) > 0
        context["success"] = True


class CurrentTasksChildrenView(TemplateView):
    template_name = "partials/child_task_rows.html"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks_facade = ui_web_container.tasks_facade
        self.child_tasks_facade = ui_web_container.child_tasks_facade
        self.sorting_config = tasks_container.get_sorting_config()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["release_column_enabled"] = self.tasks_facade.is_release_column_enabled()
        context["pr_gateway_column_enabled"] = self.tasks_facade.is_pull_request_gateway_column_enabled()
        context["task_table_colspan"] = self.tasks_facade.task_table_colspan()

        task_id = kwargs.get("task_id")

        child_tasks = asyncio.run(self.child_tasks_facade.get_child_tasks(task_id))
        sorted_child_tasks = TaskSortUtils.sort_tasks(child_tasks, self.sorting_config)
        context['child_tasks'] = sorted_child_tasks
        return context


class TaskPullRequestGatewayView(GracefulTemplateView):
    template_name = "partials/task_pull_request_gateway.html"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pull_requests_facade = ui_web_container.pull_requests_facade

    def populate_context(self, context, **kwargs):
        ref = PullRequestRef(
            pull_request_id=self.request.GET.get('pull_request_id', ''),
            repository_id=self.request.GET.get('repository_id', ''),
            project_id=self.request.GET.get('project_id', ''),
            project_name=self.request.GET.get('project', '')
        )
        context["pull_request"] = asyncio.run(self.pull_requests_facade.get_review_details(ref))
        context["success"] = True
