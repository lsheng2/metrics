import hashlib
import json

from django.utils import timezone


class JiraIssuePayloadMaterializer:
    def field_names(self, scope):
        field_names = [
            'summary', 'issuetype', 'status', 'resolution', 'priority', 'components', 'assignee',
            'created', 'updated', 'resolutiondate', scope.severity_field, scope.component_field,
            scope.owner_field, scope.team_field, scope.milestone_field, scope.fix_version_field,
            scope.package_version_field, *scope.display_fields,
        ]
        return [field_name for field_name in field_names if field_name]

    def store_issue(self, history_api, scope, issue_payload, is_in_current_scope: bool):
        fields = issue_payload.get('fields', {})
        issue_key = issue_payload['key']
        updated_at = self.parse_datetime(fields.get('updated'))
        history_api.store_snapshot(
            scope,
            issue_key,
            updated_at,
            self.payload_hash(issue_payload),
            issue_payload,
        )
        history_api.upsert_issue(scope, issue_key, {
            'summary': fields.get('summary') or '',
            'issue_type': self.name_value(fields.get('issuetype')),
            'status': self.name_value(fields.get('status')),
            'resolution_value': self.name_value(fields.get('resolution')),
            'severity_value': self.field_value(fields.get(scope.severity_field or 'priority')),
            'component_value': self.field_value(fields.get(scope.component_field or 'components')),
            'owner_value': self.field_value(fields.get(scope.owner_field or 'assignee')),
            'team_value': self.field_value(fields.get(scope.team_field)),
            'milestone_value': self.field_value(fields.get(scope.milestone_field or scope.fix_version_field)),
            'created_at': self.parse_datetime(fields.get('created')),
            'updated_at': updated_at,
            'resolved_at': self.parse_datetime(fields.get('resolutiondate')),
            'raw_fields_json': fields,
            'is_in_current_scope': is_in_current_scope,
        })
        self.store_transitions(history_api, scope, issue_key, issue_payload.get('changelog', {}))
        return updated_at

    def store_transitions(self, history_api, scope, issue_key, changelog):
        for history in changelog.get('histories', []):
            transitioned_at = self.parse_datetime(history.get('created'))
            for item in history.get('items', []):
                if item.get('field') in {'status', 'resolution'}:
                    history_api.store_transition(
                        scope,
                        issue_key,
                        transitioned_at,
                        item.get('field'),
                        item.get('fromString') or '',
                        item.get('toString') or '',
                    )

    def payload_hash(self, payload):
        encoded_payload = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(encoded_payload.encode('utf-8')).hexdigest()

    def field_value(self, raw_value):
        if raw_value is None:
            return ''
        if isinstance(raw_value, list):
            return ', '.join(self.field_value(item) for item in raw_value if item is not None)
        if isinstance(raw_value, dict):
            return raw_value.get('name') or raw_value.get('displayName') or raw_value.get('value') or raw_value.get('key') or ''
        return str(raw_value)

    def name_value(self, raw_value):
        return raw_value.get('name', '') if isinstance(raw_value, dict) else ''

    def parse_datetime(self, raw_value):
        if not raw_value:
            return None
        return timezone.datetime.fromisoformat(raw_value.replace('Z', '+00:00'))