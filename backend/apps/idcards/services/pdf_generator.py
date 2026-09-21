import io
import os
from datetime import date
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
import zipfile
from PIL import Image
import pymupdf

from django.conf import settings
from apps.core.models import School
from apps.idcards.services.qr_service import generate_qr_image, get_card_verification_url
from apps.core.services.audit import log_action


def hex_to_reportlab_color(hex_str, default_color='#000000'):
    """Safely converts hex string (#RRGGBB) to ReportLab HexColor."""
    if not hex_str or not isinstance(hex_str, str) or not hex_str.startswith('#'):
        hex_str = default_color
    try:
        return HexColor(hex_str.strip())
    except Exception:
        return HexColor(default_color)


def get_effective_school(student, default_school=None):
    """
    Returns the appropriate institutional entity (School or OrganizationClient) for the student.
    In Studio/Press multi-client mode, student.client provides individual client branding.
    Otherwise falls back to the default institutional School instance.
    """
    if default_school is None:
        default_school = School.get_instance()
    if hasattr(student, 'client') and student.client:
        if student.client.school:
            return student.client.school
        return student.client
    return default_school


def get_dynamic_field_value(key, student, school, id_card=None):
    """
    Substitutes dynamic template field keys with actual student/school/validity data.
    """
    key = key.strip().replace('{', '').replace('}', '').lower()
    
    if key == 'student.name':
        return student.full_name
    elif key == 'student.student_id':
        return student.student_id
    elif key == 'student.roll_no':
        return str(student.roll_number)
    elif key == 'student.class':
        return student.class_level.name
    elif key == 'student.section':
        return student.section.name
    elif key == 'student.dob':
        return student.date_of_birth.strftime('%Y-%m-%d') if student.date_of_birth else 'N/A'
    elif key == 'student.gender':
        return student.get_gender_display()
    elif key == 'student.address':
        return student.address or 'N/A'
    elif key == 'student.guardian_name':
        return student.guardian_name or 'N/A'
    elif key == 'student.guardian_phone':
        return student.guardian_phone or 'N/A'
    elif key == 'student.blood_group':
        return student.blood_group or 'N/A'
    elif key == 'student.emergency_contact':
        return student.emergency_contact or 'N/A'
    elif key == 'school.name':
        return school.name if school else 'School Name'
    elif key == 'school.head_teacher_name':
        return school.head_teacher_name if school else 'Principal'
    elif key == 'valid_from':
        if id_card:
            return id_card.valid_from.strftime('%d %b %Y')
        return date.today().strftime('%d %b %Y')
    elif key == 'valid_until':
        if id_card:
            return id_card.valid_until.strftime('%d %b %Y')
        return (date.today().replace(year=date.today().year + 1)).strftime('%d %b %Y')
    return ""


def draw_crop_marks(c, card_x, card_y, card_w, card_h, mark_len=4 * mm, offset=1.5 * mm):
    """
    Draws neat registration crop marks outside the 4 corners of a card.
    Never overlaps the card content area.
    """
    c.saveState()
    c.setStrokeColor(HexColor('#94A3B8'))
    c.setLineWidth(0.5)

    # Bottom-Left corner
    c.line(card_x - offset, card_y, card_x - offset - mark_len, card_y)
    c.line(card_x, card_y - offset, card_x, card_y - offset - mark_len)

    # Bottom-Right corner
    c.line(card_x + card_w + offset, card_y, card_x + card_w + offset + mark_len, card_y)
    c.line(card_x + card_w, card_y - offset, card_x + card_w, card_y - offset - mark_len)

    # Top-Left corner
    c.line(card_x - offset, card_y + card_h, card_x - offset - mark_len, card_y + card_h)
    c.line(card_x, card_y + card_h + offset, card_x, card_y + card_h + offset + mark_len)

    # Top-Right corner
    c.line(card_x + card_w + offset, card_y + card_h, card_x + card_w + offset + mark_len, card_y + card_h)
    c.line(card_x + card_w, card_y + card_h + offset, card_x + card_w, card_y + card_h + offset + mark_len)

    c.restoreState()


