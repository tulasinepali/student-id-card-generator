from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import HttpResponseForbidden

from apps.accounts.models import User
from apps.core.models import School
from apps.students.models import Student
from apps.idcards.models import IDCard, IDCardTemplate
from apps.academic.models import ClassLevel
from apps.platform_admin.models import (
    Organization,
    SubscriptionPlan,
    OrganizationSubscription,
    PlatformAuditLog,
    SupportSession,
    PlatformSetting,
)
from apps.platform_admin.decorators import super_admin_required


# ==========================================
# 1. AUTHENTICATION
# ==========================================

def login_view(request):
    """
    Dedicated Super Admin login.
    Strictly forbids normal organization admins and teachers from logging in here.
    """
    if request.user.is_authenticated and getattr(request.user, 'is_super_admin', lambda: False)():
        return redirect('platform_admin:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Check Super Admin status
            is_super = getattr(user, 'is_super_admin', None)
            has_perm = is_super() if callable(is_super) else (user.is_superuser or getattr(user, 'role', '') == 'SUPER_ADMIN')

            if not has_perm:
                messages.error(
                    request,
                    "Access Denied: This portal is strictly restricted to Platform Super Administrators. "
                    "Organization staff and administrators must log in at the organization portal."
                )
                return redirect('platform_admin:login')

            login(request, user)
            PlatformAuditLog.log(
                user=user,
                action='USER_STATUS_TOGGLED',
                target=user.username,
                description=f"Super Admin {user.username} logged in to platform portal.",
                request=request
            )
            next_url = request.GET.get('next') or request.POST.get('next') or 'platform_admin:dashboard'
            return redirect(next_url)
        else:
            messages.error(request, "Invalid Super Admin credentials. Please try again.")

    return render(request, 'platform_admin/login.html')


def logout_view(request):
    """Logs out of Super Admin portal."""
    if request.user.is_authenticated:
        PlatformAuditLog.log(
            user=request.user,
            action='USER_STATUS_TOGGLED',
            target=request.user.username,
            description="Super Admin logged out.",
            request=request
        )
        logout(request)
    return redirect('platform_admin:login')


# ==========================================
# 2. EXECUTIVE DASHBOARD
# ==========================================

@super_admin_required
def dashboard_view(request):
    """
    Real-time platform-level KPI dashboard.
    No hardcoded numbers; all statistics are queried directly from the database.
    """
    today = date.today()
    in_7_days = today + timedelta(days=7)
    in_30_days = today + timedelta(days=30)

    # 1. Organization statistics
    total_orgs = Organization.objects.count()
    active_orgs = Organization.objects.filter(status='ACTIVE').count()
    trial_orgs = Organization.objects.filter(status='TRIAL').count()
    suspended_orgs = Organization.objects.filter(status='SUSPENDED').count()
    expired_orgs = Organization.objects.filter(status='EXPIRED').count()
    this_month_orgs = Organization.objects.filter(
        created_at__year=today.year,
        created_at__month=today.month
    ).count()

    # 2. User statistics
    total_admins = User.objects.filter(role='ADMIN').count()
    total_teachers = User.objects.filter(role='TEACHER').count()
    total_students = Student.objects.count()
    total_cards = IDCard.objects.count()

    # 3. Subscription statistics
    active_subs = OrganizationSubscription.objects.filter(status='ACTIVE').count()
    trial_subs = OrganizationSubscription.objects.filter(status='TRIAL').count()
    expired_subs = OrganizationSubscription.objects.filter(
        Q(status='EXPIRED') | Q(expiry_date__lt=today)
    ).count()
    expiring_soon = OrganizationSubscription.objects.filter(
        status__in=['ACTIVE', 'TRIAL'],
        expiry_date__range=[today, in_7_days]
    ).count()
    expiring_month = OrganizationSubscription.objects.filter(
        status__in=['ACTIVE', 'TRIAL'],
        expiry_date__range=[today + timedelta(days=8), in_30_days]
    ).count()

    # 4. Recent activity & organizations
    recent_orgs = Organization.objects.select_related('subscription__plan', 'primary_admin').order_by('-created_at')[:6]
    recent_logs = PlatformAuditLog.objects.select_related('user', 'organization').order_by('-created_at')[:8]

    # 5. Organizations expiring soon
    expiring_list = OrganizationSubscription.objects.filter(
        status__in=['ACTIVE', 'TRIAL'],
        expiry_date__range=[today, in_30_days]
    ).select_related('organization', 'plan').order_by('expiry_date')[:5]

    return render(request, 'platform_admin/dashboard.html', {
        'total_orgs': total_orgs,
        'active_orgs': active_orgs,
        'trial_orgs': trial_orgs,
        'suspended_orgs': suspended_orgs,
        'expired_orgs': expired_orgs,
        'this_month_orgs': this_month_orgs,
        'total_admins': total_admins,
        'total_teachers': total_teachers,
        'total_students': total_students,
        'total_cards': total_cards,
        'active_subs': active_subs,
        'trial_subs': trial_subs,
        'expired_subs': expired_subs,
        'expiring_soon': expiring_soon,
        'expiring_month': expiring_month,
        'recent_orgs': recent_orgs,
        'recent_logs': recent_logs,
        'expiring_list': expiring_list,
    })


# ==========================================
# 3. ORGANIZATION MANAGEMENT
# ==========================================

@super_admin_required
def organizations_list_view(request):
    """
    Searchable, filterable, sortable organization catalog.
    """
    qs = Organization.objects.select_related('subscription__plan', 'primary_admin').all()

    # Filters
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')
    plan_filter = request.GET.get('plan', '')
    sort_by = request.GET.get('sort', '-created_at')

    if search:
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(org_id__icontains=search) |
            Q(short_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search) |
            Q(primary_admin__username__icontains=search) |
            Q(primary_admin__first_name__icontains=search) |
            Q(primary_admin__last_name__icontains=search)
        )

    if status_filter:
        qs = qs.filter(status=status_filter)

    if type_filter:
        qs = qs.filter(org_type=type_filter)

    if plan_filter:
        qs = qs.filter(subscription__plan__code=plan_filter)

    if sort_by in ['name', '-name', 'created_at', '-created_at', 'status', '-status']:
        qs = qs.order_by(sort_by)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    plans = SubscriptionPlan.objects.filter(is_active=True)

    return render(request, 'platform_admin/organizations_list.html', {
        'page_obj': page_obj,
        'search': search,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'plan_filter': plan_filter,
        'sort_by': sort_by,
        'plans': plans,
        'org_types': Organization.ORG_TYPE_CHOICES,
        'org_statuses': Organization.STATUS_CHOICES,
        'total_count': qs.count(),
    })


