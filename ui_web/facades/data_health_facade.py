from ..data.data_health_data import DataHealthPageData


class DataHealthFacade:
    def __init__(self, jira_sync_api, bug_trend_api):
        self._jira_sync_api = jira_sync_api
        self._bug_trend_api = bug_trend_api

    def get_data_health(self) -> DataHealthPageData:
        sync_health = self._jira_sync_api.list_sync_health()
        calculation_health = self._bug_trend_api.list_calculation_health()
        provider_sync_health = self._bug_trend_api.list_provider_sync_health()
        ai_sidecar_status = self._bug_trend_api.get_ai_sidecar_status()
        return DataHealthPageData(
            sync_health=sync_health,
            calculation_health=calculation_health,
            provider_sync_health=provider_sync_health,
            ai_sidecar_status=ai_sidecar_status,
            scope_count=len(calculation_health),
            stale_scope_count=sum(1 for item in calculation_health if item.freshness_status == 'stale_config'),
            failed_sync_count=sum(1 for item in sync_health if item.status == 'failed'),
            failed_provider_sync_count=sum(1 for item in provider_sync_health if item['status'] == 'failed'),
            failed_calculation_count=sum(1 for item in calculation_health if item.status == 'failed'),
        )
