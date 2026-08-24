import re

from jira_sync.app.api.scope_metadata import ScopeConfigOptions, TrackerFieldOption, TrackerOption


class JiraScopeMetadataAdapter:
    def __init__(self, jira_client):
        self._jira_client = jira_client

    def discover_options(self, query: str, selected_projects: list[str], selected_item_types: list[str]) -> ScopeConfigOptions:
        warnings = []
        project_keys = selected_projects or self._parse_project_keys(query)
        if not project_keys:
            warnings.append('Select at least one Jira project before refreshing project-scoped metadata.')
        projects = [TrackerOption(id=project_key, name=project_key, label=project_key, source='selected project') for project_key in project_keys]
        item_types = self._discover_item_types(project_keys, warnings)
        statuses = self._discover_statuses(project_keys, selected_item_types, warnings)
        return ScopeConfigOptions(
            projects=projects,
            item_types=item_types,
            statuses=statuses,
            resolutions=self._discover_global_options('get_all_resolutions', 'resolution', warnings),
            priorities=self._discover_global_options('get_all_priorities', 'priority', warnings),
            fields=self._discover_fields(warnings),
            components=self._discover_project_options(project_keys, 'get_project_components', 'component', warnings),
            versions=self._discover_project_options(project_keys, 'get_project_versions', 'version', warnings),
            warnings=warnings,
        )

    def discover_field_values(self, project_id: str, item_type_ids: list[str], field_id: str) -> list[TrackerOption]:
        if field_id in {'components', 'component'}:
            return self._discover_project_options([project_id], 'get_project_components', 'component', [])
        if field_id in {'fixVersions', 'versions'}:
            return self._discover_project_options([project_id], 'get_project_versions', 'version', [])
        if field_id == 'priority':
            return self._discover_global_options('get_all_priorities', 'priority', [])
        if not hasattr(self._jira_client, 'get_custom_field_options'):
            return []
        return self._to_options(
            self._jira_client.get_custom_field_options(
                self._custom_field_numeric_id(field_id),
                self._project_numeric_id(project_id),
                self._numeric_ids(item_type_ids) or None,
            ),
            'custom field',
            project_id,
        )

    def _parse_project_keys(self, query: str) -> list[str]:
        equal_match = re.search(r'\bproject\s*=\s*(["\']?[A-Z0-9][A-Z0-9_-]*["\']?)', query, re.IGNORECASE)
        if equal_match:
            return [self._clean_project_token(equal_match.group(1))]
        in_match = re.search(r'\bproject\s+in\s*\(([^)]+)\)', query, re.IGNORECASE)
        if not in_match:
            return []
        return [self._clean_project_token(part) for part in in_match.group(1).split(',') if part.strip()]

    def _clean_project_token(self, raw_token: str) -> str:
        return raw_token.strip().strip('"\'')

    def _discover_item_types(self, project_keys: list[str], warnings: list[str]) -> list[TrackerOption]:
        options = []
        for project_key in project_keys:
            try:
                payload = self._jira_client.issue_createmeta_issuetypes(project_key)
            except Exception as error:
                warnings.append(f'Unable to load issue types for {project_key}: {error}')
                continue
            options.extend(self._to_options(self._issue_type_payload(payload), 'issue type', project_key))
        return self._deduplicate_options(options)

    def _discover_statuses(self, project_keys: list[str], selected_item_types: list[str], warnings: list[str]) -> list[TrackerOption]:
        options = []
        if not hasattr(self._jira_client, 'get_status_for_project'):
            warnings.append('Jira client does not expose project status metadata.')
            return options
        for project_key in project_keys:
            try:
                payload = self._jira_client.get_status_for_project(project_key)
            except Exception as error:
                warnings.append(f'Unable to load statuses for {project_key}: {error}')
                continue
            options.extend(self._status_options(payload, project_key, selected_item_types))
        return self._deduplicate_options(options)

    def _discover_global_options(self, method_name: str, source_name: str, warnings: list[str]) -> list[TrackerOption]:
        if not hasattr(self._jira_client, method_name):
            warnings.append(f'Jira client does not expose {source_name} metadata.')
            return []
        try:
            return self._deduplicate_options(self._to_options(getattr(self._jira_client, method_name)(), source_name, 'global'))
        except Exception as error:
            warnings.append(f'Unable to load {source_name} metadata: {error}')
            return []

    def _discover_project_options(self, project_keys: list[str], method_name: str, source_name: str, warnings: list[str]) -> list[TrackerOption]:
        if not hasattr(self._jira_client, method_name):
            warnings.append(f'Jira client does not expose {source_name} metadata.')
            return []
        options = []
        for project_key in project_keys:
            try:
                options.extend(self._to_options(getattr(self._jira_client, method_name)(project_key), source_name, project_key))
            except Exception as error:
                warnings.append(f'Unable to load {source_name} metadata for {project_key}: {error}')
        return self._deduplicate_options(options)

    def _discover_fields(self, warnings: list[str]) -> list[TrackerFieldOption]:
        if not hasattr(self._jira_client, 'get_all_fields'):
            warnings.append('Jira client does not expose field metadata.')
            return []
        try:
            return self._deduplicate_fields([self._to_field_option(field) for field in self._jira_client.get_all_fields()])
        except Exception as error:
            warnings.append(f'Unable to load field metadata: {error}')
            return []

    def _issue_type_payload(self, payload):
        if isinstance(payload, dict):
            if 'issuetypes' in payload:
                return payload['issuetypes']
            if 'projects' in payload:
                return [issue_type for project in payload['projects'] for issue_type in project.get('issuetypes', [])]
        return payload

    def _status_options(self, payload, project_key: str, selected_item_types: list[str]) -> list[TrackerOption]:
        options = []
        for item_type in payload or []:
            item_type_name = self._name(item_type)
            if selected_item_types and item_type_name not in selected_item_types and str(item_type.get('id', '')) not in selected_item_types:
                continue
            for status in item_type.get('statuses', []):
                option = self._to_option(status, 'status', f'{project_key} · {item_type_name}')
                options.append(option)
        return options

    def _to_options(self, payload, source_name: str, source_context: str) -> list[TrackerOption]:
        return [self._to_option(item, source_name, source_context) for item in payload or []]

    def _to_option(self, item, source_name: str, source_context: str) -> TrackerOption:
        if isinstance(item, dict):
            option_id = str(item.get('id') or item.get('key') or item.get('name') or item.get('value') or '')
            name = self._name(item)
        else:
            option_id = str(item)
            name = str(item)
        return TrackerOption(id=option_id or name, name=name, label=name, source=f'{source_context} {source_name}'.strip())

    def _to_field_option(self, field) -> TrackerFieldOption:
        field_id = str(field.get('id') or field.get('key') or field.get('name') or '')
        name = self._name(field)
        schema = field.get('schema') or {}
        field_type = schema.get('type') or schema.get('custom') or ''
        return TrackerFieldOption(id=field_id or name, name=name, label=f'{name} ({field_id})' if field_id else name, field_type=field_type, source='global field')

    def _name(self, item) -> str:
        if not isinstance(item, dict):
            return str(item)
        return str(item.get('name') or item.get('displayName') or item.get('value') or item.get('key') or item.get('id') or '')

    def _custom_field_numeric_id(self, field_id: str) -> str:
        match = re.fullmatch(r'customfield_(\d+)', str(field_id))
        return match.group(1) if match else str(field_id)

    def _project_numeric_id(self, project_id: str) -> str:
        if str(project_id).isdecimal():
            return str(project_id)
        project = self._jira_client.get_project(project_id)
        return str(project.get('id') or project_id) if isinstance(project, dict) else str(project_id)

    def _numeric_ids(self, raw_ids: list[str]) -> list[str]:
        return [str(raw_id) for raw_id in raw_ids if str(raw_id).isdecimal()]

    def _deduplicate_options(self, options: list[TrackerOption]) -> list[TrackerOption]:
        seen = set()
        result = []
        for option in options:
            key = (option.id, option.name, option.source)
            if key not in seen:
                seen.add(key)
                result.append(option)
        return result

    def _deduplicate_fields(self, fields: list[TrackerFieldOption]) -> list[TrackerFieldOption]:
        seen = set()
        result = []
        for field in fields:
            if field.id not in seen:
                seen.add(field.id)
                result.append(field)
        return result