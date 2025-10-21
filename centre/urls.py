from django.urls import path
from . import views 
from .views import list_centre, get_delegations_by_region, repartition_centres_api, centres_api

urlpatterns = [
    path('centres/', list_centre, name='centres'),
    path('api/repartition-centres/', repartition_centres_api, name='repartition_centres_api'),
    path('api/centres/', centres_api, name='api_centres'),
    path("api/regions/", views.regions_api, name="api_regions"),
    path("api/delegations/", views.delegations_api, name="api_delegations"),
    path('ajax/get-delegations/', get_delegations_by_region, name='get_delegations_by_region'),
    
]