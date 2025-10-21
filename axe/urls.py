from django.urls import path
from . import views 
from .views import list_axe, get_delegations_by_region

urlpatterns = [
    path('axe&programme/', list_axe, name='axe&programme'),
    path('ajax/get-delegations/', get_delegations_by_region, name='get_delegations_by_region'),

]