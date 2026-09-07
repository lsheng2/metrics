from dataclasses import dataclass
import hashlib
import uuid

from django.conf import settings

from bug_metrics.models import BugTrendAuditEvent, BugTrendScopeProviderBinding, JiraScopeConfig

from .provider_profile_registry import ProjectProviderProfile, ProjectProviderProfileRegistry


@dataclass(frozen=True, slots=True)
class ScopeProviderBindingResolution:
    scope_id: str
    profile_id: str
    provider_id: str
    status: str
    provenance: dict
    blockers: list[dict[str, str]]

    @property
    def is_resolved(self) -> bool:
        return bool(self.profile_id and self.provider_id and self.status in {
            BugTrendScopeProviderBinding.STATUS_EXPLICIT,
            BugTrendScopeProviderBinding.STATUS_COMPATIBILITY,
        })


@dataclass(frozen=True, slots=True)
class ScopeProviderBindingBulkConfirmResult:
    changed: list[dict]
    skipped: list[dict]

    @property
    def changed_count(self) -> int:
        return len(self.changed)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    def to_dict(self) -> dict:
        return {
            'changed_count': self.changed_count,
            'skipped_count': self.skipped_count,
            'changed': self.changed,
            'skipped': self.skipped,
        }


class ScopeProviderBindingResolver:
    POLICY_COMPATIBILITY_ALLOWED = 'compatibility_allowed'
    POLICY_EXPLICIT_ONLY = 'explicit_only'

    def __init__(self, profile_registry: ProjectProviderProfileRegistry | None = None):
        self._profile_registry = profile_registry or ProjectProviderProfileRegistry.load_default()

    def runtime_policy(self) -> str:
        policy = str(getattr(settings, 'METRICS_SCOPE_BINDING_POLICY', self.POLICY_COMPATIBILITY_ALLOWED) or '').strip()
        if policy not in {self.POLICY_COMPATIBILITY_ALLOWED, self.POLICY_EXPLICIT_ONLY}:
            return self.POLICY_COMPATIBILITY_ALLOWED
        return policy

    def resolve(self, scope: JiraScopeConfig, enforce_policy: bool = True) -> ScopeProviderBindingResolution:
        if not scope.enabled:
            return ScopeProviderBindingResolution(
                scope_id=str(scope.id),
                profile_id='',
                provider_id='',
                status=BugTrendScopeProviderBinding.STATUS_DISABLED,
                provenance={'source': 'scope_config'},
                blockers=[{
                    'code': 'scope_disabled',
                    'message': 'Scope is disabled.',
                }],
            )
        explicit_binding = getattr(scope, 'provider_binding', None)
        if explicit_binding:
            return self._apply_runtime_policy(self._resolution_from_binding(explicit_binding), enforce_policy)
        compatibility = self._compatibility_resolution(scope)
        return self._apply_runtime_policy(compatibility, enforce_policy)

    def backfill(self, scope: JiraScopeConfig, explicit: bool = False, actor: str = 'local_operator',
                 operation_type: str = BugTrendAuditEvent.EVENT_SCOPE_BINDING_CONFIRMED,
                 bulk_operation_id: str = '') -> ScopeProviderBindingResolution:
        before = self.resolve(scope, enforce_policy=False)
        if explicit and before.status == BugTrendScopeProviderBinding.STATUS_COMPATIBILITY and before.is_resolved:
            resolution = before
        else:
            resolution = self._compatibility_resolution(scope)
        status = BugTrendScopeProviderBinding.STATUS_EXPLICIT if explicit and resolution.is_resolved else resolution.status
        binding, _ = BugTrendScopeProviderBinding.objects.update_or_create(
            scope=scope,
            defaults={
                'profile_id': resolution.profile_id,
                'provider_id': resolution.provider_id,
                'status': status,
                'provenance': {
                    **resolution.provenance,
                    'persisted_by': 'scope_provider_binding_resolver',
                },
                'blockers': resolution.blockers,
            },
        )
        after = self._resolution_from_binding(binding)
        self._record_audit(scope, actor, operation_type, before, after, bulk_operation_id)
        return after

    def set_explicit(self, scope: JiraScopeConfig, profile_id: str, actor: str = 'local_operator') -> ScopeProviderBindingResolution:
        before = self.resolve(scope, enforce_policy=False)
        registry_resolution = self._profile_registry.resolve_profile(profile_id)
        if registry_resolution.profile is None:
            raise ValueError(f'Provider profile {profile_id} is not available.')
        profile = registry_resolution.profile
        binding, _ = BugTrendScopeProviderBinding.objects.update_or_create(
            scope=scope,
            defaults={
                'profile_id': profile.profile_id,
                'provider_id': profile.provider_id,
                'status': BugTrendScopeProviderBinding.STATUS_EXPLICIT,
                'provenance': {
                    'source': 'operator_confirmed',
                    'matched_by': 'provider_profile_selection',
                    'persisted_by': 'scope_provider_binding_resolver',
                },
                'blockers': [],
            },
        )
        after = self._resolution_from_binding(binding)
        self._record_audit(scope, actor, BugTrendAuditEvent.EVENT_SCOPE_BINDING_UPDATED, before, after, '')
        return after

    def bulk_confirm_compatibility(self, scopes, actor: str = 'local_operator') -> ScopeProviderBindingBulkConfirmResult:
        changed = []
        skipped = []
        bulk_operation_id = str(uuid.uuid4())
        for scope in scopes:
            resolution = self.resolve(scope, enforce_policy=False)
            if resolution.status == BugTrendScopeProviderBinding.STATUS_COMPATIBILITY and resolution.profile_id and resolution.provider_id:
                confirmed = self.backfill(
                    scope,
                    explicit=True,
                    actor=actor,
                    operation_type=BugTrendAuditEvent.EVENT_SCOPE_BINDING_BULK_CONFIRMED,
                    bulk_operation_id=bulk_operation_id,
                )
                changed.append({
                    'scope_id': scope.id,
                    'scope_name': scope.name,
                    'profile_id': confirmed.profile_id,
                    'provider_id': confirmed.provider_id,
                    'status': confirmed.status,
                })
            else:
                skipped.append({
                    'scope_id': scope.id,
                    'scope_name': scope.name,
                    'status': resolution.status,
                    'reason': self._skip_reason(resolution),
                })
        return ScopeProviderBindingBulkConfirmResult(changed, skipped)

    def list_profile_choices(self) -> list[dict[str, str]]:
        return [
            {
                'profile_id': profile.profile_id,
                'provider_id': profile.provider_id,
                'display_name': profile.display_name,
                'scope_labels': dict(profile.scope_labels),
                'source_population': dict(profile.source_population),
                'mapping_version_hash': profile.mapping_version_hash,
            }
            for profile in self._profile_registry.list_profiles()
        ]

    def list_binding_audit_events(self, limit: int = 25) -> list[dict]:
        event_types = [
            BugTrendAuditEvent.EVENT_SCOPE_BINDING_CONFIRMED,
            BugTrendAuditEvent.EVENT_SCOPE_BINDING_UPDATED,
            BugTrendAuditEvent.EVENT_SCOPE_BINDING_BULK_CONFIRMED,
        ]
        events = BugTrendAuditEvent.objects.select_related('scope').filter(
            event_type__in=event_types,
        ).order_by('-created_at')[:limit]
        return [self._audit_event_payload(event) for event in events]

    def _resolution_from_binding(self, binding: BugTrendScopeProviderBinding) -> ScopeProviderBindingResolution:
        if binding.profile_id and binding.provider_id:
            registry_resolution = self._profile_registry.resolve_profile(binding.profile_id)
            if registry_resolution.profile and registry_resolution.profile.provider_id != binding.provider_id:
                return ScopeProviderBindingResolution(
                    scope_id=str(binding.scope_id),
                    profile_id=binding.profile_id,
                    provider_id=binding.provider_id,
                    status=BugTrendScopeProviderBinding.STATUS_CONFIGURATION_REQUIRED,
                    provenance={**binding.provenance, 'binding_id': binding.id},
                    blockers=[{
                        'code': 'provider_profile_mismatch',
                        'message': f'Binding provider {binding.provider_id} does not match provider profile {binding.profile_id}.',
                    }],
                )
        return ScopeProviderBindingResolution(
            scope_id=str(binding.scope_id),
            profile_id=binding.profile_id,
            provider_id=binding.provider_id,
            status=binding.status,
            provenance={**binding.provenance, 'binding_id': binding.id},
            blockers=list(binding.blockers or []),
        )

    def _apply_runtime_policy(self, resolution: ScopeProviderBindingResolution,
                              enforce_policy: bool) -> ScopeProviderBindingResolution:
        if not enforce_policy:
            return resolution
        if self.runtime_policy() != self.POLICY_EXPLICIT_ONLY:
            return resolution
        if resolution.status != BugTrendScopeProviderBinding.STATUS_COMPATIBILITY:
            return resolution
        return ScopeProviderBindingResolution(
            scope_id=resolution.scope_id,
            profile_id='',
            provider_id='',
            status=BugTrendScopeProviderBinding.STATUS_CONFIGURATION_REQUIRED,
            provenance={
                **resolution.provenance,
                'runtime_policy': self.POLICY_EXPLICIT_ONLY,
                'compatibility_profile_id': resolution.profile_id,
                'compatibility_provider_id': resolution.provider_id,
            },
            blockers=[{
                'code': 'explicit_binding_required',
                'message': 'Scope uses a compatibility binding and must be confirmed before explicit-only operation.',
            }],
        )

    def _compatibility_resolution(self, scope: JiraScopeConfig) -> ScopeProviderBindingResolution:
        matches = [profile for profile in self._profile_registry.list_profiles() if self._scope_matches_profile(scope, profile)]
        if len(matches) == 1:
            profile = matches[0]
            return ScopeProviderBindingResolution(
                scope_id=str(scope.id),
                profile_id=profile.profile_id,
                provider_id=profile.provider_id,
                status=BugTrendScopeProviderBinding.STATUS_COMPATIBILITY,
                provenance={'source': 'compatibility', 'matched_by': 'provider_profile_registry'},
                blockers=[],
            )
        if len(matches) > 1:
            return ScopeProviderBindingResolution(
                scope_id=str(scope.id),
                profile_id='',
                provider_id='',
                status=BugTrendScopeProviderBinding.STATUS_AMBIGUOUS,
                provenance={'source': 'compatibility'},
                blockers=[{
                    'code': 'ambiguous_scope_provider_binding',
                    'message': 'Multiple provider profiles match the selected scope.',
                }],
            )
        fallback_provider_id = self._fallback_provider_id(scope)
        if fallback_provider_id:
            return ScopeProviderBindingResolution(
                scope_id=str(scope.id),
                profile_id=str(scope.name or ''),
                provider_id=fallback_provider_id,
                status=BugTrendScopeProviderBinding.STATUS_COMPATIBILITY,
                provenance={'source': 'compatibility', 'matched_by': f'legacy_{fallback_provider_id}_scope'},
                blockers=[],
            )
        return ScopeProviderBindingResolution(
            scope_id=str(scope.id),
            profile_id='',
            provider_id='',
            status=BugTrendScopeProviderBinding.STATUS_CONFIGURATION_REQUIRED,
            provenance={'source': 'compatibility'},
            blockers=[{
                'code': 'scope_provider_binding_missing',
                'message': 'Scope is not bound to a provider profile.',
            }],
        )

    def _scope_matches_profile(self, scope: JiraScopeConfig, profile: ProjectProviderProfile) -> bool:
        scope_name = str(scope.name or '').strip().lower()
        source_population = profile.source_population
        candidates = [
            profile.profile_id,
            profile.display_name,
            source_population.get('profile_id', ''),
            source_population.get('source_query_name', ''),
        ]
        if scope_name in {str(candidate or '').strip().lower() for candidate in candidates if candidate}:
            return True
        if profile.provider_id == 'jira':
            return self._query_hash(scope.jql) == self._query_hash(source_population.get('native_query_text', ''))
        if profile.provider_id == 'hsdes':
            return self._hsdes_scope_matches_profile(scope, source_population)
        return False

    def _fallback_provider_id(self, scope: JiraScopeConfig) -> str:
        normalized_scope_name = str(scope.name or '').lower()
        if 'hsdes' in normalized_scope_name:
            return 'hsdes'
        if 'jira' in normalized_scope_name or scope.jql:
            return 'jira'
        return ''

    def _query_hash(self, query: str) -> str:
        normalized_query = ' '.join(str(query or '').replace("'", '"').split()).lower()
        return hashlib.sha256(normalized_query.encode('utf-8')).hexdigest() if normalized_query else ''

    def _hsdes_scope_matches_profile(self, scope: JiraScopeConfig, source_population: dict[str, str]) -> bool:
        source_query_ref = str(source_population.get('source_query_ref', '') or '').strip()
        if source_query_ref and source_query_ref in str(scope.jql or ''):
            return True
        profile_ip = str(source_population.get('tenant_or_site', '') or '').split('.')[0].strip().lower()
        scope_ip = str(scope.ip or '').strip().lower()
        return bool(profile_ip and scope_ip and profile_ip == scope_ip and source_population.get('source_query_name'))

    def _record_audit(self, scope: JiraScopeConfig, actor: str, event_type: str,
                      before: ScopeProviderBindingResolution, after: ScopeProviderBindingResolution,
                      bulk_operation_id: str):
        if self._snapshot(before) == self._snapshot(after):
            return
        BugTrendAuditEvent.objects.create(
            event_type=event_type,
            actor=actor,
            scope=scope,
            request_summary={
                'operation': event_type,
                'bulk_operation_id': bulk_operation_id,
                'before': self._snapshot(before),
                'after': self._snapshot(after),
            },
        )

    def _snapshot(self, resolution: ScopeProviderBindingResolution) -> dict:
        return {
            'status': resolution.status,
            'profile_id': resolution.profile_id,
            'provider_id': resolution.provider_id,
            'provenance': resolution.provenance,
            'blockers': resolution.blockers,
        }

    def _skip_reason(self, resolution: ScopeProviderBindingResolution) -> str:
        if resolution.status == BugTrendScopeProviderBinding.STATUS_EXPLICIT:
            return 'Binding is already explicit.'
        if resolution.blockers:
            return resolution.blockers[0].get('message', 'Binding is not safe to confirm.')
        if not resolution.profile_id or not resolution.provider_id:
            return 'Binding is missing profile or provider.'
        return f'Binding status {resolution.status} cannot be bulk confirmed.'

    def _audit_event_payload(self, event: BugTrendAuditEvent) -> dict:
        summary = dict(event.request_summary or {})
        before = dict(summary.get('before') or {})
        after = dict(summary.get('after') or {})
        return {
            'event_type': event.event_type,
            'actor': event.actor,
            'scope_id': event.scope_id,
            'scope_name': event.scope.name if event.scope else '',
            'created_at': event.created_at,
            'before': before,
            'after': after,
            'before_summary': self._snapshot_summary(before),
            'after_summary': self._snapshot_summary(after),
            'bulk_operation_id': summary.get('bulk_operation_id', ''),
        }

    def _snapshot_summary(self, snapshot: dict) -> str:
        status = snapshot.get('status') or '-'
        provider_id = snapshot.get('provider_id') or '-'
        profile_id = snapshot.get('profile_id') or '-'
        return f'{status}: {provider_id} / {profile_id}'