@super_admin_required
def organization_create_view(request):
    """
    Creates a new organization + primary admin user + subscription assignment in an atomic transaction.
    """
    plans = SubscriptionPlan.objects.filter(is_active=True)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        org_type = request.POST.get('org_type', 'SCHOOL')
        short_name = request.POST.get('short_name', '').strip()
        address = request.POST.get('address', '').strip()
        municipality = request.POST.get('municipality', '').strip()
        district = request.POST.get('district', '').strip()
        province = request.POST.get('province', '').strip()
        country = request.POST.get('country', 'Nepal').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        website = request.POST.get('website', '').strip()
        logo = request.FILES.get('logo')

        # Primary admin fields
        admin_name = request.POST.get('admin_name', '').strip()
        admin_email = request.POST.get('admin_email', '').strip()
        admin_phone = request.POST.get('admin_phone', '').strip()
        admin_username = request.POST.get('admin_username', '').strip()
        admin_password = request.POST.get('admin_password', '').strip()

        # Subscription fields
        plan_id = request.POST.get('plan')
        sub_status = request.POST.get('sub_status', 'ACTIVE')
        start_date_str = request.POST.get('start_date', '')
        expiry_date_str = request.POST.get('expiry_date', '')

        # Validations
        errors = []
        if not name:
            errors.append("Organization Name is required.")
        if not admin_name:
            errors.append("Primary Administrator Full Name is required.")
        if not admin_email:
            errors.append("Primary Administrator Email is required.")
        if not admin_username:
            errors.append("Primary Administrator Username is required.")
        if not admin_password or len(admin_password) < 6:
            errors.append("Initial Admin Password must be at least 6 characters.")
        if User.objects.filter(username=admin_username).exists():
            errors.append(f"Username '{admin_username}' is already taken.")
        if User.objects.filter(email=admin_email).exists():
            errors.append(f"Email '{admin_email}' is already in use by another user.")

        selected_plan = SubscriptionPlan.objects.filter(id=plan_id).first()
        if not selected_plan:
            errors.append("Please select a valid Subscription Plan.")

        start_date = date.today()
        if start_date_str:
            try:
                start_date = date.fromisoformat(start_date_str)
            except ValueError:
                errors.append("Invalid Start Date format.")

        expiry_date = start_date + timedelta(days=365)
        if expiry_date_str:
            try:
                expiry_date = date.fromisoformat(expiry_date_str)
            except ValueError:
                errors.append("Invalid Expiry Date format.")

        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, 'platform_admin/organization_create.html', {
                'plans': plans,
                'org_types': Organization.ORG_TYPE_CHOICES,
                'form_data': request.POST,
            })

        uses_mobile_app = 'uses_mobile_app' in request.POST

        try:
            with transaction.atomic():
                # 1. Create Organization
                org = Organization.objects.create(
                    name=name,
                    org_type=org_type,
                    uses_mobile_app=uses_mobile_app,
                    short_name=short_name or name[:6].upper(),
                    address=address,
                    municipality=municipality,
                    district=district,
                    province=province,
                    country=country,
                    phone=phone,
                    email=email,
                    website=website,
                    logo=logo,
                    status=sub_status
                )

                # 2. Create primary administrator User
                first_name = admin_name.split()[0]
                last_name = " ".join(admin_name.split()[1:]) if len(admin_name.split()) > 1 else ""
                admin_user = User.objects.create_user(
                    username=admin_username,
                    email=admin_email,
                    password=admin_password,
                    first_name=first_name,
                    last_name=last_name,
                    role='ADMIN',
                    phone=admin_phone,
                    organization=org
                )

                org.primary_admin = admin_user

                # 3. Create linked School model instance for backward compatibility
                school_inst = School.objects.create(
                    name=org.name,
                    short_name=org.short_name,
                    address=org.address,
                    municipality=org.municipality,
                    district=org.district,
                    province=org.province,
                    country=org.country,
                    phone=org.phone,
                    email=org.email,
                    website=org.website,
                    logo=org.logo
                )
                org.school = school_inst
                org.save()

                # 4. Create OrganizationSubscription
                OrganizationSubscription.objects.create(
                    organization=org,
                    plan=selected_plan,
                    start_date=start_date,
                    expiry_date=expiry_date,
                    status=sub_status,
                    notes=f"Initial onboarding plan: {selected_plan.name}"
                )

                # 5. Audit log
                PlatformAuditLog.log(
                    user=request.user,
                    action='ORG_CREATED',
                    organization=org,
                    target=org.org_id,
                    description=f"Created organization '{org.name}' ({org.org_id}) with plan {selected_plan.name}. Primary admin: {admin_user.username}",
                    request=request
                )

            messages.success(request, f"Organization '{org.name}' ({org.org_id}) created successfully!")
            return redirect('platform_admin:organization_detail', pk=org.pk)

        except Exception as e:
            messages.error(request, f"Failed to create organization: {str(e)}")

    return render(request, 'platform_admin/organization_create.html', {
        'plans': plans,
        'org_types': Organization.ORG_TYPE_CHOICES,
        'default_start': date.today().isoformat(),
        'default_expiry': (date.today() + timedelta(days=365)).isoformat(),
    })


