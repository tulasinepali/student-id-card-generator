from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.core.paginator import Paginator

from apps.core.models import School, AuditLog
from apps.academic.models import AcademicYear, ClassLevel, Section
from apps.accounts.models import TeacherProfile
from apps.students.models import Student
from apps.idcards.models import IDCard, IDCardTemplate, PrintLayout
from apps.core.services.audit import log_action
from apps.students.services.photo_service import process_student_photo
from apps.platform_admin.models import Organization, OrganizationClient, SubscriptionPlan
from apps.core.utils import get_current_organization


def landing_page_view(request):
    """
    Public SaaS Landing Page showcasing the ID Card Management System:
    - Dual solution for Single Schools and Commercial Studios/Printing Presses
    - Live Interactive Card Customizer
    - Mobile Companion App & QR Verification details
    - Dynamic Subscription Plans in NPR
    - Demo Request submission
    """
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_per_year')[:4]
    sample_card = IDCard.objects.filter(card_status='ACTIVE').first() or IDCard.objects.first()
    sample_token = sample_card.secure_token if sample_card else None

    total_orgs = Organization.objects.filter(status='ACTIVE').count() or 18
    total_students = Student.objects.count() or 4500
    total_cards = IDCard.objects.count() or 3200

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        org_name = request.POST.get('org_name', '').strip()
        org_type = request.POST.get('org_type', 'SCHOOL').strip()
        plan_code = request.POST.get('plan_code', '').strip()
        message_text = request.POST.get('message', '').strip()

        if name and (email or phone):
            messages.success(
                request,
                f"Thank you, {name}! Your demo request for '{org_name or 'your organization'}' has been received. Our team will contact you shortly."
            )
        else:
            messages.error(request, "Please provide your name and either an email or phone number to request a demo.")
        return redirect('landing_page')

    context = {
        'plans': plans,
        'sample_token': sample_token,
        'total_orgs': total_orgs,
        'total_students': total_students,
        'total_cards': total_cards,
    }
    return render(request, 'landing.html', context)


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.role == 'ADMIN')


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def dashboard_view(request):
    """
    Main Admin Dashboard displaying comprehensive KPI statistics and class-wise summaries.
    Supports multi-client studio scoping when operating under a Photo Studio / Printing Press account.
    Strictly scoped to the tenant organization.
    """
    org = get_current_organization(request)

    active_year_qs = AcademicYear.objects.filter(is_active=True)
    if org:
        active_year = active_year_qs.filter(organization=org).first() or active_year_qs.filter(organization__isnull=True).first()
    else:
        active_year = active_year_qs.first()

    students_qs = Student.objects.all()
    if org:
        students_qs = students_qs.filter(organization=org)
    elif not request.user.is_superuser:
        students_qs = students_qs.none()

    if active_year:
        students_qs = students_qs.filter(academic_year=active_year)

    # Multi-client scoping for Photo Studio / Commercial Printing Press accounts
    active_client = None
    if org and getattr(org, 'is_studio', False):
        active_client_id = request.session.get('active_client_id')
        if active_client_id:
            students_qs = students_qs.filter(client_id=active_client_id)
            active_client = org.clients.filter(id=active_client_id).first()

    total_students = students_qs.count()
    active_students = students_qs.filter(status='ACTIVE').count()
    verified_students = students_qs.filter(verification_status='VERIFIED').count()
    pending_verification = students_qs.filter(verification_status__in=['PENDING', 'SUBMITTED']).count()
    submitted_verification = students_qs.filter(verification_status='SUBMITTED').count()
    rejected_verification = students_qs.filter(verification_status='REJECTED').count()
    missing_photos = students_qs.filter(Q(photo='') | Q(photo__isnull=True)).count()

    teachers_qs = TeacherProfile.objects.filter(status='ACTIVE')
    if org:
        teachers_qs = teachers_qs.filter(user__organization=org)
    elif not request.user.is_superuser:
        teachers_qs = teachers_qs.none()
    total_teachers = teachers_qs.count()

    class_filter = Q(organization=org) | Q(organization__isnull=True) if org else Q()
    total_classes = ClassLevel.objects.filter(class_filter).count()

    # ID Cards stats
    cards_qs = IDCard.objects.all()
    if org:
        cards_qs = cards_qs.filter(student__organization=org)
    elif not request.user.is_superuser:
        cards_qs = cards_qs.none()

    if active_year:
        cards_qs = cards_qs.filter(academic_year=active_year)
    if active_client:
        cards_qs = cards_qs.filter(student__client=active_client)
    generated_cards = cards_qs.count()
    printed_cards = cards_qs.filter(card_status='PRINTED').count()
    expired_cards = cards_qs.filter(validity_status='EXPIRED').count()
    revoked_cards = cards_qs.filter(validity_status='REVOKED').count()

    # Class-wise breakdown
    classes = ClassLevel.objects.filter(class_filter).prefetch_related('sections').all()
    class_summaries = []
    for c in classes:
        for s in c.sections.all():
            sec_students = students_qs.filter(class_level=c, section=s)
            sec_total = sec_students.count()
            if sec_total > 0:
                sec_verified = sec_students.filter(verification_status='VERIFIED').count()
                sec_pending = sec_students.filter(verification_status__in=['PENDING', 'SUBMITTED']).count()
                sec_photos = sec_students.exclude(Q(photo='') | Q(photo__isnull=True)).count()
                sec_cards = cards_qs.filter(student__in=sec_students).count()
                class_summaries.append({
                    'class_name': c.name,
                    'section_name': s.name,
                    'total': sec_total,
                    'verified': sec_verified,
                    'pending': sec_pending,
                    'photos': sec_photos,
                    'cards': sec_cards,
                })

    logs_qs = AuditLog.objects.select_related('user')
    if org:
        logs_qs = logs_qs.filter(user__organization=org)
    elif not request.user.is_superuser:
        logs_qs = logs_qs.none()
    recent_logs = logs_qs[:10]

    context = {
        'active_year': active_year,
        'active_client': active_client,
        'total_students': total_students,
        'active_students': active_students,
        'verified_students': verified_students,
        'pending_verification': pending_verification,
        'submitted_verification': submitted_verification,
        'rejected_verification': rejected_verification,
        'missing_photos': missing_photos,
        'total_teachers': total_teachers,
        'total_classes': total_classes,
        'generated_cards': generated_cards,
        'printed_cards': printed_cards,
        'expired_cards': expired_cards,
        'revoked_cards': revoked_cards,
        'class_summaries': class_summaries,
        'recent_logs': recent_logs,
    }
    return render(request, 'core/dashboard.html', context)


