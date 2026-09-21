import io
from datetime import datetime, date
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError
from apps.students.models import Student
from apps.academic.models import ClassLevel, Section, AcademicYear
from apps.core.services.audit import log_action
from apps.core.utils import get_current_organization


def generate_excel_template(mode='class_wise', class_level=None, section=None, academic_year=None):
    """
    Generates a professionally styled Excel template (.xlsx) with header styling,
    sample data, and instructions.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Student Import Template"

    # Header styling
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    sample_font = Font(name="Arial", size=10, italic=True, color="4B5563")
    border_thin = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    if mode == 'class_wise':
        headers = [
            "Roll No*",
            "Student ID*",
            "Full Name*",
            "Date of Birth (YYYY-MM-DD)*",
            "Gender (Male/Female/Other)*",
            "Address",
            "Guardian Name",
            "Guardian Phone",
            "Blood Group (A+/B+/O+/etc)"
        ]
        sample_rows = [
            [1, "STU1001", "Aarav Sharma", "2012-05-14", "Male", "Kathmandu Ward 4", "Ramesh Sharma", "9841234567", "O+"],
            [2, "STU1002", "Priya Thapa", "2012-08-22", "Female", "Lalitpur Ward 2", "Sunita Thapa", "9849876543", "A+"],
            [3, "STU1003", "Bibek Karki", "2011-12-01", "Male", "Bhaktapur Ward 1", "Krishna Karki", "9812345678", "B+"],
        ]
    else:
        headers = [
            "Roll No*",
            "Student ID*",
            "Full Name*",
            "Class Name*",
            "Section Name*",
            "Date of Birth (YYYY-MM-DD)*",
            "Gender (Male/Female/Other)*",
            "Address",
            "Guardian Name",
            "Guardian Phone",
            "Blood Group (A+/B+/O+/etc)"
        ]
        sample_rows = [
            [1, "STU1001", "Aarav Sharma", "Grade 8", "A", "2012-05-14", "Male", "Kathmandu Ward 4", "Ramesh Sharma", "9841234567", "O+"],
            [2, "STU1002", "Priya Thapa", "Grade 8", "A", "2012-08-22", "Female", "Lalitpur Ward 2", "Sunita Thapa", "9849876543", "A+"],
            [1, "STU2001", "Rohan Gurung", "Grade 9", "B", "2011-03-10", "Male", "Pokhara Ward 5", "Govind Gurung", "9856789012", "AB+"],
        ]

    # Write headers
    ws.append(headers)
    for col_num, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border_thin

    # Write sample rows
    for row_data in sample_rows:
        ws.append(row_data)
        current_row = ws.max_row
        for col_num in range(1, len(row_data) + 1):
            cell = ws.cell(row=current_row, column=col_num)
            cell.font = sample_font
            cell.border = border_thin
            cell.alignment = Alignment(horizontal="left", vertical="center")

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def parse_date_value(raw_val):
    """Safely converts various Excel date formats (datetime, date, string) into date object."""
    if not raw_val:
        return None
    if isinstance(raw_val, datetime):
        return raw_val.date()
    if isinstance(raw_val, date):
        return raw_val

    raw_str = str(raw_val).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(raw_str, fmt).date()
        except ValueError:
            pass
    return None


def parse_and_validate_excel(file_obj, mode='class_wise', class_level=None, section=None, academic_year=None, organization=None):
    """
    Dry-run parses and validates an uploaded Excel file.
    Does NOT write to database.
    Returns:
      valid_records: list of validated record dicts
      invalid_records: list of error dicts with row numbers and exact reasons
      stats: summary counts
    """
    try:
        file_obj.seek(0)
        wb = openpyxl.load_workbook(file_obj, data_only=True)
        ws = wb.active
    except Exception as e:
        raise ValueError(f"Could not read Excel file: {str(e)}")

    rows = list(ws.iter_rows(values_only=True))
    if not rows or len(rows) < 2:
        raise ValueError("Excel file is empty or missing data rows.")

    header_row = [str(cell).strip().lower() if cell is not None else "" for cell in rows[0]]

    # Map headers
    valid_records = []
    invalid_records = []
    seen_student_ids = set()
    seen_rolls_by_scope = set()

    # Pre-fetch existing database identifiers for high-speed validation without N+1 queries, scoped by tenant
    db_students = Student.objects.all()
    if organization:
        db_students = db_students.filter(organization=organization)
    existing_db_student_ids = set(db_students.values_list('student_id', flat=True))

    # Pre-fetch all classes, sections, and active year
    class_filter = Q(organization=organization) | Q(organization__isnull=True) if organization else Q()
    all_classes = {c.name.strip().lower(): c for c in ClassLevel.objects.filter(class_filter)}
    all_sections = {}
    for s in Section.objects.filter(class_level__in=ClassLevel.objects.filter(class_filter)).select_related('class_level').all():
        all_sections[(s.class_level_id, s.name.strip().lower())] = s

    if not academic_year:
        year_qs = AcademicYear.objects.filter(is_active=True)
        if organization:
            academic_year = year_qs.filter(organization=organization).first() or year_qs.filter(organization__isnull=True).first()
        else:
            academic_year = year_qs.first()

    for row_idx, row in enumerate(rows[1:], start=2):
        if not any(row):
            continue  # Skip completely empty rows

        errors = []

        if mode == 'class_wise':
            # Expected columns: Roll, ID, Name, DOB, Gender, Address, Guardian, Phone, Blood
            raw_roll = row[0] if len(row) > 0 else None
            raw_id = row[1] if len(row) > 1 else None
            raw_name = row[2] if len(row) > 2 else None
            raw_dob = row[3] if len(row) > 3 else None
            raw_gender = row[4] if len(row) > 4 else None
            address = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ""
            guardian_name = str(row[6]).strip() if len(row) > 6 and row[6] is not None else ""
            guardian_phone = str(row[7]).strip() if len(row) > 7 and row[7] is not None else ""
            blood_group = str(row[8]).strip() if len(row) > 8 and row[8] is not None else ""

            target_class = class_level
            target_section = section
            target_year = academic_year
        else:
            # Full school columns: Roll, ID, Name, Class, Section, DOB, Gender, Address, Guardian, Phone, Blood
            raw_roll = row[0] if len(row) > 0 else None
            raw_id = row[1] if len(row) > 1 else None
            raw_name = row[2] if len(row) > 2 else None
            raw_class_name = row[3] if len(row) > 3 else None
            raw_sec_name = row[4] if len(row) > 4 else None
            raw_dob = row[5] if len(row) > 5 else None
            raw_gender = row[6] if len(row) > 6 else None
            address = str(row[7]).strip() if len(row) > 7 and row[7] is not None else ""
            guardian_name = str(row[8]).strip() if len(row) > 8 and row[8] is not None else ""
            guardian_phone = str(row[9]).strip() if len(row) > 9 and row[9] is not None else ""
            blood_group = str(row[10]).strip() if len(row) > 10 and row[10] is not None else ""

            target_year = academic_year

            # Class validation
            c_key = str(raw_class_name or '').strip().lower()
            target_class = all_classes.get(c_key)
            if not target_class:
                errors.append(f"Class '{raw_class_name}' does not exist in system.")

            # Section validation
            if target_class:
                s_key = (target_class.id, str(raw_sec_name or '').strip().lower())
                target_section = all_sections.get(s_key)
                if not target_section:
                    errors.append(f"Section '{raw_sec_name}' does not exist under {target_class.name}.")
            else:
                target_section = None

        # 1. Validate Student ID
        if not raw_id or not str(raw_id).strip():
            errors.append("Student ID is missing.")
            clean_id = ""
        else:
            clean_id = str(raw_id).strip()
            if clean_id in seen_student_ids:
                errors.append(f"Duplicate Student ID '{clean_id}' found in this Excel file.")
            elif clean_id in existing_db_student_ids:
                errors.append(f"Student ID '{clean_id}' already exists in database.")
            seen_student_ids.add(clean_id)

        # 2. Validate Name
        if not raw_name or not str(raw_name).strip():
            errors.append("Student Full Name is missing.")
            clean_name = ""
        else:
            clean_name = str(raw_name).strip()

        # 3. Validate Roll Number
        if raw_roll is None or str(raw_roll).strip() == "":
            errors.append("Roll number is missing.")
            clean_roll = None
        else:
            try:
                clean_roll = int(float(str(raw_roll).strip()))
                if clean_roll <= 0:
                    errors.append("Roll number must be a positive integer.")
                else:
                    scope_key = (target_class.id if target_class else None,
                                 target_section.id if target_section else None,
                                 target_year.id if target_year else None,
                                 clean_roll)
                    if scope_key in seen_rolls_by_scope:
                        errors.append(f"Duplicate Roll Number {clean_roll} in this class/section within file.")
                    else:
                        seen_rolls_by_scope.add(scope_key)

                        # Check against existing DB roll numbers
                        if target_class and target_section and target_year:
                            roll_check = Student.objects.filter(
                                class_level=target_class,
                                section=target_section,
                                academic_year=target_year,
                                roll_number=clean_roll
                            )
                            if organization:
                                roll_check = roll_check.filter(organization=organization)
                            exists_in_db = roll_check.exists()
                            if exists_in_db:
                                errors.append(f"Roll Number {clean_roll} is already assigned in {target_class.name} - {target_section.name}.")
            except ValueError:
                errors.append(f"Invalid roll number format '{raw_roll}'.")
                clean_roll = None

        # 4. Validate Date of Birth
        clean_dob = parse_date_value(raw_dob)
        if not clean_dob and raw_dob:
            errors.append(f"Invalid Date of Birth format '{raw_dob}'. Use YYYY-MM-DD.")

        # 5. Validate Gender
        gender_str = str(raw_gender or '').strip().upper()
        if gender_str in ('M', 'MALE', 'BOY'):
            clean_gender = 'MALE'
        elif gender_str in ('F', 'FEMALE', 'GIRL'):
            clean_gender = 'FEMALE'
        elif gender_str in ('O', 'OTHER'):
            clean_gender = 'OTHER'
        else:
            clean_gender = 'MALE'
            if raw_gender:
                errors.append(f"Unrecognized gender '{raw_gender}'. Allowed: Male, Female, Other.")

        # Summary for this row
        row_payload = {
            'row_index': row_idx,
            'roll_number': clean_roll,
            'student_id': clean_id,
            'full_name': clean_name,
            'date_of_birth': clean_dob.isoformat() if clean_dob else None,
            'gender': clean_gender,
            'class_id': target_class.id if target_class else None,
            'class_name': target_class.name if target_class else "",
            'section_id': target_section.id if target_section else None,
            'section_name': target_section.name if target_section else "",
            'academic_year_id': target_year.id if target_year else None,
            'address': address,
            'guardian_name': guardian_name,
            'guardian_phone': guardian_phone,
            'blood_group': blood_group,
        }

        if errors:
            invalid_records.append({
                'row_index': row_idx,
                'data': row_payload,
                'errors': errors
            })
        else:
            valid_records.append(row_payload)

    return {
        'total_found': len(valid_records) + len(invalid_records),
        'valid_count': len(valid_records),
        'invalid_count': len(invalid_records),
        'valid_records': valid_records,
        'invalid_records': invalid_records,
    }


@transaction.atomic
def commit_excel_import(valid_records, user=None, request=None):
    """
    Atomically creates Student records from pre-validated payloads.
    Logs comprehensive audit action.
    """
    created_students = []
    org = None
    client_id = None
    if request:
        org = get_current_organization(request)
        if org and getattr(org, 'is_studio', False):
            client_id = request.session.get('active_client_id')
    elif user:
        org = getattr(user, 'organization', None)

    for r in valid_records:
        dob = datetime.strptime(r['date_of_birth'], '%Y-%m-%d').date() if r.get('date_of_birth') else None
        student = Student.objects.create(
            organization=org,
            student_id=r['student_id'],
            roll_number=r['roll_number'],
            full_name=r['full_name'],
            date_of_birth=dob,
            gender=r['gender'],
            class_level_id=r['class_id'],
            section_id=r['section_id'],
            academic_year_id=r['academic_year_id'],
            address=r.get('address', ''),
            guardian_name=r.get('guardian_name', ''),
            guardian_phone=r.get('guardian_phone', ''),
            blood_group=r.get('blood_group', ''),
            verification_status='PENDING',
            client_id=client_id
        )
        created_students.append(student)

    log_action(
        user=user,
        action='EXCEL_IMPORT',
        object_type='Student',
        object_repr=f"Imported {len(created_students)} students",
        details={'imported_count': len(created_students)},
        request=request
    )

    return len(created_students)


def export_students_to_excel(queryset):
    """
    Exports filtered students to a styled Excel (.xlsx) file.
    Does NOT include secrets or private authentication info.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Students List"

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Arial", size=10)
    border_thin = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    headers = [
        "Student ID", "Roll No", "Full Name", "Class", "Section", "Academic Year",
        "Gender", "Date of Birth", "Guardian Name", "Guardian Phone", "Address",
        "Blood Group", "Verification Status", "Has Photo", "Card Status"
    ]
    ws.append(headers)
    for col_idx, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for s in queryset.select_related('class_level', 'section', 'academic_year').prefetch_related('id_cards'):
        latest_card = s.id_cards.first()
        card_status = latest_card.get_validity_status_display() if latest_card else "None"

        row = [
            s.student_id,
            s.roll_number,
            s.full_name,
            s.class_level.name,
            s.section.name,
            s.academic_year.name,
            s.get_gender_display(),
            s.date_of_birth.strftime('%Y-%m-%d') if s.date_of_birth else "",
            s.guardian_name,
            s.guardian_phone,
            s.address,
            s.blood_group,
            s.get_verification_status_display(),
            "Yes" if s.has_photo else "No",
            card_status
        ]
        ws.append(row)
        curr_row = ws.max_row
        for col_idx in range(1, len(row) + 1):
            cell = ws.cell(row=curr_row, column=col_idx)
            cell.font = data_font
            cell.border = border_thin

    # Auto-width
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
