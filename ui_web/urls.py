from django.conf import settings
from django.urls import path

from .utils.url_utils import django_normalized_base_url
from .views.current_tasks_view import CurrentTasksView, CurrentTasksChildrenView, CurrentTasksStageView, \
    AvailableMembersView, TaskPullRequestGatewayView
from .views.ai_dashboard_identity_view import AiDashboardIdentityApiView
from .views.ai_dashboard_view import (
    AiDashboardCatalogApiView,
    AiDashboardContextApiView,
    AiDashboardArtifactValidationApiView,
    AiDashboardGcxPreconditionApiView,
    AiDashboardGcxPublicationCallbackApiView,
    AiDashboardIntentValidationApiView,
    AiDashboardRenderConfigValidationApiView,
    AiDashboardWorkflowApiView,
    AiDashboardWorkflowView,
    AiDashboardWorkspaceContextApiView,
)
from .views.ai_dashboard_publish_view import (
    AiDashboardPublishApprovalApiView,
    AiDashboardPublishApprovalDecisionApiView,
    AiDashboardPublishHistoryApiView,
    AiDashboardPublishDemoApiView,
)
from .views.dev_velocity_view import DevVelocityView, DevVelocityChartView, DevStoryPointsChartView, DevVelocityTasksView
from .views.homepage_view import HomepageView
from .views.pull_requests_view import PullRequestsView, PullRequestReviewStateView
from .views.bug_trend_scope_views import BugTrendScopeConfigView, BugTrendScopeLibraryView, BugTrendScopeMetadataView
from .views.bug_trend_view import BugTrendView, BugTrendEvidenceView, BugTrendEvidenceExportView, BugTrendScopeAuditView, BugTrendChartDataApiView, BugTrendEvidenceApiView
from .views.data_health_view import DataHealthView
from .views.provider_setup_view import ProviderSetupView
from .views.provider_chart_view import ProviderChartDataApiView, ProviderChartEvidenceApiView, ProviderProfileAlignDashboardRangeApiView, ProviderProfileReadinessApiView
from .views.project_management_views import (
    ProjectArchiveView,
    ProjectDetailView,
    ProjectLanguageView,
    ProjectListView,
    ProjectStageConfirmView,
    ProjectStagePreviewView,
)
from .views.project_reports import (
    ProjectStageReportView,
    ReportDraftClipboardView,
    ReportDraftCreateView,
    ReportDraftDownloadView,
    ReportDraftEditView,
    ReportDraftFinalizeView,
    ReportDraftRenderView,
    ReportDraftResumeView,
    ReportDraftSaveView,
    ReportPublicationDownloadView,
    ReportPublicationRevisionView,
    ReportPublicationView,
)
from .views.report_history import (
    ReportPeriodView,
    ReportPublicationLinkedRevisionView,
    ReportSeriesCreateView,
    ReportSeriesPolicyView,
    ReportWeeklyDraftCreateView,
)
from .views.report_daily import (
    ReportBaselinePreviewView,
    ReportPreparationCreateView,
    ReportPreparationDetailView,
    ReportPreparationReprepareView,
)
from .views.report_completion import ReportDraftCompletionView
from .views.report_meetings import ReportMeetingsView
from .views.report_assists import ReportAssistView
from .views.report_exports import ReportDraftExportView, ReportPublicationExportView
from .views.report_templates import (
    ReportTemplateArchiveView,
    ReportTemplateCopyView,
    ReportTemplateEditorView,
    ReportTemplateLibraryView,
    ReportTemplateSaveView,
)
from .views.project_run_views import (
    ProjectRunCancelView,
    ProjectRunResumeView,
    ProjectRunStatusView,
    ProjectRunSubmitView,
)
from .views.task_forecast_view import TaskForecastView
from .views.team_velocity_view import TeamVelocityView, TeamVelocityChartView, TeamStoryPointsChartView, TeamVelocityTasksView
from .views.workbench_view import WorkbenchGrafanaSelectionView, WorkbenchView

app_name = 'ui_web'

_base_prefix = django_normalized_base_url(settings.METRICS_BASE_URL)