@super_admin_required
def organization_detail_view(request, pk):
    """
    360-degree organization dossier.
    """
    org = get_object_or_404(
        Organization.objects.select_related('subscription__plan', 'primary_admin', 'school'),
        pk=pk
    )

    # Calculate real statistics
    users_qs = User.objects.filter(organization=org)
    admins_count = users_qs.filter(role='ADMIN').count()
    teachers_count = users_qs.filter(role='TEACHER').count()

    # For students, cards, classes, templates scoped to this tenant organization:
    students_qs = Student.objects.filter(organization=org)
    students_count = students_qs.count()
    active_students = students_qs.filter(status='ACTIVE').count()
    verified_students = students_qs.filter(verification_status='VERIFIED').count()
    cards_count = IDCard.objects.filter(student__organization=org).count()
    classes_count = ClassLevel.objects.filter(Q(organization=org) | Q(organization__isnull=True)).count()
    templates_count = IDCardTemplate.objects.filter(Q(organization=org) | Q(organization__isnull=True)).count()

    recent_logs = PlatformAuditLog.objects.filter(organization=org).order_by('-created_at')[:8]
    org_users = users_qs.order_by('-date_joined')[:10]

    return render(request, 'platform_admin/organization_detail.html', {
        'org': org,
        'sub': getattr(org, 'subscription', None),
        'admins_count': admins_count,
        'teachers_count': teachers_count,
        'students_count': students_count,
        'active_students': active_students,
        'verified_students': verified_students,
        'cards_count': cards_count,
        'classes_count': classes_count,
        'templates_count': templates_count,
        'recent_logs': recent_logs,
        'org_users': org_users,
    })


