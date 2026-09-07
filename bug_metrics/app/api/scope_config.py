from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bug_metrics.models import BugTrendAuditEvent, BugTrendCalculationRun, BugTrendBucket, BugTrendBucketIssue, BugTrendScopeProviderBinding, JiraScopeConfig, SCOPE_SEMANTIC_LIST_FIELD_NAMES, normalize_scope_list_values
from jira_history.models import JiraIssue, JiraIssueSnapshot, JiraTransition
from jira_sync.models import JiraSyncCursor


SEMANTIC_LIST_FIELDS = SCOPE_SEMANTIC_LIST_FIELD_NAMES

SEMANTIC_TEXT_FIELDS = (
    'jql',
    'severity_field',
    'component_field',
    'owner_field',
    'team_field',
    'milestone_field',
    'fix_version_field',
    'package_version_field',
    'timezone',
    'bucket_granularity',
)

IDENTITY_TEXT_FIELDS = (
    'name',
    'ip',
    'project_label',
)


@dataclass(slots=True)
class ScopeConfigValidationResult:
    valid: bool
    errors: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class SavedScopeConfig:
    id: Optional[int]
    name: str
    ip: str
    project_label: str
    jql: str
    bug_type_values: List[str]
    open_status_values: List[str]
    fixed_status_values: List[str]
    closed_status_values: List[str]
    terminal_excluded_status_values: List[str]
    fixed_resolution_values: List[str]
    closed_resolution_values: List[str]
    reopen_status_values: List[str]
    severity_field: str
    critical_high_values: List[str]
    medium_low_values: List[str]
    component_field: str
    owner_field: str
    team_field: str
    milestone_field: str
    fix_version_field: str
    package_version_field: str
    display_fields: List[str]
    timezone: str
    bucket_granularity: str
    enabled: bool
    config_version_hash: str = ''


