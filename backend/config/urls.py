from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.core.views import (
    dashboard_view, school_settings_view, audit_logs_view, public_qr_verify_view,
    client_management_view, client_create_view, client_edit_view, client_delete_view, switch_client_view,
    landing_page_view
)
from apps.accounts.views import admin_login_view, admin_logout_view, teachers_list_view
from apps.academic.views import academic_years_view, classes_sections_view
from apps.students.views import (
    students_list_view, student_detail_view, student_create_edit_view,
    student_delete_view, excel_import_view, excel_template_download_view,
    excel_export_view, bulk_photos_view, verification_queue_view
)
from apps.idcards.views import (
    templates_list_view, template_designer_view, template_duplicate_view,
    template_new_version_view, template_preview_students_view,
    print_center_view, cards_history_view, revoke_card_view
)

urlpatterns = [
    # Django Admin
    path('django-admin/', admin.site.urls),

    # Web Admin Authentication
    path('login/', admin_login_view, name='admin_login'),
    path('logout/', admin_logout_view, name='admin_logout'),

    # Public Landing Page
    path('', landing_page_view, name='landing_page'),
    path('home/', landing_page_view, name='landing_home'),

    # Core & Dashboard
    path('dashboard/', dashboard_view, name='dashboard'),
    path('school-settings/', school_settings_view, name='school_settings'),
    path('organization-settings/', school_settings_view, name='organization_settings'),
    path('audit-logs/', audit_logs_view, name='audit_logs'),

    # Multi-Client Management for Photo Studios & Commercial Presses
    path('clients/', client_management_view, name='client_management'),
    path('clients/create/', client_create_view, name='client_create'),
    path('clients/<int:pk>/edit/', client_edit_view, name='client_edit'),
    path('clients/<int:pk>/delete/', client_delete_view, name='client_delete'),
    path('clients/switch/<int:pk>/', switch_client_view, name='switch_client'),

    # Public QR Code Verification Endpoint (scanned by camera or mobile app)
    path('verify/<str:token>/', public_qr_verify_view, name='public_qr_verify'),

    # Academic Structure
    path('academic-years/', academic_years_view, name='academic_years'),
    path('classes-sections/', classes_sections_view, name='classes_sections'),

    # Teacher Management
    path('teachers/', teachers_list_view, name='teachers_list'),

    # Students & Operations
    path('students/', students_list_view, name='students_list'),
    path('students/new/', student_create_edit_view, name='student_create'),
    path('students/<int:pk>/', student_detail_view, name='student_detail'),
    path('students/<int:pk>/edit/', student_create_edit_view, name='student_edit'),
    path('students/<int:pk>/delete/', student_delete_view, name='student_delete'),
    path('excel-import/', excel_import_view, name='excel_import'),
    path('excel-template/', excel_template_download_view, name='excel_template_download'),
    path('excel-export/', excel_export_view, name='excel_export'),
    path('bulk-photos/', bulk_photos_view, name='bulk_photos'),
    path('verification-queue/', verification_queue_view, name='verification_queue'),

    # ID Cards, Designer, Printing
    path('templates/', templates_list_view, name='templates_list'),
    path('templates/<int:pk>/designer/', template_designer_view, name='template_designer'),
    path('templates/<int:pk>/duplicate/', template_duplicate_view, name='template_duplicate'),
    path('templates/<int:pk>/new-version/', template_new_version_view, name='template_new_version'),
    path('templates/<int:pk>/preview-students/', template_preview_students_view, name='template_preview_students'),
    path('print-center/', print_center_view, name='print_center'),
    path('cards-history/', cards_history_view, name='cards_history'),
    path('cards/<int:pk>/revoke/', revoke_card_view, name='revoke_card'),

    # REST API for Teacher Mobile Application
    path('api/', include('apps.api.urls')),

    # Platform Super Administrator Portal
    path('platform-admin/', include('apps.platform_admin.urls', namespace='platform_admin')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    from django.views.static import serve
    from django.urls import re_path
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]

