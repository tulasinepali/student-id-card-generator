from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.platform_admin.models import Organization, OrganizationClient
from apps.accounts.models import TeacherProfile
from apps.academic.models import ClassLevel, Section, AcademicYear
from apps.students.models import Student
from rest_framework.test import APIClient

User = get_user_model()


class StudioTeacherIsolationTests(TestCase):
    def setUp(self):
        # 1. Setup Studio Organization
        self.studio_org = Organization.objects.create(
            name="Apex Studio & Press",
            org_id="ORG-STUDIO-1",
            org_type="STUDIO_PRESS",
            status="ACTIVE"
        )
        self.client_a = OrganizationClient.objects.create(
            organization=self.studio_org,
            name="Client School Alpha"
        )
        self.client_b = OrganizationClient.objects.create(
            organization=self.studio_org,
            name="Client School Beta"
        )

        # 2. Setup Studio Admin
        self.studio_admin = User.objects.create_user(
            username="studio_admin",
            password="adminpassword",
            email="studio@example.com",
            role="ADMIN",
            organization=self.studio_org
        )

        # 3. Setup Academic Structure
        self.academic_year = AcademicYear.objects.create(
            organization=self.studio_org,
            name="2026/2027",
            start_date="2026-01-01",
            end_date="2026-12-31",
            is_active=True
        )
        self.class_1 = ClassLevel.objects.create(
            organization=self.studio_org,
            name="Grade 1",
            numeric_order=1
        )
        self.sec_a = Section.objects.create(
            class_level=self.class_1,
            name="A"
        )

        # 4. Setup Teachers for Client A and Client B
        self.user_teacher_a = User.objects.create_user(
            username="teacher_a",
            password="teacherpassword",
            first_name="Alice",
            last_name="Alpha",
            email="alice@alpha.edu",
            role="TEACHER",
            organization=self.studio_org
        )
        self.profile_a = TeacherProfile.objects.create(
            user=self.user_teacher_a,
            employee_id="EMP-A01",
            client=self.client_a,
            assigned_class=self.class_1,
            assigned_section=self.sec_a,
            status="ACTIVE"
        )
        self.sec_a.assigned_teachers.add(self.profile_a)

        self.user_teacher_b = User.objects.create_user(
            username="teacher_b",
            password="teacherpassword",
            first_name="Bob",
            last_name="Beta",
            email="bob@beta.edu",
            role="TEACHER",
            organization=self.studio_org
        )
        self.profile_b = TeacherProfile.objects.create(
            user=self.user_teacher_b,
            employee_id="EMP-B01",
            client=self.client_b,
            assigned_class=self.class_1,
            assigned_section=self.sec_a,
            status="ACTIVE"
        )
        self.sec_a.assigned_teachers.add(self.profile_b)

        # 5. Setup Students for Client A and Client B in same Grade 1 Section A
        self.student_a1 = Student.objects.create(
            organization=self.studio_org,
            client=self.client_a,
            student_id="STU-A01",
            roll_number=1,
            full_name="Student Alpha One",
            gender="MALE",
            class_level=self.class_1,
            section=self.sec_a,
            academic_year=self.academic_year,
            status="ACTIVE"
        )
        self.student_a2 = Student.objects.create(
            organization=self.studio_org,
            client=self.client_a,
            student_id="STU-A02",
            roll_number=2,
            full_name="Student Alpha Two",
            gender="FEMALE",
            class_level=self.class_1,
            section=self.sec_a,
            academic_year=self.academic_year,
            status="ACTIVE"
        )
        self.student_b1 = Student.objects.create(
            organization=self.studio_org,
            client=self.client_b,
            student_id="STU-B01",
            roll_number=1,
            full_name="Student Beta One",
            gender="MALE",
            class_level=self.class_1,
            section=self.sec_a,
            academic_year=self.academic_year,
            status="ACTIVE"
        )

    def test_web_admin_teachers_list_scoping(self):
        """Studio admin viewing teachers filtered by active_client session."""
        client = Client()
        client.login(username="studio_admin", password="adminpassword")

        # Select Client A
        session = client.session
        session['active_client_id'] = str(self.client_a.id)
        session.save()

        res = client.get('/teachers/')
        self.assertEqual(res.status_code, 200)
        teachers = list(res.context['teachers'])
        self.assertIn(self.profile_a, teachers)
        self.assertNotIn(self.profile_b, teachers)

        # Select Client B
        session['active_client_id'] = str(self.client_b.id)
        session.save()

        res = client.get('/teachers/')
        self.assertEqual(res.status_code, 200)
        teachers = list(res.context['teachers'])
        self.assertIn(self.profile_b, teachers)
        self.assertNotIn(self.profile_a, teachers)

    def test_mobile_api_teacher_student_list_isolation(self):
        """Teacher A only sees Client A students in REST API, never Client B students."""
        api_client = APIClient()
        api_client.force_authenticate(user=self.user_teacher_a)

        res = api_client.get('/api/teacher/students/')
        self.assertEqual(res.status_code, 200)
        results = res.data.get('results', res.data)
        returned_ids = [s['student_id'] for s in results]

        self.assertIn('STU-A01', returned_ids)
        self.assertIn('STU-A02', returned_ids)
        self.assertNotIn('STU-B01', returned_ids)

    def test_mobile_api_teacher_dashboard_stats_isolation(self):
        """Teacher A stats only count Client A students."""
        api_client = APIClient()
        api_client.force_authenticate(user=self.user_teacher_a)

        res = api_client.get('/api/teacher/dashboard/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['total_students'], 2)

    def test_mobile_api_cross_client_detail_access_blocked(self):
        """Teacher A cannot access Client B student details (404/403)."""
        api_client = APIClient()
        api_client.force_authenticate(user=self.user_teacher_a)

        res = api_client.get(f'/api/teacher/students/{self.student_b1.id}/')
        self.assertIn(res.status_code, [403, 404])

    def test_mobile_api_student_enrollment_auto_binds_client(self):
        """When Teacher A creates a student, it automatically inherits Client A."""
        api_client = APIClient()
        api_client.force_authenticate(user=self.user_teacher_a)

        payload = {
            'roll_number': 3,
            'full_name': 'New Alpha Student',
            'gender': 'MALE',
            'date_of_birth': '2015-05-10',
            'guardian_name': 'Alpha Parent',
            'guardian_phone': '9800000000',
        }
        res = api_client.post('/api/teacher/students/create/', payload)
        self.assertEqual(res.status_code, 201)

        new_student = Student.objects.get(roll_number=3, full_name='New Alpha Student')
        self.assertEqual(new_student.client, self.client_a)
        self.assertEqual(new_student.organization, self.studio_org)

    def test_web_admin_create_teacher_with_client(self):
        """Studio admin creating a teacher with client_id assigns client foreign key."""
        client = Client()
        client.login(username="studio_admin", password="adminpassword")

        payload = {
            'action': 'create',
            'username': 'new_teacher_b',
            'employee_id': 'EMP-B02',
            'first_name': 'Charlie',
            'last_name': 'Beta',
            'password': 'password123',
            'client_id': str(self.client_b.id),
        }
        res = client.post('/teachers/', payload)
        self.assertEqual(res.status_code, 302)

        new_profile = TeacherProfile.objects.get(employee_id='EMP-B02')
        self.assertEqual(new_profile.client, self.client_b)
