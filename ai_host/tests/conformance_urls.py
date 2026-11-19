from django.http import JsonResponse
from django.urls import path


VISITS = []


def identity(request):
    VISITS.append(request.metrics_basic_auth_username)
    return JsonResponse({'principal': request.metrics_basic_auth_username})


urlpatterns = [path('django-identity/', identity)]
