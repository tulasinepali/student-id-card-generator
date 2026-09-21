import json
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q
from django.db import transaction

from apps.idcards.models import IDCardTemplate, TemplateElement, PrintLayout, IDCard
from apps.academic.models import AcademicYear, ClassLevel, Section
from apps.students.models import Student
from apps.core.models import School
from apps.platform_admin.models import Organization
from apps.core.utils import get_current_organization
from apps.idcards.services.pdf_generator import generate_id_cards_pdf, export_id_cards_batch
from apps.idcards.services.image_analysis import analyze_card_image
from apps.core.services.audit import log_action


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.role == 'ADMIN')


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def templates_list_view(request):
    org = get_current_organization(request)

    template_filter = Q(organization=org) | Q(organization__isnull=True) if org else Q()
    templates = IDCardTemplate.objects.filter(template_filter).prefetch_related('elements', 'generated_cards').all()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, "Template name is required.")
                return redirect('templates_list')

            design_mode = request.POST.get('design_mode', 'SCRATCH')
            orientation = request.POST.get('orientation', 'PORTRAIT')
            default_w = 54.0 if orientation == 'PORTRAIT' else 86.0
            default_h = 86.0 if orientation == 'PORTRAIT' else 54.0

            try:
                width_mm = float(request.POST.get('width_mm') or default_w)
                height_mm = float(request.POST.get('height_mm') or default_h)
            except ValueError:
                width_mm, height_mm = default_w, default_h

            duplex_mode = request.POST.get('duplex_mode', 'FRONT_BACK')
            bg_fit_mode = request.POST.get('bg_fit_mode', 'FILL')
            back_bg_fit_mode = request.POST.get('back_bg_fit_mode', 'FILL')
            bg_color = request.POST.get('background_color', '#FFFFFF')
            back_bg_color = request.POST.get('back_background_color', '#F8FAFC')

            front_img = request.FILES.get('front_image')
            back_img = request.FILES.get('back_image')

            front_dpi, front_w_px, front_h_px = None, None, None
            back_dpi, back_w_px, back_h_px = None, None, None

            # Perform DPI analysis on uploaded designs
            if front_img:
                analysis = analyze_card_image(front_img, width_mm, height_mm)
                if analysis.get('success'):
                    front_dpi = analysis['dpi']
                    front_w_px = analysis['width_px']
                    front_h_px = analysis['height_px']
                    if not analysis['is_suitable']:
                        messages.warning(request, f"Front Design Image: {analysis['message']}")
                    else:
                        messages.info(request, f"Front Design: {analysis['resolution_str']} ({front_dpi} DPI) - {analysis['message']}")

            if back_img:
                analysis_back = analyze_card_image(back_img, width_mm, height_mm)
                if analysis_back.get('success'):
                    back_dpi = analysis_back['dpi']
                    back_w_px = analysis_back['width_px']
                    back_h_px = analysis_back['height_px']
                    if not analysis_back['is_suitable']:
                        messages.warning(request, f"Back Design Image: {analysis_back['message']}")

            t = IDCardTemplate.objects.create(
                organization=org,
                name=name,
                design_mode=design_mode,
                orientation=orientation,
                width_mm=width_mm,
                height_mm=height_mm,
                duplex_mode=duplex_mode,
                background_color=bg_color,
                background_image=front_img,
                bg_fit_mode=bg_fit_mode,
                front_image_dpi=front_dpi,
                front_resolution_w=front_w_px,
                front_resolution_h=front_h_px,
                back_background_color=back_bg_color,
                back_background_image=back_img,
                back_bg_fit_mode=back_bg_fit_mode,
                back_image_dpi=back_dpi,
                back_resolution_w=back_w_px,
                back_resolution_h=back_h_px,
            )

            # Prepopulate standard elements according to mode
            if design_mode == 'SCRATCH':
                if orientation == 'PORTRAIT':
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='RECTANGLE', label_text="Header Bar", x_mm=0, y_mm=0, width_mm=width_mm, height_mm=16, fill_color='#1E3A8A', z_index=1)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='SCHOOL_LOGO', label_text="Logo", x_mm=3, y_mm=2, width_mm=12, height_mm=12, z_index=2)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='DYNAMIC_FIELD', dynamic_field_key='{{school.name}}', label_text="{{school.name}}", x_mm=16, y_mm=4, width_mm=35, height_mm=8, font_size=8.5, font_weight='BOLD', font_color='#FFFFFF', z_index=3)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='STUDENT_PHOTO', label_text="Photo", x_mm=14, y_mm=19, width_mm=26, height_mm=32, border_width=0.5, border_color='#CBD5E1', border_radius=2.0, z_index=4)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='DYNAMIC_FIELD', dynamic_field_key='{{student.name}}', label_text="{{student.name}}", x_mm=3, y_mm=53, width_mm=48, height_mm=6, font_size=9.5, font_weight='BOLD', font_color='#0F172A', text_align='CENTER', z_index=5)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='TEXT', label_text="ID: ", x_mm=5, y_mm=60, width_mm=12, height_mm=4, font_size=7, font_weight='BOLD', font_color='#64748B', z_index=6)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='DYNAMIC_FIELD', dynamic_field_key='{{student.student_id}}', label_text="{{student.student_id}}", x_mm=17, y_mm=60, width_mm=32, height_mm=4, font_size=7.5, font_weight='BOLD', font_color='#1E293B', z_index=7)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='TEXT', label_text="Class: ", x_mm=5, y_mm=65, width_mm=12, height_mm=4, font_size=7, font_weight='BOLD', font_color='#64748B', z_index=8)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='DYNAMIC_FIELD', dynamic_field_key='{{student.class}} - {{student.section}}', label_text="{{student.class}} - {{student.section}}", x_mm=17, y_mm=65, width_mm=32, height_mm=4, font_size=7.5, font_weight='NORMAL', font_color='#1E293B', z_index=9)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='QR_CODE', label_text="QR", x_mm=4, y_mm=71, width_mm=12, height_mm=12, z_index=10)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='SIGNATURE', label_text="Signature", x_mm=26, y_mm=73, width_mm=24, height_mm=8, z_index=11)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='TEXT', label_text="Principal", x_mm=26, y_mm=81, width_mm=24, height_mm=3.5, font_size=5.5, font_color='#64748B', text_align='CENTER', z_index=12)
                else:
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='RECTANGLE', label_text="Header Bar", x_mm=0, y_mm=0, width_mm=width_mm, height_mm=12, fill_color='#1E3A8A', z_index=1)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='SCHOOL_LOGO', label_text="Logo", x_mm=4, y_mm=1.5, width_mm=9, height_mm=9, z_index=2)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='DYNAMIC_FIELD', dynamic_field_key='{{school.name}}', label_text="{{school.name}}", x_mm=16, y_mm=3, width_mm=65, height_mm=6, font_size=9.0, font_weight='BOLD', font_color='#FFFFFF', z_index=3)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='STUDENT_PHOTO', label_text="Photo", x_mm=6, y_mm=16, width_mm=24, height_mm=32, border_width=0.5, border_color='#CBD5E1', border_radius=2.0, z_index=4)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='DYNAMIC_FIELD', dynamic_field_key='{{student.name}}', label_text="{{student.name}}", x_mm=34, y_mm=16, width_mm=48, height_mm=6, font_size=9.5, font_weight='BOLD', font_color='#0F172A', z_index=5)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='DYNAMIC_FIELD', dynamic_field_key='ID: {{student.student_id}}', label_text="ID: {{student.student_id}}", x_mm=34, y_mm=23, width_mm=48, height_mm=5, font_size=7.5, font_weight='NORMAL', font_color='#334155', z_index=6)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='DYNAMIC_FIELD', dynamic_field_key='Class: {{student.class}} - {{student.section}}', label_text="Class: {{student.class}} - {{student.section}}", x_mm=34, y_mm=29, width_mm=48, height_mm=5, font_size=7.5, font_weight='NORMAL', font_color='#334155', z_index=7)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='QR_CODE', label_text="QR", x_mm=34, y_mm=36, width_mm=14, height_mm=14, z_index=8)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='SIGNATURE', label_text="Signature", x_mm=56, y_mm=38, width_mm=24, height_mm=8, z_index=9)
            else:
                # Mode B: Image Upload - place dynamic overlay fields
                if orientation == 'PORTRAIT':
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='STUDENT_PHOTO', label_text="Photo", x_mm=14, y_mm=18, width_mm=26, height_mm=32, z_index=1)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='DYNAMIC_FIELD', dynamic_field_key='{{student.name}}', label_text="{{student.name}}", x_mm=4, y_mm=52, width_mm=46, height_mm=6, font_size=9.5, font_weight='BOLD', font_color='#0F172A', text_align='CENTER', z_index=2)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='DYNAMIC_FIELD', dynamic_field_key='{{student.class}} - {{student.section}}', label_text="{{student.class}} - {{student.section}}", x_mm=4, y_mm=59, width_mm=46, height_mm=5, font_size=8.0, text_align='CENTER', z_index=3)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='QR_CODE', label_text="QR", x_mm=5, y_mm=68, width_mm=14, height_mm=14, z_index=4)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='SIGNATURE', label_text="Signature", x_mm=25, y_mm=72, width_mm=24, height_mm=8, z_index=5)
                else:
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='STUDENT_PHOTO', label_text="Photo", x_mm=6, y_mm=14, width_mm=24, height_mm=32, z_index=1)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='DYNAMIC_FIELD', dynamic_field_key='{{student.name}}', label_text="{{student.name}}", x_mm=34, y_mm=15, width_mm=48, height_mm=6, font_size=10.0, font_weight='BOLD', font_color='#0F172A', z_index=2)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='DYNAMIC_FIELD', dynamic_field_key='ID: {{student.student_id}}', label_text="ID: {{student.student_id}}", x_mm=34, y_mm=22, width_mm=48, height_mm=5, font_size=8.0, z_index=3)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='DYNAMIC_FIELD', dynamic_field_key='Class: {{student.class}} - {{student.section}}', label_text="Class: {{student.class}} - {{student.section}}", x_mm=34, y_mm=28, width_mm=48, height_mm=5, font_size=8.0, z_index=4)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='QR_CODE', label_text="QR", x_mm=34, y_mm=36, width_mm=14, height_mm=14, z_index=5)
                    TemplateElement.objects.create(template=t, side='FRONT', element_type='SIGNATURE', label_text="Signature", x_mm=56, y_mm=38, width_mm=24, height_mm=8, z_index=6)

            log_action(
                user=request.user,
                action='TEMPLATE_CREATED',
                object_type='IDCardTemplate',
                object_id=t.id,
                object_repr=t.name,
                details={'mode': design_mode, 'dimensions': f"{width_mm}x{height_mm}mm"},
                request=request
            )
            messages.success(request, f"Template '{t.name}' created successfully. Now position and customize your elements.")
            return redirect('template_designer', pk=t.pk)

    return render(request, 'idcards/templates_list.html', {'templates': templates})


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def template_duplicate_view(request, pk):
    """Duplicates an existing template and all its associated elements."""
    org = get_current_organization(request)

    template_filter = Q(organization=org) | Q(organization__isnull=True) if org else Q()
    template = get_object_or_404(IDCardTemplate.objects.filter(template_filter), pk=pk)
    cloned = template.duplicate()
    if org and not cloned.organization:
        cloned.organization = org
        cloned.save(update_fields=['organization'])

    log_action(
        user=request.user,
        action='TEMPLATE_DUPLICATED',
        object_type='IDCardTemplate',
        object_id=cloned.id,
        object_repr=cloned.name,
        details={'source_template_id': template.id},
        request=request
    )
    messages.success(request, f"Template '{template.name}' successfully duplicated as '{cloned.name}'.")
    return redirect('template_designer', pk=cloned.pk)


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def template_new_version_view(request, pk):
    """Creates an incremented version of this template while preserving historical generated cards."""
    org = get_current_organization(request)

    template_filter = Q(organization=org) | Q(organization__isnull=True) if org else Q()
    template = get_object_or_404(IDCardTemplate.objects.filter(template_filter), pk=pk)
    new_ver = template.create_new_version()
    if org and not new_ver.organization:
        new_ver.organization = org
        new_ver.save(update_fields=['organization'])

    log_action(
        user=request.user,
        action='TEMPLATE_NEW_VERSION',
        object_type='IDCardTemplate',
        object_id=new_ver.id,
        object_repr=new_ver.name,
        details={'original_version': template.version, 'new_version': new_ver.version},
        request=request
    )
    messages.success(request, f"Created Version {new_ver.version} for '{template.name}'. Previously generated cards will safely retain Version {template.version}.")
    return redirect('template_designer', pk=new_ver.pk)


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def template_preview_students_view(request, pk):
    """Returns real student records and a long-name sample student for interactive canvas preview."""
    org = get_current_organization(request)

    template_filter = Q(organization=org) | Q(organization__isnull=True) if org else Q()
    template = get_object_or_404(IDCardTemplate.objects.filter(template_filter), pk=pk)

    students = Student.objects.select_related('class_level', 'section', 'academic_year').filter(status='ACTIVE')
    if org:
        students = students.filter(organization=org)
    elif not request.user.is_superuser:
        students = students.none()

    school = (org.school if org and org.school else School.get_instance())

    # Studio multi-client scope
    active_client = None
    if org and getattr(org, 'is_studio', False):
        active_client_id = request.session.get('active_client_id')
        if active_client_id:
            active_client = org.clients.filter(id=active_client_id).first()
            students = students.filter(client_id=active_client_id)

    students = students[:25]

    student_list = []
    # Include sample long name to test overflow detection
    student_list.append({
        'id': -1,
        'student_id': 'STU-9999',
        'roll_number': 99,
        'full_name': 'Ram Prasad Bahadur Sharma',
        'class_name': 'Grade 10',
        'section_name': 'A',
        'dob': '2008-04-15',
        'gender': 'Male',
        'blood_group': 'B+',
        'guardian_name': 'Hari Bahadur Sharma',
        'guardian_phone': '+977-9800000000',
        'address': 'Ward No 4, Kathmandu, Nepal',
        'photo_url': None,
        'is_long_name': True
    })

    for s in students:
        student_list.append({
            'id': s.id,
            'student_id': s.student_id,
            'roll_number': s.roll_number,
            'full_name': s.full_name,
            'class_name': s.class_level.name if s.class_level else '',
            'section_name': s.section.name if s.section else '',
            'dob': s.date_of_birth.strftime('%Y-%m-%d') if s.date_of_birth else '',
            'gender': s.get_gender_display(),
            'blood_group': s.blood_group,
            'guardian_name': s.guardian_name,
            'guardian_phone': s.guardian_phone,
            'address': s.address,
            'photo_url': s.photo.url if s.photo else None,
            'is_long_name': len(s.full_name) > 22
        })

    effective_name = active_client.name if active_client else (school.name if school else 'Apex Academy')
    effective_logo_url = active_client.logo.url if active_client and active_client.logo else (school.logo.url if school and school.logo else None)
    effective_sig_url = active_client.authorized_signature.url if active_client and active_client.authorized_signature else (school.head_teacher_signature.url if school and school.head_teacher_signature else None)
    effective_head_teacher = active_client.signatory_name if active_client else (school.head_teacher_name if school else 'Principal')

    return JsonResponse({
        'students': student_list,
        'school': {
            'name': effective_name,
            'logo_url': effective_logo_url,
            'signature_url': effective_sig_url,
            'head_teacher_name': effective_head_teacher
        }
    })


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def template_designer_view(request, pk):
    """
    Advanced interactive ID Card Template Designer.
    Features drag-and-drop canvas, physical mm positioning, real student preview,
    pre-save validation, DPI analysis, layer reordering, and atomic saving.
    """
    org = get_current_organization(request)

    template_filter = Q(organization=org) | Q(organization__isnull=True) if org else Q()
    template = get_object_or_404(IDCardTemplate.objects.filter(template_filter), pk=pk)
    school = (org.school if org and org.school else School.get_instance())

    # Handle AJAX Requests (Save Canvas Elements, Background Upload)
    if request.method == 'POST':
        # Check if JSON payload (Canvas save)
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body.decode('utf-8'))
                action = data.get('action')

                if action == 'save_canvas_elements':
                    elements_data = data.get('elements', [])
                    warnings = []

                    # Pre-save validation: Check boundaries and QR overlaps
                    qr_boxes = []
                    for idx, el_d in enumerate(elements_data):
                        x = float(el_d.get('x_mm', 0))
                        y = float(el_d.get('y_mm', 0))
                        w = float(el_d.get('width_mm', 10))
                        h = float(el_d.get('height_mm', 10))
                        el_type = el_d.get('element_type')
                        side = el_d.get('side', 'FRONT')

                        # Boundary check
                        if x < 0 or y < 0 or (x + w) > (template.width_mm + 0.1) or (y + h) > (template.height_mm + 0.1):
                            label = el_d.get('label_text') or el_d.get('dynamic_field_key') or el_type
                            warnings.append(f"Element '{label}' extends beyond card boundaries ({x}mm, {y}mm, {w}x{h}mm).")

                        # QR size check
                        if el_type == 'QR_CODE':
                            if min(w, h) < 14.0:
                                warnings.append(f"QR Code size ({w}x{h}mm) is under recommended 15mm minimum for reliable scanning.")
                            qr_boxes.append({'side': side, 'x1': x, 'y1': y, 'x2': x + w, 'y2': y + h, 'z': int(el_d.get('z_index', 1))})

                    # Check QR overlaps
                    for el_d in elements_data:
                        el_type = el_d.get('element_type')
                        if el_type in ('QR_CODE', 'RECTANGLE', 'LINE'):
                            continue
                        ex1 = float(el_d.get('x_mm', 0))
                        ey1 = float(el_d.get('y_mm', 0))
                        ex2 = ex1 + float(el_d.get('width_mm', 10))
                        ey2 = ey1 + float(el_d.get('height_mm', 10))
                        eside = el_d.get('side', 'FRONT')
                        ez = int(el_d.get('z_index', 1))

                        for qr in qr_boxes:
                            if qr['side'] == eside and ez > qr['z']:
                                # Overlap condition
                                if not (ex2 <= qr['x1'] or ex1 >= qr['x2'] or ey2 <= qr['y1'] or ey1 >= qr['y2']):
                                    lbl = el_d.get('label_text') or el_d.get('dynamic_field_key') or el_type
                                    warnings.append(f"Element '{lbl}' overlaps the QR Code. Ensure QR code remains completely unobstructed for scanner readability.")

                    # Atomic save
                    with transaction.atomic():
                        template.elements.all().delete()
                        for el_d in elements_data:
                            TemplateElement.objects.create(
                                template=template,
                                side=el_d.get('side', 'FRONT'),
                                element_type=el_d.get('element_type', 'TEXT'),
                                dynamic_field_key=el_d.get('dynamic_field_key', '').strip(),
                                label_text=el_d.get('label_text', '').strip(),
                                x_mm=float(el_d.get('x_mm', 5.0)),
                                y_mm=float(el_d.get('y_mm', 5.0)),
                                width_mm=float(el_d.get('width_mm', 40.0)),
                                height_mm=float(el_d.get('height_mm', 8.0)),
                                font_family=el_d.get('font_family', 'Helvetica'),
                                font_size=float(el_d.get('font_size', 8.0)),
                                font_weight=el_d.get('font_weight', 'NORMAL'),
                                font_style=el_d.get('font_style', 'NORMAL'),
                                font_color=el_d.get('font_color', '#0F172A'),
                                text_align=el_d.get('text_align', 'LEFT'),
                                fill_color=el_d.get('fill_color', ''),
                                border_color=el_d.get('border_color', ''),
                                border_width=float(el_d.get('border_width', 0.0)),
                                border_radius=float(el_d.get('border_radius', 0.0)),
                                opacity=float(el_d.get('opacity', 1.0)),
                                is_circular=bool(el_d.get('is_circular', False)),
                                qr_error_correction=el_d.get('qr_error_correction', 'M'),
                                auto_shrink_text=bool(el_d.get('auto_shrink_text', True)),
                                text_wrap=bool(el_d.get('text_wrap', False)),
                                z_index=int(el_d.get('z_index', 1))
                            )

                    log_action(
                        user=request.user,
                        action='TEMPLATE_UPDATED',
                        object_type='IDCardTemplate',
                        object_id=template.id,
                        object_repr=template.name,
                        details={'elements_count': len(elements_data), 'warnings': warnings},
                        request=request
                    )

                    return JsonResponse({
                        'success': True,
                        'message': 'Template layout saved successfully.',
                        'warnings': warnings
                    })

            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)}, status=400)

        # Standard multipart form update (e.g. background upload or settings)
        action = request.POST.get('action')
        if action == 'upload_background':
            target_side = request.POST.get('target_side', 'FRONT')
            fit_mode = request.POST.get('bg_fit_mode', 'FILL')
            bg_file = request.FILES.get('background_file')

            if bg_file:
                analysis = analyze_card_image(bg_file, template.width_mm, template.height_mm)
                if target_side == 'FRONT':
                    template.background_image = bg_file
                    template.bg_fit_mode = fit_mode
                    if analysis.get('success'):
                        template.front_image_dpi = analysis['dpi']
                        template.front_resolution_w = analysis['width_px']
                        template.front_resolution_h = analysis['height_px']
                else:
                    template.back_background_image = bg_file
                    template.back_bg_fit_mode = fit_mode
                    if analysis.get('success'):
                        template.back_image_dpi = analysis['dpi']
                        template.back_resolution_w = analysis['width_px']
                        template.back_resolution_h = analysis['height_px']

                template.save()
                if not analysis.get('is_suitable', True):
                    messages.warning(request, f"{target_side.capitalize()} Design: {analysis.get('message')}")
                else:
                    messages.success(request, f"{target_side.capitalize()} background updated ({analysis.get('resolution_str')}, {analysis.get('dpi')} DPI).")
            return redirect('template_designer', pk=template.pk)

        elif action == 'update_template_meta':
            template.name = request.POST.get('name', template.name).strip()
            template.orientation = request.POST.get('orientation', template.orientation)
            template.width_mm = float(request.POST.get('width_mm', template.width_mm))
            template.height_mm = float(request.POST.get('height_mm', template.height_mm))
            template.background_color = request.POST.get('background_color', template.background_color)
            template.back_background_color = request.POST.get('back_background_color', template.back_background_color)
            template.bg_fit_mode = request.POST.get('bg_fit_mode', template.bg_fit_mode)
            template.back_bg_fit_mode = request.POST.get('back_bg_fit_mode', template.back_bg_fit_mode)
            template.duplex_mode = request.POST.get('duplex_mode', template.duplex_mode)
            template.is_default = request.POST.get('is_default') == 'on'
            template.save()
            messages.success(request, "Template properties updated.")
            return redirect('template_designer', pk=template.pk)

    # Prepare element serialization for interactive frontend
    elements = template.elements.all()
    elements_json = []
    for el in elements:
        elements_json.append({
            'id': el.id,
            'side': el.side,
            'element_type': el.element_type,
            'dynamic_field_key': el.dynamic_field_key,
            'label_text': el.label_text,
            'x_mm': el.x_mm,
            'y_mm': el.y_mm,
            'width_mm': el.width_mm,
            'height_mm': el.height_mm,
            'font_family': el.font_family,
            'font_size': el.font_size,
            'font_weight': el.font_weight,
            'font_style': getattr(el, 'font_style', 'NORMAL'),
            'font_color': el.font_color,
            'text_align': el.text_align,
            'fill_color': el.fill_color,
            'border_color': el.border_color,
            'border_width': el.border_width,
            'border_radius': el.border_radius,
            'opacity': getattr(el, 'opacity', 1.0),
            'is_circular': getattr(el, 'is_circular', False),
            'qr_error_correction': getattr(el, 'qr_error_correction', 'M'),
            'auto_shrink_text': getattr(el, 'auto_shrink_text', True),
            'text_wrap': getattr(el, 'text_wrap', False),
            'z_index': el.z_index,
        })

    # Available sample students for live preview dropdown
    students_for_preview = Student.objects.select_related('class_level', 'section').filter(status='ACTIVE')
    if org:
        students_for_preview = students_for_preview.filter(organization=org)
    elif not request.user.is_superuser:
        students_for_preview = students_for_preview.none()
    students_for_preview = students_for_preview[:20]

    # Check if this template was already used in printing
    cards_count = template.generated_cards.count()

    return render(request, 'idcards/template_designer.html', {
        'template': template,
        'elements_json': elements_json,
        'elements_json_str': json.dumps(elements_json),
        'school': school,
        'students_for_preview': students_for_preview,
        'cards_count': cards_count,
    })


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def print_center_view(request):
    """
    ID Card generation and print layout center.
    Adheres strictly to Rule 15: displays eligibility report (Verified, Pending, Missing Photo).
    Calculates auto grid, allows manual override, and generates real print-ready PDF.
    """
    org = get_current_organization(request)

    class_filter = Q(organization=org) | Q(organization__isnull=True) if org else Q()
    classes = ClassLevel.objects.filter(class_filter).prefetch_related('sections').all()
    years = AcademicYear.objects.filter(class_filter).all()
    templates = IDCardTemplate.objects.filter(class_filter, is_active=True)
    layouts = PrintLayout.objects.all()

    class_id = request.POST.get('class') or request.GET.get('class')
    section_id = request.POST.get('section') or request.GET.get('section')
    year_id = request.POST.get('year') or request.GET.get('year')
    template_id = request.POST.get('template') or request.GET.get('template')
    layout_id = request.POST.get('layout') or request.GET.get('layout')
    override_unverified = (request.POST.get('override_unverified') or request.GET.get('override_unverified')) in ['true', 'True', '1', 'on']
    format_type = (request.POST.get('format_type') or request.GET.get('format_type') or 'PDF').upper()
    sides_mode = request.POST.get('sides_mode') or request.GET.get('sides_mode') or 'FRONT_ONLY'
    image_side = request.POST.get('image_side', 'COMBINED')
    print_mode = request.POST.get('print_mode', 'all')
    selected_student_ids = request.POST.getlist('selected_students')

    selected_class = ClassLevel.objects.filter(class_filter, id=class_id).first() if class_id else classes.first()
    if section_id == 'all' or section_id == '':
        selected_section = None
    elif section_id:
        selected_section = Section.objects.filter(id=section_id).first()
        # Verify selected_section belongs to selected_class
        if selected_section and selected_class and selected_section.class_level != selected_class:
            selected_section = None
    else:
        selected_section = None

    selected_year = AcademicYear.objects.filter(class_filter, id=year_id).first() if year_id else AcademicYear.objects.filter(class_filter, is_active=True).first()
    selected_template = IDCardTemplate.objects.filter(class_filter, id=template_id, is_active=True).first() if template_id else (templates.filter(is_default=True).first() or templates.first())
    selected_layout = PrintLayout.objects.filter(id=layout_id).first() if layout_id else layouts.first()

    # Query students in selected scope
    students_in_scope = Student.objects.none()
    if selected_class and selected_year:
        student_base = Student.objects.all()
        if org:
            student_base = student_base.filter(organization=org)
        elif not request.user.is_superuser:
            student_base = student_base.none()

        if selected_section:
            students_in_scope = student_base.filter(
                class_level=selected_class,
                section=selected_section,
                academic_year=selected_year
            ).order_by('roll_number')
        else:
            students_in_scope = student_base.filter(
                class_level=selected_class,
                academic_year=selected_year
            ).order_by('section__name', 'roll_number')

    # Studio multi-client scope
    if org and getattr(org, 'is_studio', False):
        active_client_id = request.session.get('active_client_id')
        if active_client_id:
            students_in_scope = students_in_scope.filter(client_id=active_client_id)

    total_in_scope = students_in_scope.count()
    verified_eligible = [s for s in students_in_scope if s.is_print_eligible]
    verified_count = len(verified_eligible)
    pending_count = students_in_scope.filter(verification_status__in=['PENDING', 'SUBMITTED']).count()
    rejected_count = students_in_scope.filter(verification_status='REJECTED').count()
    missing_photo_count = students_in_scope.filter(Q(photo='') | Q(photo__isnull=True)).count()

    # Grid calculations
    auto_cols, auto_rows, auto_cards_per_page = (3, 5, 15)
    if selected_layout and selected_template:
        auto_cols, auto_rows, auto_cards_per_page = selected_layout.calculate_auto_grid(
            selected_template.width_mm, selected_template.height_mm
        )

    # Handle PDF or Image Export (JPEG / PNG / PDF)
    if request.method == 'POST' and request.POST.get('action') in ('generate_pdf', 'export_cards'):
        try:
            target_students = students_in_scope
            if print_mode == 'selected' and selected_student_ids:
                target_students = target_students.filter(id__in=selected_student_ids)

            if not target_students.exists():
                messages.warning(request, "No students selected for printing or export.")
                return redirect(request.get_full_path())

            enforce_rule = not override_unverified

            if override_unverified:
                log_action(
                    user=request.user,
                    action='PDF_GENERATED',
                    object_type='IDCard',
                    object_repr="OVERRIDE: Printed/Exported unverified students",
                    details={'class': selected_class.name if selected_class else 'All', 'section': selected_section.name if selected_section else 'All Sections'},
                    request=request
                )

            sec_name = selected_section.name if selected_section else "All_Sections"
            class_name = selected_class.name.replace(' ', '_') if selected_class else "Class"
            year_name = selected_year.name.replace('/', '_') if selected_year else "Session"
            scope_name = f"{class_name}_{sec_name}_{year_name}"

            if not selected_template:
                messages.error(request, "Please select an ID Card Template.")
                return redirect(request.get_full_path())

            if not selected_layout:
                messages.error(request, "Please select a Print Layout sheet.")
                return redirect(request.get_full_path())

            # Export ZIP batch of single images / PDFs
            if request.POST.get('action') == 'export_cards':
                content, content_type, filename = export_id_cards_batch(
                    students=target_students,
                    template=selected_template,
                    layout=selected_layout,
                    academic_year=selected_year,
                    format_type=format_type,
                    side=image_side,
                    sides_mode=sides_mode,
                    user=request.user,
                    request=request,
                    enforce_verified_only=enforce_rule,
                    scope_name=scope_name
                )
                response = HttpResponse(content, content_type=content_type)
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response

            # Generate multi-page print-sheet PDF
            pdf_bytes = generate_id_cards_pdf(
                students=target_students,
                template=selected_template,
                layout=selected_layout,
                academic_year=selected_year,
                user=request.user,
                request=request,
                enforce_verified_only=enforce_rule,
                sides_mode=sides_mode
            )
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="ID_Cards_Print_{scope_name}.pdf"'
            return response

        except ValueError as ve:
            messages.error(request, str(ve))
            return redirect(request.get_full_path())
        except Exception as e:
            messages.error(request, f"Card generation failed: {str(e)}")
            return redirect(request.get_full_path())

    return render(request, 'idcards/print_center.html', {
        'classes': classes,
        'years': years,
        'templates': templates,
        'layouts': layouts,
        'selected_class': selected_class,
        'selected_section': selected_section,
        'selected_year': selected_year,
        'selected_template': selected_template,
        'selected_layout': selected_layout,
        'students_in_scope': students_in_scope,
        'total_in_scope': total_in_scope,
        'verified_count': verified_count,
        'pending_count': pending_count,
        'rejected_count': rejected_count,
        'missing_photo_count': missing_photo_count,
        'auto_cols': auto_cols,
        'auto_rows': auto_rows,
        'auto_cards_per_page': auto_cards_per_page,
        'format_type': format_type,
        'sides_mode': sides_mode,
        'override_unverified': override_unverified,
    })


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def cards_history_view(request):
    """
    Audit and history of all generated, printed, and revoked ID cards.
    Strictly scoped per organization and per studio client.
    """
    org = get_current_organization(request)
    if not org:
        qs = IDCard.objects.none()
        is_studio = False
        active_client = None
    else:
        is_studio = bool(getattr(org, 'is_studio', False))
        active_client_id = request.session.get('active_client_id') if is_studio else None
        active_client = None

        qs = IDCard.objects.filter(student__organization=org).select_related(
            'student', 'academic_year', 'template', 'student__class_level', 'student__section', 'student__client'
        )
        if is_studio and active_client_id and str(active_client_id) != '0':
            active_client = org.clients.filter(id=active_client_id).first()
            if active_client:
                qs = qs.filter(student__client=active_client)

    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('validity_status')

    if search:
        qs = qs.filter(
            Q(student__full_name__icontains=search) |
            Q(student__student_id__icontains=search) |
            Q(card_number__icontains=search)
        )
    if status_filter:
        qs = qs.filter(validity_status=status_filter)

    paginator = Paginator(qs, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'idcards/cards_history.html', {
        'page_obj': page_obj,
        'search_query': search,
        'selected_status': status_filter,
        'is_studio': is_studio if org else False,
        'active_client': active_client if org else None,
    })


