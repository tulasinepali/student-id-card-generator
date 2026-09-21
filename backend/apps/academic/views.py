from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q, Prefetch
from datetime import datetime
from apps.academic.models import AcademicYear, ClassLevel, Section
from apps.accounts.models import TeacherProfile
from apps.students.models import Student
from apps.platform_admin.models import Organization
from apps.core.utils import get_current_organization
from apps.core.services.audit import log_action


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.role == 'ADMIN')


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def academic_years_view(request):
    org = get_current_organization(request)

    year_qs = AcademicYear.objects.all()
    if org:
        years = year_qs.filter(Q(organization=org) | Q(organization__isnull=True))
    elif not request.user.is_superuser:
        years = year_qs.none()
    else:
        years = year_qs.all()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            start_str = request.POST.get('start_date')
            end_str = request.POST.get('end_date')
            is_active = request.POST.get('is_active') == 'on'

            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
                ay = AcademicYear.objects.create(
                    organization=org,
                    name=name,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=is_active
                )
                log_action(user=request.user, action='TEMPLATE_CHANGED', object_type='AcademicYear', object_id=ay.id, object_repr=str(ay), request=request)
                messages.success(request, f"Academic Year {ay.name} created successfully.")
            except Exception as e:
                messages.error(request, f"Error creating academic year: {str(e)}")
            return redirect('academic_years')

        elif action == 'set_active':
            ay_id = request.POST.get('ay_id')
            ay = get_object_or_404(years, id=ay_id)
            ay.is_active = True
            ay.save()
            messages.success(request, f"{ay.name} is now the active academic year.")
            return redirect('academic_years')

    return render(request, 'academic/academic_years.html', {'years': years})


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def classes_sections_view(request):
    org = get_current_organization(request)

    is_studio = bool(org and getattr(org, 'is_studio', False))
    active_client_id = request.session.get('active_client_id') if is_studio else None
    active_client = None

    if is_studio:
        if active_client_id and str(active_client_id) != '0':
            active_client = org.clients.filter(id=active_client_id).first()
            student_filter = Q(organization=org, client_id=active_client.id) if active_client else Q(organization=org)
            class_count_filter = Q(students__organization=org, students__client_id=active_client.id) if active_client else Q(students__organization=org)
        else:
            student_filter = Q(organization=org)
            class_count_filter = Q(students__organization=org)
    else:
        if org:
            student_filter = Q(organization=org)
            class_count_filter = Q(students__organization=org)
        elif not request.user.is_superuser:
            student_filter = Q(id__isnull=True)
            class_count_filter = Q(students__id__isnull=True)
        else:
            student_filter = Q()
            class_count_filter = Q()

    teacher_qs = TeacherProfile.objects.select_related('user', 'client')
    if is_studio:
        if active_client:
            teacher_qs = teacher_qs.filter(client=active_client)
        else:
            teacher_qs = teacher_qs.filter(user__organization=org)
    else:
        if org:
            teacher_qs = teacher_qs.filter(user__organization=org)
        elif not request.user.is_superuser:
            teacher_qs = teacher_qs.none()

    student_qs = Student.objects.filter(student_filter).select_related('academic_year', 'client').prefetch_related('id_cards').order_by('roll_number')

    class_filter = Q(organization=org) | Q(organization__isnull=True) if org else Q()
    classes = ClassLevel.objects.filter(class_filter).prefetch_related(
        Prefetch('sections', queryset=Section.objects.prefetch_related(
            Prefetch('assigned_teachers', queryset=teacher_qs, to_attr='scoped_teachers'),
            Prefetch('students', queryset=student_qs, to_attr='scoped_students')
        )),
    ).annotate(
        student_count=Count('students', filter=class_count_filter, distinct=True)
    ).order_by('numeric_order', 'id')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_class':
            name = request.POST.get('name', '').strip()
            order = request.POST.get('numeric_order', 1)
            try:
                c = ClassLevel.objects.create(organization=org, name=name, numeric_order=int(order))
                # Automatically create default Section A
                Section.objects.create(class_level=c, name="A")
                messages.success(request, f"Class {c.name} created with Section A.")
            except Exception as e:
                messages.error(request, f"Error creating class: {str(e)}")
            return redirect('classes_sections')

        elif action == 'create_section':
            class_id = request.POST.get('class_id')
            c = get_object_or_404(ClassLevel.objects.filter(class_filter), id=class_id)
            sec_name = request.POST.get('name', '').strip().upper()
            try:
                Section.objects.create(class_level=c, name=sec_name)
                messages.success(request, f"Section {sec_name} added to {c.name}.")
            except Exception as e:
                messages.error(request, f"Error adding section: {str(e)}")
            return redirect('classes_sections')

    return render(request, 'academic/classes_sections.html', {
        'classes': classes,
        'is_studio': is_studio,
        'active_client': active_client,
    })
