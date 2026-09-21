from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import get_user_model
from apps.accounts.models import TeacherProfile
from apps.academic.models import ClassLevel, Section
from apps.core.services.audit import log_action
from apps.platform_admin.models import Organization
from apps.core.utils import get_current_organization
from django.db.models import Q

User = get_user_model()


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.role == 'ADMIN')


def admin_login_view(request):
    if request.user.is_authenticated and (request.user.is_superuser or request.user.role == 'ADMIN'):
        return redirect('dashboard')

    if request.method == 'POST':
        u = request.POST.get('username', '').strip()
        p = request.POST.get('password', '')

        user = authenticate(username=u, password=p)
        if user is not None:
            if user.role == 'TEACHER':
                messages.error(request, "Teacher accounts are not permitted in the web administration panel. Please use the mobile application.")
                return render(request, 'accounts/login.html')

            if not user.is_active:
                messages.error(request, "This account is inactive. Please contact system administrator.")
                return render(request, 'accounts/login.html')

            # Check organization suspension
            org = getattr(user, 'organization', None)
            if not org and not (user.is_superuser or getattr(user, 'role', '') == 'SUPER_ADMIN'):
                from apps.platform_admin.models import Organization
                org = Organization.objects.filter(school_id=1).first()

            if org and org.status == 'SUSPENDED':
                messages.error(request, f"Access Denied: Organization '{org.name}' ({org.org_id}) is currently suspended by the platform owner. Access is locked.")
                return render(request, 'accounts/login.html')

            login(request, user)
            log_action(user=user, action='ADMIN_LOGIN', details={'panel': 'Web Admin'}, request=request)
            next_url = request.GET.get('next') or 'dashboard'
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'accounts/login.html')


def admin_logout_view(request):
    if request.user.is_authenticated:
        log_action(user=request.user, action='ADMIN_LOGIN', details={'action': 'logout'}, request=request)
    logout(request)
    return redirect('admin_login')


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def teachers_list_view(request):
    org = get_current_organization(request)

    teacher_qs = TeacherProfile.objects.select_related('user', 'assigned_class', 'assigned_section', 'client')
    if org:
        teachers = teacher_qs.filter(user__organization=org)
    elif not request.user.is_superuser:
        teachers = teacher_qs.none()
    else:
        teachers = teacher_qs.all()

    is_studio = bool(org and getattr(org, 'is_studio', False))
    studio_clients = org.clients.filter(is_active=True).order_by('name') if is_studio else []
    active_client_id = request.session.get('active_client_id') if is_studio else None
    active_client = None

    if is_studio:
        if active_client_id and str(active_client_id) != '0':
            active_client = org.clients.filter(id=active_client_id).first()
            if active_client:
                teachers = teachers.filter(client=active_client)

    class_filter = Q(organization=org) | Q(organization__isnull=True) if org else Q()
    classes = ClassLevel.objects.filter(class_filter).prefetch_related('sections').all()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            username = request.POST.get('username', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone', '').strip()
            employee_id = request.POST.get('employee_id', '').strip()
            password = request.POST.get('password', '').strip()
            class_id = request.POST.get('assigned_class')
            section_id = request.POST.get('assigned_section')
            client_id = request.POST.get('client_id') or (str(active_client_id) if active_client_id and str(active_client_id) != '0' else None)

            if User.objects.filter(username=username).exists():
                messages.error(request, f"Username '{username}' is already taken.")
                return redirect('teachers_list')

            if TeacherProfile.objects.filter(employee_id=employee_id).exists():
                messages.error(request, f"Employee ID '{employee_id}' already exists.")
                return redirect('teachers_list')

            if is_studio and not client_id and studio_clients.exists():
                messages.error(request, "Please select a Client Organization for this teacher.")
                return redirect('teachers_list')

            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role='TEACHER',
                phone=phone,
                organization=org,
                password=password or 'teacher123'
            )

            profile = TeacherProfile.objects.create(
                user=user,
                client_id=client_id if is_studio and client_id else None,
                employee_id=employee_id,
                assigned_class_id=class_id if class_id else None,
                assigned_section_id=section_id if section_id else None,
                status='ACTIVE'
            )

            log_action(
                user=request.user,
                action='TEACHER_ASSIGNMENT_CHANGED',
                object_type='TeacherProfile',
                object_id=profile.id,
                object_repr=str(profile),
                details={'event': 'teacher_created', 'client': str(profile.client) if profile.client else None},
                request=request
            )
            messages.success(request, f"Teacher {user.get_full_name() or user.username} created successfully.")
            return redirect('teachers_list')

        elif action == 'edit':
            profile_id = request.POST.get('profile_id')
            profile = get_object_or_404(teachers, id=profile_id)
            user = profile.user

            user.first_name = request.POST.get('first_name', user.first_name).strip()
            user.last_name = request.POST.get('last_name', user.last_name).strip()
            user.email = request.POST.get('email', user.email).strip()
            user.phone = request.POST.get('phone', user.phone).strip()
            user.save()

            class_id = request.POST.get('assigned_class')
            section_id = request.POST.get('assigned_section')
            profile.assigned_class_id = class_id if class_id else None
            profile.assigned_section_id = section_id if section_id else None
            profile.status = request.POST.get('status', profile.status)
            if is_studio:
                new_client_id = request.POST.get('client_id')
                if new_client_id:
                    profile.client_id = new_client_id
            profile.save()

            log_action(
                user=request.user,
                action='TEACHER_ASSIGNMENT_CHANGED',
                object_type='TeacherProfile',
                object_id=profile.id,
                object_repr=str(profile),
                details={'event': 'teacher_updated'},
                request=request
            )
            messages.success(request, f"Teacher {user.get_full_name()} updated successfully.")
            return redirect('teachers_list')

        elif action == 'toggle_status':
            profile_id = request.POST.get('profile_id')
            profile = get_object_or_404(teachers, id=profile_id)
            new_status = 'INACTIVE' if profile.status == 'ACTIVE' else 'ACTIVE'
            profile.status = new_status
            profile.user.is_active = (new_status == 'ACTIVE')
            profile.user.save()
            profile.save()

            log_action(
                user=request.user,
                action='TEACHER_ASSIGNMENT_CHANGED',
                object_type='TeacherProfile',
                object_id=profile.id,
                object_repr=str(profile),
                details={'new_status': new_status},
                request=request
            )
            messages.success(request, f"Teacher status changed to {new_status}.")
            return redirect('teachers_list')

        elif action == 'reset_password':
            profile_id = request.POST.get('profile_id')
            new_password = request.POST.get('new_password', '').strip()
            profile = get_object_or_404(teachers, id=profile_id)
            if new_password:
                profile.user.set_password(new_password)
                profile.user.save()
                messages.success(request, f"Password reset successfully for {profile.user.username}.")
            else:
                messages.error(request, "New password cannot be empty.")
            return redirect('teachers_list')

    return render(request, 'accounts/teachers_list.html', {
        'teachers': teachers,
        'classes': classes,
        'is_studio': is_studio,
        'studio_clients': studio_clients,
        'active_client': active_client,
        'selected_client_id': active_client_id,
    })
