class BugTrendAiFacadeMixin:
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

    def get_ai_sidecar_status_payload(self) -> dict:
        return self._bug_trend_api.get_ai_sidecar_status()

    def validate_ai_dashboard_composition_intent(self, request) -> dict:
        return self._bug_trend_api.validate_ai_dashboard_composition_intent(request)

    def run_ai_dashboard_workflow(self, request) -> dict:
        return self._bug_trend_api.run_ai_dashboard_workflow(request)

    def validate_ai_dashboard_render_config_draft(self, draft_render_config: dict) -> dict:
        return self._bug_trend_api.validate_ai_dashboard_render_config_draft(draft_render_config)

    def validate_ai_dashboard_workspace_artifact(self, request) -> dict:
        return self._bug_trend_api.validate_ai_dashboard_workspace_artifact(request)

    def validate_ai_gcx_publication_precondition(self, request) -> dict:
        return self._bug_trend_api.validate_ai_gcx_publication_precondition(request)

    def record_ai_gcx_publication_callback(self, request) -> dict:
        return self._bug_trend_api.record_ai_gcx_publication_callback(request)

    def publish_ai_grafana_dashboard_demo(self, request, correlation_id: str) -> dict:
        return self._bug_trend_api.publish_ai_grafana_dashboard_demo(request, correlation_id)

    def request_ai_grafana_publish_approval(self, request) -> dict:
        return self._bug_trend_api.request_ai_grafana_publish_approval(request)

    def decide_ai_grafana_publish_approval(self, approval_id: str, decision: str, actor: str) -> dict:
        return self._bug_trend_api.decide_ai_grafana_publish_approval(approval_id, decision, actor)

    def get_ai_grafana_publish_approval(self, approval_id: str) -> dict:
        return self._bug_trend_api.get_ai_grafana_publish_approval(approval_id)

    def list_ai_grafana_publish_history(self, limit: int = 25) -> dict:
        return self._bug_trend_api.list_ai_grafana_publish_history(limit)

    def get_ai_dashboard_context_payload(self, query) -> dict:
        return self._bug_trend_api.get_ai_dashboard_context(query)

    def get_ai_workspace_context_bundle_payload(self, profile_id: str) -> dict:
        return self._bug_trend_api.get_ai_workspace_context_bundle(profile_id)
