from django.contrib.auth import authenticate
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from rest_framework import status, views, generics, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import TeacherProfile
from apps.academic.models import ClassLevel
from apps.students.models import Student, VerificationRecord
from apps.idcards.models import IDCard
from apps.core.models import School
from apps.core.services.audit import log_action
from apps.students.services.photo_service import process_student_photo
from apps.api.permissions import IsTeacherUser, IsAssignedTeacher
from apps.api.serializers import (
    TeacherProfileSerializer,
    StudentListSerializer,
    StudentDetailSerializer,
    StudentPermittedUpdateSerializer,
    TeacherStudentCreateSerializer,
    QRVerificationResultSerializer,
    ClassLevelWithSectionsSerializer,
)


class CustomLoginView(views.APIView):
    """
    Secure JWT authentication endpoint.
    Verifies user credentials, blocks inactive teachers, and returns tokens + profile info.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')

        if not username or not password:
            return Response(
                {'error': 'Both username and password are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(username=username, password=password)
        if not user:
            return Response(
                {'error': 'Invalid username or password.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {'error': 'This user account has been disabled. Please contact administrator.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check organization suspension
        org = getattr(user, 'organization', None)
        if not org and not (user.is_superuser or getattr(user, 'role', '') == 'SUPER_ADMIN'):
            from apps.platform_admin.models import Organization
            org = Organization.objects.filter(school_id=1).first()

        if org and org.status == 'SUSPENDED':
            return Response(
                {
                    'error': 'organization_suspended',
                    'message': f"Access Denied: Organization '{org.name}' ({org.org_id}) is currently suspended. Please contact platform support."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Check teacher profile active status and mobile app enabled
        if user.role == 'TEACHER':
            profile = getattr(user, 'teacher_profile', None)
            if not profile or profile.status != 'ACTIVE':
                return Response(
                    {'error': 'Your teacher account is deactivated. Please contact administration.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            teacher_client = getattr(profile, 'client', None)
            if teacher_client is not None:
                if not teacher_client.uses_mobile_app:
                    return Response(
                        {
                            'error': 'mobile_app_disabled',
                            'detail': f"Mobile application access has been disabled for {teacher_client.name}."
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )
            elif org and not org.uses_mobile_app:
                return Response(
                    {
                        'error': 'mobile_app_disabled',
                        'detail': f"Mobile application access has been disabled for {org.name}."
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        refresh = RefreshToken.for_user(user)
        log_action(
            user=user,
            action='TEACHER_LOGIN' if user.role == 'TEACHER' else 'ADMIN_LOGIN',
            object_type='User',
            object_id=user.id,
            object_repr=user.username,
            details={'client': 'Mobile App / REST API'},
            request=request
        )

        profile_data = None
        if hasattr(user, 'teacher_profile'):
            profile_data = TeacherProfileSerializer(user.teacher_profile, context={'request': request}).data

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'role': user.role,
            },
            'teacher_profile': profile_data
        })


class TeacherProfileView(views.APIView):
    permission_classes = [IsTeacherUser]

    def get(self, request):
        if not hasattr(request.user, 'teacher_profile'):
            return Response({'error': 'Teacher profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = TeacherProfileSerializer(request.user.teacher_profile, context={'request': request})
        return Response(serializer.data)


class ChangePasswordView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        current_password = request.data.get('current_password', '')
        new_password = request.data.get('new_password', '')

        if not request.user.check_password(current_password):
            return Response({'error': 'Current password does not match.'}, status=status.HTTP_400_BAD_REQUEST)

        if len(new_password) < 6:
            return Response({'error': 'New password must be at least 6 characters.'}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(new_password)
        request.user.save()
        log_action(
            user=request.user,
            action='STUDENT_EDITED',
            object_type='User',
            object_id=request.user.id,
            object_repr=request.user.username,
            details={'action': 'password_changed'},
            request=request
        )
        return Response({'message': 'Password changed successfully.'})


class TeacherDashboardStatsView(views.APIView):
    permission_classes = [IsTeacherUser]

    def get(self, request):
        user_org = getattr(request.user, 'organization', None)

        if request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN':
            qs = Student.objects.all()
            if user_org:
                qs = qs.filter(organization=user_org)
            elif not request.user.is_superuser:
                qs = qs.filter(organization__isnull=True)

            total = qs.count()
            verified = qs.filter(verification_status='VERIFIED').count()
            submitted = qs.filter(verification_status='SUBMITTED').count()
            pending = qs.filter(verification_status='PENDING').count()
            rejected = qs.filter(verification_status='REJECTED').count()
            missing_photos = qs.filter(Q(photo='') | Q(photo__isnull=True)).count()

            return Response({
                'has_assigned_class': True,
                'assigned_class_id': None,
                'assigned_class_name': 'All Classes',
                'assigned_section_id': None,
                'assigned_section_name': 'All Sections',
                'teacher_name': request.user.get_full_name() or request.user.username,
                'total_students': total,
                'verified_count': verified,
                'submitted_count': submitted,
                'pending_count': pending,
                'rejected_count': rejected,
                'missing_photos_count': missing_photos,
            })

        profile = getattr(request.user, 'teacher_profile', None)
        if not profile or not profile.assigned_class or not profile.assigned_section:
            return Response({
                'has_assigned_class': False,
                'message': 'No class or section assigned currently.',
                'assigned_class_name': '',
                'assigned_section_name': '',
                'total_students': 0,
                'verified_count': 0,
                'submitted_count': 0,
                'pending_count': 0,
                'rejected_count': 0,
                'missing_photos_count': 0,
            })

        qs = Student.objects.filter(
            class_level=profile.assigned_class,
            section=profile.assigned_section
        )
        if user_org:
            qs = qs.filter(organization=user_org)
        elif not request.user.is_superuser:
            qs = qs.filter(organization__isnull=True)
        if getattr(profile, 'client_id', None):
            qs = qs.filter(client_id=profile.client_id)

        total = qs.count()
        verified = qs.filter(verification_status='VERIFIED').count()
        submitted = qs.filter(verification_status='SUBMITTED').count()
        pending = qs.filter(verification_status='PENDING').count()
        rejected = qs.filter(verification_status='REJECTED').count()
        missing_photos = qs.filter(Q(photo='') | Q(photo__isnull=True)).count()

        return Response({
            'has_assigned_class': True,
            'assigned_class_id': profile.assigned_class.id,
            'assigned_class_name': profile.assigned_class.name,
            'assigned_section_id': profile.assigned_section.id,
            'assigned_section_name': profile.assigned_section.name,
            'teacher_name': request.user.get_full_name() or request.user.username,
            'total_students': total,
            'verified_count': verified,
            'submitted_count': submitted,
            'pending_count': pending,
            'rejected_count': rejected,
            'missing_photos_count': missing_photos,
        })


class TeacherStudentListView(generics.ListAPIView):
    """
    Lists students strictly scoped to teacher's assigned class/section (or all for admin).
    Supports search (name, student_id, roll) and verification_status filter.
    """
    serializer_class = StudentListSerializer
    permission_classes = [IsTeacherUser]

    def get_queryset(self):
        user_org = getattr(self.request.user, 'organization', None)

        if self.request.user.is_superuser or getattr(self.request.user, 'role', '') == 'ADMIN':
            qs = Student.objects.all().select_related('class_level', 'section')
            if user_org:
                qs = qs.filter(organization=user_org)
            elif not self.request.user.is_superuser:
                qs = qs.filter(organization__isnull=True)
        else:
            profile = getattr(self.request.user, 'teacher_profile', None)
            if not profile or not profile.assigned_class or not profile.assigned_section:
                return Student.objects.none()

            qs = Student.objects.filter(
                class_level=profile.assigned_class,
                section=profile.assigned_section
            ).select_related('class_level', 'section')
            if user_org:
                qs = qs.filter(organization=user_org)
            elif not self.request.user.is_superuser:
                qs = qs.filter(organization__isnull=True)
            if getattr(profile, 'client_id', None):
                qs = qs.filter(client_id=profile.client_id)

        # Filter by search term
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(full_name__icontains=search) |
                Q(student_id__icontains=search) |
                Q(roll_number__icontains=search)
            )

        # Filter by verification status
        v_status = self.request.query_params.get('status', '').strip().upper()
        if v_status in ('PENDING', 'SUBMITTED', 'VERIFIED', 'REJECTED'):
            qs = qs.filter(verification_status=v_status)

        return qs.order_by('roll_number')


class TeacherStudentDetailView(generics.RetrieveAPIView):
    serializer_class = StudentDetailSerializer
    permission_classes = [IsTeacherUser, IsAssignedTeacher]

    def get_queryset(self):
        user_org = getattr(self.request.user, 'organization', None)
        qs = Student.objects.all()
        if user_org:
            qs = qs.filter(organization=user_org)
        elif not self.request.user.is_superuser:
            qs = qs.filter(organization__isnull=True)
        profile = getattr(self.request.user, 'teacher_profile', None)
        if profile and getattr(profile, 'client_id', None):
            qs = qs.filter(client_id=profile.client_id)
        return qs


class TeacherStudentUpdateView(generics.UpdateAPIView):
    """
    Teacher can ONLY edit permitted student details (guardian, phone, address, blood group).
    Strictly forbids altering Student ID, Class, Section, or verification status.
    """
    serializer_class = StudentPermittedUpdateSerializer
    permission_classes = [IsTeacherUser, IsAssignedTeacher]

    def get_queryset(self):
        user_org = getattr(self.request.user, 'organization', None)
        qs = Student.objects.all()
        if user_org:
            qs = qs.filter(organization=user_org)
        elif not self.request.user.is_superuser:
            qs = qs.filter(organization__isnull=True)
        profile = getattr(self.request.user, 'teacher_profile', None)
        if profile and getattr(profile, 'client_id', None):
            qs = qs.filter(client_id=profile.client_id)
        return qs

    def perform_update(self, serializer):
        student = serializer.save()
        log_action(
            user=self.request.user,
            action='STUDENT_EDITED',
            object_type='Student',
            object_id=student.id,
            object_repr=str(student),
            details={'updated_fields': list(serializer.validated_data.keys())},
            request=self.request
        )


class TeacherStudentCreateView(generics.CreateAPIView):
    """
    Allows a class teacher to enroll a new student directly into their assigned class and section.
    Automatically scopes the student to the teacher's class, section, and the active academic year.
    """
    serializer_class = TeacherStudentCreateSerializer
    permission_classes = [IsTeacherUser]

    def perform_create(self, serializer):
        student = serializer.save()
        log_action(
            user=self.request.user,
            action='STUDENT_CREATED',
            object_type='Student',
            object_id=student.id,
            object_repr=str(student),
            details={'created_via': 'Teacher Mobile App'},
            request=self.request
        )


class TeacherStudentPhotoUploadView(views.APIView):
    """
    Handles single student photo capture/gallery upload from teacher mobile app.
    Crops, resizes, optimizes with Pillow, and updates student record safely.
    """
    permission_classes = [IsTeacherUser]

    def post(self, request, pk):
        try:
            student = Student.objects.get(pk=pk)
        except Student.DoesNotExist:
            return Response({'error': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Check teacher assignment permission
        profile = getattr(request.user, 'teacher_profile', None)
        user_org = getattr(request.user, 'organization', None)
        user_org_id = user_org.id if user_org else None
        if not request.user.is_superuser and student.organization_id != user_org_id:
            return Response({'error': 'You do not have permission to modify this student.'}, status=status.HTTP_403_FORBIDDEN)

        if not request.user.is_superuser and request.user.role != 'ADMIN':
            if not profile or student.class_level_id != profile.assigned_class_id or student.section_id != profile.assigned_section_id:
                return Response({'error': 'You do not have permission to modify this student.'}, status=status.HTTP_403_FORBIDDEN)
            if getattr(profile, 'client_id', None) and student.client_id != profile.client_id:
                return Response({'error': 'You do not have permission to modify this student.'}, status=status.HTTP_403_FORBIDDEN)

        photo_file = request.FILES.get('photo')
        if not photo_file:
            return Response({'error': 'No photo file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        if photo_file.size > settings.MAX_IMAGE_UPLOAD_SIZE:
            return Response({'error': 'Image size exceeds 5MB limit.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            processed_image = process_student_photo(photo_file)
            filename = f"{student.student_id}.jpg"
            student.photo.save(filename, processed_image, save=True)

            log_action(
                user=request.user,
                action='PHOTO_CHANGED',
                object_type='Student',
                object_id=student.id,
                object_repr=str(student),
                details={'method': 'mobile_app_upload'},
                request=request
            )

            photo_url = request.build_absolute_uri(student.photo.url)
            return Response({
                'message': 'Photo uploaded and optimized successfully.',
                'photo_url': photo_url
            })
        except Exception as e:
            return Response(
                {'error': f'Photo processing failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class TeacherStudentSubmitVerificationView(views.APIView):
    """
    Submits student for administrator verification.
    Transitions status to SUBMITTED.
    """
    permission_classes = [IsTeacherUser]

    def post(self, request, pk):
        try:
            student = Student.objects.get(pk=pk)
        except Student.DoesNotExist:
            return Response({'error': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Check assignment
        profile = getattr(request.user, 'teacher_profile', None)
        user_org = getattr(request.user, 'organization', None)
        user_org_id = user_org.id if user_org else None
        if not request.user.is_superuser and student.organization_id != user_org_id:
            return Response({'error': 'You do not have permission for this student.'}, status=status.HTTP_403_FORBIDDEN)

        if not request.user.is_superuser and request.user.role != 'ADMIN':
            if not profile or student.class_level_id != profile.assigned_class_id or student.section_id != profile.assigned_section_id:
                return Response({'error': 'You do not have permission for this student.'}, status=status.HTTP_403_FORBIDDEN)
            if getattr(profile, 'client_id', None) and student.client_id != profile.client_id:
                return Response({'error': 'You do not have permission for this student.'}, status=status.HTTP_403_FORBIDDEN)

        if not student.has_photo:
            return Response(
                {'error': 'Student must have a valid photograph before submitting for verification.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        prev_status = student.verification_status
        student.verification_status = 'SUBMITTED'
        student.submitted_at = timezone.now()
        student.submitted_by = request.user
        student.rejection_reason = ""
        student.save()

        VerificationRecord.objects.create(
            student=student,
            actor=request.user,
            previous_status=prev_status,
            new_status='SUBMITTED',
            notes=request.data.get('notes', 'Submitted via teacher mobile app')
        )

        log_action(
            user=request.user,
            action='VERIFICATION_SUBMITTED',
            object_type='Student',
            object_id=student.id,
            object_repr=str(student),
            details={'previous_status': prev_status, 'new_status': 'SUBMITTED'},
            request=request
        )

        return Response({
            'message': 'Student information successfully submitted for administrator verification.',
            'verification_status': student.verification_status
        })


class VerifyQRTokenView(views.APIView):
    """
    Validates QR code token scanned by teacher or public scanner.
    Returns card status, student info (non-sensitive), and validity dates.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        token = str(token).strip()
        try:
            card = IDCard.objects.select_related(
                'student', 'student__class_level', 'student__section',
                'student__client__school', 'student__organization__school'
            ).get(secure_token=token)
        except IDCard.DoesNotExist:
            return Response({
                'status': 'INVALID',
                'status_display': 'INVALID ID CARD',
                'message': 'This QR code is not recognized as a valid school ID card.',
            }, status=status.HTTP_404_NOT_FOUND)

        is_valid, reason = card.is_currently_valid()
        if card.student.client and card.student.client.school:
            school_name = card.student.client.school.name
        elif card.student.organization and card.student.organization.school:
            school_name = card.student.organization.school.name
        elif card.student.organization:
            school_name = card.student.organization.name
        else:
            school_name = School.get_instance().name

        photo_url = None
        if card.student.photo and hasattr(card.student.photo, 'url'):
            photo_url = request.build_absolute_uri(card.student.photo.url)

        if reason == 'REVOKED':
            return Response({
                'status': 'REVOKED',
                'status_display': 'ID CARD REVOKED',
                'message': f"This ID card was revoked by administration. Reason: {card.revocation_reason or 'Card invalidated'}",
                'student_id': card.student.student_id,
                'student_name': card.student.full_name,
                'class_name': card.student.class_level.name,
                'section_name': card.student.section.name,
                'photo_url': photo_url,
                'school_name': school_name,
                'valid_until': card.valid_until.strftime('%d %b %Y'),
                'card_number': card.card_number
            })
        elif reason == 'EXPIRED':
            return Response({
                'status': 'EXPIRED',
                'status_display': 'ID CARD EXPIRED',
                'message': f"This ID card expired on {card.valid_until.strftime('%d %b %Y')}.",
                'student_id': card.student.student_id,
                'student_name': card.student.full_name,
                'class_name': card.student.class_level.name,
                'section_name': card.student.section.name,
                'photo_url': photo_url,
                'school_name': school_name,
                'valid_until': card.valid_until.strftime('%d %b %Y'),
                'card_number': card.card_number
            })
        else:
            return Response({
                'status': 'ACTIVE',
                'status_display': 'VERIFIED ID CARD',
                'message': 'Official and authentic student identity card.',
                'student_id': card.student.student_id,
                'student_name': card.student.full_name,
                'class_name': card.student.class_level.name,
                'section_name': card.student.section.name,
                'photo_url': photo_url,
                'school_name': school_name,
                'valid_until': card.valid_until.strftime('%d %b %Y'),
                'card_number': card.card_number
            })


