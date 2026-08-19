from django.conf import settings
from django.urls import path

from .utils.url_utils import django_normalized_base_url
from .views.current_tasks_view import CurrentTasksView, CurrentTasksChildrenView, CurrentTasksStageView, \
    AvailableMembersView, TaskPullRequestGatewayView
from .views.dev_velocity_view import DevVelocityView, DevVelocityChartView, DevStoryPointsChartView, DevVelocityTasksView
from .views.homepage_view import HomepageView
from .views.pull_requests_view import PullRequestsView, PullRequestReviewStateView
from .views.bug_trend_view import BugTrendView, BugTrendChartView, BugTrendDrilldownView
from .views.task_forecast_view import TaskForecastView
from .views.team_velocity_view import TeamVelocityView, TeamVelocityChartView, TeamStoryPointsChartView, TeamVelocityTasksView

app_name = 'ui_web'

_base_prefix = django_normalized_base_url(settings.METRICS_BASE_URL)

urlpatterns = [
    # Homepage
    path(_base_prefix, HomepageView.as_view(), name='homepage'),

    # Full page views
    path(_base_prefix + 'current-tasks/', CurrentTasksView.as_view(), name='current_tasks'),
    path(_base_prefix + 'current-tasks/<str:team_id>/', CurrentTasksView.as_view(), name='current_tasks_with_team'),
    path(_base_prefix + 'team-velocity/', TeamVelocityView.as_view(), name='team_velocity'),
    path(_base_prefix + 'team-velocity/<str:team_id>/', TeamVelocityView.as_view(), name='team_velocity_with_team'),
    path(_base_prefix + 'dev-velocity/', DevVelocityView.as_view(), name='dev_velocity'),
    path(_base_prefix + 'dev-velocity/<str:team_id>/', DevVelocityView.as_view(), name='dev_velocity_with_team'),
    path(_base_prefix + 'task-forecast/', TaskForecastView.as_view(), name='task_forecast'),
    path(_base_prefix + 'pull-requests/', PullRequestsView.as_view(), name='pull_requests'),
    path(_base_prefix + 'bug-trend/', BugTrendView.as_view(), name='bug_trend'),

    # Partials for HTMX
    path(_base_prefix + 'partials/tasks/', CurrentTasksView.as_view(), name='partials_tasks'),
    path(_base_prefix + 'partials/tasks/stage/', CurrentTasksStageView.as_view(), name='partials_tasks_stage'),
    path(_base_prefix + 'partials/tasks/available-members/', AvailableMembersView.as_view(),
         name='partials_available_members'),
    path(_base_prefix + 'partials/pull-requests/', PullRequestsView.as_view(), name='partials_pull_requests'),
    path(_base_prefix + 'partials/pull-requests/<str:pull_request_id>/review-state/',
         PullRequestReviewStateView.as_view(), name='partials_pr_review_state'),
    path(_base_prefix + 'partials/tasks/<str:task_id>/children/', CurrentTasksChildrenView.as_view(),
         name='partials_task_children'),
    path(_base_prefix + 'partials/tasks/<str:task_id>/pr-gateway/', TaskPullRequestGatewayView.as_view(),
         name='partials_task_pr_gateway'),
    path(_base_prefix + 'partials/dev-velocity/chart/', DevVelocityChartView.as_view(), name='dev_velocity_chart'),
    path(_base_prefix + 'partials/dev-velocity/sp-chart/', DevStoryPointsChartView.as_view(), name='dev_sp_chart'),
    path(_base_prefix + 'partials/dev-velocity/tasks/', DevVelocityTasksView.as_view(), name='dev_velocity_tasks'),
    path(_base_prefix + 'partials/team-velocity/chart/', TeamVelocityChartView.as_view(), name='team_velocity_chart'),
    path(_base_prefix + 'partials/team-velocity/sp-chart/', TeamStoryPointsChartView.as_view(), name='team_sp_chart'),
    path(_base_prefix + 'partials/team-velocity/tasks/', TeamVelocityTasksView.as_view(), name='team_velocity_tasks'),
    path(_base_prefix + 'partials/bug-trend/chart/', BugTrendChartView.as_view(), name='bug_trend_chart'),
    path(_base_prefix + 'bug-trend/drilldown/', BugTrendDrilldownView.as_view(), name='bug_trend_drilldown'),
]
