from datetime import date, timedelta
from django.test import TestCase
from apps.academic.models import AcademicYear, ClassLevel, Section
from apps.students.models import Student
from apps.idcards.models import IDCard, IDCardTemplate, TemplateElement, PrintLayout
from apps.idcards.services.pdf_generator import generate_id_cards_pdf
from apps.idcards.services.image_analysis import analyze_card_image
from apps.core.models import School
from PIL import Image
import io
from django.core.files.base import ContentFile


class IDCardEngineTestCase(TestCase):
    def setUp(self):
        self.school = School.get_instance()
        self.school.name = "Apex International Academy"
        self.school.save()

        self.ay = AcademicYear.objects.create(
            name="2026/27",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True
        )
        self.grade8 = ClassLevel.objects.create(name="Grade 8", numeric_order=8)
        self.sec_a = Section.objects.create(class_level=self.grade8, name="A")

        # Verified student WITH photo
        img = Image.new('RGB', (300, 400), color=(50, 100, 150))
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        photo_file = ContentFile(buf.getvalue(), name="stu1.jpg")

        self.stu_verified = Student.objects.create(
            student_id="STU8001",
            roll_number=1,
            full_name="Verified Student",
            class_level=self.grade8,
            section=self.sec_a,
            academic_year=self.ay,
            photo=photo_file,
            verification_status="VERIFIED"
        )

        # Unverified student
        self.stu_unverified = Student.objects.create(
            student_id="STU8002",
            roll_number=2,
            full_name="Unverified Student",
            class_level=self.grade8,
            section=self.sec_a,
            academic_year=self.ay,
            verification_status="PENDING"
        )

        # Template
        self.template = IDCardTemplate.objects.create(
            name="Test CR80 Template",
            orientation="PORTRAIT",
            width_mm=54.0,
            height_mm=86.0,
            duplex_mode="FRONT_BACK"
        )
        TemplateElement.objects.create(
            template=self.template, side="FRONT", element_type="DYNAMIC_FIELD",
            dynamic_field_key="{{student.name}}", label_text="Full Name",
            x_mm=5, y_mm=10, width_mm=44, height_mm=6
        )
        TemplateElement.objects.create(
            template=self.template, side="FRONT", element_type="QR_CODE",
            x_mm=5, y_mm=60, width_mm=15, height_mm=15
        )

        # Print layout
        self.layout = PrintLayout.objects.create(
            name="A4 Test Layout",
            paper_size="A4",
            cols=3,
            rows=5,
            show_crop_marks=True
        )

    def test_unverified_student_prevented_by_default_rule15(self):
        # Attempting to print only unverified students must raise ValueError
        with self.assertRaises(ValueError) as ctx:
            generate_id_cards_pdf(
                [self.stu_unverified],
                self.template,
                self.layout,
                self.ay,
                enforce_verified_only=True
            )
        self.assertIn("No eligible students selected", str(ctx.exception))

    def test_verified_student_pdf_generation_success(self):
        pdf_bytes = generate_id_cards_pdf(
            [self.stu_verified],
            self.template,
            self.layout,
            self.ay,
            enforce_verified_only=True
        )
        self.assertGreater(len(pdf_bytes), 1000)
        # Verify card record created
        card = IDCard.objects.get(student=self.stu_verified)
        self.assertEqual(card.validity_status, 'ACTIVE')
        self.assertTrue(card.secure_token)

    def test_card_validity_state_machine(self):
        # Active card
        card = IDCard.objects.create(
            student=self.stu_verified,
            template=self.template,
            academic_year=self.ay,
            card_number="CARD-001",
            valid_from=date.today() - timedelta(days=10),
            valid_until=date.today() + timedelta(days=350),
            validity_status="ACTIVE"
        )
        is_val, reason = card.is_currently_valid()
        self.assertTrue(is_val)
        self.assertEqual(reason, "ACTIVE")

        # Expired card
        card.valid_until = date.today() - timedelta(days=1)
        is_val, reason = card.is_currently_valid()
        self.assertFalse(is_val)
        self.assertEqual(reason, "EXPIRED")

        # Revoked card
        card.validity_status = "REVOKED"
        card.revocation_reason = "Student transferred"
        is_val, reason = card.is_currently_valid()
        self.assertFalse(is_val)
        self.assertEqual(reason, "REVOKED")

    def test_image_dpi_analysis(self):
        # High resolution test: 1016 x 638 px on 86 x 54 mm card (~300 DPI)
        high_res = Image.new('RGB', (1016, 638), color=(200, 200, 200))
        buf = io.BytesIO()
        high_res.save(buf, format='PNG')
        buf.seek(0)

        res_high = analyze_card_image(buf, 86.0, 54.0)
        self.assertTrue(res_high['success'])
        self.assertTrue(res_high['is_suitable'])
        self.assertGreaterEqual(res_high['dpi'], 250)
        self.assertEqual(res_high['rating'], 'SUITABLE')

        # Low resolution test: 200 x 150 px on 86 x 54 mm card (< 100 DPI)
        low_res = Image.new('RGB', (200, 150), color=(100, 100, 100))
        buf_low = io.BytesIO()
        low_res.save(buf_low, format='JPEG')
        buf_low.seek(0)

        res_low = analyze_card_image(buf_low, 86.0, 54.0)
        self.assertTrue(res_low['success'])
        self.assertFalse(res_low['is_suitable'])
        self.assertLess(res_low['dpi'], 150)
        self.assertEqual(res_low['rating'], 'LOW_RESOLUTION')

    def test_template_duplication(self):
        cloned = self.template.duplicate(new_name="Cloned CR80 Template")
        self.assertNotEqual(cloned.id, self.template.id)
        self.assertEqual(cloned.name, "Cloned CR80 Template")
        self.assertEqual(cloned.width_mm, self.template.width_mm)
        self.assertEqual(cloned.height_mm, self.template.height_mm)
        self.assertEqual(cloned.elements.count(), self.template.elements.count())

        original_el = self.template.elements.first()
        cloned_el = cloned.elements.filter(element_type=original_el.element_type).first()
        self.assertIsNotNone(cloned_el)
        self.assertEqual(cloned_el.x_mm, original_el.x_mm)
        self.assertEqual(cloned_el.y_mm, original_el.y_mm)

    def test_template_versioning(self):
        # Generate card using version 1
        card = IDCard.objects.create(
            student=self.stu_verified,
            template=self.template,
            academic_year=self.ay,
            card_number="CARD-V1-001",
            valid_from=date.today(),
            valid_until=date.today() + timedelta(days=365)
        )
        self.assertEqual(self.template.version, 1)

        # Create new version
        ver2 = self.template.create_new_version()
        self.assertEqual(ver2.version, 2)
        self.assertIn("v2", ver2.name)
        self.assertEqual(ver2.parent_template, self.template)

        # Ensure historical card still points to version 1
        card.refresh_from_db()
        self.assertEqual(card.template.id, self.template.id)
        self.assertEqual(card.template.version, 1)

    def test_pdf_generation_with_advanced_elements(self):
        # Add circular photo element, italic text, and background
        TemplateElement.objects.create(
            template=self.template, side="FRONT", element_type="STUDENT_PHOTO",
            x_mm=15, y_mm=20, width_mm=24, height_mm=24, is_circular=True, border_width=1.0
        )
        TemplateElement.objects.create(
            template=self.template, side="FRONT", element_type="TEXT",
            label_text="Verified Student Pass", x_mm=5, y_mm=48, width_mm=44, height_mm=5,
            font_style="ITALIC", font_weight="BOLD"
        )
        self.template.bg_fit_mode = 'CROP'
        self.template.save()

        pdf_bytes = generate_id_cards_pdf(
            [self.stu_verified],
            self.template,
            self.layout,
            self.ay,
            enforce_verified_only=True
        )
        self.assertGreater(len(pdf_bytes), 1500)

    def test_print_center_template_selection(self):
        template_landscape = IDCardTemplate.objects.create(
            name="Landscape Modern Card",
            orientation="LANDSCAPE",
            width_mm=86.0,
            height_mm=54.0,
            is_active=True
        )

        from django.contrib.auth import get_user_model
        admin_user = get_user_model().objects.create_superuser(
            username="test_admin_printer",
            password="adminpassword123",
            role="ADMIN"
        )
        self.client.force_login(admin_user)

        # 1. GET with template parameter
        response = self.client.get('/print-center/', {'template': template_landscape.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_template'].id, template_landscape.id)

        # 2. POST to generate PDF with specific template
        post_data = {
            'action': 'generate_pdf',
            'template': template_landscape.id,
            'layout': self.layout.id,
            'class': self.grade8.id,
            'section': self.sec_a.id,
            'year': self.ay.id,
        }
        res_pdf = self.client.post('/print-center/', post_data)
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf['Content-Type'], 'application/pdf')

    def test_single_card_png_and_jpeg_export(self):
        from apps.idcards.services.pdf_generator import render_single_card_image
        png_bytes, ct_png, fn_png = render_single_card_image(self.stu_verified, self.template, format_type='PNG')
        self.assertEqual(ct_png, 'image/png')
        self.assertTrue(fn_png.endswith('.png'))
        self.assertGreater(len(png_bytes), 1000)

        jpeg_bytes, ct_jpg, fn_jpg = render_single_card_image(self.stu_verified, self.template, format_type='JPEG')
        self.assertEqual(ct_jpg, 'image/jpeg')
        self.assertTrue(fn_jpg.endswith('.jpg'))
        self.assertGreater(len(jpeg_bytes), 1000)

    def test_batch_export_class_png_and_jpeg_zip(self):
        from apps.idcards.services.pdf_generator import export_id_cards_batch
        # Verified students
        stus = [self.stu_verified]
        zip_bytes, ct, fn = export_id_cards_batch(stus, self.template, format_type='PNG', scope_name="Grade_8")
        # For single student it returns direct image; for multiple it returns zip
        self.assertTrue(fn.endswith('.png') or fn.endswith('.zip'))

        # With 2 students
        stu2 = Student.objects.create(
            student_id="STU8003", roll_number=3, full_name="Student 3",
            class_level=self.grade8, section=self.sec_a, academic_year=self.ay,
            photo=self.stu_verified.photo, verification_status="VERIFIED"
        )
        zip_bytes2, ct2, fn2 = export_id_cards_batch([self.stu_verified, stu2], self.template, format_type='PNG', scope_name="Grade_8")
        self.assertEqual(ct2, 'application/zip')
        self.assertTrue(fn2.endswith('.zip'))
        self.assertGreater(len(zip_bytes2), 2000)

    def test_student_directory_print_class_post(self):
        from django.contrib.auth import get_user_model
        admin_user = get_user_model().objects.create_superuser(
            username="test_admin_dir", password="adminpassword123", role="ADMIN"
        )
        self.client.force_login(admin_user)

        post_data = {
            'bulk_action': 'print_class',
            'class_id': self.grade8.id,
            'section_id': 'all',
            'year_id': self.ay.id,
            'template': self.template.id,
            'layout': self.layout.id,
            'format_type': 'PDF',
            'include_unverified': 'true'
        }
        res = self.client.post('/students/', post_data)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertIn('Grade_8_All_Sections_ID_Cards.pdf', res['Content-Disposition'])

    def test_student_directory_print_selected_png_zip(self):
        from django.contrib.auth import get_user_model
        admin_user = get_user_model().objects.create_superuser(
            username="test_admin_dir2", password="adminpassword123", role="ADMIN"
        )
        self.client.force_login(admin_user)

        post_data = {
            'bulk_action': 'print',
            'selected_students': [self.stu_verified.id],
            'template': self.template.id,
            'format_type': 'PNG',
            'image_side': 'COMBINED',
            'include_unverified': 'true'
        }
        res = self.client.post('/students/', post_data)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'image/png')

    def test_student_detail_print_card_export(self):
        from django.contrib.auth import get_user_model
        admin_user = get_user_model().objects.create_superuser(
            username="test_admin_det", password="adminpassword123", role="ADMIN"
        )
        self.client.force_login(admin_user)

        # PDF single card export
        res_pdf = self.client.post(f'/students/{self.stu_verified.id}/', {
            'action': 'print_card',
            'template': self.template.id,
            'format_type': 'PDF',
            'layout_choice': 'card'
        })
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf['Content-Type'], 'application/pdf')

        # JPEG export
        res_jpg = self.client.post(f'/students/{self.stu_verified.id}/', {
            'action': 'print_card',
            'template': self.template.id,
            'format_type': 'JPEG',
            'image_side': 'COMBINED'
        })
        self.assertEqual(res_jpg.status_code, 200)
        self.assertEqual(res_jpg['Content-Type'], 'image/jpeg')

