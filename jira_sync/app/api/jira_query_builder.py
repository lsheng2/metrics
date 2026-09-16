from bug_metrics.model_hashes import normalize_query_builder_state


class JiraScopeQueryBuilder:
    FIELD_ORDER = (
        ('project', 'project'),
        ('issue_types', 'issuetype'),
        ('components', 'components'),
        ('affected_versions', 'versions'),
        ('fix_versions', 'fixVersions'),
        ('priorities', 'priority'),
        ('resolutions', 'resolution'),
        ('security_levels', 'security'),
        ('labels', 'labels'),
    )

    def build(self, builder_state: dict) -> str:
        state = normalize_query_builder_state(builder_state)
        clauses = []
        project = state.get('project', '')
        if project:
            clauses.append(self._clause('project', [project]))
        for state_key, jql_field in self.FIELD_ORDER[1:]:
            clauses.extend(self._field_clauses(jql_field, state.get(state_key, [])))
        for custom_field in state.get('custom_fields', []):
            clauses.extend(self._field_clauses(custom_field.get('field', ''), custom_field.get('values', [])))
        return ' AND '.join(clauses)

    def _field_clauses(self, field_name: str, values: list[str]) -> list[str]:
        field_name = str(field_name or '').strip()
        if not field_name or not values:
            return []
        return [self._clause(field_name, values)]

    def _clause(self, field_name: str, values: list[str]) -> str:
        if len(values) == 1:
            return f'{field_name} = {self._quote_value(values[0])}'
        return f'{field_name} in ({", ".join(self._quote_value(value) for value in values)})'

    def _quote_value(self, value: str) -> str:
        text = str(value)
        if self._can_use_bare_value(text):
            return text
        escaped_text = text.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped_text}"'

    def _can_use_bare_value(self, value: str) -> bool:
        if not value:
            return False
        return all(character.isalnum() or character in {'_', '-', '.'} for character in value)