def render_card_side(c, card_x, card_y, card_w_mm, card_h_mm, template, elements, student, school, id_card, side='FRONT', request=None):
    """
    Renders one side (FRONT or BACK) of an ID card at the given canvas coordinates.
    card_x, card_y are the bottom-left of the card box in points.
    """
    card_w_pt = card_w_mm * mm
    card_h_pt = card_h_mm * mm

    c.saveState()
    # Clip to card boundaries
    p = c.beginPath()
    p.rect(card_x, card_y, card_w_pt, card_h_pt)
    c.clipPath(p, stroke=0)

    # 1. Background fill
    bg_color = template.background_color if side == 'FRONT' else template.back_background_color
    c.setFillColor(hex_to_reportlab_color(bg_color, '#FFFFFF'))
    c.rect(card_x, card_y, card_w_pt, card_h_pt, fill=1, stroke=0)

    # Background image if configured
    bg_img = template.background_image if side == 'FRONT' else template.back_background_image
    fit_mode = getattr(template, 'bg_fit_mode', 'FILL') if side == 'FRONT' else getattr(template, 'back_bg_fit_mode', 'FILL')
    if bg_img and hasattr(bg_img, 'path') and os.path.exists(bg_img.path):
        try:
            if fit_mode == 'FIT':
                c.drawImage(bg_img.path, card_x, card_y, width=card_w_pt, height=card_h_pt, preserveAspectRatio=True, anchor='c')
            elif fit_mode == 'CROP':
                with Image.open(bg_img.path) as pil_img:
                    img_w, img_h = pil_img.size
                img_aspect = img_w / img_h
                card_aspect = card_w_pt / card_h_pt
                if img_aspect > card_aspect:
                    draw_h = card_h_pt
                    draw_w = card_h_pt * img_aspect
                    draw_x = card_x - (draw_w - card_w_pt) / 2.0
                    draw_y = card_y
                else:
                    draw_w = card_w_pt
                    draw_h = card_w_pt / img_aspect
                    draw_x = card_x
                    draw_y = card_y - (draw_h - card_h_pt) / 2.0
                c.drawImage(bg_img.path, draw_x, draw_y, width=draw_w, height=draw_h, preserveAspectRatio=False)
            else:  # FILL
                c.drawImage(bg_img.path, card_x, card_y, width=card_w_pt, height=card_h_pt, preserveAspectRatio=False)
        except Exception:
            pass

    # 2. Render elements sorted by z_index
    sorted_elements = sorted([e for e in elements if e.side == side], key=lambda x: getattr(x, 'z_index', 1))

    for el in sorted_elements:
        el_x_pt = card_x + (el.x_mm * mm)
        # Convert web top-origin coordinate to ReportLab bottom-origin coordinate
        el_y_pt = card_y + ((card_h_mm - el.y_mm - el.height_mm) * mm)
        el_w_pt = el.width_mm * mm
        el_h_pt = el.height_mm * mm

        c.saveState()

        # Apply opacity if specified
        if hasattr(el, 'opacity') and el.opacity < 1.0:
            c.setFillAlpha(max(0.0, min(1.0, el.opacity)))

        if el.element_type == 'RECTANGLE':
            fill = hex_to_reportlab_color(el.fill_color, '#3B82F6') if el.fill_color else None
            stroke = hex_to_reportlab_color(el.border_color, '#000000') if (el.border_color and el.border_width > 0) else None
            
            if fill:
                c.setFillColor(fill)
            if stroke:
                c.setStrokeColor(stroke)
                c.setLineWidth(el.border_width * mm)

            c.roundRect(el_x_pt, el_y_pt, el_w_pt, el_h_pt, radius=(el.border_radius or 0) * mm, fill=1 if fill else 0, stroke=1 if stroke else 0)

        elif el.element_type == 'LINE':
            c.setStrokeColor(hex_to_reportlab_color(el.border_color or el.font_color, '#CBD5E1'))
            c.setLineWidth((el.border_width or 1.0) * mm)
            c.line(el_x_pt, el_y_pt + el_h_pt / 2, el_x_pt + el_w_pt, el_y_pt + el_h_pt / 2)

        elif el.element_type in ('TEXT', 'DYNAMIC_FIELD'):
            text = el.label_text
            if el.element_type == 'DYNAMIC_FIELD' or '{{' in text:
                text = get_dynamic_field_value(el.dynamic_field_key or text, student, school, id_card)

            c.setFillColor(hex_to_reportlab_color(el.font_color, '#0F172A'))
            is_bold = el.font_weight == 'BOLD'
            is_italic = getattr(el, 'font_style', 'NORMAL') == 'ITALIC'

            if is_bold and is_italic:
                font_name = "Helvetica-BoldOblique"
            elif is_bold:
                font_name = "Helvetica-Bold"
            elif is_italic:
                font_name = "Helvetica-Oblique"
            else:
                font_name = "Helvetica"

            font_size = el.font_size
            # Auto-shrink text if enabled and string exceeds box width
            if getattr(el, 'auto_shrink_text', True) and str(text):
                while font_size > 5.0 and c.stringWidth(str(text), font_name, font_size) > el_w_pt:
                    font_size -= 0.5

            c.setFont(font_name, font_size)

            # Alignment
            text_str = str(text)
            if el.text_align == 'CENTER':
                c.drawCentredString(el_x_pt + el_w_pt / 2, el_y_pt + (el_h_pt * 0.25), text_str)
            elif el.text_align == 'RIGHT':
                c.drawRightString(el_x_pt + el_w_pt, el_y_pt + (el_h_pt * 0.25), text_str)
            else:
                c.drawString(el_x_pt, el_y_pt + (el_h_pt * 0.25), text_str)

        elif el.element_type == 'STUDENT_PHOTO':
            is_circular = getattr(el, 'is_circular', False)
            if student.photo and hasattr(student.photo, 'path') and os.path.exists(student.photo.path):
                try:
                    if is_circular:
                        radius = min(el_w_pt, el_h_pt) / 2.0
                        center_x = el_x_pt + (el_w_pt / 2.0)
                        center_y = el_y_pt + (el_h_pt / 2.0)

                        c.saveState()
                        p_circ = c.beginPath()
                        p_circ.circle(center_x, center_y, radius)
                        c.clipPath(p_circ, stroke=0)
                        c.drawImage(student.photo.path, center_x - radius, center_y - radius, width=radius * 2, height=radius * 2, preserveAspectRatio=True, anchor='c')
                        c.restoreState()

                        if el.border_width > 0:
                            c.setStrokeColor(hex_to_reportlab_color(el.border_color, '#000000'))
                            c.setLineWidth(el.border_width * mm)
                            c.circle(center_x, center_y, radius, stroke=1, fill=0)
                    else:
                        c.drawImage(student.photo.path, el_x_pt, el_y_pt, width=el_w_pt, height=el_h_pt, preserveAspectRatio=True, anchor='c')
                        if el.border_width > 0:
                            c.setStrokeColor(hex_to_reportlab_color(el.border_color, '#000000'))
                            c.setLineWidth(el.border_width * mm)
                            c.roundRect(el_x_pt, el_y_pt, el_w_pt, el_h_pt, radius=(el.border_radius or 0) * mm, stroke=1, fill=0)
                except Exception:
                    pass
            else:
                c.setStrokeColor(HexColor('#CBD5E1'))
                c.setLineWidth(1)
                if is_circular:
                    radius = min(el_w_pt, el_h_pt) / 2.0
                    c.circle(el_x_pt + el_w_pt / 2.0, el_y_pt + el_h_pt / 2.0, radius, stroke=1, fill=0)
                else:
                    c.rect(el_x_pt, el_y_pt, el_w_pt, el_h_pt, stroke=1, fill=0)
                c.setFont("Helvetica", 7)
                c.setFillColor(HexColor('#94A3B8'))
                c.drawCentredString(el_x_pt + el_w_pt / 2, el_y_pt + el_h_pt / 2 - 3, "No Photo")

        elif el.element_type == 'SCHOOL_LOGO':
            if school and school.logo and hasattr(school.logo, 'path') and os.path.exists(school.logo.path):
                try:
                    c.drawImage(school.logo.path, el_x_pt, el_y_pt, width=el_w_pt, height=el_h_pt, preserveAspectRatio=True, anchor='c', mask='auto')
                except Exception:
                    pass

        elif el.element_type == 'SIGNATURE':
            if school and school.head_teacher_signature and hasattr(school.head_teacher_signature, 'path') and os.path.exists(school.head_teacher_signature.path):
                try:
                    c.drawImage(school.head_teacher_signature.path, el_x_pt, el_y_pt, width=el_w_pt, height=el_h_pt, preserveAspectRatio=True, anchor='c', mask='auto')
                except Exception:
                    pass

        elif el.element_type == 'QR_CODE':
            if id_card:
                try:
                    verify_url = get_card_verification_url(id_card, request)
                    qr_level = getattr(el, 'qr_error_correction', 'M')
                    qr_pil = generate_qr_image(verify_url, error_level=qr_level)
                    qr_reader = ImageReader(qr_pil)
                    c.drawImage(qr_reader, el_x_pt, el_y_pt, width=el_w_pt, height=el_h_pt, preserveAspectRatio=True)
                except Exception:
                    pass

        c.restoreState()

    c.restoreState()


