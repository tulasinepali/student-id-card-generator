import json
from datetime import datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone

from apps.students.models import Student, VerificationRecord
from apps.academic.models import AcademicYear, ClassLevel, Section
from apps.idcards.models import IDCardTemplate, PrintLayout
from apps.platform_admin.models import Organization
from apps.core.utils import get_current_organization
from apps.idcards.services.pdf_generator import (
    generate_id_cards_pdf,
    export_id_cards_batch,
    render_single_card_image,
    render_single_card_pdf
)
from apps.students.services.excel_service import (
    generate_excel_template,
    parse_and_validate_excel,
    commit_excel_import,
    export_students_to_excel
)
from apps.students.services.photo_service import process_student_photo, process_bulk_photo_zip
from apps.core.services.audit import log_action


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.role == 'ADMIN')


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def students_list_view(request):
    """
    Searchable and filterable student directory with pagination and bulk actions.
    Strictly scoped to the tenant organization.
    """
    org = get_current_organization(request)

    qs = Student.objects.select_related('class_level', 'section', 'academic_year', 'client').prefetch_related('id_cards')
    if org:
        qs = qs.filter(organization=org)
    elif not request.user.is_superuser:
        qs = qs.none()

    # Filters
    search = request.GET.get('search', '').strip()
    class_id = request.GET.get('class')
    section_id = request.GET.get('section')
    year_id = request.GET.get('year') or request.GET.get('academic_year')
    v_status = request.GET.get('verification_status')
    missing_photo = request.GET.get('missing_photo')

    if search:
        qs = qs.filter(
            Q(full_name__icontains=search) |
            Q(student_id__icontains=search) |
            Q(roll_number__icontains=search) |
            Q(class_level__name__icontains=search) |
            Q(section__name__icontains=search) |
            Q(guardian_name__icontains=search) |
            Q(guardian_phone__icontains=search)
        )
    if class_id:
        qs = qs.filter(class_level_id=class_id)
    if section_id:
        qs = qs.filter(section_id=section_id)
    if year_id:
        qs = qs.filter(academic_year_id=year_id)
    if v_status:
        qs = qs.filter(verification_status=v_status)
    if missing_photo == 'yes':
        qs = qs.filter(Q(photo='') | Q(photo__isnull=True))

    # Multi-client scoping for Photo Studio / Printing Press accounts
    active_client = None
    if org and getattr(org, 'is_studio', False):
        active_client_id = request.session.get('active_client_id')
        client_param = request.GET.get('client')
        effective_client_id = client_param or active_client_id
        if effective_client_id and str(effective_client_id) != '0':
            qs = qs.filter(client_id=effective_client_id)
            active_client = org.clients.filter(id=effective_client_id).first()


    # Active filter descriptions for UI display
    active_filters = []
    if search:
        active_filters.append({'key': 'search', 'label': f'Search: "{search}"'})
    if class_id:
        c_item = ClassLevel.objects.filter(id=class_id).first()
        if c_item:
            active_filters.append({'key': 'class', 'label': f'Class: {c_item.name}'})
    if section_id:
        s_item = Section.objects.filter(id=section_id).first()
        if s_item:
            active_filters.append({'key': 'section', 'label': f'Section: Sec {s_item.name}'})
    if year_id:
        y_item = AcademicYear.objects.filter(id=year_id).first()
        if y_item:
            active_filters.append({'key': 'year', 'label': f'Session: {y_item.name}'})
    if v_status:
        active_filters.append({'key': 'verification_status', 'label': f'Status: {v_status.capitalize()}'})
    if missing_photo == 'yes':
        active_filters.append({'key': 'missing_photo', 'label': 'Missing Photo Only'})
    if active_client:
        active_filters.append({'key': 'client', 'label': f'Client: {active_client.name}'})

    total_all_students = Student.objects.filter(organization=org).count() if org else qs.count()

    # Bulk actions and Card Export actions
    if request.method == 'POST':
        bulk_action = request.POST.get('bulk_action')
        selected_ids = request.POST.getlist('selected_students')

        # print_class and print_single do not require selected_ids
        if bulk_action not in ('print_class', 'print_single') and not selected_ids:
            messages.warning(request, "Please select at least one student checkbox to perform this action.")
            return redirect(request.get_full_path())

        students_to_act = Student.objects.filter(id__in=selected_ids)

        if bulk_action == 'verify':
            count = 0
            for s in students_to_act:
                if s.has_photo:
                    s.verification_status = 'VERIFIED'
                    s.verified_at = timezone.now()
                    s.verified_by = request.user
                    s.rejection_reason = ""
                    s.save()
                    VerificationRecord.objects.create(
                        student=s, actor=request.user, previous_status='PENDING', new_status='VERIFIED', notes='Bulk approved by admin'
                    )
                    count += 1
            messages.success(request, f"Successfully approved and verified {count} students with photos.")
            return redirect(request.get_full_path())

        elif bulk_action == 'delete':
            deleted_count = students_to_act.count()
            students_to_act.delete()
            log_action(user=request.user, action='STUDENT_EDITED', details={'action': 'bulk_delete', 'count': deleted_count}, request=request)
            messages.success(request, f"Deleted {deleted_count} student records.")
            return redirect(request.get_full_path())

        elif bulk_action == 'print':
            # Export selected students
            template_id = request.POST.get('template')
            layout_id = request.POST.get('layout')
            format_type = request.POST.get('format_type', 'PDF').upper()
            sides_mode = request.POST.get('sides_mode', 'FRONT_ONLY')
            image_side = request.POST.get('image_side', 'COMBINED')
            include_unverified = request.POST.get('include_unverified') in ['true', 'True', '1', 'on']

            template = IDCardTemplate.objects.filter(id=template_id, is_active=True).first() or IDCardTemplate.objects.filter(is_default=True).first() or IDCardTemplate.objects.first()
            layout = PrintLayout.objects.filter(id=layout_id).first() or PrintLayout.objects.first()
            academic_year = AcademicYear.objects.filter(is_active=True).first()

            try:
                content, content_type, filename = export_id_cards_batch(
                    students=students_to_act,
                    template=template,
                    layout=layout,
                    academic_year=academic_year,
                    format_type=format_type,
                    side=image_side,
                    sides_mode=sides_mode,
                    user=request.user,
                    request=request,
                    enforce_verified_only=not include_unverified,
                    scope_name=f"Selected_{len(selected_ids)}_Students"
                )
                response = HttpResponse(content, content_type=content_type)
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            except Exception as e:
                messages.error(request, f"Printing/Export Error: {str(e)}")
                return redirect(request.get_full_path())

        elif bulk_action == 'print_class':
            target_class_id = request.POST.get('class_id')
            target_section_id = request.POST.get('section_id')
            target_year_id = request.POST.get('year_id')
            template_id = request.POST.get('template')
            layout_id = request.POST.get('layout')
            format_type = request.POST.get('format_type', 'PDF').upper()
            sides_mode = request.POST.get('sides_mode', 'FRONT_ONLY')
            image_side = request.POST.get('image_side', 'COMBINED')
            include_unverified = request.POST.get('include_unverified') in ['true', 'True', '1', 'on']

            target_class = ClassLevel.objects.filter(id=target_class_id).first() if target_class_id else None
            target_section = Section.objects.filter(id=target_section_id).first() if target_section_id and target_section_id != 'all' else None
            academic_year = AcademicYear.objects.filter(id=target_year_id).first() if target_year_id else (AcademicYear.objects.filter(is_active=True).first() or AcademicYear.objects.first())

            students_qs = Student.objects.all()
            if target_class:
                students_qs = students_qs.filter(class_level=target_class)
            if target_section:
                students_qs = students_qs.filter(section=target_section)
            if academic_year:
                students_qs = students_qs.filter(academic_year=academic_year)
            students_qs = students_qs.order_by('class_level__numeric_order', 'section__name', 'roll_number')

            if not students_qs.exists():
                messages.warning(request, "No students found in the selected class and section.")
                return redirect(request.get_full_path())

            template = IDCardTemplate.objects.filter(id=template_id, is_active=True).first() or IDCardTemplate.objects.filter(is_default=True).first() or IDCardTemplate.objects.first()
            layout = PrintLayout.objects.filter(id=layout_id).first() or PrintLayout.objects.first()

            sec_str = f"_{target_section.name}" if target_section else "_All_Sections"
            class_str = target_class.name.replace(' ', '_') if target_class else "All_Classes"
            scope_name = f"{class_str}{sec_str}"

            try:
                content, content_type, filename = export_id_cards_batch(
                    students=students_qs,
                    template=template,
                    layout=layout,
                    academic_year=academic_year,
                    format_type=format_type,
                    side=image_side,
                    sides_mode=sides_mode,
                    user=request.user,
                    request=request,
                    enforce_verified_only=not include_unverified,
                    scope_name=scope_name
                )
                response = HttpResponse(content, content_type=content_type)
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            except Exception as e:
                messages.error(request, f"Printing/Export Error: {str(e)}")
                return redirect(request.get_full_path())

        elif bulk_action == 'print_single':
            single_student_id = request.POST.get('student_id')
            student = get_object_or_404(qs, id=single_student_id)
            template_id = request.POST.get('template')
            layout_id = request.POST.get('layout')
            format_type = request.POST.get('format_type', 'PDF').upper()
            sides_mode = request.POST.get('sides_mode', 'FRONT_ONLY')
            image_side = request.POST.get('image_side', 'COMBINED')
            include_unverified = request.POST.get('include_unverified') in ['true', 'True', '1', 'on']

            template = IDCardTemplate.objects.filter(id=template_id, is_active=True).first() or IDCardTemplate.objects.filter(is_default=True).first() or IDCardTemplate.objects.first()
            layout = PrintLayout.objects.filter(id=layout_id).first() if layout_id else 'single'
            academic_year = student.academic_year or AcademicYear.objects.filter(is_active=True).first()

            try:
                content, content_type, filename = export_id_cards_batch(
                    students=[student],
                    template=template,
                    layout=layout,
                    academic_year=academic_year,
                    format_type=format_type,
                    side=image_side,
                    sides_mode=sides_mode,
                    user=request.user,
                    request=request,
                    enforce_verified_only=not include_unverified,
                    scope_name=student.student_id
                )
                response = HttpResponse(content, content_type=content_type)
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            except Exception as e:
                messages.error(request, f"Printing/Export Error: {str(e)}")
                return redirect(request.get_full_path())

        return redirect(request.get_full_path())

    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    classes = ClassLevel.objects.filter(Q(organization=org) | Q(organization__isnull=True)).prefetch_related('sections').all()
    years = AcademicYear.objects.filter(Q(organization=org) | Q(organization__isnull=True)).all()
    templates = IDCardTemplate.objects.filter(Q(organization=org) | Q(organization__isnull=True), is_active=True)
    layouts = PrintLayout.objects.all()

    return render(request, 'students/students_list.html', {
        'page_obj': page_obj,
        'classes': classes,
        'years': years,
        'templates': templates,
        'layouts': layouts,
        'selected_class': class_id,
        'selected_section': section_id,
        'selected_year': year_id,
        'selected_v_status': v_status,
        'selected_missing_photo': missing_photo,
        'search_query': search,
        'active_filters': active_filters,
        'total_all_students': total_all_students,
    })


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def student_detail_view(request, pk):
    org = get_current_organization(request)

    student_qs = Student.objects.select_related('class_level', 'section', 'academic_year', 'verified_by').prefetch_related('id_cards', 'verification_history__actor')
    if org:
        student_qs = student_qs.filter(organization=org)
    student = get_object_or_404(student_qs, pk=pk)

    templates = IDCardTemplate.objects.filter(Q(organization=org) | Q(organization__isnull=True), is_active=True)
    layouts = PrintLayout.objects.all()

    if request.method == 'POST' and request.POST.get('action') == 'print_card':
        template_id = request.POST.get('template')
        layout_id = request.POST.get('layout')
        format_type = request.POST.get('format_type', 'PDF').upper()
        sides_mode = request.POST.get('sides_mode', 'FRONT_ONLY')
        image_side = request.POST.get('image_side', 'COMBINED')
        layout_choice = request.POST.get('layout_choice', 'card')

        template = IDCardTemplate.objects.filter(id=template_id, is_active=True).first() or IDCardTemplate.objects.filter(is_default=True).first() or IDCardTemplate.objects.first()
        layout = PrintLayout.objects.filter(id=layout_id).first() if (layout_choice == 'sheet' and layout_id) else 'single'
        academic_year = student.academic_year or AcademicYear.objects.filter(is_active=True).first()

        try:
            content, content_type, filename = export_id_cards_batch(
                students=[student],
                template=template,
                layout=layout,
                academic_year=academic_year,
                format_type=format_type,
                side=image_side,
                sides_mode=sides_mode,
                user=request.user,
                request=request,
                enforce_verified_only=False,
                scope_name=student.student_id
            )
            response = HttpResponse(content, content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            messages.error(request, f"Printing/Export Error: {str(e)}")
            return redirect(request.get_full_path())

    return render(request, 'students/student_detail.html', {
        'student': student,
        'templates': templates,
        'layouts': layouts,
    })


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def student_create_edit_view(request, pk=None):
    org = get_current_organization(request)

    student = get_object_or_404(Student, pk=pk, organization=org) if (pk and org) else (get_object_or_404(Student, pk=pk) if pk else None)
    classes = ClassLevel.objects.filter(Q(organization=org) | Q(organization__isnull=True)).prefetch_related('sections').all()
    years = AcademicYear.objects.filter(Q(organization=org) | Q(organization__isnull=True)).all()

    is_studio = bool(org and getattr(org, 'is_studio', False))
    studio_clients = org.clients.filter(is_active=True) if is_studio else []
    active_client_id = request.session.get('active_client_id') if is_studio else None

    prefill_class = request.GET.get('class', '')
    prefill_section = request.GET.get('section', '')
    prefill_client = request.GET.get('client', '') or (str(active_client_id) if active_client_id else '')

    if request.method == 'POST':
        student_id = request.POST.get('student_id', '').strip()
        roll_number = request.POST.get('roll_number', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        class_id = request.POST.get('class_level')
        section_id = request.POST.get('section')
        year_id = request.POST.get('academic_year')
        dob_str = request.POST.get('date_of_birth', '').strip()
        gender = request.POST.get('gender', 'MALE')
        address = request.POST.get('address', '').strip()
        guardian_name = request.POST.get('guardian_name', '').strip()
        guardian_phone = request.POST.get('guardian_phone', '').strip()
        blood_group = request.POST.get('blood_group', '').strip()
        status_val = request.POST.get('status', 'ACTIVE')
        client_id_val = request.POST.get('client_id') or request.POST.get('client') or (str(active_client_id) if active_client_id else None)

        # Form preservation object
        temp_data = {
            'student_id': student_id,
            'roll_number': roll_number,
            'full_name': full_name,
            'class_level_id': int(class_id) if class_id and class_id.isdigit() else None,
            'section_id': int(section_id) if section_id and section_id.isdigit() else None,
            'academic_year_id': int(year_id) if year_id and year_id.isdigit() else None,
            'date_of_birth': dob_str,
            'gender': gender,
            'address': address,
            'guardian_name': guardian_name,
            'guardian_phone': guardian_phone,
            'blood_group': blood_group,
            'status': status_val,
            'client_id': int(client_id_val) if client_id_val and str(client_id_val).isdigit() else None,
        }

        # Auto-generate student_id if not provided
        if not student_id and not student:
            last_stu = Student.objects.filter(organization=org).order_by('-id').first() if org else Student.objects.order_by('-id').first()
            next_num = (last_stu.id + 1) if last_stu else 1
            gen_id = f"STU{8000 + next_num}"
            while Student.objects.filter(organization=org, student_id=gen_id).exists() if org else Student.objects.filter(student_id=gen_id).exists():
                next_num += 1
                gen_id = f"STU{8000 + next_num}"
            student_id = gen_id
            temp_data['student_id'] = student_id

        # Validate required fields
        if not full_name:
            messages.error(request, "Student Full Name is required.")
            return render(request, 'students/student_form.html', {
                'student': student or temp_data, 'classes': classes, 'years': years,
                'is_studio': is_studio, 'studio_clients': studio_clients,
                'selected_client_id': client_id_val or prefill_client,
                'prefill_class': prefill_class, 'prefill_section': prefill_section,
            })

        if not roll_number or not roll_number.isdigit() or int(roll_number) <= 0:
            messages.error(request, "Please enter a valid positive roll number.")
            return render(request, 'students/student_form.html', {
                'student': student or temp_data, 'classes': classes, 'years': years,
                'is_studio': is_studio, 'studio_clients': studio_clients,
                'selected_client_id': client_id_val or prefill_client,
                'prefill_class': prefill_class, 'prefill_section': prefill_section,
            })

        if not class_id or not section_id:
            messages.error(request, "Please select both a Class Level and a Section.")
            return render(request, 'students/student_form.html', {
                'student': student or temp_data, 'classes': classes, 'years': years,
                'is_studio': is_studio, 'studio_clients': studio_clients,
                'selected_client_id': client_id_val or prefill_client,
                'prefill_class': prefill_class, 'prefill_section': prefill_section,
            })

        if is_studio and not client_id_val and studio_clients.exists():
            messages.error(request, "Please select a Client Organization for this student.")
            return render(request, 'students/student_form.html', {
                'student': student or temp_data, 'classes': classes, 'years': years,
                'is_studio': is_studio, 'studio_clients': studio_clients,
                'selected_client_id': client_id_val or prefill_client,
                'prefill_class': prefill_class, 'prefill_section': prefill_section,
            })

        # Check unique student ID within organization
        existing_id = Student.objects.filter(student_id=student_id)
        if org:
            existing_id = existing_id.filter(organization=org)
        if student:
            existing_id = existing_id.exclude(pk=student.pk)
        if existing_id.exists():
            messages.error(request, f"Student ID '{student_id}' is already assigned to another student in your organization.")
            return render(request, 'students/student_form.html', {
                'student': student or temp_data, 'classes': classes, 'years': years,
                'is_studio': is_studio, 'studio_clients': studio_clients,
                'selected_client_id': client_id_val or prefill_client,
                'prefill_class': prefill_class, 'prefill_section': prefill_section,
            })

        # Check unique roll within class/section/year/org
        existing_roll = Student.objects.filter(
            class_level_id=class_id, section_id=section_id, academic_year_id=year_id, roll_number=int(roll_number)
        )
        if org:
            existing_roll = existing_roll.filter(organization=org)
        if student:
            existing_roll = existing_roll.exclude(pk=student.pk)
        if existing_roll.exists():
            messages.error(request, f"Roll Number #{roll_number} is already assigned in this section.")
            return render(request, 'students/student_form.html', {
                'student': student or temp_data, 'classes': classes, 'years': years,
                'is_studio': is_studio, 'studio_clients': studio_clients,
                'selected_client_id': client_id_val or prefill_client,
                'prefill_class': prefill_class, 'prefill_section': prefill_section,
            })

        dob = None
        if dob_str:
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y'):
                try:
                    dob = datetime.strptime(dob_str, fmt).date()
                    break
                except ValueError:
                    pass
            if not dob:
                messages.error(request, f"Invalid date format: '{dob_str}'. Please use YYYY-MM-DD.")
                return render(request, 'students/student_form.html', {
                    'student': student or temp_data, 'classes': classes, 'years': years,
                    'is_studio': is_studio, 'studio_clients': studio_clients,
                    'selected_client_id': client_id_val or prefill_client,
                    'prefill_class': prefill_class, 'prefill_section': prefill_section,
                })

        if not student:
            student = Student(
                organization=org,
                student_id=student_id,
                roll_number=int(roll_number),
                full_name=full_name,
                class_level_id=class_id,
                section_id=section_id,
                academic_year_id=year_id,
                date_of_birth=dob,
                gender=gender,
                address=address,
                guardian_name=guardian_name,
                guardian_phone=guardian_phone,
                blood_group=blood_group,
                status=status_val
            )
        else:
            if org and not student.organization:
                student.organization = org
            student.student_id = student_id
            student.roll_number = int(roll_number)
            student.full_name = full_name
            student.class_level_id = class_id
            student.section_id = section_id
            student.academic_year_id = year_id
            student.date_of_birth = dob
            student.gender = gender
            student.address = address
            student.guardian_name = guardian_name
            student.guardian_phone = guardian_phone
            student.blood_group = blood_group
            student.status = status_val

        # Handle Photo Upload
        if 'photo' in request.FILES:
            photo_file = request.FILES['photo']
            ext = os.path.splitext(photo_file.name)[1].lower()
            allowed_exts = getattr(settings, 'ALLOWED_IMAGE_EXTENSIONS', ['.jpg', '.jpeg', '.png', '.webp'])
            max_size = getattr(settings, 'MAX_IMAGE_UPLOAD_SIZE', 5 * 1024 * 1024)
            if ext not in allowed_exts:
                messages.error(request, f"Unsupported photo format '{ext}'. Allowed extensions: JPG, JPEG, PNG, WEBP.")
            elif photo_file.size > max_size:
                messages.error(request, f"Photo exceeds the maximum allowed size of {max_size // (1024 * 1024)}MB.")
            else:
                try:
                    processed = process_student_photo(photo_file)
                    student.photo.save(f"{student.student_id}.jpg", processed, save=False)
                except Exception as e:
                    messages.error(request, f"Photo processing failed: {str(e)}")

        # Client association under Studio / Press account
        if is_studio and client_id_val:
            try:
                student.client = org.clients.filter(id=int(client_id_val)).first()
            except (ValueError, TypeError):
                pass

        if org and not student.organization:
            student.organization = org

        student.save()
        log_action(
            user=request.user,
            action='STUDENT_EDITED' if pk else 'STUDENT_CREATED',
            object_type='Student',
            object_id=student.id,
            object_repr=str(student),
            request=request
        )
        messages.success(request, f"Student {student.full_name} saved successfully.")
        return redirect('student_detail', pk=student.pk)

    selected_client_id = (
        getattr(student, 'client_id', None)
        or (str(student.client.id) if getattr(student, 'client', None) else None)
        or prefill_client
    )

    return render(request, 'students/student_form.html', {
        'student': student,
        'classes': classes,
        'years': years,
        'is_studio': is_studio,
        'studio_clients': studio_clients,
        'selected_client_id': str(selected_client_id) if selected_client_id else '',
        'prefill_class': prefill_class,
        'prefill_section': prefill_section,
    })


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def student_delete_view(request, pk):
    org = get_current_organization(request)

    student = get_object_or_404(Student, pk=pk, organization=org) if org else get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        student_repr = str(student)
        student.delete()
        log_action(
            user=request.user,
            action='STUDENT_EDITED',
            object_type='Student',
            object_id=pk,
            object_repr=student_repr,
            details={'action': 'deleted'},
            request=request
        )
        messages.success(request, f"Student {student_repr} was deleted.")
        return redirect('students_list')
    return render(request, 'students/student_confirm_delete.html', {'student': student})


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def excel_import_view(request):
    """
    Strict 2-Phase Excel Import:
    Phase 1: Parse, validate against duplicate IDs, rolls, dates, and preview results with error breakdown.
    Phase 2: User confirms valid records -> atomic database transaction commits records.
    """
    org = get_current_organization(request)

    org_filter = Q(organization=org) | Q(organization__isnull=True) if org else Q()
    classes = ClassLevel.objects.filter(org_filter).prefetch_related('sections').all()
    years = AcademicYear.objects.filter(org_filter).all()

    if request.method == 'POST':
        step = request.POST.get('step', 'upload')

        if step == 'upload':
            excel_file = request.FILES.get('excel_file')
            mode = request.POST.get('mode', 'class_wise')
            class_id = request.POST.get('class_level')
            section_id = request.POST.get('section')
            year_id = request.POST.get('academic_year')

            if not excel_file:
                messages.error(request, "Please select an Excel (.xlsx) file to upload.")
                return redirect('excel_import')

            # Security: Validate file extension and size
            file_ext = os.path.splitext(excel_file.name)[1].lower()
            if file_ext not in ['.xlsx', '.xlsm']:
                messages.error(request, "Invalid file format. Only Excel files (.xlsx, .xlsm) are permitted.")
                return redirect('excel_import')

            max_excel_size = getattr(settings, 'MAX_EXCEL_UPLOAD_SIZE', 10 * 1024 * 1024)
            if excel_file.size > max_excel_size:
                messages.error(request, f"Excel file exceeds maximum allowed size of {max_excel_size // (1024 * 1024)}MB.")
                return redirect('excel_import')

            class_obj = ClassLevel.objects.filter(id=class_id).first() if class_id else None
            section_obj = Section.objects.filter(id=section_id).first() if section_id else None
            year_obj = AcademicYear.objects.filter(id=year_id).first() if year_id else None

            if mode == 'class_wise' and (not class_obj or not section_obj or not year_obj):
                messages.error(request, "For class-wise import, please select Class, Section, and Academic Year.")
                return redirect('excel_import')

            try:
                results = parse_and_validate_excel(
                    excel_file,
                    mode=mode,
                    class_level=class_obj,
                    section=section_obj,
                    academic_year=year_obj,
                    organization=org
                )
                # Store valid records in session for Phase 2 confirmation
                request.session['pending_import_records'] = results['valid_records']

                return render(request, 'students/excel_preview.html', {
                    'results': results,
                    'mode': mode,
                    'class_obj': class_obj,
                    'section_obj': section_obj,
                    'year_obj': year_obj,
                })
            except Exception as e:
                messages.error(request, f"Excel processing error: {str(e)}")
                return redirect('excel_import')

        elif step == 'confirm':
            valid_records = request.session.get('pending_import_records', [])
            if not valid_records:
                messages.warning(request, "No pending records found to import.")
                return redirect('excel_import')

            try:
                imported_count = commit_excel_import(valid_records, user=request.user, request=request)
                request.session.pop('pending_import_records', None)
                messages.success(request, f"Successfully imported {imported_count} students into database!")
                return redirect('students_list')
            except Exception as e:
                messages.error(request, f"Database transaction failed: {str(e)}")
                return redirect('excel_import')

        elif step == 'cancel':
            request.session.pop('pending_import_records', None)
            messages.info(request, "Excel import cancelled.")
            return redirect('excel_import')

    return render(request, 'students/excel_import.html', {
        'classes': classes,
        'years': years,
    })


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def excel_template_download_view(request):
    mode = request.GET.get('mode', 'class_wise')
    output = generate_excel_template(mode=mode)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"Student_Import_Template_{mode}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def excel_export_view(request):
    org = get_current_organization(request)

    qs = Student.objects.all()
    if org:
        qs = qs.filter(organization=org)
    elif not request.user.is_superuser:
        qs = qs.none()

    class_id = request.GET.get('class')
    section_id = request.GET.get('section')
    year_id = request.GET.get('year')

    if class_id:
        qs = qs.filter(class_level_id=class_id)
    if section_id:
        qs = qs.filter(section_id=section_id)
    if year_id:
        qs = qs.filter(academic_year_id=year_id)

    output = export_students_to_excel(qs)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="Students_Directory_Export.xlsx"'
    return response


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def bulk_photos_view(request):
    """
    Bulk student photo upload via ZIP.
    Matches filename (e.g. STU1001.jpg) to Student.student_id, normalizes with Pillow,
    and returns comprehensive match report and missing photo list.
    """
    org = get_current_organization(request)

    org_filter = Q(organization=org) | Q(organization__isnull=True) if org else Q()
    classes = ClassLevel.objects.filter(org_filter).prefetch_related('sections').all()
    years = AcademicYear.objects.filter(org_filter).all()

    if request.method == 'POST':
        zip_file = request.FILES.get('photo_zip')
        class_id = request.POST.get('class_level')
        section_id = request.POST.get('section')
        year_id = request.POST.get('academic_year')

        if not zip_file:
            messages.error(request, "Please select a ZIP file containing student photos.")
            return redirect('bulk_photos')

        # Security: Validate file extension and size
        file_ext = os.path.splitext(zip_file.name)[1].lower()
        if file_ext != '.zip':
            messages.error(request, "Invalid file format. Only ZIP archives (.zip) are permitted.")
            return redirect('bulk_photos')

        max_zip_size = getattr(settings, 'MAX_ZIP_UPLOAD_SIZE', 100 * 1024 * 1024)
        if zip_file.size > max_zip_size:
            messages.error(request, f"ZIP file exceeds maximum allowed size of {max_zip_size // (1024 * 1024)}MB.")
            return redirect('bulk_photos')

        class_obj = ClassLevel.objects.filter(id=class_id).first() if class_id else None
        section_obj = Section.objects.filter(id=section_id).first() if section_id else None
        year_obj = AcademicYear.objects.filter(id=year_id).first() if year_id else None

        try:
            results = process_bulk_photo_zip(
                zip_file,
                class_level=class_obj,
                section=section_obj,
                academic_year=year_obj,
                user=request.user,
                request=request
            )
            messages.success(request, f"Processed {results['matched_count']} student photos successfully.")
            return render(request, 'students/bulk_photos_result.html', {
                'results': results,
                'class_obj': class_obj,
                'section_obj': section_obj,
            })
        except Exception as e:
            messages.error(request, f"Photo ZIP processing error: {str(e)}")
            return redirect('bulk_photos')

    return render(request, 'students/bulk_photos.html', {
        'classes': classes,
        'years': years,
    })


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def verification_queue_view(request):
    """
    Review and approve/reject students submitted by teachers for verification.
    Strictly isolated per organization and per studio client.
    """
    org = get_current_organization(request)
    if not org:
        queue = Student.objects.none()
        is_studio = False
        active_client = None
        effective_uses_mobile_app = True
    else:
        is_studio = bool(getattr(org, 'is_studio', False))
        active_client_id = request.session.get('active_client_id') if is_studio else None
        active_client = None

        queue = Student.objects.filter(organization=org, verification_status__in=['SUBMITTED', 'PENDING'])
        if is_studio and active_client_id and str(active_client_id) != '0':
            active_client = org.clients.filter(id=active_client_id).first()
            if active_client:
                queue = queue.filter(client=active_client)

        if active_client:
            effective_uses_mobile_app = getattr(active_client, 'uses_mobile_app', True)
        else:
            effective_uses_mobile_app = getattr(org, 'uses_mobile_app', True)

    queue = queue.select_related('class_level', 'section', 'academic_year', 'submitted_by', 'client').order_by('-submitted_at', 'class_level', 'roll_number')

    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        decision = request.POST.get('decision')  # 'approve' or 'reject'
        notes = request.POST.get('notes', '').strip()

        if not org:
            student_qs = Student.objects.none()
        else:
            student_qs = Student.objects.filter(organization=org)
            if is_studio and active_client:
                student_qs = student_qs.filter(client=active_client)

        student = get_object_or_404(student_qs, id=student_id)
        prev_status = student.verification_status

        if decision == 'approve':
            if not student.has_photo:
                messages.error(request, f"Cannot verify {student.full_name}: Photo is missing.")
                return redirect('verification_queue')

            student.verification_status = 'VERIFIED'
            student.verified_at = timezone.now()
            student.verified_by = request.user
            student.rejection_reason = ""
            student.save()

            VerificationRecord.objects.create(
                student=student,
                actor=request.user,
                previous_status=prev_status,
                new_status='VERIFIED',
                notes=notes or 'Approved for ID card printing by admin'
            )

            log_action(
                user=request.user,
                action='STUDENT_APPROVED',
                object_type='Student',
                object_id=student.id,
                object_repr=str(student),
                request=request
            )
            messages.success(request, f"Student {student.full_name} has been approved and marked as VERIFIED.")

        elif decision == 'reject':
            if not notes:
                messages.error(request, "A reason is mandatory when rejecting a verification request.")
                return redirect('verification_queue')

            student.verification_status = 'REJECTED'
            student.rejection_reason = notes
            student.save()

            VerificationRecord.objects.create(
                student=student,
                actor=request.user,
                previous_status=prev_status,
                new_status='REJECTED',
                notes=notes
            )

            log_action(
                user=request.user,
                action='STUDENT_REJECTED',
                object_type='Student',
                object_id=student.id,
                object_repr=str(student),
                details={'rejection_reason': notes},
                request=request
            )
            messages.warning(request, f"Student {student.full_name} verification was rejected. Reason: {notes}")

        return redirect('verification_queue')

    return render(request, 'students/verification_queue.html', {
        'queue': queue,
        'is_studio': is_studio if org else False,
        'active_client': active_client if org else None,
        'effective_uses_mobile_app': effective_uses_mobile_app,
    })