urlpatterns = [
    path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/meetings/',
         ReportMeetingsView.as_view(), name='report_meetings'),
    # Homepage
    path(_base_prefix, HomepageView.as_view(), name='homepage'),
    path(_base_prefix + 'workbench/', WorkbenchView.as_view(), name='workbench'),
    path(_base_prefix + 'workbench/grafana-selection/', WorkbenchGrafanaSelectionView.as_view(), name='workbench_grafana_selection'),

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
     path(_base_prefix + 'provider-setup/', ProviderSetupView.as_view(), name='provider_setup'),
     path(_base_prefix + 'bug-trend/scope-audit/', BugTrendScopeAuditView.as_view(), name='bug_trend_scope_audit'),
     path(_base_prefix + 'bug-trend/scopes/', BugTrendScopeLibraryView.as_view(), name='bug_trend_scope_library'),
     path(_base_prefix + 'bug-trend/scope-config/', BugTrendScopeConfigView.as_view(), name='bug_trend_scope_config'),
     path(_base_prefix + 'projects/', ProjectListView.as_view(), name='projects'),
     path(_base_prefix + 'projects/language/', ProjectLanguageView.as_view(), name='project_language'),
     path(_base_prefix + 'projects/<uuid:project_id>/', ProjectDetailView.as_view(), name='project_detail'),
     path(_base_prefix + 'projects/<uuid:project_id>/report-templates/',
          ReportTemplateLibraryView.as_view(), name='report_templates'),
     path(_base_prefix + 'projects/<uuid:project_id>/report-templates/<uuid:template_id>/',
          ReportTemplateEditorView.as_view(), name='report_template_editor'),
     path(_base_prefix + 'projects/<uuid:project_id>/report-templates/<uuid:template_id>/save/',
          ReportTemplateSaveView.as_view(), name='report_template_save'),
     path(_base_prefix + 'projects/<uuid:project_id>/report-templates/<uuid:template_id>/archive/',
          ReportTemplateArchiveView.as_view(), name='report_template_archive'),
     path(_base_prefix + 'projects/<uuid:project_id>/report-templates/<uuid:template_id>/copy/',
          ReportTemplateCopyView.as_view(), name='report_template_copy'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/',
          ProjectStageReportView.as_view(), name='project_stage_reports'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/drafts/',
          ReportDraftCreateView.as_view(), name='report_draft_create'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/weekly-drafts/',
          ReportWeeklyDraftCreateView.as_view(), name='report_weekly_draft_create'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/baseline-preview/',
          ReportBaselinePreviewView.as_view(), name='report_baseline_preview'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/preparations/',
          ReportPreparationCreateView.as_view(), name='report_preparation_create'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/preparations/<uuid:preparation_id>/',
          ReportPreparationDetailView.as_view(), name='report_preparation_detail'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/preparations/<uuid:preparation_id>/reprepare/',
          ReportPreparationReprepareView.as_view(), name='report_preparation_reprepare'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/series/',
          ReportSeriesCreateView.as_view(), name='report_series_create'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/series/<uuid:series_id>/policy/',
          ReportSeriesPolicyView.as_view(), name='report_series_policy'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/runs/',
          ProjectRunSubmitView.as_view(), name='project_run_submit'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/runs/<uuid:operation_id>/',
          ProjectRunStatusView.as_view(), name='project_run_status'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/runs/<uuid:operation_id>/cancel/',
          ProjectRunCancelView.as_view(), name='project_run_cancel'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/runs/<uuid:operation_id>/resume/',
          ProjectRunResumeView.as_view(), name='project_run_resume'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/drafts/<uuid:draft_id>/',
          ReportDraftEditView.as_view(), name='report_draft_edit'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/drafts/<uuid:draft_id>/save/',
          ReportDraftSaveView.as_view(), name='report_draft_save'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/drafts/<uuid:draft_id>/completions/',
          ReportDraftCompletionView.as_view(), name='report_draft_completion'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/drafts/<uuid:draft_id>/assists/',
          ReportAssistView.as_view(), name='report_assists'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/drafts/<uuid:draft_id>/export/',
          ReportDraftExportView.as_view(), name='report_draft_export'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/publications/<uuid:publication_id>/export/',
          ReportPublicationExportView.as_view(), name='report_publication_export'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/drafts/<uuid:draft_id>/assists/<uuid:assist_id>/',
          ReportAssistView.as_view(action='observe'), name='report_assist_observe'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/drafts/<uuid:draft_id>/assists/<uuid:assist_id>/candidate/',
          ReportAssistView.as_view(action='candidate'), name='report_assist_candidate'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/drafts/<uuid:draft_id>/assists/<uuid:assist_id>/cancel/',
          ReportAssistView.as_view(action='cancel'), name='report_assist_cancel'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/drafts/<uuid:draft_id>/render/',
          ReportDraftRenderView.as_view(), name='report_draft_render'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/drafts/<uuid:draft_id>/download/',
          ReportDraftDownloadView.as_view(), name='report_draft_download'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/drafts/<uuid:draft_id>/clipboard/',
          ReportDraftClipboardView.as_view(), name='report_draft_clipboard'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/drafts/<uuid:draft_id>/finalize/',
          ReportDraftFinalizeView.as_view(), name='report_draft_finalize'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/drafts/<uuid:draft_id>/resume/',
          ReportDraftResumeView.as_view(), name='report_draft_resume'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/publications/<uuid:publication_id>/',
          ReportPublicationView.as_view(), name='report_publication'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/periods/<path:period_key>/',
          ReportPeriodView.as_view(), name='report_period'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/publications/<uuid:publication_id>/revisions/',
          ReportPublicationRevisionView.as_view(), name='report_publication_revision'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/publications/<uuid:publication_id>/linked-revisions/',
          ReportPublicationLinkedRevisionView.as_view(), name='report_publication_linked_revision'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/<uuid:stage_id>/reports/publications/<uuid:publication_id>/download/',
          ReportPublicationDownloadView.as_view(), name='report_publication_download'),
     path(_base_prefix + 'projects/<uuid:project_id>/preview/', ProjectStagePreviewView.as_view(), name='project_stage_preview'),
     path(_base_prefix + 'projects/<uuid:project_id>/stages/', ProjectStageConfirmView.as_view(), name='project_stage_confirm'),
     path(_base_prefix + 'projects/<uuid:project_id>/archive/', ProjectArchiveView.as_view(), name='project_archive'),

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
     path(_base_prefix + 'api/ai-dashboard/identity/', AiDashboardIdentityApiView.as_view(), name='ai_dashboard_identity_api'),
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
