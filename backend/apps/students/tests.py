import io
from datetime import date
from PIL import Image
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from apps.academic.models import AcademicYear, ClassLevel, Section
from apps.students.models import Student
from apps.students.services.photo_service import process_student_photo
from apps.students.services.excel_service import (
    generate_excel_template,
    parse_and_validate_excel,
    commit_excel_import
)

User = get_user_model()


class StudentServicesTestCase(TestCase):
    def setUp(self):
        self.ay = AcademicYear.objects.create(
            name="2026/27",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True
        )
        self.grade8 = ClassLevel.objects.create(name="Grade 8", numeric_order=8)
        self.sec_a = Section.objects.create(class_level=self.grade8, name="A")

    def test_photo_processing_crop_aspect_ratio(self):
        # Create a non-3:4 ratio test image (e.g. 500x300 landscape)
        img = Image.new('RGB', (500, 300), color=(100, 150, 200))
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        buf.seek(0)

        processed = process_student_photo(buf, target_aspect_ratio=(3, 4))
        # Verify processed image has 3:4 aspect ratio
        result_img = Image.open(processed)
        w, h = result_img.size
        self.assertAlmostEqual(w / h, 3.0 / 4.0, places=1)

    def test_excel_template_generation(self):
        buf = generate_excel_template(mode='class_wise')
        self.assertGreater(len(buf.getvalue()), 1000)

    def test_excel_validation_detects_duplicates(self):
        # Generate an in-memory workbook with duplicates
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Roll", "ID", "Name", "DOB", "Gender", "Address", "Guardian", "Phone", "Blood"])
        # Duplicate Student ID row
        ws.append([1, "STU101", "Student A", "2012-01-01", "Male", "", "", "", ""])
        ws.append([2, "STU101", "Student B", "2012-01-01", "Female", "", "", "", ""])  # Duplicate ID
        # Duplicate Roll row in same class
        ws.append([1, "STU103", "Student C", "2012-01-01", "Male", "", "", "", ""])    # Duplicate roll 1

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        results = parse_and_validate_excel(
            buf, mode='class_wise', class_level=self.grade8, section=self.sec_a, academic_year=self.ay
        )

        self.assertEqual(results['valid_count'], 1)  # Only STU101 (row 2) is valid
        self.assertEqual(results['invalid_count'], 2) # Row 3 (dup id) and Row 4 (dup roll) are invalid
        self.assertIn("Duplicate Student ID", results['invalid_records'][0]['errors'][0])

    def test_atomic_excel_commit(self):
        valid_records = [
            {
                'roll_number': 10,
                'student_id': 'STU9901',
                'full_name': 'Test New Student',
                'date_of_birth': '2012-05-10',
                'gender': 'MALE',
                'class_id': self.grade8.id,
                'section_id': self.sec_a.id,
                'academic_year_id': self.ay.id,
                'address': 'Test Street',
                'guardian_name': 'Parent Name',
                'guardian_phone': '9840000000',
                'blood_group': 'A+'
            }
        ]
        count = commit_excel_import(valid_records)
        self.assertEqual(count, 1)

        stu = Student.objects.get(student_id='STU9901')
        self.assertEqual(stu.roll_number, 10)
        self.assertEqual(stu.verification_status, 'PENDING')
