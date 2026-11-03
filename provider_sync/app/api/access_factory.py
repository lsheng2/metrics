from dataclasses import fields

from django.conf import settings

from bug_metrics.app.api.provider_connections import create_provider_connection_resolver
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from project_management.app.api.factories import build_capture_archive_service, build_project_api
from provider_sync.app.api.access import ProviderAccessService
from provider_sync.app.api.access_contracts import CaptureLimits
from provider_sync.out.jira_capture import JiraCaptureAdapter


def capture_limits_from_settings(source=settings):
    defaults = CaptureLimits()
    return CaptureLimits(**{
        field.name: getattr(source, 'METRICS_PROJECT_CAPTURE_' + field.name.upper(), getattr(defaults, field.name))
        for field in fields(defaults)
    })


def create_provider_access_service():
    projects = build_project_api()
    registry = ProjectProviderProfileRegistry.load_default()
    resolver = create_provider_connection_resolver(profile_registry=registry)
    archive = None
    if getattr(settings, 'METRICS_PROJECT_ARCHIVE_ROOT', ''):
        archive = build_capture_archive_service(project_api=projects)
    return ProviderAccessService(projects, resolver, {'jira': JiraCaptureAdapter()}, archive,
                                 profile_registry=registry)