def generate_id_cards_pdf(students, template, layout, academic_year, user=None, request=None, enforce_verified_only=True, sides_mode='FRONT_ONLY'):
    """
    Generates a print-ready, millimeter-accurate PDF containing all requested ID cards.
    Adheres strictly to the verification rule, automatic card grid calculations, duplex alignment,
    and crop marks.
    """
    school = School.get_instance()

    # Rule 15: The system MUST prevent unverified students from being printed accidentally.
    if enforce_verified_only:
        eligible_students = [s for s in students if s.is_print_eligible]
    else:
        eligible_students = list(students)

    if not eligible_students:
        raise ValueError("No eligible students selected for printing. Eligible students must be Active, Verified, and have a valid Photo.")

    # Create/update IDCard records for all eligible students to retain permanent card history
    id_cards = []
    from apps.idcards.models import IDCard
    for s in eligible_students:
        card, created = IDCard.objects.get_or_create(
            student=s,
            academic_year=academic_year,
            defaults={
                'template': template,
                'card_number': f"ID-{academic_year.name.replace('/', '-')}-{s.student_id}",
                'valid_from': academic_year.start_date,
                'valid_until': academic_year.end_date,
                'card_status': 'GENERATED',
                'validity_status': 'ACTIVE',
                'generated_by': user if user and user.is_authenticated else None
            }
        )
        if not created and card.validity_status == 'REVOKED':
            # Do not print revoked cards
            continue
        id_cards.append((s, card))

    if not id_cards:
        raise ValueError("All selected cards have been REVOKED and cannot be printed.")

    # Sheet calculations
    sheet_w_mm, sheet_h_mm = layout.get_sheet_dimensions_mm()
    sheet_w_pt = sheet_w_mm * mm
    sheet_h_pt = sheet_h_mm * mm

    auto_cols, auto_rows, auto_cards_per_page = layout.calculate_auto_grid(template.width_mm, template.height_mm)
    # Respect layout overrides only if they fit within physical sheet bounds
    cols = layout.cols if (0 < layout.cols <= auto_cols) else auto_cols
    rows = layout.rows if (0 < layout.rows <= auto_rows) else auto_rows
    cards_per_page = cols * rows

    card_w_mm = template.width_mm
    card_h_mm = template.height_mm
    card_w_pt = card_w_mm * mm
    card_h_pt = card_h_mm * mm

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(sheet_w_pt, sheet_h_pt))
    c.setTitle(f"School_ID_Cards_{academic_year.name.replace('/', '_')}")

    elements = list(template.elements.all())
    front_elements = [e for e in elements if e.side == 'FRONT']
    back_elements = [e for e in elements if e.side == 'BACK']

    # Chunk students by cards_per_page
    batches = [id_cards[i:i + cards_per_page] for i in range(0, len(id_cards), cards_per_page)]

    for batch in batches:
        # Page 1: FRONT SIDE OF BATCH
        render_front = sides_mode in ('FRONT_ONLY', 'BOTH')
        if render_front:
            for idx, (student, card) in enumerate(batch):
                r = idx // cols
                col = idx % cols

                card_x = (layout.margin_left_mm * mm) + (col * (card_w_pt + (layout.gap_x_mm * mm)))
                card_y = sheet_h_pt - (layout.margin_top_mm * mm) - ((r + 1) * card_h_pt) - (r * (layout.gap_y_mm * mm))

                # Render front
                effective_school = get_effective_school(student, school)
                render_card_side(c, card_x, card_y, card_w_mm, card_h_mm, template, front_elements, student, effective_school, card, side='FRONT', request=request)

                # Crop marks
                if layout.show_crop_marks:
                    draw_crop_marks(c, card_x, card_y, card_w_pt, card_h_pt,
                                    mark_len=layout.crop_mark_length_mm * mm,
                                    offset=layout.crop_mark_offset_mm * mm)

            c.showPage()

        # Page 2: BACK SIDE OF BATCH (Duplex aligned) - only if sides_mode == 'BOTH' or 'BACK_ONLY'
        render_back = sides_mode in ('BACK_ONLY', 'BOTH') and bool(back_elements)
        if render_back:
            for idx, (student, card) in enumerate(batch):
                r = idx // cols
                col = idx % cols

                # Duplex column mirroring: On the back side of paper flipped along the long edge,
                # column 0 is positioned behind column (cols - 1), etc.
                if layout.duplex_alignment == 'MIRROR_COLUMNS':
                    mirrored_col = (cols - 1) - col
                else:
                    mirrored_col = col

                card_x = (layout.margin_left_mm * mm) + (mirrored_col * (card_w_pt + (layout.gap_x_mm * mm)))
                card_y = sheet_h_pt - (layout.margin_top_mm * mm) - ((r + 1) * card_h_pt) - (r * (layout.gap_y_mm * mm))

                # Render back
                effective_school = get_effective_school(student, school)
                render_card_side(c, card_x, card_y, card_w_mm, card_h_mm, template, back_elements, student, effective_school, card, side='BACK', request=request)

                if layout.show_crop_marks:
                    draw_crop_marks(c, card_x, card_y, card_w_pt, card_h_pt,
                                    mark_len=layout.crop_mark_length_mm * mm,
                                    offset=layout.crop_mark_offset_mm * mm)

            c.showPage()

    c.save()
    buffer.seek(0)

    # Update printed timestamp on cards
    from django.utils import timezone
    from apps.idcards.models import IDCard as IDCardModel
    card_ids = [c[1].id for c in id_cards]
    IDCardModel.objects.filter(id__in=card_ids).update(
        card_status='PRINTED',
        printed_at=timezone.now(),
        printed_by=user if user and user.is_authenticated else None
    )

    log_action(
        user=user,
        action='PDF_GENERATED',
        object_type='IDCard',
        object_repr=f"Generated PDF for {len(id_cards)} cards",
        details={
            'cards_count': len(id_cards),
            'template': template.name,
            'layout': layout.name,
            'academic_year': academic_year.name
        },
        request=request
    )

    return buffer.getvalue()