@login_required(login_url='admin_login')
@user_passes_test(is_admin)
def revoke_card_view(request, pk):
    """
    Revokes an active ID card with a mandatory reason.
    Immediate effect: QR scan renders '✕ ID CARD REVOKED'.
    Strictly scoped per organization and per studio client.
    """
    org = get_current_organization(request)
    if not org:
        card_qs = IDCard.objects.none()
        is_studio = False
        active_client = None
    else:
        is_studio = bool(getattr(org, 'is_studio', False))
        active_client_id = request.session.get('active_client_id') if is_studio else None
        active_client = None

        card_qs = IDCard.objects.filter(student__organization=org).select_related('student', 'student__client')
        if is_studio and active_client_id and str(active_client_id) != '0':
            active_client = org.clients.filter(id=active_client_id).first()
            if active_client:
                card_qs = card_qs.filter(student__client=active_client)

    card = get_object_or_404(card_qs, pk=pk)

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, "A reason is required to revoke an ID card.")
            return redirect('cards_history')

        card.validity_status = 'REVOKED'
        card.revocation_reason = reason
        card.revoked_at = timezone.now()
        card.revoked_by = request.user
        card.save()

        log_action(
            user=request.user,
            action='ID_REVOKED',
            object_type='IDCard',
            object_id=card.id,
            object_repr=card.card_number,
            details={'reason': reason, 'student': str(card.student)},
            request=request
        )
        messages.warning(request, f"ID Card {card.card_number} was REVOKED. QR scans will now reflect this status.")
        return redirect('cards_history')

    return render(request, 'idcards/revoke_card_confirm.html', {
        'card': card,
        'is_studio': is_studio if org else False,
        'active_client': active_client if org else None,
    })
