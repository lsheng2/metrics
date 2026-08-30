from .provider_aggregate_contracts import (
    FIRST_HSDES_PROFILE_ID,
    FIRST_HSDES_SUBJECT,
    FIRST_HSDES_TENANT,
    MAPPING_VERSION,
    static_scope_labels_for_profile,
)


class HsdesProviderProjectionService:
    HSDES_FIELD_NAMES = frozenset({
        'HSD_type',
        'status',
        'reason',
        'priority',
        'exposure',
        'component',
        'release',
        'release_affected',
        'target_MS',
        'owner',
        'submitted_by',
        'submitted_date',
        'updated_date',
        'implemented_date',
        'closed_date',
        'team_found',
        'pss_escape',
        'days_open',
    })

    def normalize_search_page(self, profile_id: str, payload: dict) -> dict:
        articles = payload.get('articles') or payload.get('data') or payload.get('results') or []
        return {
            'provider_id': 'hsdes',
            'profile_id': profile_id,
            'mapping_version': MAPPING_VERSION,
            'scope_labels': static_scope_labels_for_profile(profile_id),
            'pagination': self._pagination(payload, len(articles)),
            'facts': [self._fact(profile_id, article) for article in articles],
            'errors': payload.get('errors', []),
        }

    def normalize_article_detail(self, profile_id: str, payload: dict) -> dict:
        return {
            'provider_id': 'hsdes',
            'profile_id': profile_id,
            'mapping_version': MAPPING_VERSION,
            'fact': self._fact(profile_id, payload),
            'comments': payload.get('comments', []),
            'links': payload.get('links', []),
            'children': payload.get('children', []),
            'errors': payload.get('errors', []),
        }

    def _fact(self, profile_id: str, article: dict) -> dict:
        field_values = self._field_values(article)
        tenant = article.get('tenant') or (FIRST_HSDES_TENANT if profile_id == FIRST_HSDES_PROFILE_ID else '')
        subject = article.get('subject') or (FIRST_HSDES_SUBJECT if profile_id == FIRST_HSDES_PROFILE_ID else '')
        return {
            'provider_id': 'hsdes',
            'profile_id': profile_id,
            'source_item_id': str(article.get('id', '')),
            'source_item_revision': str(article.get('rev', '')),
            'tenant': tenant,
            'subject': subject,
            'canonical_fields': self._canonical_fields(field_values),
            'project_fields': self._project_fields(field_values),
            'field_values': field_values,
            'provider_fields': article,
            'mapping_version': MAPPING_VERSION,
        }

    def _field_values(self, article: dict) -> dict:
        nested_values = article.get('fieldValues') or article.get('field_values') or {}
        if nested_values:
            return nested_values
        return {
            field_name: article.get(field_name, '')
            for field_name in self.HSDES_FIELD_NAMES
            if field_name in article
        }

    def _canonical_fields(self, field_values: dict) -> dict:
        return {
            'source_item_type': self._value(field_values, 'HSD_type'),
            'source_state': self._value(field_values, 'status'),
            'outcome': self._value(field_values, 'reason'),
            'severity_or_priority': self._value(field_values, 'exposure') or self._value(field_values, 'priority'),
            'component_or_area': self._value(field_values, 'component'),
            'release_target': self._value(field_values, 'release'),
            'affected_release': self._value(field_values, 'release_affected'),
            'milestone': self._value(field_values, 'target_MS'),
            'owner': self._value(field_values, 'owner'),
            'submitter': self._value(field_values, 'submitted_by'),
            'created_at': self._value(field_values, 'submitted_date'),
            'updated_at': self._value(field_values, 'updated_date'),
            'resolved_at': self._value(field_values, 'implemented_date'),
            'closed_at': self._value(field_values, 'closed_date'),
        }

    def _project_fields(self, field_values: dict) -> dict:
        return {
            'team_found': self._value(field_values, 'team_found'),
            'pss_escape': self._value(field_values, 'pss_escape'),
            'days_open': self._value(field_values, 'days_open'),
        }

    def _pagination(self, payload: dict, returned_count: int) -> dict:
        start_at = int(payload.get('start_at', 0) or 0)
        max_results = int(payload.get('max_results', returned_count) or returned_count)
        total = int(payload.get('total', returned_count) or returned_count)
        next_start_at = start_at + returned_count
        return {
            'start_at': start_at,
            'max_results': max_results,
            'total': total,
            'next_start_at': next_start_at,
            'has_more': next_start_at < total,
        }

    def _value(self, field_values: dict, field_name: str) -> str:
        value = field_values.get(field_name, '')
        if value is None:
            return ''
        return str(value)