@super_admin_required
def organization_edit_view(request, pk):
    """
    Updates organization properties and syncs changes safely.
    """
    org = get_object_or_404(Organization, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        org_type = request.POST.get('org_type', org.org_type)
        short_name = request.POST.get('short_name', '').strip()
        address = request.POST.get('address', '').strip()
        municipality = request.POST.get('municipality', '').strip()
        district = request.POST.get('district', '').strip()
        province = request.POST.get('province', '').strip()
        country = request.POST.get('country', org.country).strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        website = request.POST.get('website', '').strip()

        if not name:
            messages.error(request, "Organization Name cannot be empty.")
            return redirect('platform_admin:organization_edit', pk=org.pk)

        org.name = name
        org.org_type = org_type
        org.uses_mobile_app = 'uses_mobile_app' in request.POST
        org.short_name = short_name
        org.address = address
        org.municipality = municipality
        org.district = district
        org.province = province
        org.country = country
        org.phone = phone
        org.email = email
        org.website = website

        if 'logo' in request.FILES:
            org.logo = request.FILES['logo']

        org.save()

        if not org.uses_mobile_app:
            Student.objects.filter(organization=org, verification_status='PENDING').update(verification_status='VERIFIED')

        # Sync to linked School record if present
        if org.school:
            org.school.name = org.name
            org.school.short_name = org.short_name
            org.school.address = org.address
            org.school.municipality = org.municipality
            org.school.district = org.district
            org.school.province = org.province
            org.school.country = org.country
            org.school.phone = org.phone
            org.school.email = org.email
            org.school.website = org.website

            signatory_name = request.POST.get('signatory_name', '').strip()
            if signatory_name:
                org.school.head_teacher_name = signatory_name

            if 'authorized_signature' in request.FILES:
                org.school.head_teacher_signature = request.FILES['authorized_signature']

            if org.logo:
                org.school.logo = org.logo
            org.school.save()

        PlatformAuditLog.log(
            user=request.user,
            action='ORG_UPDATED',
            organization=org,
            target=org.org_id,
            description=f"Updated profile for '{org.name}' ({org.org_id}).",
            request=request
        )

        messages.success(request, f"Organization '{org.name}' updated successfully.")
        return redirect('platform_admin:organization_detail', pk=org.pk)

    return render(request, 'platform_admin/organization_edit.html', {
        'org': org,
        'org_types': Organization.ORG_TYPE_CHOICES,
    })


@super_admin_required
def organization_suspend_view(request, pk):
    """
    Safely suspends an organization.
    Reversible. Does not delete any data.
    """
    org = get_object_or_404(Organization, pk=pk)
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Suspended by Super Admin.')
        org.status = 'SUSPENDED'
        org.save()

        if hasattr(org, 'subscription'):
            org.subscription.status = 'SUSPENDED'
            org.subscription.notes += f"\n[{date.today()}] Suspended: {reason}"
            org.subscription.save()

        PlatformAuditLog.log(
            user=request.user,
            action='ORG_SUSPENDED',
            organization=org,
            target=org.org_id,
            description=f"Suspended organization '{org.name}'. Reason: {reason}",
            request=request
        )
        messages.warning(request, f"Organization '{org.name}' ({org.org_id}) has been SUSPENDED.")
    return redirect('platform_admin:organization_detail', pk=org.pk)


@super_admin_required
def organization_activate_view(request, pk):
    """
    Reactivates a suspended organization.
    """
    org = get_object_or_404(Organization, pk=pk)
    if request.method == 'POST':
        org.status = 'ACTIVE'
        org.save()

        if hasattr(org, 'subscription'):
            org.subscription.status = 'ACTIVE'
            org.subscription.save()

        PlatformAuditLog.log(
            user=request.user,
            action='ORG_ACTIVATED',
            organization=org,
            target=org.org_id,
            description=f"Reactivated organization '{org.name}'.",
            request=request
        )
        messages.success(request, f"Organization '{org.name}' ({org.org_id}) is now ACTIVE.")
    return redirect('platform_admin:organization_detail', pk=org.pk)


@super_admin_required
def organization_subscription_view(request, pk):
    """
    Super Admin management of organization plan, extension, and notes.
    """
    org = get_object_or_404(Organization, pk=pk)
    sub = getattr(org, 'subscription', None)
    plans = SubscriptionPlan.objects.filter(is_active=True)

    if request.method == 'POST':
        plan_id = request.POST.get('plan')
        sub_status = request.POST.get('status', 'ACTIVE')
        expiry_date_str = request.POST.get('expiry_date')
        notes = request.POST.get('notes', '')

        selected_plan = get_object_or_404(SubscriptionPlan, id=plan_id)

        try:
            expiry_date = date.fromisoformat(expiry_date_str)
        except (ValueError, TypeError):
            expiry_date = date.today() + timedelta(days=365)

        if sub:
            old_plan_name = sub.plan.name
            sub.plan = selected_plan
            sub.status = sub_status
            sub.expiry_date = expiry_date
            sub.notes = notes
            sub.save()
        else:
            sub = OrganizationSubscription.objects.create(
                organization=org,
                plan=selected_plan,
                start_date=date.today(),
                expiry_date=expiry_date,
                status=sub_status,
                notes=notes
            )
            old_plan_name = "None"

        # Update org status to match
        org.status = sub_status
        org.save()

        PlatformAuditLog.log(
            user=request.user,
            action='PLAN_CHANGED',
            organization=org,
            target=org.org_id,
            description=f"Subscription updated for '{org.name}'. Plan: {old_plan_name} -> {selected_plan.name}. Valid until {expiry_date}.",
            request=request
        )

        messages.success(request, f"Subscription for '{org.name}' updated successfully.")
        return redirect('platform_admin:organization_detail', pk=org.pk)

    return render(request, 'platform_admin/organization_subscription.html', {
        'org': org,
        'sub': sub,
        'plans': plans,
    })


# ==========================================
# 4. SUPPORT MODE & INSPECTION
# ==========================================

@super_admin_required
def support_enter_view(request, pk):
    """
    Enters a secure, logged support session for the chosen organization.
    """
    org = get_object_or_404(Organization, pk=pk)

    # Close any existing open sessions for this super admin
    SupportSession.objects.filter(super_admin=request.user, is_active=True).update(
        is_active=False,
        ended_at=timezone.now()
    )

    # Create new SupportSession
    SupportSession.objects.create(
        super_admin=request.user,
        organization=org,
        ip_address=request.META.get('REMOTE_ADDR'),
        is_active=True
    )

    request.session['support_mode_org_id'] = org.id
    request.session['support_mode_org_name'] = org.name

    PlatformAuditLog.log(
        user=request.user,
        action='SUPPORT_MODE_ENTERED',
        organization=org,
        target=org.org_id,
        description=f"Super Admin entered Support Mode for '{org.name}'.",
        request=request
    )

    messages.info(request, f"SUPPORT MODE ACTIVE: You are now inspecting '{org.name}' ({org.org_id}).")
    return redirect('platform_admin:support_inspection', pk=org.pk)


@super_admin_required
def support_exit_view(request):
    """
    Exits support mode cleanly, logging session termination.
    """
    org_id = request.session.get('support_mode_org_id')
    org = Organization.objects.filter(id=org_id).first() if org_id else None

    SupportSession.objects.filter(super_admin=request.user, is_active=True).update(
        is_active=False,
        ended_at=timezone.now()
    )

    if 'support_mode_org_id' in request.session:
        del request.session['support_mode_org_id']
    if 'support_mode_org_name' in request.session:
        del request.session['support_mode_org_name']

    if org:
        PlatformAuditLog.log(
            user=request.user,
            action='SUPPORT_MODE_EXITED',
            organization=org,
            target=org.org_id,
            description=f"Super Admin exited Support Mode for '{org.name}'.",
            request=request
        )
        messages.success(request, f"Exited Support Mode for '{org.name}'.")
        return redirect('platform_admin:organization_detail', pk=org.pk)

    messages.success(request, "Exited Support Mode.")
    return redirect('platform_admin:organizations_list')


@super_admin_required
def support_inspection_view(request, pk):
    """
    Safe read-only / diagnostic inspection workspace for an organization.
    """
    org = get_object_or_404(Organization, pk=pk)

    # Query organization details
    users = User.objects.filter(organization=org)
    templates = IDCardTemplate.objects.filter(Q(organization=org) | Q(organization__isnull=True))
    classes = ClassLevel.objects.filter(Q(organization=org) | Q(organization__isnull=True))
    sample_students = Student.objects.filter(organization=org)[:15]

    return render(request, 'platform_admin/support_inspection.html', {
        'org': org,
        'users': users,
        'templates': templates,
        'classes': classes,
        'sample_students': sample_students,
    })


# ==========================================
# 5. USER & ADMIN MANAGEMENT
# ==========================================

@super_admin_required
def users_list_view(request):
    """
    Platform-wide user directory across all organizations.
    """
    qs = User.objects.select_related('organization').all()

    search = request.GET.get('search', '').strip()
    role_filter = request.GET.get('role', '')
    org_filter = request.GET.get('org', '')
    status_filter = request.GET.get('status', '')

    if search:
        qs = qs.filter(
            Q(username__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )

    if role_filter:
        qs = qs.filter(role=role_filter)

    if org_filter:
        qs = qs.filter(organization_id=org_filter)

    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)

    qs = qs.order_by('-date_joined')

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    organizations = Organization.objects.all().order_by('name')

    return render(request, 'platform_admin/users_list.html', {
        'page_obj': page_obj,
        'search': search,
        'role_filter': role_filter,
        'org_filter': org_filter,
        'status_filter': status_filter,
        'organizations': organizations,
        'roles': User.ROLE_CHOICES,
        'total_count': qs.count(),
    })


@super_admin_required
def admins_list_view(request):
    """
    Filter shortcut for organization administrators.
    """
    return users_list_view(request)


@super_admin_required
def admin_create_view(request):
    """
    Creates an organization administrator account for a specific organization.
    """
    organizations = Organization.objects.filter(status='ACTIVE').order_by('name')
    initial_org_id = request.GET.get('org')

    if request.method == 'POST':
        org_id = request.POST.get('organization')
        name = request.POST.get('name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()

        org = get_object_or_404(Organization, id=org_id)

        errors = []
        if not name:
            errors.append("Full Name is required.")
        if not username:
            errors.append("Username is required.")
        if not email:
            errors.append("Email is required.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if User.objects.filter(username=username).exists():
            errors.append(f"Username '{username}' is already in use.")

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'platform_admin/admin_create.html', {
                'organizations': organizations,
                'initial_org_id': org_id,
                'form_data': request.POST,
            })

        first_name = name.split()[0]
        last_name = " ".join(name.split()[1:]) if len(name.split()) > 1 else ""

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role='ADMIN',
            organization=org
        )

        PlatformAuditLog.log(
            user=request.user,
            action='ADMIN_CREATED',
            organization=org,
            target=user.username,
            description=f"Created Org Admin {user.username} ({user.email}) for '{org.name}'.",
            request=request
        )

        messages.success(request, f"Administrator account '{user.username}' created for {org.name}.")
        return redirect('platform_admin:organization_detail', pk=org.pk)

    return render(request, 'platform_admin/admin_create.html', {
        'organizations': organizations,
        'initial_org_id': initial_org_id,
    })


@super_admin_required
def user_toggle_status_view(request, pk):
    """
    Enables / Disables user account safely.
    """
    user = get_object_or_404(User, pk=pk)

    if user == request.user:
        messages.error(request, "You cannot deactivate your own Super Admin account.")
        return redirect('platform_admin:users_list')

    if request.method == 'POST':
        user.is_active = not user.is_active
        user.save()

        status_str = "ACTIVATED" if user.is_active else "DISABLED"
        PlatformAuditLog.log(
            user=request.user,
            action='USER_STATUS_TOGGLED',
            organization=user.organization,
            target=user.username,
            description=f"User {user.username} account was {status_str}.",
            request=request
        )
        messages.success(request, f"User '{user.username}' account is now {status_str}.")

    return redirect(request.META.get('HTTP_REFERER') or 'platform_admin:users_list')


@super_admin_required
def user_reset_password_view(request, pk):
    """
    Super Admin password reset workflow for any organization admin or teacher.
    """
    user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if not new_password or len(new_password) < 6:
            messages.error(request, "Password must be at least 6 characters.")
            return render(request, 'platform_admin/admin_reset_password.html', {'target_user': user})

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'platform_admin/admin_reset_password.html', {'target_user': user})

        user.set_password(new_password)
        user.save()

        PlatformAuditLog.log(
            user=request.user,
            action='ADMIN_PASSWORD_RESET',
            organization=user.organization,
            target=user.username,
            description=f"Password was reset for user '{user.username}'.",
            request=request
        )

        messages.success(request, f"Password for '{user.username}' has been successfully reset.")
        if user.organization:
            return redirect('platform_admin:organization_detail', pk=user.organization.pk)
        return redirect('platform_admin:users_list')

    return render(request, 'platform_admin/admin_reset_password.html', {'target_user': user})


