from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from apps.api.views import (
    CustomLoginView,
    TeacherProfileView,
    ChangePasswordView,
    TeacherDashboardStatsView,
    TeacherStudentListView,
    TeacherStudentDetailView,
    TeacherStudentCreateView,
    TeacherStudentUpdateView,
    TeacherStudentPhotoUploadView,
    TeacherStudentSubmitVerificationView,
    VerifyQRTokenView,
    AppConfigView,
    ClassesSectionsListView,
)

urlpatterns = [
    # Authentication
    path('auth/login/', CustomLoginView.as_view(), name='api_login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='api_token_refresh'),
    path('teacher/profile/', TeacherProfileView.as_view(), name='api_teacher_profile'),
    path('teacher/change-password/', ChangePasswordView.as_view(), name='api_teacher_change_password'),

    # Academic Reference Data
    path('academic/classes-sections/', ClassesSectionsListView.as_view(), name='api_classes_sections'),

    # Teacher Dashboard & Students
    path('teacher/dashboard/', TeacherDashboardStatsView.as_view(), name='api_teacher_dashboard'),
    path('teacher/students/', TeacherStudentListView.as_view(), name='api_teacher_students'),
    path('teacher/students/create/', TeacherStudentCreateView.as_view(), name='api_teacher_student_create'),
    path('teacher/students/<int:pk>/', TeacherStudentDetailView.as_view(), name='api_teacher_student_detail'),
    path('teacher/students/<int:pk>/update/', TeacherStudentUpdateView.as_view(), name='api_teacher_student_update'),
    path('teacher/students/<int:pk>/photo/', TeacherStudentPhotoUploadView.as_view(), name='api_teacher_student_photo'),
    path('teacher/students/<int:pk>/submit-verification/', TeacherStudentSubmitVerificationView.as_view(), name='api_teacher_student_submit'),

    # QR Verification Endpoint (Scanned token)
    path('verify-qr/<str:token>/', VerifyQRTokenView.as_view(), name='api_verify_qr'),

    # Central App Configuration & About Metadata
    path('app-config/', AppConfigView.as_view(), name='api_app_config'),
]