def render_single_card_pdf(student, template, academic_year=None, user=None, request=None, card=None, side='BOTH', sides_mode=None):
    """
    Renders an individual card directly to exact physical card dimensions (e.g. 54x86mm).
    Zero margins, print-ready, crisp vector layout.
    """
    school = get_effective_school(student, School.get_instance())
    if not academic_year:
        from apps.students.models import AcademicYear
        academic_year = student.academic_year or AcademicYear.objects.filter(is_active=True).first()

    if not card:
        from apps.idcards.models import IDCard
        card, _ = IDCard.objects.get_or_create(
            student=student,
            academic_year=academic_year,
            defaults={
                'template': template,
                'card_number': f"ID-{academic_year.name.replace('/', '-') if academic_year else 'GEN'}-{student.student_id}",
                'valid_from': academic_year.start_date if academic_year else date.today(),
                'valid_until': academic_year.end_date if academic_year else date.today().replace(year=date.today().year + 1),
                'card_status': 'GENERATED',
                'validity_status': 'ACTIVE',
                'generated_by': user if user and user.is_authenticated else None
            }
        )

    card_w_pt = template.width_mm * mm
    card_h_pt = template.height_mm * mm
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(card_w_pt, card_h_pt))
    c.setTitle(f"ID_Card_{student.student_id}")

    elements = list(template.elements.all())
    front_elements = [e for e in elements if e.side == 'FRONT']
    back_elements = [e for e in elements if e.side == 'BACK']

    # Determine sides to render
    if sides_mode == 'FRONT_ONLY':
        has_front = True
        has_back = False
    elif sides_mode == 'BACK_ONLY':
        has_front = False
        has_back = bool(back_elements)
    elif sides_mode == 'BOTH':
        has_front = True
        has_back = bool(back_elements)
    else:
        # Fall back to side parameter
        has_front = side in ('FRONT', 'BOTH', 'COMBINED', 'ZIP') and template.duplex_mode in ('FRONT_ONLY', 'FRONT_BACK')
        has_back = side in ('BACK', 'BOTH', 'COMBINED', 'ZIP') and template.duplex_mode in ('BACK_ONLY', 'FRONT_BACK') and bool(back_elements)

    # Page 1: Front
    if has_front:
        render_card_side(c, 0, 0, template.width_mm, template.height_mm, template, front_elements, student, school, card, side='FRONT', request=request)
        c.showPage()

    # Page 2: Back
    if has_back:
        render_card_side(c, 0, 0, template.width_mm, template.height_mm, template, back_elements, student, school, card, side='BACK', request=request)
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.getvalue(), card


