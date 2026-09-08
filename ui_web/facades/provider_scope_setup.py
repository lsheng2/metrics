from dataclasses import dataclass

from ..data.bug_trend_data import BugTrendProviderSetupDetail, BugTrendProviderSetupOption


@dataclass(frozen=True, slots=True)
class ProviderSetupDetailTemplate:
    label: str
    source_path: str
    fallback: str
    help_text: str


@dataclass(frozen=True, slots=True)
class ProviderSetupTemplate:
    provider_id: str
    label: str
    summary: str
    color: str
    source_query_label: str
    source_query_help: str
    metadata_supported: bool
    metadata_summary: str
    enabled_without_profile: bool
    detail_templates: tuple[ProviderSetupDetailTemplate, ...]


PROVIDER_SETUP_TEMPLATES = {
    'jira': ProviderSetupTemplate(
        'jira',
        'Jira',
        'Jira project, issue type, JQL and Jira field metadata.',
        'green',
        'JQL',
        'Jira Query Language used for sync and metadata discovery. Metadata can infer project from project = ... or project in (...).',
        True,
        'Jira metadata refresh is available from JQL project, Selected Jira projects and bug type values.',
        True,
        (
            ProviderSetupDetailTemplate('Base URL', 'connection_settings.base_url', 'settings:METRICS_JIRA_SERVER_URL', 'Jira instance URL used by the deployment.'),
            ProviderSetupDetailTemplate('Auth method', 'connection_settings.auth_mode_label', 'API token / PAT', 'Selected Jira authentication method.'),
            ProviderSetupDetailTemplate('System status', 'connection_settings.connection_status_label', 'Configuration required', 'System-derived readiness for connection testing.'),
        ),
    ),
    'hsdes': ProviderSetupTemplate(
        'hsdes',
        'HSD-ES',
        'HSD-ES tenant, subject, saved query and provider-owned field mappings.',
        'blue',
        'HSD-ES source reference',
        'Provider-owned saved query, query id or EQL reference. This editor stores it in the source query field for compatibility.',
        False,
        'HSD-ES metadata refresh is not wired to this Jira metadata panel; use provider profile workflow/readiness for HSD-ES field bindings.',
        False,
        (
            ProviderSetupDetailTemplate('Base URL', 'connection_settings.base_url', 'settings:METRICS_HSDES_API_BASE_URL', 'HSD-ES API base URL used by the deployment.'),
            ProviderSetupDetailTemplate('Auth method', 'connection_settings.auth_mode_label', 'Windows Integrated Auth', 'Selected HSD-ES authentication method.'),
            ProviderSetupDetailTemplate('System status', 'connection_settings.connection_status_label', 'Configuration required', 'System-derived readiness for connection testing.'),
        ),
    ),
    'github': ProviderSetupTemplate(
        'github',
        'GitHub',
        'Future GitHub Issues provider template for repository, labels and milestones.',
        'purple',
        'GitHub issue search',
        'Future provider query template for GitHub Issues search. A live adapter is not configured yet.',
        False,
        'GitHub metadata is template-only until a provider profile and adapter are registered.',
        False,
        (
            ProviderSetupDetailTemplate('Base URL', 'connection_settings.base_url', 'settings:METRICS_GITHUB_BASE_URL', 'GitHub API base URL used by the deployment.'),
            ProviderSetupDetailTemplate('Auth method', 'connection_settings.auth_mode_label', 'Personal access token', 'Selected GitHub authentication method.'),
            ProviderSetupDetailTemplate('System status', 'connection_settings.connection_status_label', 'Template only', 'System-derived readiness for connection testing.'),
        ),
    ),
}

GENERIC_PROVIDER_TEMPLATE = ProviderSetupTemplate(
    '',
    'Provider',
    'Provider profile supplied by registry.',
    'neutral',
    'Provider source query',
    'Provider-specific source query or saved-query reference.',
    False,
    'Metadata refresh requires a provider metadata adapter.',
    False,
    (
        ProviderSetupDetailTemplate('Base URL', 'connection_settings.base_url', 'Provider profile required', 'Provider API base URL.'),
        ProviderSetupDetailTemplate('Auth method', 'connection_settings.auth_mode_label', 'Provider profile required', 'Provider authentication method.'),
        ProviderSetupDetailTemplate('System status', 'connection_settings.connection_status_label', 'Configuration required', 'System-derived readiness for connection testing.'),
    ),
)


