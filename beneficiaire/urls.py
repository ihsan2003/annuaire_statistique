from django.urls import path
from . import views 
from .views import list_benefic, get_delegations_by_region, repartition_beneficiaires_api

urlpatterns = [
    path('beneficiaires/', list_benefic, name='beneficiaires'),
    path('ajax/get-delegations/', get_delegations_by_region, name='get_delegations_by_region'),
    path('api/repartition-beneficiaires/', repartition_beneficiaires_api, name='repartition_beneficiaires_api'),

]