def render_single_card_image(student, template, academic_year=None, format_type='PNG', side='COMBINED', sides_mode='FRONT_ONLY', user=None, request=None, card=None, dpi=300):
    """
    Renders an individual student's card to high-resolution (300 DPI) JPEG or PNG.
    Supports sides_mode ('FRONT_ONLY', 'BOTH') and side ('COMBINED', 'FRONT', 'BACK', 'ZIP').
    Returns (bytes, content_type, filename).
    """
    fmt = 'jpeg' if format_type.upper() in ('JPG', 'JPEG') else 'png'
    ext = 'jpg' if fmt == 'jpeg' else 'png'
    content_type = 'image/jpeg' if fmt == 'jpeg' else 'image/png'
    safe_name = f"{student.student_id}_{student.full_name.replace(' ', '_')}"

    # If FRONT_ONLY, directly produce front image
    effective_sides_mode = sides_mode or ('FRONT_ONLY' if side == 'FRONT' else 'BOTH')
    if effective_sides_mode == 'FRONT_ONLY':
        pdf_bytes, card_obj = render_single_card_pdf(
            student=student,
            template=template,
            academic_year=academic_year,
            user=user,
            request=request,
            card=card,
            sides_mode='FRONT_ONLY'
        )
        doc = pymupdf.open(stream=pdf_bytes, filetype='pdf')
        pix = doc[0].get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes(fmt)
        filename = f"ID_Card_{safe_name}_Front.{ext}"
        return img_bytes, content_type, filename

    # Render single card PDF with both sides
    pdf_bytes, card_obj = render_single_card_pdf(
        student=student,
        template=template,
        academic_year=academic_year,
        user=user,
        request=request,
        card=card,
        sides_mode='BOTH'
    )

    doc = pymupdf.open(stream=pdf_bytes, filetype='pdf')
    num_pages = len(doc)

    if side == 'FRONT' or num_pages == 1:
        pix = doc[0].get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes(fmt)
        filename = f"ID_Card_{safe_name}_Front.{ext}"
        return img_bytes, content_type, filename

    elif side == 'BACK':
        pix = doc[-1].get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes(fmt)
        filename = f"ID_Card_{safe_name}_Back.{ext}"
        return img_bytes, content_type, filename

    elif side == 'COMBINED':
        pix_front = doc[0].get_pixmap(dpi=dpi)
        pix_back = doc[1].get_pixmap(dpi=dpi)
        img_front = Image.open(io.BytesIO(pix_front.tobytes('png')))
        img_back = Image.open(io.BytesIO(pix_back.tobytes('png')))

        # Place side by side with a 24px separator
        gap = 24
        combined_w = img_front.width + img_back.width + gap
        combined_h = max(img_front.height, img_back.height)
        combined_img = Image.new('RGB', (combined_w, combined_h), (255, 255, 255))
        combined_img.paste(img_front, (0, 0))
        combined_img.paste(img_back, (img_front.width + gap, 0))

        out_buf = io.BytesIO()
        if fmt == 'jpeg':
            combined_img.save(out_buf, format='JPEG', quality=95)
        else:
            combined_img.save(out_buf, format='PNG')
        out_buf.seek(0)
        filename = f"ID_Card_{safe_name}_Complete.{ext}"
        return out_buf.getvalue(), content_type, filename

    else:  # ZIP with both sides
        pix_front = doc[0].get_pixmap(dpi=dpi)
        pix_back = doc[1].get_pixmap(dpi=dpi)

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"ID_Card_{safe_name}_Front.{ext}", pix_front.tobytes(fmt))
            zf.writestr(f"ID_Card_{safe_name}_Back.{ext}", pix_back.tobytes(fmt))
        zip_buf.seek(0)
        filename = f"ID_Card_{safe_name}_{fmt.upper()}.zip"
        return zip_buf.getvalue(), 'application/zip', filename


