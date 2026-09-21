from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.academic.models import AcademicYear, ClassLevel, Section
from apps.accounts.models import TeacherProfile
from apps.students.models import Student
from apps.idcards.models import IDCard, IDCardTemplate
from apps.core.models import School
from datetime import date

User = get_user_model()


class APISecurityTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create school
        self.school = School.get_instance()
        self.school.name = "Test International Academy"
        self.school.save()

        # Academic Year
        self.ay = AcademicYear.objects.create(
            name="2026/27",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True
        )

        # Classes & Sections
        self.class8 = ClassLevel.objects.create(name="Grade 8", numeric_order=8)
        self.class9 = ClassLevel.objects.create(name="Grade 9", numeric_order=9)
        self.sec8a = Section.objects.create(class_level=self.class8, name="A")
        self.sec8b = Section.objects.create(class_level=self.class8, name="B")
        self.sec9a = Section.objects.create(class_level=self.class9, name="A")

        # Teacher 1 (Grade 8 - A)
        self.teacher1_user = User.objects.create_user(
            username="teacher1",
            password="password123",
            role="TEACHER"
        )
        self.teacher1_profile = TeacherProfile.objects.create(
            user=self.teacher1_user,
            employee_id="EMP-001",
            assigned_class=self.class8,
            assigned_section=self.sec8a,
            status="ACTIVE"
        )

        # Inactive Teacher
        self.teacher_inactive_user = User.objects.create_user(
            username="inactive_teacher",
            password="password123",
            role="TEACHER"
        )
        self.teacher_inactive_profile = TeacherProfile.objects.create(
            user=self.teacher_inactive_user,
            employee_id="EMP-INACT",
            assigned_class=self.class8,
            assigned_section=self.sec8a,
            status="INACTIVE"
        )

        # Students
        # Student 1 in Grade 8 - A (Teacher 1's class)
        self.stu1 = Student.objects.create(
            student_id="STU8001",
            roll_number=1,
            full_name="Student One",
            class_level=self.class8,
            section=self.sec8a,
            academic_year=self.ay,
            guardian_phone="9841000001",
            verification_status="PENDING"
        )

        # Student 2 in Grade 8 - B (Different section)
        self.stu2 = Student.objects.create(
            student_id="STU8002",
            roll_number=1,
            full_name="Student Two",
            class_level=self.class8,
            section=self.sec8b,
            academic_year=self.ay,
            guardian_phone="9841000002",
            verification_status="PENDING"
        )

        # Student 3 in Grade 9 - A (Different class)
        self.stu3 = Student.objects.create(
            student_id="STU9001",
            roll_number=1,
            full_name="Student Three",
            class_level=self.class9,
            section=self.sec9a,
            academic_year=self.ay,
            guardian_phone="9841000003",
            verification_status="PENDING"
        )

    def test_login_active_teacher_success(self):
        url = reverse('api_login')
        response = self.client.post(url, {'username': 'teacher1', 'password': 'password123'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['teacher_profile']['employee_id'], 'EMP-001')

    def test_login_inactive_teacher_blocked(self):
        url = reverse('api_login')
        response = self.client.post(url, {'username': 'inactive_teacher', 'password': 'password123'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('deactivated', response.data['error'])

    def test_teacher_can_only_see_assigned_class_students(self):
        # Login as teacher1
        login_res = self.client.post(reverse('api_login'), {'username': 'teacher1', 'password': 'password123'}, format='json')
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # List students
        url = reverse('api_teacher_students')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should only contain Student 1, NOT Student 2 or Student 3
        returned_ids = [s['student_id'] for s in response.data['results']]
        self.assertIn("STU8001", returned_ids)
        self.assertNotIn("STU8002", returned_ids)
        self.assertNotIn("STU9001", returned_ids)

    def test_teacher_cannot_access_unauthorized_student_detail(self):
        # Login as teacher1
        login_res = self.client.post(reverse('api_login'), {'username': 'teacher1', 'password': 'password123'}, format='json')
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Accessing assigned student details (Grade 8A) -> 200 OK
        res1 = self.client.get(reverse('api_teacher_student_detail', kwargs={'pk': self.stu1.id}))
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # Accessing unassigned student details (Grade 8B) -> 403 Forbidden
        res2 = self.client.get(reverse('api_teacher_student_detail', kwargs={'pk': self.stu2.id}))
        self.assertEqual(res2.status_code, status.HTTP_403_FORBIDDEN)

        # Accessing unassigned student details (Grade 9A) -> 403 Forbidden
        res3 = self.client.get(reverse('api_teacher_student_detail', kwargs={'pk': self.stu3.id}))
        self.assertEqual(res3.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_permitted_edit_enforcement(self):
        login_res = self.client.post(reverse('api_login'), {'username': 'teacher1', 'password': 'password123'}, format='json')
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        url = reverse('api_teacher_student_update', kwargs={'pk': self.stu1.id})
        # Teacher edits permitted fields (student_id, roll_number, guardian_phone) and verification_status (forbidden)
        payload = {
            'guardian_phone': '9800000000',
            'student_id': 'STU8099',
            'roll_number': 99,
            'verification_status': 'VERIFIED'
        }
        res = self.client.patch(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.stu1.refresh_from_db()
        # Permitted fields updated by teacher
        self.assertEqual(self.stu1.guardian_phone, '9800000000')
        self.assertEqual(self.stu1.roll_number, 99)
        self.assertEqual(self.stu1.student_id, 'STU8099')
        # Verification status remains protected
        self.assertEqual(self.stu1.verification_status, 'PENDING')

    def test_classes_sections_endpoint(self):
        login_res = self.client.post(reverse('api_login'), {'username': 'teacher1', 'password': 'password123'}, format='json')
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        res = self.client.get(reverse('api_classes_sections'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 2)
        first = res.data[0]
        self.assertIn('name', first)
        self.assertIn('sections', first)
        self.assertIsInstance(first['sections'], list)

    def test_teacher_student_enrollment(self):
        login_res = self.client.post(reverse('api_login'), {'username': 'teacher1', 'password': 'password123'}, format='json')
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        url = reverse('api_teacher_student_create')
        payload = {
            'roll_number': 5,
            'full_name': 'New Student Enrolled',
            'gender': 'FEMALE',
            'date_of_birth': '2010-05-15',
            'blood_group': 'B+',
            'guardian_name': 'Parent Test',
            'guardian_phone': '9812345678',
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', res.data)
        self.assertEqual(res.data['roll_number'], 5)
        self.assertEqual(res.data['full_name'], 'New Student Enrolled')
        self.assertEqual(res.data['class_name'], self.class8.name)
        self.assertEqual(res.data['section_name'], self.sec8a.name)

