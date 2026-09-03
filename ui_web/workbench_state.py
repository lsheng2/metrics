from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class WorkbenchListFilters:
    text: str = ''
    status: str = ''
    severity: str = ''
    owner: str = ''
    component: str = ''

    @classmethod
    def from_query(cls, query):
        return cls(
            text=str(query.get('text', '') or ''),
            status=str(query.get('status', '') or ''),
            severity=str(query.get('severity', '') or ''),
            owner=str(query.get('owner', '') or ''),
            component=str(query.get('component', '') or ''),
        )

    def to_query_params(self) -> dict:
        return {
            key: value
            for key, value in {
                'text': self.text,
                'status': self.status,
                'severity': self.severity,
                'owner': self.owner,
                'component': self.component,
            }.items()
            if value
        }


@dataclass(frozen=True, slots=True)
class WorkbenchPageQueryState:
    scope_id: str = ''
    profile_id: str = 'chiplet-2a-jira'
    provider_id: str = ''
    range_mode: str = 'ww'
    begin: str = ''
    end: str = ''
    chart_id: str = 'default_bug_trend'
    chart_version: str = '1'
    calculation_run_id: str = ''
    fact_snapshot_id: str = ''
    selected_bucket_id: str = ''
    selected_series_name: str = ''
    list_filters: WorkbenchListFilters = field(default_factory=WorkbenchListFilters)

    @classmethod
    def from_query(cls, query):
        return cls(
            scope_id=str(query.get('scope_id', '') or ''),
            profile_id=str(query.get('profile_id', '') or 'chiplet-2a-jira'),
            provider_id=str(query.get('provider_id', '') or ''),
            range_mode=str(query.get('range_mode', '') or 'ww'),
            begin=str(query.get('begin', '') or ''),
            end=str(query.get('end', '') or ''),
            chart_id=str(query.get('chart_id', '') or 'default_bug_trend'),
            chart_version=str(query.get('chart_version', '') or '1'),
            calculation_run_id=str(query.get('run', query.get('calculation_run_id', '')) or ''),
            fact_snapshot_id=str(query.get('snapshot', query.get('fact_snapshot_id', '')) or ''),
            selected_bucket_id=str(query.get('bucket', query.get('selected_bucket_id', '')) or ''),
            selected_series_name=str(query.get('series', query.get('selected_series_name', '')) or ''),
            list_filters=WorkbenchListFilters.from_query(query),
        )

    def to_query_params(self, include_selection: bool = True, include_list_filters: bool = True) -> dict:
        params = {
            'profile_id': self.profile_id,
            'scope_id': self.scope_id,
            'provider_id': self.provider_id,
            'range_mode': self.range_mode,
            'begin': self.begin,
            'end': self.end,
            'chart_id': self.chart_id,
            'chart_version': self.chart_version,
            'run': self.calculation_run_id,
            'snapshot': self.fact_snapshot_id,
        }
        if include_selection:
            params['bucket'] = self.selected_bucket_id
            params['series'] = self.selected_series_name
        if include_list_filters:
            params.update(self.list_filters.to_query_params())
        return {key: value for key, value in params.items() if value}

    def chart_query_params(self) -> dict:
        return self.to_query_params(include_selection=False, include_list_filters=False)

    def evidence_query_params(self) -> dict:
        return self.to_query_params(include_selection=True, include_list_filters=True)

    def cleared_selection(self):
        return WorkbenchPageQueryState(
            profile_id=self.profile_id,
            scope_id=self.scope_id,
            provider_id=self.provider_id,
            range_mode=self.range_mode,
            begin=self.begin,
            end=self.end,
            chart_id=self.chart_id,
            chart_version=self.chart_version,
            calculation_run_id=self.calculation_run_id,
            fact_snapshot_id=self.fact_snapshot_id,
            list_filters=self.list_filters,
        )

    def selection_validation_error(self) -> str:
        if self.chart_version and not self.chart_version.isdecimal():
            return 'chart_version must be an integer.'
        has_selection_value = bool(self.selected_bucket_id or self.selected_series_name)
        if not has_selection_value:
            return ''
        if not self.selected_bucket_id or not self.selected_series_name:
            return 'Chart evidence selection requires both bucket and series.'
        if not self.calculation_run_id and not self.fact_snapshot_id:
            return 'Chart evidence selection requires a calculation run or fact snapshot.'
        return ''