def export_id_cards_batch(students, template, layout=None, academic_year=None, format_type='PDF', side='COMBINED', sides_mode='FRONT_ONLY', user=None, request=None, enforce_verified_only=True, scope_name="Students"):
    """
    Universal export engine for single, selected, or entire class of students.
    Formats:
    - 'PDF': Generates multi-card print sheet PDF (or single card if layout is 'single' or 1 student with single mode).
    - 'PNG' / 'JPEG': High-res 300 DPI images (single image or ZIP archive for multiple students).
    Returns (bytes, content_type, filename).
    """
    format_type = format_type.upper()
    if enforce_verified_only:
        eligible = [s for s in students if s.is_print_eligible]
    else:
        eligible = list(students)

    if not eligible:
        raise ValueError("No eligible students found for export. Students must be Active and have a photo attached.")

    if not academic_year:
        from apps.students.models import AcademicYear
        academic_year = AcademicYear.objects.filter(is_active=True).first()

    # 1. Single student export
    if len(eligible) == 1:
        s = eligible[0]
        safe_name = f"{s.student_id}_{s.full_name.replace(' ', '_')}"

        if format_type in ('PNG', 'JPEG', 'JPG'):
            return render_single_card_image(
                student=s,
                template=template,
                academic_year=academic_year,
                format_type=format_type,
                side=side,
                sides_mode=sides_mode,
                user=user,
                request=request
            )
        elif format_type == 'PDF' and (layout == 'single' or layout is None):
            pdf_bytes, _ = render_single_card_pdf(s, template, academic_year, user=user, request=request, sides_mode=sides_mode)
            return pdf_bytes, 'application/pdf', f"ID_Card_{safe_name}.pdf"
        # Standard sheet PDF for 1 student continues below to generate_id_cards_pdf

    # 2. Multi-student or sheet PDF
    if format_type == 'PDF':
        if not layout or layout == 'single':
            from apps.idcards.models import PrintLayout
            layout = PrintLayout.objects.first()
        pdf_bytes = generate_id_cards_pdf(
            students=eligible,
            template=template,
            layout=layout,
            academic_year=academic_year,
            user=user,
            request=request,
            enforce_verified_only=enforce_verified_only,
            sides_mode=sides_mode
        )
        return pdf_bytes, 'application/pdf', f"{scope_name}_ID_Cards.pdf"

    # 3. Multi-student PNG / JPEG ZIP Archive
    fmt = 'jpeg' if format_type in ('JPEG', 'JPG') else 'png'
    ext = 'jpg' if fmt == 'jpeg' else 'png'

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for idx, s in enumerate(eligible, start=1):
            safe_s = f"{s.roll_number:02d}_{s.student_id}_{s.full_name.replace(' ', '_')}"
            pdf_bytes, _ = render_single_card_pdf(s, template, academic_year, user=user, request=request, sides_mode=sides_mode)
            doc = pymupdf.open(stream=pdf_bytes, filetype='pdf')
            num_pages = len(doc)

            if sides_mode == 'FRONT_ONLY' or side == 'FRONT' or num_pages == 1:
                zf.writestr(f"{safe_s}_Front.{ext}", doc[0].get_pixmap(dpi=300).tobytes(fmt))
            elif side == 'BACK':
                zf.writestr(f"{safe_s}_Back.{ext}", doc[-1].get_pixmap(dpi=300).tobytes(fmt))
            elif side == 'COMBINED' and num_pages > 1:
                p0 = doc[0].get_pixmap(dpi=300)
                p1 = doc[1].get_pixmap(dpi=300)
                im0 = Image.open(io.BytesIO(p0.tobytes('png')))
                im1 = Image.open(io.BytesIO(p1.tobytes('png')))
                gap = 20
                comb = Image.new('RGB', (im0.width + im1.width + gap, max(im0.height, im1.height)), (255, 255, 255))
                comb.paste(im0, (0, 0))
                comb.paste(im1, (im0.width + gap, 0))
                out = io.BytesIO()
                if fmt == 'jpeg':
                    comb.save(out, format='JPEG', quality=95)
                else:
                    comb.save(out, format='PNG')
                zf.writestr(f"{safe_s}_Card.{ext}", out.getvalue())
            else:  # BOTH separate
                zf.writestr(f"{safe_s}_Front.{ext}", doc[0].get_pixmap(dpi=300).tobytes(fmt))
                if num_pages > 1:
                    zf.writestr(f"{safe_s}_Back.{ext}", doc[1].get_pixmap(dpi=300).tobytes(fmt))

    zip_buf.seek(0)
    filename = f"{scope_name}_ID_Cards_{format_type}.zip"
    return zip_buf.getvalue(), 'application/zip', filename
