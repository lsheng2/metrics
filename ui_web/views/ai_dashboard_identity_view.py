from django.http import JsonResponse
from django.views import View


class AiDashboardIdentityApiView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({
            'contract_version': '0.2',
            'serviceId': 'metrics-dashboard-service',
            'profileId': 'metrics-dashboard',
            'capabilities': {
                'dashboardQuery': True,
                'metricsConnector': True,
                'grafanaOperations': True,
            },
        })
