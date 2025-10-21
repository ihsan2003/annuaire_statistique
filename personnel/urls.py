from django.urls import path
from . import views 
from .views import list_personnel, get_delegations_by_region

urlpatterns = [
    path('personnel/', list_personnel, name='personnel'),
    path('ajax/get-delegations/', get_delegations_by_region, name='get_delegations_by_region'),

]