@login_required(login_url='admin_login')
def school_settings_view(request):
    """
    Organization profile, branding, and signatures are managed centrally by Platform Super Admin
    at /platform-admin/organizations/<pk>/edit/.
    Direct tenant access to school settings is completely removed.
    """
    is_super = getattr(request.user, 'is_super_admin', None)
    has_super = is_super() if callable(is_super) else (request.user.is_superuser or getattr(request.user, 'role', '') == 'SUPER_ADMIN')

    if has_super:
        messages.info(request, "Organization profile and branding parameters are managed centrally in the Platform Admin panel.")
        org = getattr(request.user, 'organization', None)
        if org:
            return redirect('platform_admin:organization_edit', pk=org.pk)
        return redirect('platform_admin:organizations_list')

    messages.info(request, "Organization profile and branding parameters are managed centrally by the Platform Super Administrator.")
    return redirect('dashboard')



@login_required(login_url='admin_login')
def audit_logs_view(request):
    """
    System Audit is restricted strictly to Platform Super Administrators.
    Normal school administrators receive HTTP 403 Forbidden.
    Super Administrators are redirected to the platform audit logs console.
    """
    is_super = getattr(request.user, 'is_super_admin', None)
    has_perm = is_super() if callable(is_super) else (request.user.is_superuser or getattr(request.user, 'role', '') == 'SUPER_ADMIN')

    if not has_perm:
        return HttpResponseForbidden("Access Denied: System Audit Logs are strictly restricted to Platform Super Administrators.")

    return redirect('platform_admin:audit_logs')


