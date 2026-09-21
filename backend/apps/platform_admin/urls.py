from django.urls import path
from apps.platform_admin.views import (
    login_view,
    logout_view,
    dashboard_view,
    organizations_list_view,
    organization_create_view,
    organization_detail_view,
    organization_edit_view,
    organization_suspend_view,
    organization_activate_view,
    organization_subscription_view,
    support_enter_view,
    support_exit_view,
    support_inspection_view,
    users_list_view,
    admins_list_view,
    admin_create_view,
    user_toggle_status_view,
    user_reset_password_view,
    subscriptions_list_view,
    plans_list_view,
    plan_create_view,
    plan_edit_view,
    plan_toggle_status_view,
    plan_delete_view,
    audit_logs_view,
    global_search_view,
    platform_settings_view,
)

app_name = 'platform_admin'

urlpatterns = [
    # Auth
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    # Dashboard
    path('', dashboard_view, name='dashboard'),

    # Organizations
    path('organizations/', organizations_list_view, name='organizations_list'),
    path('organizations/create/', organization_create_view, name='organization_create'),
    path('organizations/<int:pk>/', organization_detail_view, name='organization_detail'),
    path('organizations/<int:pk>/edit/', organization_edit_view, name='organization_edit'),
    path('organizations/<int:pk>/suspend/', organization_suspend_view, name='organization_suspend'),
    path('organizations/<int:pk>/activate/', organization_activate_view, name='organization_activate'),
    path('organizations/<int:pk>/subscription/', organization_subscription_view, name='organization_subscription'),
    path('organizations/<int:pk>/support-enter/', support_enter_view, name='support_enter'),
    path('organizations/<int:pk>/inspect/', support_inspection_view, name='support_inspection'),

    # Support Session Exit
    path('support-exit/', support_exit_view, name='support_exit'),

    # Users
    path('users/', users_list_view, name='users_list'),
    path('users/admins/', admins_list_view, name='admins_list'),
    path('users/create-admin/', admin_create_view, name='admin_create'),
    path('users/<int:pk>/toggle-status/', user_toggle_status_view, name='user_toggle_status'),
    path('users/<int:pk>/reset-password/', user_reset_password_view, name='user_reset_password'),

    # Subscriptions & Plans
    path('subscriptions/', subscriptions_list_view, name='subscriptions_list'),
    path('subscriptions/plans/', plans_list_view, name='plans_list'),
    path('subscriptions/plans/create/', plan_create_view, name='plan_create'),
    path('subscriptions/plans/<int:pk>/edit/', plan_edit_view, name='plan_edit'),
    path('subscriptions/plans/<int:pk>/toggle-status/', plan_toggle_status_view, name='plan_toggle_status'),
    path('subscriptions/plans/<int:pk>/delete/', plan_delete_view, name='plan_delete'),

    # Audit & Search & Settings
    path('audit-logs/', audit_logs_view, name='audit_logs'),
    path('search/', global_search_view, name='global_search'),
    path('settings/', platform_settings_view, name='settings'),
]