# ==========================================
# 6. SUBSCRIPTIONS & EXPIRATION BUCKETS
# ==========================================

@super_admin_required
def subscriptions_list_view(request):
    """
    Platform subscription tracking with expiration bucket filters.
    """
    today = date.today()
    in_7_days = today + timedelta(days=7)
    in_30_days = today + timedelta(days=30)

    bucket = request.GET.get('bucket', 'all')
    search = request.GET.get('search', '').strip()

    qs = OrganizationSubscription.objects.select_related('organization', 'plan').all()

    if search:
        qs = qs.filter(
            Q(organization__name__icontains=search) |
            Q(organization__org_id__icontains=search) |
            Q(plan__name__icontains=search)
        )

    # Expiration buckets
    if bucket == 'expired':
        qs = qs.filter(Q(status='EXPIRED') | Q(expiry_date__lt=today))
    elif bucket == 'today':
        qs = qs.filter(expiry_date=today)
    elif bucket == 'in_7_days':
        qs = qs.filter(expiry_date__range=[today, in_7_days])
    elif bucket == 'in_30_days':
        qs = qs.filter(expiry_date__range=[today + timedelta(days=8), in_30_days])
    elif bucket == 'active':
        qs = qs.filter(status='ACTIVE', expiry_date__gt=today)

    qs = qs.order_by('expiry_date')

    # Bucket counts
    all_subs = OrganizationSubscription.objects.all()
    count_expired = all_subs.filter(Q(status='EXPIRED') | Q(expiry_date__lt=today)).count()
    count_today = all_subs.filter(expiry_date=today).count()
    count_7_days = all_subs.filter(expiry_date__range=[today, in_7_days]).count()
    count_30_days = all_subs.filter(expiry_date__range=[today + timedelta(days=8), in_30_days]).count()
    count_active = all_subs.filter(status='ACTIVE', expiry_date__gt=today).count()

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'platform_admin/subscriptions_list.html', {
        'page_obj': page_obj,
        'bucket': bucket,
        'search': search,
        'count_expired': count_expired,
        'count_today': count_today,
        'count_7_days': count_7_days,
        'count_30_days': count_30_days,
        'count_active': count_active,
        'total_count': all_subs.count(),
    })


