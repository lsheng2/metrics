from bug_metrics.app.api import bug_trend_api


class BugMetricsContainer:
    @property
    def bug_trend_api(self):
        return bug_trend_api


bug_metrics_container = BugMetricsContainer()