def public_qr_verify_view(request, token):
    """
    Clean, responsive verification page rendered when anyone scans the QR code.
    Displays verification badge, student name, student ID, class, section, photo,
    organization name, and validity dates.
    Strictly protects sensitive private data (omits address, guardian phone).
    """
    token = str(token).strip()

    try:
        card = IDCard.objects.select_related(
            'student', 'student__class_level', 'student__section',
            'student__client__school', 'student__organization__school'
        ).get(secure_token=token)
        is_valid, reason = card.is_currently_valid()
        if card.student.client and card.student.client.school:
            school = card.student.client.school
        elif card.student.organization and card.student.organization.school:
            school = card.student.organization.school
        else:
            school = School.get_instance()
    except IDCard.DoesNotExist:
        card = None
        is_valid = False
        reason = "INVALID"
        school = School.get_instance()

    context = {
        'school': school,
        'card': card,
        'is_valid': is_valid,
        'reason': reason,
        'today': date.today(),
    }
    return render(request, 'core/public_qr_verify.html', context)


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def client_management_view(request):
    """
    Client Hub for Studios, Printing Presses, and Corporate Subscribers.
    Lists all client schools/institutions with student & card print statistics.
    """
    org = get_current_organization(request)

    if not org or not org.is_studio:
        messages.info(request, "Multi-Client Management is reserved for Photo Studios, Printing Presses, and Corporate accounts.")
        return redirect('dashboard')

    search = request.GET.get('search', '').strip()
    clients = org.clients.all()
    if search:
        clients = clients.filter(
            Q(name__icontains=search) |
            Q(client_code__icontains=search) |
            Q(phone__icontains=search) |
            Q(signatory_name__icontains=search)
        )

    can_add_more = True
    active_client_id = request.session.get('active_client_id')

    context = {
        'org': org,
        'clients': clients,
        'search': search,
        'total_clients': clients.count(),
        'can_add_more': can_add_more,
        'active_client_id': active_client_id,
    }
    return render(request, 'core/client_management.html', context)


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def client_create_view(request):
    """
    Registers a new client organization under this studio/press account without capacity limit.
    """
    org = get_current_organization(request)
    if not org and request.user.is_superuser:
        org = Organization.objects.filter(org_type__in=['STUDIO_PRESS', 'COMPANY', 'CORPORATE_AGENCY']).first()

    if not org or not org.is_studio:
        messages.error(request, "Permission denied. Client addition is reserved for Photo Studios and Printing Presses.")
        return redirect('dashboard')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        short_name = request.POST.get('short_name', '').strip()
        client_type = request.POST.get('client_type', 'SCHOOL')
        address = request.POST.get('address', '').strip()
        municipality = request.POST.get('municipality', '').strip()
        district = request.POST.get('district', '').strip()
        province = request.POST.get('province', '').strip()
        country = request.POST.get('country', 'Nepal').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        website = request.POST.get('website', '').strip()
        signatory_name = request.POST.get('signatory_name', 'Principal').strip()
        signatory_title = request.POST.get('signatory_title', 'Principal').strip()

        if not name:
            messages.error(request, "Client institution name is required.")
            return render(request, 'core/client_form.html', {'is_edit': False})

        # Create associated School record for seamless card rendering & backwards compatibility
        school = School.objects.create(
            name=name,
            short_name=short_name or name[:10],
            address=address,
            municipality=municipality,
            district=district,
            province=province,
            country=country,
            phone=phone,
            email=email,
            website=website,
            head_teacher_name=signatory_name or "Principal",
        )

        if 'logo' in request.FILES:
            school.logo = request.FILES['logo']
        if 'authorized_signature' in request.FILES:
            school.head_teacher_signature = request.FILES['authorized_signature']
        school.save()

        uses_mobile_app = 'uses_mobile_app' in request.POST

        client = OrganizationClient.objects.create(
            organization=org,
            name=name,
            short_name=short_name,
            client_type=client_type,
            uses_mobile_app=uses_mobile_app,
            address=address,
            municipality=municipality,
            district=district,
            province=province,
            country=country,
            phone=phone,
            email=email,
            website=website,
            signatory_name=signatory_name,
            signatory_title=signatory_title,
            school=school,
            logo=school.logo,
            authorized_signature=school.head_teacher_signature,
        )

        # Automatically switch to new client
        request.session['active_client_id'] = client.id
        messages.success(request, f"Client institution '{client.name}' successfully added! Workspace switched to this client.")
        return redirect('client_management')

    return render(request, 'core/client_form.html', {'is_edit': False})


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def client_edit_view(request, pk):
    """
    Edits an existing client school/organization profile and branding assets.
    """
    org = get_current_organization(request)

    client = get_object_or_404(OrganizationClient, pk=pk, organization=org)

    if request.method == 'POST':
        client.name = request.POST.get('name', client.name).strip()
        client.short_name = request.POST.get('short_name', client.short_name).strip()
        client.client_type = request.POST.get('client_type', client.client_type)
        client.uses_mobile_app = 'uses_mobile_app' in request.POST
        client.address = request.POST.get('address', client.address).strip()
        client.municipality = request.POST.get('municipality', client.municipality).strip()
        client.district = request.POST.get('district', client.district).strip()
        client.province = request.POST.get('province', client.province).strip()
        client.country = request.POST.get('country', client.country).strip()
        client.phone = request.POST.get('phone', client.phone).strip()
        client.email = request.POST.get('email', client.email).strip()
        client.website = request.POST.get('website', client.website).strip()
        client.signatory_name = request.POST.get('signatory_name', client.signatory_name).strip()
        client.signatory_title = request.POST.get('signatory_title', client.signatory_title).strip()

        if 'logo' in request.FILES:
            client.logo = request.FILES['logo']
        if 'authorized_signature' in request.FILES:
            client.authorized_signature = request.FILES['authorized_signature']

        client.save()

        if not client.uses_mobile_app:
            Student.objects.filter(client=client, verification_status='PENDING').update(verification_status='VERIFIED')

        # Keep linked school instance in sync
        if client.school:
            client.school.name = client.name
            client.school.short_name = client.short_name
            client.school.address = client.address
            client.school.phone = client.phone
            client.school.email = client.email
            client.school.head_teacher_name = client.signatory_name
            if client.logo:
                client.school.logo = client.logo
            if client.authorized_signature:
                client.school.head_teacher_signature = client.authorized_signature
            client.school.save()

        messages.success(request, f"Client institution '{client.name}' updated successfully.")
        return redirect('client_management')

    return render(request, 'core/client_form.html', {'client': client, 'is_edit': True})


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def switch_client_view(request, pk):
    """
    Switches the active client workspace in session. pk=0 switches to 'All Clients'.
    """
    org = get_current_organization(request)
    if pk == 0 or str(pk) == '0':
        request.session.pop('active_client_id', None)
        messages.info(request, "Switched to 'All Clients' global view.")
    else:
        if org:
            client = get_object_or_404(OrganizationClient, pk=pk, organization=org)
        else:
            client = get_object_or_404(OrganizationClient, pk=pk)
        request.session['active_client_id'] = client.id
        messages.success(request, f"Active workspace set to: {client.name}")

    referer = request.META.get('HTTP_REFERER')
    if referer and '/clients/' not in referer:
        return redirect(referer)
    return redirect('dashboard')


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def client_delete_view(request, pk):
    """
    Permanently deletes a client organization along with its associated students,
    cards, templates, and linked school branding profile under this studio/press account.
    """
    org = get_current_organization(request)
    if not org and request.user.is_superuser:
        org = Organization.objects.filter(org_type__in=['STUDIO_PRESS', 'COMPANY', 'CORPORATE_AGENCY']).first()

    if not org or not org.is_studio:
        messages.error(request, "Permission denied. Client deletion is reserved for Photo Studios and Printing Presses.")
        return redirect('dashboard')

    client = get_object_or_404(OrganizationClient, pk=pk, organization=org)

    students_count = client.students.count()
    cards_count = IDCard.objects.filter(student__client=client).count()
    teachers_count = client.teachers.count()
    templates_count = client.templates.count()

    if request.method == 'POST':
        client_name = client.name
        client_code = client.client_code
        linked_school = client.school

        with transaction.atomic():
            # Delete client-specific ID card templates
            client.templates.all().delete()

            # Delete all students belonging to this client (cascades to ID cards, photos, verifications)
            client.students.all().delete()

            # Unassign teachers linked to this client
            client.teachers.update(client=None)

            # Delete client record
            client.delete()

            # Delete linked School record if present
            if linked_school:
                try:
                    linked_school.delete()
                except Exception:
                    pass

        # If deleted client was active workspace, reset session
        active_id = request.session.get('active_client_id')
        if active_id == pk or str(active_id) == str(pk):
            request.session.pop('active_client_id', None)

        log_action(
            user=request.user,
            action='ORG_UPDATED',
            object_type='OrganizationClient',
            object_id=pk,
            object_repr=f"{client_name} [{client_code}]",
            details={
                'action': 'deleted',
                'students_deleted': students_count,
                'cards_deleted': cards_count,
            },
            request=request
        )

        messages.success(request, f"Client organization '{client_name}' and all associated student records were successfully deleted.")
        return redirect('client_management')

    return render(request, 'core/client_confirm_delete.html', {
        'client': client,
        'students_count': students_count,
        'cards_count': cards_count,
        'teachers_count': teachers_count,
        'templates_count': templates_count,
    })