@super_admin_required
def plans_list_view(request):
    """
    Manage subscription plan tiers.
    """
    plans = SubscriptionPlan.objects.annotate(org_count=Count('subscriptions')).order_by('price_per_year')
    return render(request, 'platform_admin/plans_list.html', {'plans': plans})


@super_admin_required
def plan_create_view(request):
    """
    Create a new subscription plan tier.
    """
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        description = request.POST.get('description', '').strip()
        try:
            max_students = int(request.POST.get('max_students', 500))
            max_staff = int(request.POST.get('max_staff', 50))
            max_clients = int(request.POST.get('max_clients', 1))
            price = float(request.POST.get('price_per_year', 0.0))
        except (ValueError, TypeError):
            messages.error(request, "Invalid numeric input for capacity limits or price.")
            return redirect('platform_admin:plans_list')

        if not name or not code:
            messages.error(request, "Plan Name and Code are required.")
            return redirect('platform_admin:plans_list')

        if SubscriptionPlan.objects.filter(code=code).exists():
            messages.error(request, f"Plan with code '{code}' already exists.")
            return redirect('platform_admin:plans_list')

        is_active = 'is_active' in request.POST or len(request.POST) == 0

        plan = SubscriptionPlan.objects.create(
            name=name,
            code=code,
            description=description,
            max_students=max_students,
            max_staff=max_staff,
            max_clients=max_clients,
            price_per_year=price,
            is_active=is_active
        )

        PlatformAuditLog.log(
            user=request.user,
            action='PLAN_CHANGED',
            target=plan.name,
            description=f"Created new subscription plan '{plan.name}' ({plan.code}). Price: NPR {plan.price_per_year}, Max Students: {plan.max_students}, Max Clients: {plan.max_clients}.",
            request=request
        )

        messages.success(request, f"Subscription plan '{plan.name}' created successfully.")
        return redirect('platform_admin:plans_list')

    return redirect('platform_admin:plans_list')