@dataclass(slots=True)
class ScopeDeleteImpact:
    scope_id: int
    scope_name: str
    enabled: bool
    calculation_runs: int
    trend_buckets: int
    bucket_issues: int
    jira_issues: int
    jira_snapshots: int
    jira_transitions: int
    sync_cursors: int
    provider_bindings: int
    audit_events: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ScopeConfigService:
    EXPORT_FORMAT = 'metrics.scope-config'
    EXPORT_VERSION = 1

    def list_scope_configs(self) -> List[SavedScopeConfig]:
        return [self._to_saved_scope_config(scope) for scope in JiraScopeConfig.objects.order_by('ip', 'project_label', 'name')]

    def get_scope_config(self, scope_id: int) -> SavedScopeConfig:
        return self._to_saved_scope_config(JiraScopeConfig.objects.get(id=scope_id))

    def validate_scope_config(self, config: SavedScopeConfig) -> ScopeConfigValidationResult:
        config = normalize_saved_scope_config(config)
        errors = {}
        if not config.name.strip():
            errors['name'] = 'Scope name is required.'
        if not config.jql.strip():
            errors['jql'] = 'JQL is required.'
        if not config.bug_type_values:
            errors['bug_type_values'] = 'At least one bug type value is required.'
        if config.bucket_granularity not in {JiraScopeConfig.GRANULARITY_DAILY, JiraScopeConfig.GRANULARITY_WEEKLY}:
            errors['bucket_granularity'] = 'Bucket granularity must be daily or weekly.'
        if not config.timezone.strip():
            errors['timezone'] = 'Timezone is required.'
        else:
            try:
                ZoneInfo(config.timezone)
            except ZoneInfoNotFoundError:
                errors['timezone'] = 'Timezone must be a valid IANA timezone name.'
        if config.enabled:
            self._validate_deployment_fields(config, errors)
        self._validate_list_fields(config, errors)
        self._validate_unique_name(config, errors)
        return ScopeConfigValidationResult(not errors, errors)

    def save_scope_config(self, config: SavedScopeConfig) -> SavedScopeConfig:
        config = normalize_saved_scope_config(config)
        validation = self.validate_scope_config(config)
        if not validation.valid:
            raise ValueError(validation.errors)

        scope = JiraScopeConfig.objects.get(id=config.id) if config.id else JiraScopeConfig()
        original_hash = scope.config_version_hash if scope.id else ''
        self._apply_config(scope, config)
        scope.save()
        self._record_scope_audit('scope_saved', scope, {
            'previous_config_version_hash': original_hash,
            'current_config_version_hash': scope.config_version_hash,
            'semantic_hash_changed': original_hash != scope.config_version_hash,
        })
        return self._to_saved_scope_config(scope)

    def activate_scope_config(self, scope_id: int) -> SavedScopeConfig:
        scope = JiraScopeConfig.objects.get(id=scope_id)
        validation = self.validate_scope_config(self._to_saved_scope_config(scope))
        if not validation.valid:
            raise ValueError(validation.errors)
        was_enabled = scope.enabled
        scope.enabled = True
        scope.save(update_fields=['enabled', 'config_version_hash', 'updated_at'])
        self._record_scope_audit('scope_activated', scope, {
            'was_enabled': was_enabled,
            'current_config_version_hash': scope.config_version_hash,
        })
        return self._to_saved_scope_config(scope)

    def disable_scope_config(self, scope_id: int) -> SavedScopeConfig:
        scope = JiraScopeConfig.objects.get(id=scope_id)
        was_enabled = scope.enabled
        scope.enabled = False
        scope.save(update_fields=['enabled', 'config_version_hash', 'updated_at'])
        self._record_scope_audit('scope_disabled', scope, {
            'was_enabled': was_enabled,
            'current_config_version_hash': scope.config_version_hash,
        })
        return self._to_saved_scope_config(scope)

    def get_scope_delete_impact(self, scope_id: int) -> ScopeDeleteImpact:
        scope = JiraScopeConfig.objects.get(id=scope_id)
        return ScopeDeleteImpact(
            scope_id=scope.id,
            scope_name=scope.name,
            enabled=scope.enabled,
            calculation_runs=BugTrendCalculationRun.objects.filter(scope=scope).count(),
            trend_buckets=BugTrendBucket.objects.filter(scope=scope).count(),
            bucket_issues=BugTrendBucketIssue.objects.filter(scope=scope).count(),
            jira_issues=JiraIssue.objects.filter(scope=scope).count(),
            jira_snapshots=JiraIssueSnapshot.objects.filter(scope=scope).count(),
            jira_transitions=JiraTransition.objects.filter(scope=scope).count(),
            sync_cursors=JiraSyncCursor.objects.filter(scope=scope).count(),
            provider_bindings=BugTrendScopeProviderBinding.objects.filter(scope=scope).count(),
            audit_events=BugTrendAuditEvent.objects.filter(scope=scope).count(),
        )

    def export_scope_config_package(self, scope_id: int) -> Dict[str, Any]:
        scope = JiraScopeConfig.objects.get(id=scope_id)
        binding = BugTrendScopeProviderBinding.objects.filter(scope=scope).first()
        self._record_scope_audit('scope_exported', scope, {
            'config_version_hash': scope.config_version_hash,
            'included_history': False,
        })
        return {
            'format': self.EXPORT_FORMAT,
            'version': self.EXPORT_VERSION,
            'scope': asdict(self._to_saved_scope_config(scope)),
            'provider_binding': self._binding_payload(binding),
            'excludes': [
                'calculation_runs',
                'trend_buckets',
                'bucket_issues',
                'jira_issues',
                'jira_issue_snapshots',
                'jira_transitions',
                'sync_cursor',
                'audit_events',
            ],
        }

    def import_scope_config_package(self, package: Dict[str, Any]) -> SavedScopeConfig:
        if package.get('format') != self.EXPORT_FORMAT or not isinstance(package.get('scope'), dict):
            raise ValueError({'scope_import': 'Scope import package is not recognized.'})
        source_config = saved_scope_config_from_dict(package['scope'])
        source_config.id = None
        source_config.enabled = False
        source_config.name = self._imported_scope_name(source_config.name)
        saved = self.save_scope_config(source_config)
        binding = package.get('provider_binding') or {}
        if binding.get('profile_id') and binding.get('provider_id'):
            BugTrendScopeProviderBinding.objects.update_or_create(
                scope_id=saved.id,
                defaults={
                    'profile_id': str(binding.get('profile_id', '')),
                    'provider_id': str(binding.get('provider_id', '')),
                    'status': BugTrendScopeProviderBinding.STATUS_EXPLICIT,
                    'provenance': {
                        'source': 'scope_config_import',
                        'imported_status': binding.get('status', ''),
                    },
                    'blockers': [],
                },
            )
        self._record_scope_audit('scope_imported', JiraScopeConfig.objects.get(id=saved.id), {
            'source_name': package['scope'].get('name', ''),
            'imported_as_enabled': False,
        })
        return saved

    def delete_archived_scope_config(self, scope_id: int, confirmation: str) -> ScopeDeleteImpact:
        scope = JiraScopeConfig.objects.get(id=scope_id)
        expected_confirmation = self.delete_confirmation_token(scope)
        if scope.enabled:
            raise ValueError({'scope_delete': 'Only archived scopes can be deleted.'})
        if confirmation != expected_confirmation:
            raise ValueError({'scope_delete': f'Type {expected_confirmation} to delete this archived scope.'})
        impact = self.get_scope_delete_impact(scope_id)
        self._record_scope_audit('scope_deleted', scope, {
            'impact': impact.to_dict(),
            'confirmation': confirmation,
        })
        scope.delete()
        return impact

    def delete_confirmation_token(self, scope: JiraScopeConfig) -> str:
        return f'DELETE {scope.name}'

    def _record_scope_audit(self, event_type: str, scope: JiraScopeConfig, request_summary: Dict[str, Any]) -> None:
        BugTrendAuditEvent.objects.create(
            event_type=event_type,
            actor='local_operator',
            scope=scope,
            request_summary=request_summary,
        )

    def _validate_list_fields(self, config: SavedScopeConfig, errors: Dict[str, str]) -> None:
        for field_name in SEMANTIC_LIST_FIELDS:
            value = getattr(config, field_name)
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                errors[field_name] = 'Value must be a list of strings.'

    def _validate_deployment_fields(self, config: SavedScopeConfig, errors: Dict[str, str]) -> None:
        if not config.open_status_values:
            errors['open_status_values'] = 'At least one open status value is required.'
        if not config.severity_field.strip():
            errors['severity_field'] = 'Severity field is required for critical/high and medium/low trend metrics.'
        if not config.critical_high_values:
            errors['critical_high_values'] = 'At least one critical/high value is required.'
        if not config.medium_low_values:
            errors['medium_low_values'] = 'At least one medium/low value is required.'
        if not config.fixed_status_values and not config.closed_status_values:
            errors['fixed_status_values'] = 'At least one fixed or closed status value is required.'

    def _validate_unique_name(self, config: SavedScopeConfig, errors: Dict[str, str]) -> None:
        existing = JiraScopeConfig.objects.filter(name=config.name)
        if config.id:
            existing = existing.exclude(id=config.id)
        if existing.exists():
            errors['name'] = 'Scope name must be unique.'

    def _apply_config(self, scope: JiraScopeConfig, config: SavedScopeConfig) -> None:
        for field_name in IDENTITY_TEXT_FIELDS + SEMANTIC_TEXT_FIELDS + SEMANTIC_LIST_FIELDS:
            setattr(scope, field_name, getattr(config, field_name))
        scope.enabled = config.enabled

    def _to_saved_scope_config(self, scope: JiraScopeConfig) -> SavedScopeConfig:
        return SavedScopeConfig(
            id=scope.id,
            name=scope.name,
            ip=scope.ip,
            project_label=scope.project_label,
            jql=scope.jql,
            bug_type_values=list(scope.bug_type_values),
            open_status_values=list(scope.open_status_values),
            fixed_status_values=list(scope.fixed_status_values),
            closed_status_values=list(scope.closed_status_values),
            terminal_excluded_status_values=list(scope.terminal_excluded_status_values),
            fixed_resolution_values=list(scope.fixed_resolution_values),
            closed_resolution_values=list(scope.closed_resolution_values),
            reopen_status_values=list(scope.reopen_status_values),
            severity_field=scope.severity_field,
            critical_high_values=list(scope.critical_high_values),
            medium_low_values=list(scope.medium_low_values),
            component_field=scope.component_field,
            owner_field=scope.owner_field,
            team_field=scope.team_field,
            milestone_field=scope.milestone_field,
            fix_version_field=scope.fix_version_field,
            package_version_field=scope.package_version_field,
            display_fields=list(scope.display_fields),
            timezone=scope.timezone,
            bucket_granularity=scope.bucket_granularity,
            enabled=scope.enabled,
            config_version_hash=scope.config_version_hash,
        )

    def _binding_payload(self, binding: BugTrendScopeProviderBinding | None) -> Dict[str, Any]:
        if binding is None:
            return {}
        return {
            'profile_id': binding.profile_id,
            'provider_id': binding.provider_id,
            'status': binding.status,
            'provenance': dict(binding.provenance or {}),
            'blockers': list(binding.blockers or []),
        }

    def _imported_scope_name(self, source_name: str) -> str:
        base_name = f'{source_name} imported'.strip()
        if not JiraScopeConfig.objects.filter(name=base_name).exists():
            return base_name
        index = 2
        while JiraScopeConfig.objects.filter(name=f'{base_name} {index}').exists():
            index += 1
        return f'{base_name} {index}'


