import io
import os
from datetime import date
from PIL import Image, ImageDraw, ImageFont
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from apps.core.models import School
from apps.academic.models import AcademicYear, ClassLevel, Section
from apps.accounts.models import TeacherProfile
from apps.students.models import Student, VerificationRecord
from apps.idcards.models import IDCardTemplate, TemplateElement, PrintLayout, IDCard


User = get_user_model()


def create_sample_logo():
    """Generates a crisp school emblem using Pillow."""
    img = Image.new('RGBA', (300, 300), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # Circle badge
    draw.ellipse([10, 10, 290, 290], fill=(30, 58, 138, 255), outline=(234, 179, 8, 255), width=8)
    draw.ellipse([30, 30, 270, 270], outline=(255, 255, 255, 200), width=3)
    # Book / Star graphic
    draw.polygon([(150, 60), (175, 115), (235, 120), (190, 160), (205, 220), (150, 185), (95, 220), (110, 160), (65, 120), (125, 115)], fill=(234, 179, 8, 255))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return ContentFile(buf.getvalue(), name="school_logo.png")


def create_sample_signature():
    """Generates a professional transparent PNG signature."""
    img = Image.new('RGBA', (400, 150), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # Realistic cursive signature strokes
    points = [
        (40, 95), (65, 40), (85, 110), (105, 60), (120, 85),
        (150, 80), (175, 30), (195, 115), (220, 75), (250, 80),
        (280, 50), (310, 100), (350, 90), (375, 45)
    ]
    draw.line(points, fill=(15, 23, 42, 230), width=4, joint='curve')
    draw.line([(30, 115), (360, 110)], fill=(15, 23, 42, 200), width=3)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return ContentFile(buf.getvalue(), name="principal_signature.png")


def create_sample_student_photo(name, bg_color):
    """Generates a clean ID portrait avatar for sample students."""
    img = Image.new('RGB', (300, 400), bg_color)
    draw = ImageDraw.Draw(img)
    # Head and shoulders silhouette
    draw.ellipse([90, 70, 210, 190], fill=(248, 250, 252))
    draw.chord([40, 180, 260, 420], 180, 360, fill=(248, 250, 252))
    # Initials badge
    initials = "".join([part[0].upper() for part in name.split()[:2]])
    # Draw simple initial indicator
    draw.rectangle([110, 340, 190, 380], fill=(15, 23, 42))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    buf.seek(0)
    return ContentFile(buf.getvalue(), name=f"{name.replace(' ', '_').lower()}.jpg")


class Command(BaseCommand):
    help = "Seeds comprehensive demo data for development and demonstration."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding production demo data..."))

        # 1. School Settings
        school = School.get_instance()
        school.name = "Apex International Academy"
        school.short_name = "AIA"
        school.address = "123 Education Lane, Shanti Nagar"
        school.municipality = "Kathmandu Metropolitan"
        school.district = "Kathmandu"
        school.province = "Bagmati"
        school.country = "Nepal"
        school.phone = "+977-1-4567890"
        school.email = "admin@apexschool.edu.np"
        school.website = "https://apexschool.edu.np"
        school.head_teacher_name = "Dr. Surendra Sharma"
        school.default_id_validity_days = 365
        school.default_qr_correction_level = 'M'

        if not school.logo:
            school.logo.save("school_logo.png", create_sample_logo(), save=False)
        if not school.head_teacher_signature:
            school.head_teacher_signature.save("principal_signature.png", create_sample_signature(), save=False)
        school.save()
        self.stdout.write("[OK] School settings configured.")

        # 2. Academic Year
        ay, _ = AcademicYear.objects.get_or_create(
            name="2026/27",
            defaults={
                'start_date': date(2026, 4, 1),
                'end_date': date(2027, 3, 31),
                'is_active': True,
            }
        )
        ay.is_active = True
        ay.save()
        self.stdout.write(f"[OK] Active Academic Year set: {ay.name}")

        # 3. Classes and Sections
        grades = {}
        for num in range(1, 11):
            class_name = f"Grade {num}"
            c, _ = ClassLevel.objects.get_or_create(name=class_name, defaults={'numeric_order': num})
            grades[num] = c
            Section.objects.get_or_create(class_level=c, name="A")
            Section.objects.get_or_create(class_level=c, name="B")
        self.stdout.write("[OK] Grades 1 through 10 (Sections A & B) initialized.")

        # 4. Users (Admin and Teachers)
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                'email': 'admin@apexschool.edu.np',
                'first_name': 'System',
                'last_name': 'Administrator',
                'role': 'ADMIN',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin_user.set_password("admin123")
            admin_user.save()
        self.stdout.write("[OK] Admin user created: admin / admin123")

        # Teacher 1 (Assigned to Grade 8 - Section A)
        t1_user, created = User.objects.get_or_create(
            username="teacher1",
            defaults={
                'email': 'teacher1@apexschool.edu.np',
                'first_name': 'Bishnu',
                'last_name': 'Adhikari',
                'role': 'TEACHER',
                'phone': '9841000001',
            }
        )
        if created:
            t1_user.set_password("teacher123")
            t1_user.save()

        grade8 = grades[8]
        sec_8a = Section.objects.get(class_level=grade8, name="A")
        sec_8b = Section.objects.get(class_level=grade8, name="B")

        t1_profile, _ = TeacherProfile.objects.get_or_create(
            user=t1_user,
            defaults={
                'employee_id': 'EMP-8001',
                'assigned_class': grade8,
                'assigned_section': sec_8a,
                'status': 'ACTIVE',
            }
        )
        t1_profile.assigned_class = grade8
        t1_profile.assigned_section = sec_8a
        t1_profile.save()
        self.stdout.write("[OK] Teacher 1 created: teacher1 / teacher123 (Grade 8 - Section A)")

        # Teacher 2 (Grade 8 - Section B)
        t2_user, created = User.objects.get_or_create(
            username="teacher2",
            defaults={
                'email': 'teacher2@apexschool.edu.np',
                'first_name': 'Sarita',
                'last_name': 'Shrestha',
                'role': 'TEACHER',
                'phone': '9841000002',
            }
        )
        if created:
            t2_user.set_password("teacher123")
            t2_user.save()

        t2_profile, _ = TeacherProfile.objects.get_or_create(
            user=t2_user,
            defaults={
                'employee_id': 'EMP-8002',
                'assigned_class': grade8,
                'assigned_section': sec_8b,
                'status': 'ACTIVE',
            }
        )
        t2_profile.assigned_class = grade8
        t2_profile.assigned_section = sec_8b
        t2_profile.save()

        # 5. ID Card Template (CR80 Portrait 54x86 mm)
        template, _ = IDCardTemplate.objects.get_or_create(
            name="Standard CR80 Student ID",
            defaults={
                'card_type': 'STUDENT',
                'orientation': 'PORTRAIT',
                'width_mm': 54.0,
                'height_mm': 86.0,
                'background_color': '#FFFFFF',
                'back_background_color': '#F8FAFC',
                'duplex_mode': 'FRONT_BACK',
                'is_active': True,
                'is_default': True,
            }
        )
        template.elements.all().delete()

        # Front Elements
        # Top banner header
        TemplateElement.objects.create(
            template=template, side='FRONT', element_type='RECTANGLE',
            x_mm=0, y_mm=0, width_mm=54, height_mm=18,
            fill_color='#1E3A8A', z_index=1
        )
        # School logo
        TemplateElement.objects.create(
            template=template, side='FRONT', element_type='SCHOOL_LOGO',
            x_mm=2, y_mm=2, width_mm=14, height_mm=14, z_index=2
        )
        # School Name in banner
        TemplateElement.objects.create(
            template=template, side='FRONT', element_type='DYNAMIC_FIELD',
            dynamic_field_key='{{school.name}}', label_text='Apex International Academy',
            x_mm=17, y_mm=3, width_mm=35, height_mm=7,
            font_size=8, font_weight='BOLD', font_color='#FFFFFF', text_align='LEFT', z_index=2
        )
        TemplateElement.objects.create(
            template=template, side='FRONT', element_type='TEXT',
            label_text='STUDENT IDENTITY CARD',
            x_mm=17, y_mm=10, width_mm=35, height_mm=5,
            font_size=6, font_weight='BOLD', font_color='#FDE047', text_align='LEFT', z_index=2
        )
        # Student Photo box
        TemplateElement.objects.create(
            template=template, side='FRONT', element_type='STUDENT_PHOTO',
            x_mm=14.5, y_mm=20, width_mm=25, height_mm=32, z_index=2
        )
        # Student Name
        TemplateElement.objects.create(
            template=template, side='FRONT', element_type='DYNAMIC_FIELD',
            dynamic_field_key='{{student.name}}', label_text='Full Name',
            x_mm=2, y_mm=53, width_mm=50, height_mm=5,
            font_size=9, font_weight='BOLD', font_color='#0F172A', text_align='CENTER', z_index=2
        )
        # Roll No & ID
        TemplateElement.objects.create(
            template=template, side='FRONT', element_type='DYNAMIC_FIELD',
            dynamic_field_key='ID: {{student.student_id}}  |  Roll: {{student.roll_no}}',
            label_text='ID & Roll',
            x_mm=2, y_mm=58, width_mm=50, height_mm=4,
            font_size=7, font_weight='NORMAL', font_color='#475569', text_align='CENTER', z_index=2
        )
        # Class & Section
        TemplateElement.objects.create(
            template=template, side='FRONT', element_type='DYNAMIC_FIELD',
            dynamic_field_key='Class: {{student.class}} - {{student.section}}',
            label_text='Class & Section',
            x_mm=2, y_mm=62, width_mm=50, height_mm=4,
            font_size=7, font_weight='BOLD', font_color='#1E3A8A', text_align='CENTER', z_index=2
        )
        # Validity
        TemplateElement.objects.create(
            template=template, side='FRONT', element_type='DYNAMIC_FIELD',
            dynamic_field_key='Valid Till: {{valid_until}}', label_text='Validity',
            x_mm=2, y_mm=66, width_mm=50, height_mm=4,
            font_size=6, font_weight='NORMAL', font_color='#64748B', text_align='CENTER', z_index=2
        )
        # Principal Signature
        TemplateElement.objects.create(
            template=template, side='FRONT', element_type='SIGNATURE',
            x_mm=32, y_mm=71, width_mm=20, height_mm=10, z_index=2
        )
        TemplateElement.objects.create(
            template=template, side='FRONT', element_type='TEXT',
            label_text='Principal Signature',
            x_mm=32, y_mm=81, width_mm=20, height_mm=3,
            font_size=5, font_weight='NORMAL', font_color='#475569', text_align='CENTER', z_index=2
        )
        # Front QR Code
        TemplateElement.objects.create(
            template=template, side='FRONT', element_type='QR_CODE',
            x_mm=3, y_mm=70, width_mm=14, height_mm=14, z_index=2
        )

        # Back Elements
        TemplateElement.objects.create(
            template=template, side='BACK', element_type='RECTANGLE',
            x_mm=0, y_mm=0, width_mm=54, height_mm=10,
            fill_color='#0F172A', z_index=1
        )
        TemplateElement.objects.create(
            template=template, side='BACK', element_type='TEXT',
            label_text='TERMS & CONDITIONS',
            x_mm=0, y_mm=3, width_mm=54, height_mm=5,
            font_size=7, font_weight='BOLD', font_color='#FFFFFF', text_align='CENTER', z_index=2
        )
        terms = (
            "1. This card must be presented upon request by school staff.\n"
            "2. If found, please return to school administration.\n"
            "3. Tampering with or altering this card is strictly prohibited."
        )
        TemplateElement.objects.create(
            template=template, side='BACK', element_type='TEXT',
            label_text=terms,
            x_mm=3, y_mm=14, width_mm=48, height_mm=25,
            font_size=6, font_weight='NORMAL', font_color='#334155', text_align='LEFT', z_index=2
        )
        TemplateElement.objects.create(
            template=template, side='BACK', element_type='LINE',
            x_mm=3, y_mm=42, width_mm=48, height_mm=1,
            border_color='#CBD5E1', border_width=0.5, z_index=2
        )
        TemplateElement.objects.create(
            template=template, side='BACK', element_type='DYNAMIC_FIELD',
            dynamic_field_key='Emergency Phone: {{student.guardian_phone}}', label_text='Emergency Phone',
            x_mm=3, y_mm=45, width_mm=48, height_mm=5,
            font_size=6, font_weight='BOLD', font_color='#DC2626', text_align='LEFT', z_index=2
        )
        TemplateElement.objects.create(
            template=template, side='BACK', element_type='DYNAMIC_FIELD',
            dynamic_field_key='Blood Group: {{student.blood_group}}', label_text='Blood Group',
            x_mm=3, y_mm=50, width_mm=48, height_mm=5,
            font_size=6, font_weight='BOLD', font_color='#0F172A', text_align='LEFT', z_index=2
        )
        # School Contact Footer
        TemplateElement.objects.create(
            template=template, side='BACK', element_type='DYNAMIC_FIELD',
            dynamic_field_key='{{school.address}}, {{school.municipality}} | Tel: {{school.phone}}',
            label_text='School Contact',
            x_mm=2, y_mm=76, width_mm=50, height_mm=8,
            font_size=5, font_weight='NORMAL', font_color='#64748B', text_align='CENTER', z_index=2
        )
        self.stdout.write("[OK] Standard CR80 Template & Front/Back Elements configured.")

        # 6. Default PrintLayout (A4 3x5 Grid)
        layout, _ = PrintLayout.objects.get_or_create(
            name="Standard A4 (3x5 Grid)",
            defaults={
                'paper_size': 'A4',
                'orientation': 'PORTRAIT',
                'margin_top_mm': 10.0,
                'margin_bottom_mm': 10.0,
                'margin_left_mm': 10.0,
                'margin_right_mm': 10.0,
                'gap_x_mm': 4.0,
                'gap_y_mm': 4.0,
                'cols': 3,
                'rows': 5,
                'show_crop_marks': True,
                'crop_mark_length_mm': 4.0,
                'crop_mark_offset_mm': 1.5,
                'duplex_alignment': 'MIRROR_COLUMNS',
            }
        )
        self.stdout.write("[OK] Standard A4 PrintLayout initialized.")

        # 7. Sample Students for Grade 8 - Section A
        sample_students_data = [
            (1, "STU8001", "Aarav Sharma", "2012-05-14", "MALE", "O+", "9841234501", (59, 130, 246), "VERIFIED"),
            (2, "STU8002", "Priya Thapa", "2012-08-22", "FEMALE", "A+", "9841234502", (236, 72, 153), "VERIFIED"),
            (3, "STU8003", "Bibek Karki", "2011-12-01", "MALE", "B+", "9841234503", (16, 185, 129), "VERIFIED"),
            (4, "STU8004", "Ananya Shrestha", "2012-03-18", "FEMALE", "AB+", "9841234504", (168, 85, 247), "VERIFIED"),
            (5, "STU8005", "Rohan Gurung", "2011-09-09", "MALE", "O-", "9841234505", (245, 158, 11), "VERIFIED"),
            (6, "STU8006", "Sujata Rai", "2012-07-11", "FEMALE", "A-", "9841234506", (244, 63, 94), "VERIFIED"),
            (7, "STU8007", "Dipesh Basnet", "2011-11-25", "MALE", "B+", "9841234507", (14, 165, 233), "SUBMITTED"),
            (8, "STU8008", "Kritika Magar", "2012-01-30", "FEMALE", "O+", "9841234508", (139, 92, 246), "SUBMITTED"),
            (9, "STU8009", "Manish Tamang", "2012-04-05", "MALE", "AB-", "9841234509", (20, 184, 166), "PENDING"),
            (10, "STU8010", "Sneha Adhikari", "2012-06-19", "FEMALE", "B-", "9841234510", (249, 115, 22), "PENDING"),
            (11, "STU8011", "Ayush Poudel", "2011-10-14", "MALE", "A+", "9841234511", None, "PENDING"), # Missing photo test
            (12, "STU8012", "Pooja Dahal", "2012-02-28", "FEMALE", "O+", "9841234512", None, "REJECTED"), # Rejected test
        ]

        for roll, stu_id, name, dob_str, gender, bg, phone, color, v_status in sample_students_data:
            dob = date.fromisoformat(dob_str)
            student, _ = Student.objects.get_or_create(
                student_id=stu_id,
                defaults={
                    'roll_number': roll,
                    'full_name': name,
                    'date_of_birth': dob,
                    'gender': gender,
                    'class_level': grade8,
                    'section': sec_8a,
                    'academic_year': ay,
                    'blood_group': bg,
                    'guardian_name': f"Guardian of {name}",
                    'guardian_phone': phone,
                    'address': "Kathmandu Ward 4",
                    'verification_status': v_status,
                }
            )
            student.verification_status = v_status
            if v_status == 'VERIFIED':
                student.verified_by = admin_user
                student.verified_at = date.today()
            elif v_status == 'REJECTED':
                student.rejection_reason = "Photo unclear and roll number mismatch."

            if color and not student.photo:
                photo_file = create_sample_student_photo(name, color)
                student.photo.save(f"{stu_id}.jpg", photo_file, save=False)

            student.save()

            # Pre-generate ID cards for verified students
            if v_status == 'VERIFIED' and student.has_photo:
                IDCard.objects.get_or_create(
                    student=student,
                    academic_year=ay,
                    defaults={
                        'template': template,
                        'card_number': f"ID-2026-27-{stu_id}",
                        'valid_from': ay.start_date,
                        'valid_until': ay.end_date,
                        'card_status': 'GENERATED',
                        'validity_status': 'ACTIVE',
                        'generated_by': admin_user
                    }
                )

        self.stdout.write(self.style.SUCCESS("[OK] Demo data successfully seeded!"))
        self.stdout.write(self.style.SUCCESS("  Admin credentials:   admin / admin123"))
        self.stdout.write(self.style.SUCCESS("  Teacher credentials: teacher1 / teacher123"))