@super_admin_required
def plan_edit_view(request, pk):
    """
    Edit an existing subscription plan tier's parameters, capacity thresholds, pricing, and active status.
    """
    plan = get_object_or_404(SubscriptionPlan, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        try:
            max_students = int(request.POST.get('max_students', plan.max_students))
            max_staff = int(request.POST.get('max_staff', plan.max_staff))
            max_clients = int(request.POST.get('max_clients', plan.max_clients))
            price = float(request.POST.get('price_per_year', plan.price_per_year))
        except (ValueError, TypeError):
            messages.error(request, "Invalid numeric input for capacity or pricing.")
            return redirect('platform_admin:plans_list')

        if not name:
            messages.error(request, "Plan Display Name cannot be empty.")
            return redirect('platform_admin:plans_list')

        new_code = request.POST.get('code', plan.code).strip().upper()
        if new_code and new_code != plan.code:
            if SubscriptionPlan.objects.filter(code=new_code).exclude(pk=plan.pk).exists():
                messages.error(request, f"Plan code '{new_code}' is already used by another plan tier.")
                return redirect('platform_admin:plans_list')
            plan.code = new_code

        plan.name = name
        plan.description = description
        plan.max_students = max_students
        plan.max_staff = max_staff
        plan.max_clients = max_clients
        plan.price_per_year = price
        plan.is_active = 'is_active' in request.POST
        plan.save()

        PlatformAuditLog.log(
            user=request.user,
            action='PLAN_CHANGED',
            target=plan.name,
            description=f"Updated subscription plan '{plan.name}' ({plan.code}). Price: NPR {plan.price_per_year}, Max Students: {plan.max_students}, Max Clients: {plan.max_clients}, Active: {plan.is_active}.",
            request=request
        )

        messages.success(request, f"Subscription plan '{plan.name}' updated successfully.")
        return redirect('platform_admin:plans_list')

    return redirect('platform_admin:plans_list')


@super_admin_required
def plan_toggle_status_view(request, pk):
    """
    Toggle a plan between Active and Inactive.
    """
    plan = get_object_or_404(SubscriptionPlan, pk=pk)
    if request.method == 'POST':
        plan.is_active = not plan.is_active
        plan.save()

        status_label = "activated" if plan.is_active else "deactivated"
        PlatformAuditLog.log(
            user=request.user,
            action='PLAN_CHANGED',
            target=plan.name,
            description=f"Plan '{plan.name}' ({plan.code}) was {status_label}.",
            request=request
        )
        messages.success(request, f"Subscription plan '{plan.name}' has been {status_label}.")

    return redirect('platform_admin:plans_list')


@super_admin_required
def plan_delete_view(request, pk):
    """
    Safely delete a plan if it has no active organizations subscribed.
    """
    plan = get_object_or_404(SubscriptionPlan, pk=pk)
    if request.method == 'POST':
        orgs_count = plan.subscriptions.count()
        if orgs_count > 0:
            messages.error(
                request,
                f"Cannot delete plan '{plan.name}' because it is assigned to {orgs_count} organization(s). Deactivate the plan instead."
            )
            return redirect('platform_admin:plans_list')

        plan_name = plan.name
        plan_code = plan.code
        plan.delete()

        PlatformAuditLog.log(
            user=request.user,
            action='PLAN_CHANGED',
            target=plan_name,
            description=f"Deleted subscription plan '{plan_name}' ({plan_code}).",
            request=request
        )
        messages.success(request, f"Subscription plan '{plan_name}' was permanently deleted.")

    return redirect('platform_admin:plans_list')


# ==========================================
# 7. PLATFORM AUDIT LOGS & SEARCH
# ==========================================

@super_admin_required
def audit_logs_view(request):
    """
    Comprehensive platform audit trail with filters.
    """
    qs = PlatformAuditLog.objects.select_related('user', 'organization').all()

    search = request.GET.get('search', '').strip()
    action_filter = request.GET.get('action', '')
    org_filter = request.GET.get('org', '')

    if search:
        qs = qs.filter(
            Q(target__icontains=search) |
            Q(description__icontains=search) |
            Q(user__username__icontains=search)
        )

    if action_filter:
        qs = qs.filter(action=action_filter)

    if org_filter:
        qs = qs.filter(organization_id=org_filter)

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    organizations = Organization.objects.all().order_by('name')

    return render(request, 'platform_admin/audit_logs.html', {
        'page_obj': page_obj,
        'search': search,
        'action_filter': action_filter,
        'org_filter': org_filter,
        'actions': PlatformAuditLog.ACTION_CHOICES,
        'organizations': organizations,
    })


@super_admin_required
def global_search_view(request):
    """
    Global platform-wide search across Organizations, Admins, Staff, and Students.
    """
    query = request.GET.get('q', '').strip()

    orgs_found = []
    users_found = []
    students_found = []

    if query and len(query) >= 2:
        orgs_found = Organization.objects.filter(
            Q(name__icontains=query) |
            Q(org_id__icontains=query) |
            Q(short_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query)
        ).select_related('subscription__plan', 'primary_admin')[:10]

        users_found = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        ).select_related('organization')[:10]

        students_found = Student.objects.filter(
            Q(student_id__icontains=query) |
            Q(full_name__icontains=query)
        ).select_related('class_level', 'section')[:10]

    return render(request, 'platform_admin/search_results.html', {
        'query': query,
        'orgs_found': orgs_found,
        'users_found': users_found,
        'students_found': students_found,
        'total_results': len(orgs_found) + len(users_found) + len(students_found),
    })