def saved_scope_config_from_dict(payload: Dict[str, Any]) -> SavedScopeConfig:
    return SavedScopeConfig(
        id=payload.get('id'),
        name=payload.get('name', ''),
        ip=payload.get('ip', ''),
        project_label=payload.get('project_label', ''),
        jql=payload.get('jql', ''),
        bug_type_values=normalize_scope_list_values(payload.get('bug_type_values', [])),
        open_status_values=normalize_scope_list_values(payload.get('open_status_values', [])),
        fixed_status_values=normalize_scope_list_values(payload.get('fixed_status_values', [])),
        closed_status_values=normalize_scope_list_values(payload.get('closed_status_values', [])),
        terminal_excluded_status_values=normalize_scope_list_values(payload.get('terminal_excluded_status_values', [])),
        fixed_resolution_values=normalize_scope_list_values(payload.get('fixed_resolution_values', [])),
        closed_resolution_values=normalize_scope_list_values(payload.get('closed_resolution_values', [])),
        reopen_status_values=normalize_scope_list_values(payload.get('reopen_status_values', [])),
        severity_field=payload.get('severity_field', ''),
        critical_high_values=normalize_scope_list_values(payload.get('critical_high_values', [])),
        medium_low_values=normalize_scope_list_values(payload.get('medium_low_values', [])),
        component_field=payload.get('component_field', ''),
        owner_field=payload.get('owner_field', 'assignee'),
        team_field=payload.get('team_field', ''),
        milestone_field=payload.get('milestone_field', ''),
        fix_version_field=payload.get('fix_version_field', ''),
        package_version_field=payload.get('package_version_field', ''),
        display_fields=normalize_scope_list_values(payload.get('display_fields', [])),
        timezone=payload.get('timezone', 'UTC'),
        bucket_granularity=payload.get('bucket_granularity', JiraScopeConfig.GRANULARITY_WEEKLY),
        enabled=payload.get('enabled', False),
        config_version_hash=payload.get('config_version_hash', ''),
    )


def normalize_saved_scope_config(config: SavedScopeConfig) -> SavedScopeConfig:
    for field_name in SEMANTIC_LIST_FIELDS:
        setattr(config, field_name, normalize_scope_list_values(getattr(config, field_name)))
    return config
