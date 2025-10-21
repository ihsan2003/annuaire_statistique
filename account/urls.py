# account/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import profile_view, home_view, user_list, add_user, edit_user, delete_user, CustomPasswordChangeView, admin_dashboard, user_dashboard, dashboard_api_stats, dashboard_clear_cache, dashboard_api_system_info
#SignUpView, profile_view, user_list, add_user, edit_user, delete_user, CustomPasswordChangeView, 

urlpatterns = [

    # API endpoints pour le dashboard
    path('api/dashboard/stats/', dashboard_api_stats, name='dashboard_api_stats'),
    path('api/dashboard/clear-cache/', dashboard_clear_cache, name='dashboard_clear_cache'),
    path('dashboard/api/system-info/', dashboard_api_system_info, name='dashboard_api_system_info'),

 
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    path('user-dashboard/', user_dashboard, name='user_dashboard'),
    path('home/', home_view, name='home'),
    path('profile/', profile_view, name='profile'),
    path('settings/users/', user_list, name='user_list'),
    path('settings/users/add/', add_user, name='add_user'),
    path('settings/users/edit/<int:user_id>/', edit_user, name='edit_user'),
    path('settings/users/delete/<int:user_id>/', delete_user, name='delete_user'),
    


    # Changement de mot de passe
    path("settings/users/password_change/", CustomPasswordChangeView.as_view(), name="user_password_change"),
    path('settings/users/password_change_done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='users/password_change_done.html'
    ), name='user_password_change_done'),

    # Réinitialisation du mot de passe
    #path('settings/users/password_reset/', auth_views.PasswordResetView.as_view(
        #template_name='registration/password_reset_form.html'
    #), name='password_reset'),
    #path('settings/users/password_reset_done/', auth_views.PasswordResetDoneView.as_view(
    #    template_name='registration/password_reset_done.html'
    #), name='password_reset_done'),
    #path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
    #    template_name='registration/password_reset_confirm.html'
    #), name='password_reset_confirm'),
    #path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
    #    template_name='registration/password_reset_complete.html'
    #), name='password_reset_complete'),
]