@super_admin_required
def platform_settings_view(request):
    """
    Platform-level settings (Platform Name, Logo, Support Contact, Trial defaults).
    """
    settings_obj = PlatformSetting.get_instance()

    if request.method == 'POST':
        # Platform Web Settings
        settings_obj.platform_name = request.POST.get('platform_name', settings_obj.platform_name).strip()
        settings_obj.support_email = request.POST.get('support_email', settings_obj.support_email).strip()
        settings_obj.support_phone = request.POST.get('support_phone', settings_obj.support_phone).strip()
        settings_obj.default_trial_days = int(request.POST.get('default_trial_days', 30))
        settings_obj.default_subscription_months = int(request.POST.get('default_subscription_months', 12))

        # Mobile Application Settings
        settings_obj.app_name = request.POST.get('app_name', settings_obj.app_name).strip()
        settings_obj.app_version = request.POST.get('app_version', settings_obj.app_version).strip()
        settings_obj.app_description = request.POST.get('app_description', settings_obj.app_description).strip()
        settings_obj.app_designer_name = request.POST.get('app_designer_name', settings_obj.app_designer_name).strip()
        settings_obj.app_designer_role = request.POST.get('app_designer_role', settings_obj.app_designer_role).strip()
        settings_obj.app_contact_phone = request.POST.get('app_contact_phone', settings_obj.app_contact_phone).strip()
        settings_obj.app_contact_email = request.POST.get('app_contact_email', settings_obj.app_contact_email).strip()
        settings_obj.app_website = request.POST.get('app_website', settings_obj.app_website).strip()
        settings_obj.app_copyright_text = request.POST.get('app_copyright_text', settings_obj.app_copyright_text).strip()

        if 'platform_logo' in request.FILES:
            settings_obj.platform_logo = request.FILES['platform_logo']

        if 'app_logo' in request.FILES:
            settings_obj.app_logo = request.FILES['app_logo']

        settings_obj.save()

        PlatformAuditLog.log(
            user=request.user,
            action='SETTINGS_UPDATED',
            target='PlatformSetting',
            description="Platform settings updated.",
            request=request
        )

        messages.success(request, "Platform settings updated successfully.")
        return redirect('platform_admin:settings')

    return render(request, 'platform_admin/settings.html', {'settings_obj': settings_obj})
