from django.conf import settings
from django.urls import path

from .utils.url_utils import django_normalized_base_url
from .views.current_tasks_view import CurrentTasksView, CurrentTasksChildrenView, CurrentTasksStageView, \
    AvailableMembersView, TaskPullRequestGatewayView
from .views.ai_dashboard_view import (
    AiDashboardCatalogApiView,
    AiDashboardContextApiView,
    AiDashboardArtifactValidationApiView,
    AiDashboardGcxPreconditionApiView,
    AiDashboardGcxPublicationCallbackApiView,
    AiDashboardIntentValidationApiView,
    AiDashboardPublishApprovalApiView,
    AiDashboardPublishApprovalDecisionApiView,
    AiDashboardPublishHistoryApiView,
    AiDashboardPublishDemoApiView,
    AiDashboardRenderConfigValidationApiView,
    AiDashboardWorkflowApiView,
    AiDashboardWorkflowView,
    AiDashboardWorkspaceContextApiView,
)
from .views.dev_velocity_view import DevVelocityView, DevVelocityChartView, DevStoryPointsChartView, DevVelocityTasksView
from .views.homepage_view import HomepageView
from .views.pull_requests_view import PullRequestsView, PullRequestReviewStateView
from .views.bug_trend_view import BugTrendView, BugTrendEvidenceView, BugTrendEvidenceExportView, BugTrendScopeAuditView, BugTrendScopeConfigView, BugTrendScopeLibraryView, BugTrendScopeMetadataView, BugTrendChartDataApiView, BugTrendEvidenceApiView
from .views.data_health_view import DataHealthView
from .views.provider_chart_view import ProviderChartDataApiView, ProviderChartEvidenceApiView, ProviderProfileAlignDashboardRangeApiView, ProviderProfileReadinessApiView
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
     path(_base_prefix + 'ai-dashboard/workflow/', AiDashboardWorkflowView.as_view(), name='ai_dashboard_workflow'),
     path(_base_prefix + 'data-health/', DataHealthView.as_view(), name='data_health'),
     path(_base_prefix + 'bug-trend/scope-audit/', BugTrendScopeAuditView.as_view(), name='bug_trend_scope_audit'),
     path(_base_prefix + 'bug-trend/scopes/', BugTrendScopeLibraryView.as_view(), name='bug_trend_scope_library'),
     path(_base_prefix + 'bug-trend/scope-config/', BugTrendScopeConfigView.as_view(), name='bug_trend_scope_config'),

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
    path(_base_prefix + 'partials/bug-trend/evidence/', BugTrendEvidenceView.as_view(), name='bug_trend_evidence'),
     path(_base_prefix + 'partials/bug-trend/scope-metadata/', BugTrendScopeMetadataView.as_view(), name='bug_trend_scope_metadata'),
     path(_base_prefix + 'bug-trend/evidence/export/', BugTrendEvidenceExportView.as_view(), name='bug_trend_evidence_export'),
     path(_base_prefix + 'api/charts/data/', BugTrendChartDataApiView.as_view(), name='chart_data_api'),
     path(_base_prefix + 'api/charts/evidence/', BugTrendEvidenceApiView.as_view(), name='chart_evidence_api'),
     path(_base_prefix + 'api/provider-charts/data/', ProviderChartDataApiView.as_view(), name='provider_chart_data_api'),
     path(_base_prefix + 'api/provider-charts/evidence/', ProviderChartEvidenceApiView.as_view(), name='provider_chart_evidence_api'),
     path(_base_prefix + 'api/provider-profiles/readiness/', ProviderProfileReadinessApiView.as_view(), name='provider_profile_readiness_api'),
     path(_base_prefix + 'api/provider-profiles/align-dashboard-range/', ProviderProfileAlignDashboardRangeApiView.as_view(), name='provider_profile_align_dashboard_range_api'),
     path(_base_prefix + 'api/ai-dashboard/catalog/', AiDashboardCatalogApiView.as_view(), name='ai_dashboard_catalog_api'),
     path(_base_prefix + 'api/ai-dashboard/intent/validate/', AiDashboardIntentValidationApiView.as_view(), name='ai_dashboard_intent_validation_api'),
     path(_base_prefix + 'api/ai-dashboard/render-config/validate/', AiDashboardRenderConfigValidationApiView.as_view(), name='ai_dashboard_render_config_validation_api'),
     path(_base_prefix + 'api/ai-dashboard/artifacts/validate/', AiDashboardArtifactValidationApiView.as_view(), name='ai_dashboard_artifact_validation_api'),
     path(_base_prefix + 'api/ai-dashboard/workflow/', AiDashboardWorkflowApiView.as_view(), name='ai_dashboard_workflow_api'),
     path(_base_prefix + 'api/ai-dashboard/gcx/precondition/', AiDashboardGcxPreconditionApiView.as_view(), name='ai_dashboard_gcx_precondition_api'),
     path(_base_prefix + 'api/ai-dashboard/gcx/publication-callback/', AiDashboardGcxPublicationCallbackApiView.as_view(), name='ai_dashboard_gcx_publication_callback_api'),
     path(_base_prefix + 'api/ai-dashboard/publish-approval/', AiDashboardPublishApprovalApiView.as_view(), name='ai_dashboard_publish_approval_api'),
     path(_base_prefix + 'api/ai-dashboard/publish-approval/decision/', AiDashboardPublishApprovalDecisionApiView.as_view(), name='ai_dashboard_publish_approval_decision_api'),
     path(_base_prefix + 'api/ai-dashboard/publish-demo/', AiDashboardPublishDemoApiView.as_view(), name='ai_dashboard_publish_demo_api'),
     path(_base_prefix + 'api/ai-dashboard/publish-history/', AiDashboardPublishHistoryApiView.as_view(), name='ai_dashboard_publish_history_api'),
     path(_base_prefix + 'api/ai-dashboard/context/', AiDashboardContextApiView.as_view(), name='ai_dashboard_context_api'),
     path(_base_prefix + 'api/ai-dashboard/workspace-context/', AiDashboardWorkspaceContextApiView.as_view(), name='ai_dashboard_workspace_context_api'),
]