def provider_setup_template(provider_id: str) -> ProviderSetupTemplate:
    provider_id = str(provider_id or '').strip().lower()
    if provider_id in PROVIDER_SETUP_TEMPLATES:
        return PROVIDER_SETUP_TEMPLATES[provider_id]
    return ProviderSetupTemplate(
        provider_id,
        provider_id.upper() if provider_id else GENERIC_PROVIDER_TEMPLATE.label,
        GENERIC_PROVIDER_TEMPLATE.summary,
        GENERIC_PROVIDER_TEMPLATE.color,
        GENERIC_PROVIDER_TEMPLATE.source_query_label,
        GENERIC_PROVIDER_TEMPLATE.source_query_help,
        GENERIC_PROVIDER_TEMPLATE.metadata_supported,
        GENERIC_PROVIDER_TEMPLATE.metadata_summary,
        GENERIC_PROVIDER_TEMPLATE.enabled_without_profile,
        GENERIC_PROVIDER_TEMPLATE.detail_templates,
    )


def provider_setup_options(
    profile_choices: list,
    selected_provider_id: str,
    allow_template_creation: bool = False,
) -> list[BugTrendProviderSetupOption]:
    profile_counts = _profile_counts(profile_choices)
    provider_ids = list(PROVIDER_SETUP_TEMPLATES.keys())
    for profile in profile_choices:
        if profile.provider_id not in provider_ids:
            provider_ids.append(profile.provider_id)
    return [
        _setup_option(
            provider_setup_template(provider_id),
            profile_counts.get(provider_id, 0),
            selected_provider_id,
            allow_template_creation,
        )
        for provider_id in provider_ids
    ]


def provider_profile_choices_for(profile_choices: list, provider_id: str) -> list:
    return [profile for profile in profile_choices if profile.provider_id == provider_id]


def selected_profile_id_for(profile_choices: list, provider_id: str, requested_profile_id: str, current_profile_id: str) -> str:
    provider_profiles = provider_profile_choices_for(profile_choices, provider_id)
    for candidate in [requested_profile_id, current_profile_id]:
        if candidate and any(profile.profile_id == candidate for profile in provider_profiles):
            return candidate
    return provider_profiles[0].profile_id if provider_profiles else ''


def selected_profile_for(profile_choices: list, profile_id: str):
    for profile in profile_choices:
        if profile.profile_id == profile_id:
            return profile
    return None


def provider_detail_rows(template: ProviderSetupTemplate, selected_profile) -> list[BugTrendProviderSetupDetail]:
    return [
        BugTrendProviderSetupDetail(detail.label, _profile_value(selected_profile, detail.source_path, detail.fallback), detail.help_text)
        for detail in template.detail_templates
    ]


def provider_id_for_profile(profile_choices: list, profile_id: str) -> str:
    profile = selected_profile_for(profile_choices, profile_id)
    return profile.provider_id if profile else ''


def default_provider_id(profile_choices: list) -> str:
    if any(profile.provider_id == 'jira' for profile in profile_choices):
        return 'jira'
    if profile_choices:
        return profile_choices[0].provider_id
    return 'jira'


def _setup_option(
    template: ProviderSetupTemplate,
    profile_count: int,
    selected_provider_id: str,
    allow_template_creation: bool,
) -> BugTrendProviderSetupOption:
    return BugTrendProviderSetupOption(
        template.provider_id,
        template.label,
        template.summary,
        template.color,
        template.provider_id == selected_provider_id,
        bool(profile_count or template.enabled_without_profile or allow_template_creation),
        profile_count,
        template.metadata_supported,
        template.metadata_summary,
    )


def _profile_counts(profile_choices: list) -> dict[str, int]:
    counts = {}
    for profile in profile_choices:
        counts[profile.provider_id] = counts.get(profile.provider_id, 0) + 1
    return counts


def _profile_value(profile, source_path: str, fallback: str) -> str:
    if profile is None:
        return fallback
    container_name, _, key = source_path.partition('.')
    if container_name == 'source_population':
        value = (profile.source_population or {}).get(key, '')
        return str(value) if value not in {None, ''} else 'Not set'
    if container_name == 'connection_settings':
        value = (profile.connection_settings or {}).get(key, '')
        return str(value) if value not in {None, ''} else 'Not set'
    if container_name == 'scope_labels':
        value = (profile.scope_labels or {}).get(key, '')
        return str(value) if value not in {None, ''} else 'Not set'
    return fallback