class AppConfigView(views.APIView):
    """
    Returns application configuration & About page metadata managed dynamically
    from Super Admin Platform Settings.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from apps.platform_admin.models import PlatformSetting
        ps = PlatformSetting.get_instance()

        logo_url = None
        if ps.app_logo:
            logo_url = request.build_absolute_uri(ps.app_logo.url)

        return Response({
            'app_name': ps.app_name or getattr(settings, 'APP_NAME', 'Apex ID - Teacher Portal'),
            'logo_url': logo_url,
            'version': ps.app_version or getattr(settings, 'APP_VERSION', '1.0.0'),
            'description': ps.app_description or getattr(settings, 'APP_DESCRIPTION', ''),
            'designer_name': ps.app_designer_name or getattr(settings, 'APP_DESIGNER_NAME', ''),
            'designer_role': ps.app_designer_role or getattr(settings, 'APP_DESIGNER_ROLE', ''),
            'contact_phone': ps.app_contact_phone or getattr(settings, 'APP_CONTACT_PHONE', ''),
            'contact_email': ps.app_contact_email or getattr(settings, 'APP_CONTACT_EMAIL', ''),
            'website': ps.app_website or getattr(settings, 'APP_WEBSITE', ''),
            'copyright_year': ps.app_copyright_text or getattr(settings, 'APP_COPYRIGHT_YEAR', '2026'),
        })


class ClassesSectionsListView(generics.ListAPIView):
    """
    Returns available classes and sections for mobile app dropdown selection.
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None
    serializer_class = ClassLevelWithSectionsSerializer

    def get_queryset(self):
        org = getattr(self.request.user, 'organization', None)
        class_filter = Q(organization=org) | Q(organization__isnull=True) if org else Q()
        return ClassLevel.objects.filter(class_filter).prefetch_related('sections').all()
