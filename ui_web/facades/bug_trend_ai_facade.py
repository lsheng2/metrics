class BugTrendAiFacadeMixin:
    def evaluate_ai_chart_workflow(self, request):
        return self._bug_trend_api.evaluate_ai_chart_workflow(request)

    def get_ai_chart_publications(self, limit=25):
        return self._bug_trend_api.list_ai_chart_publications(limit)
    def get_provider_chart_payload(self, provider_id: str, profile_id: str, begin_ww: str, end_ww: str,
                                   chart_id: str, chart_version: int = 1, fact_snapshot_id: str = '',
                                   range_mode: str = 'ww', begin_date: str = '', end_date: str = '') -> dict:
        return self._provider_dashboard_facade.get_provider_chart_payload(provider_id, profile_id, begin_ww, end_ww, chart_id, chart_version, fact_snapshot_id, range_mode, begin_date, end_date)

    def get_provider_chart_evidence_payload(self, provider_id: str, profile_id: str, begin_ww: str, end_ww: str,
                                            chart_id: str, calculation_run_id: str, bucket_id: str = '',
                                            series_name: str = '', chart_version: int = 1, fact_snapshot_id: str = '',
                                            owner: str = '', status: str = '', severity: str = '',
                                            component: str = '', text: str = '', range_mode: str = 'ww',
                                            begin_date: str = '', end_date: str = '') -> dict:
        return self._provider_dashboard_facade.get_provider_chart_evidence_payload(provider_id, profile_id, begin_ww, end_ww, chart_id, calculation_run_id, bucket_id, series_name, chart_version, fact_snapshot_id, owner, status, severity, component, text, range_mode, begin_date, end_date)

    def get_provider_profile_readiness_payload(self, provider_id: str, profile_id: str, range_mode: str = 'ww',
                                               begin_ww: str = '', end_ww: str = '', begin_date: str = '',
                                               end_date: str = '') -> dict:
        return self._provider_dashboard_facade.get_provider_profile_readiness_payload(provider_id, profile_id, range_mode, begin_ww, end_ww, begin_date, end_date)

    def get_provider_profile_time_range_action_url(self, provider_id: str, profile_id: str, range_mode: str = 'ww',
                                                   begin_ww: str = '', end_ww: str = '', begin_date: str = '',
                                                   end_date: str = '') -> str:
        return self._provider_dashboard_facade.get_provider_profile_time_range_action_url(provider_id, profile_id, range_mode, begin_ww, end_ww, begin_date, end_date)

    def get_ai_dashboard_catalog_payload(self, profile_id: str = '') -> dict:
        return self._bug_trend_api.list_ai_dashboard_composition_catalog(profile_id)
