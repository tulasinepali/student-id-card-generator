from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User
from apps.core.models import School
from apps.students.models import Student
from apps.academic.models import ClassLevel
from apps.platform_admin.models import (
    Organization,
    SubscriptionPlan,
    OrganizationSubscription,
    PlatformAuditLog,
    SupportSession,
    PlatformSetting,
    OrganizationClient,
    PlatformNotification,
)


class PlatformAdminSecurityAndAuthTests(TestCase):
    """
    Tests security isolation and permission enforcement:
    - Normal teachers / admins MUST get HTTP 403 Forbidden.
    - Unauthenticated requests must be redirected to platform login.
    - Only users with role='SUPER_ADMIN' or is_superuser=True can access.
    """
    def setUp(self):
        self.client = Client()
        self.superadmin = User.objects.create_superuser(
            username='platform_super',
            email='super@platform.internal',
            password='secretpassword123'
        )
        self.superadmin.role = 'SUPER_ADMIN'
        self.superadmin.save()

        self.teacher = User.objects.create_user(
            username='regular_teacher',
            email='teacher@school.edu.np',
            password='teacherpassword123',
            role='TEACHER'
        )

        self.org_admin = User.objects.create_user(
            username='org_admin_user',
            email='admin@school.edu.np',
            password='adminpassword123',
            role='ADMIN'
        )

        self.plan = SubscriptionPlan.objects.create(
            name='Standard',
            code='STANDARD',
            price_per_year=299.00,
            max_students=500,
            max_staff=50
        )

    def test_unauthenticated_access_redirects_to_login(self):
        """Unauthenticated user accessing /platform-admin/ is redirected to login."""
        response = self.client.get(reverse('platform_admin:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/platform-admin/login/', response.url)

    def test_teacher_access_returns_403_forbidden(self):
        """Normal organization teacher gets HTTP 403 Forbidden."""
        self.client.login(username='regular_teacher', password='teacherpassword123')
        response = self.client.get(reverse('platform_admin:dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_org_admin_access_returns_403_forbidden(self):
        """Organization admin gets HTTP 403 Forbidden."""
        self.client.login(username='org_admin_user', password='adminpassword123')
        response = self.client.get(reverse('platform_admin:dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_superadmin_access_granted(self):
        """Super Admin gets HTTP 200 OK on platform dashboard."""
        self.client.login(username='platform_super', password='secretpassword123')
        response = self.client.get(reverse('platform_admin:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Platform Executive Dashboard")

    def test_login_view_blocks_non_superadmins(self):
        """Dedicated platform login view rejects non-superadmins even with valid passwords."""
        response = self.client.post(reverse('platform_admin:login'), {
            'username': 'regular_teacher',
            'password': 'teacherpassword123'
        })
        self.assertEqual(response.status_code, 302)
        # Should redirect back to platform login with error
        self.assertIn('/platform-admin/login/', response.url)

    def test_platform_owner_credentials_blocked_from_organization_site_login(self):
        """Platform Super Admin credentials cannot be used to log into the Organization site."""
        response = self.client.post(reverse('admin_login'), {
            'username': 'platform_super',
            'password': 'secretpassword123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Access Denied: Platform Owner")
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_organization_admin_credentials_blocked_from_platform_login(self):
        """Organization Admin credentials cannot be used to log into the Platform Portal."""
        response = self.client.post(reverse('platform_admin:login'), {
            'username': 'org_admin_user',
            'password': 'adminpassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/platform-admin/login/', response.url)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_platform_owner_credentials_blocked_from_mobile_api(self):
        """Platform Super Admin credentials cannot log into Teacher Mobile App REST API."""
        response = self.client.post(reverse('api_login'), {
            'username': 'platform_super',
            'password': 'secretpassword123'
        })
        self.assertEqual(response.status_code, 403)
        self.assertIn('Platform Owner', response.json().get('error', ''))

    def test_organization_admin_allowed_into_organization_login(self):
        """Organization Admin credentials succeed at Organization Site login."""
        response = self.client.post(reverse('admin_login'), {
            'username': 'org_admin_user',
            'password': 'adminpassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboard'), response.url)
        self.assertIn('_auth_user_id', self.client.session)

    def test_platform_owner_allowed_into_platform_login(self):
        """Platform Owner credentials succeed at Platform Portal login."""
        response = self.client.post(reverse('platform_admin:login'), {
            'username': 'platform_super',
            'password': 'secretpassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('platform_admin:dashboard'), response.url)
        self.assertIn('_auth_user_id', self.client.session)


class PlatformAdminOrganizationTests(TestCase):
    """
    Tests Organization onboarding, lifecycle management, suspension, and updates.
    """
    def setUp(self):
        self.client = Client()
        self.superadmin = User.objects.create_superuser(
            username='platform_super',
            email='super@platform.internal',
            password='secretpassword123'
        )
        self.superadmin.role = 'SUPER_ADMIN'
        self.superadmin.save()
        self.client.login(username='platform_super', password='secretpassword123')

        self.plan = SubscriptionPlan.objects.create(
            name='Professional',
            code='PROFESSIONAL',
            price_per_year=499.00,
            max_students=1200,
            max_staff=100
        )

    def test_create_organization_atomic(self):
        """Creating an organization provisions Org, Admin User, Subscription, and linked School atomically."""
        post_data = {
            'name': 'Pokhara Valley School',
            'org_type': 'SCHOOL',
            'short_name': 'PVS',
            'address': 'Lakeside Ward 6',
            'municipality': 'Pokhara Metropolitan',
            'district': 'Kaski',
            'province': 'Gandaki',
            'country': 'Nepal',
            'phone': '+977-61-520000',
            'email': 'info@pvs.edu.np',
            'website': 'https://pvs.edu.np',
            'admin_name': 'Bikash Gurung',
            'admin_username': 'admin_pvs',
            'admin_email': 'admin@pvs.edu.np',
            'admin_phone': '+977-9800000001',
            'admin_password': 'securepassword123',
            'plan': self.plan.id,
            'sub_status': 'ACTIVE',
            'start_date': date.today().isoformat(),
            'expiry_date': (date.today() + timedelta(days=365)).isoformat(),
        }

        response = self.client.post(reverse('platform_admin:organization_create'), post_data)
        self.assertEqual(response.status_code, 302)

        # Verify Org was created
        org = Organization.objects.filter(name='Pokhara Valley School').first()
        self.assertIsNotNone(org)
        self.assertTrue(org.org_id.startswith('ORG-'))
        self.assertEqual(org.status, 'ACTIVE')

        # Verify Primary Admin user
        admin = User.objects.filter(username='admin_pvs').first()
        self.assertIsNotNone(admin)
        self.assertEqual(admin.role, 'ADMIN')
        self.assertEqual(admin.organization, org)
        self.assertEqual(org.primary_admin, admin)

        # Verify linked School instance
        self.assertIsNotNone(org.school)
        self.assertEqual(org.school.name, 'Pokhara Valley School')

        # Verify Subscription
        sub = OrganizationSubscription.objects.filter(organization=org).first()
        self.assertIsNotNone(sub)
        self.assertEqual(sub.plan, self.plan)
        self.assertEqual(sub.status, 'ACTIVE')

        # Verify Audit Log entry
        log_entry = PlatformAuditLog.objects.filter(action='ORG_CREATED', organization=org).first()
        self.assertIsNotNone(log_entry)

    def test_organization_detail_and_edit(self):
        """Verifies organization detail page and editing organization fields."""
        org = Organization.objects.create(
            name='Test Academy',
            org_type='COLLEGE',
            short_name='TAC'
        )
        OrganizationSubscription.objects.create(
            organization=org,
            plan=self.plan,
            start_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            status='ACTIVE'
        )

        # Detail view
        response = self.client.get(reverse('platform_admin:organization_detail', args=[org.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Academy')

        # Edit view POST
        edit_data = {
            'name': 'Test Academy Updated',
            'org_type': 'COLLEGE',
            'short_name': 'TAC-U',
            'address': 'New Campus Road',
            'municipality': 'Lalitpur',
            'district': 'Lalitpur',
            'province': 'Bagmati',
            'country': 'Nepal',
            'phone': '01-5555555',
            'email': 'contact@tac.edu.np',
            'website': 'https://tac.edu.np',
        }
        response = self.client.post(reverse('platform_admin:organization_edit', args=[org.pk]), edit_data)
        self.assertEqual(response.status_code, 302)

        org.refresh_from_db()
        self.assertEqual(org.name, 'Test Academy Updated')
        self.assertEqual(org.short_name, 'TAC-U')

    def test_organization_suspend_and_reactivate(self):
        """Tests zero-deletion reversible suspension and reactivation."""
        org = Organization.objects.create(
            name='Biratnagar Model School',
            org_type='SCHOOL',
            status='ACTIVE'
        )
        sub = OrganizationSubscription.objects.create(
            organization=org,
            plan=self.plan,
            start_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            status='ACTIVE'
        )

        # Suspend
        response = self.client.post(reverse('platform_admin:organization_suspend', args=[org.pk]), {
            'reason': 'Payment renewal overdue'
        })
        self.assertEqual(response.status_code, 302)

        org.refresh_from_db()
        sub.refresh_from_db()
        self.assertEqual(org.status, 'SUSPENDED')
        self.assertEqual(sub.status, 'SUSPENDED')
        self.assertIn('Payment renewal overdue', sub.notes)

        # Verify audit log recorded
        self.assertTrue(PlatformAuditLog.objects.filter(action='ORG_SUSPENDED', organization=org).exists())

        # Reactivate
        response = self.client.post(reverse('platform_admin:organization_activate', args=[org.pk]))
        self.assertEqual(response.status_code, 302)

        org.refresh_from_db()
        sub.refresh_from_db()
        self.assertEqual(org.status, 'ACTIVE')
        self.assertEqual(sub.status, 'ACTIVE')
        self.assertTrue(PlatformAuditLog.objects.filter(action='ORG_ACTIVATED', organization=org).exists())

    def test_organizations_list_renders_cleanly(self):
        """Tests that /platform-admin/organizations/ renders without template syntax errors for both active and expired orgs."""
        # Create active org
        org_active = Organization.objects.create(name='Active Academy', org_type='SCHOOL', status='ACTIVE')
        OrganizationSubscription.objects.create(
            organization=org_active,
            plan=self.plan,
            start_date=date.today(),
            expiry_date=date.today() + timedelta(days=90),
            status='ACTIVE'
        )
        # Create expired org
        org_expired = Organization.objects.create(name='Expired Academy', org_type='SCHOOL', status='EXPIRED')
        OrganizationSubscription.objects.create(
            organization=org_expired,
            plan=self.plan,
            start_date=date.today() - timedelta(days=400),
            expiry_date=date.today() - timedelta(days=35),
            status='EXPIRED'
        )

        response = self.client.get(reverse('platform_admin:organizations_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Active Academy')
        self.assertContains(response, 'Expired Academy')
        self.assertContains(response, '35d ago')
        self.assertContains(response, '90 days left')


class PlatformAdminSubscriptionAndSupportTests(TestCase):
    """
    Tests subscription plan management, expiration buckets, and support inspection sessions.
    """
    def setUp(self):
        self.client = Client()
        self.superadmin = User.objects.create_superuser(
            username='platform_super',
            email='super@platform.internal',
            password='secretpassword123'
        )
        self.superadmin.role = 'SUPER_ADMIN'
        self.superadmin.save()
        self.client.login(username='platform_super', password='secretpassword123')

        self.plan1 = SubscriptionPlan.objects.create(
            name='Starter',
            code='STARTER',
            price_per_year=99.00,
            max_students=200,
            max_staff=20
        )
        self.plan2 = SubscriptionPlan.objects.create(
            name='Enterprise',
            code='ENTERPRISE',
            price_per_year=999.00,
            max_students=5000,
            max_staff=500
        )

        self.org = Organization.objects.create(
            name='Alpine International College',
            org_type='COLLEGE',
            status='ACTIVE'
        )
        self.sub = OrganizationSubscription.objects.create(
            organization=self.org,
            plan=self.plan1,
            start_date=date.today(),
            expiry_date=date.today() + timedelta(days=30),
            status='ACTIVE'
        )

    def test_update_subscription_plan(self):
        """Super Admin can change plan tier and extend expiry date."""
        new_expiry = date.today() + timedelta(days=365)
        response = self.client.post(reverse('platform_admin:organization_subscription', args=[self.org.pk]), {
            'plan': self.plan2.id,
            'status': 'ACTIVE',
            'expiry_date': new_expiry.isoformat(),
            'notes': 'Upgraded to Enterprise tier via wire transfer.'
        })
        self.assertEqual(response.status_code, 302)

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, self.plan2)
        self.assertEqual(self.sub.expiry_date, new_expiry)
        self.assertIn('Upgraded to Enterprise', self.sub.notes)

    def test_subscription_expiration_buckets(self):
        """Verifies filtering by expiration bucket."""
        # Sub expires in 30 days
        response = self.client.get(reverse('platform_admin:subscriptions_list') + '?bucket=in_30_days')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpine International College')

    def test_support_mode_lifecycle(self):
        """Entering and exiting Support Mode creates sessions and audit records."""
        # Enter support mode
        response = self.client.get(reverse('platform_admin:support_enter', args=[self.org.pk]))
        self.assertEqual(response.status_code, 302)

        session = SupportSession.objects.filter(super_admin=self.superadmin, organization=self.org, is_active=True).first()
        self.assertIsNotNone(session)
        self.assertTrue(PlatformAuditLog.objects.filter(action='SUPPORT_MODE_ENTERED', organization=self.org).exists())

        # Inspect view
        response = self.client.get(reverse('platform_admin:support_inspection', args=[self.org.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SUPPORT MODE ACTIVE')

        # Exit support mode
        response = self.client.get(reverse('platform_admin:support_exit'))
        self.assertEqual(response.status_code, 302)

        session.refresh_from_db()
        self.assertFalse(session.is_active)
        self.assertIsNotNone(session.ended_at)
        self.assertTrue(PlatformAuditLog.objects.filter(action='SUPPORT_MODE_EXITED', organization=self.org).exists())

    def test_user_management_and_password_reset(self):
        """Super Admin can create org admins, toggle user status, and reset passwords."""
        # Create org admin
        response = self.client.post(reverse('platform_admin:admin_create'), {
            'organization': self.org.id,
            'name': 'Sunita Rai',
            'username': 'admin_sunita',
            'email': 'sunita@alpine.edu.np',
            'phone': '9812345678',
            'password': 'initialpassword123'
        })
        self.assertEqual(response.status_code, 302)

        user = User.objects.filter(username='admin_sunita').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.organization, self.org)
        self.assertEqual(user.role, 'ADMIN')

        # Toggle status
        self.assertTrue(user.is_active)
        self.client.post(reverse('platform_admin:user_toggle_status', args=[user.pk]))
        user.refresh_from_db()
        self.assertFalse(user.is_active)

        # Reset password
        self.client.post(reverse('platform_admin:user_reset_password', args=[user.pk]), {
            'new_password': 'newpassword999',
            'confirm_password': 'newpassword999'
        })
        user.refresh_from_db()
        self.assertTrue(user.check_password('newpassword999'))

    def test_global_search(self):
        """Global search finds organizations and users."""
        response = self.client.get(reverse('platform_admin:global_search') + '?q=Alpine')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpine International College')


class PlatformAdminSuspensionEnforcementTests(TestCase):
    """
    Tests real-time enforcement of organization suspension across web and API portals:
    - Suspended org users cannot log in.
    - Active sessions for suspended orgs are intercepted and terminated by middleware.
    - Suspended org mobile API requests are rejected with HTTP 403.
    - Reactivation immediately restores access without any data loss.
    - Super Admins are never blocked.
    """
    def setUp(self):
        self.client = Client()

        self.plan = SubscriptionPlan.objects.create(
            name='Standard',
            code='STANDARD',
            price_per_year=299.00,
            max_students=1000,
            max_staff=50
        )

        self.org = Organization.objects.create(
            name='Janata Secondary School',
            org_type='SCHOOL',
            status='ACTIVE'
        )
        self.sub = OrganizationSubscription.objects.create(
            organization=self.org,
            plan=self.plan,
            start_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            status='ACTIVE'
        )

        self.admin_user = User.objects.create_user(
            username='janata_admin',
            email='admin@janata.edu.np',
            password='janatapassword123',
            role='ADMIN',
            organization=self.org
        )

        self.teacher_user = User.objects.create_user(
            username='janata_teacher',
            email='teacher@janata.edu.np',
            password='teacherpassword123',
            role='TEACHER',
            organization=self.org
        )

    def test_suspended_org_web_login_blocked(self):
        """Admin of suspended org cannot log in via /login/."""
        self.org.status = 'SUSPENDED'
        self.org.save()

        response = self.client.post(reverse('admin_login'), {
            'username': 'janata_admin',
            'password': 'janatapassword123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "suspended")

        # Verify user is NOT authenticated in session
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_suspended_org_active_session_intercepted_by_middleware(self):
        """Active session of suspended org is immediately terminated by middleware on next request."""
        # 1. Log in while ACTIVE
        login_resp = self.client.post(reverse('admin_login'), {
            'username': 'janata_admin',
            'password': 'janatapassword123'
        })
        self.assertEqual(login_resp.status_code, 302)

        # Confirm admin can access dashboard
        dash_resp = self.client.get(reverse('dashboard'))
        self.assertEqual(dash_resp.status_code, 200)

        # 2. Super Admin suspends the organization
        self.org.status = 'SUSPENDED'
        self.org.save()

        # 3. Next request by admin is intercepted by OrganizationSuspensionMiddleware
        blocked_resp = self.client.get(reverse('dashboard'))
        self.assertEqual(blocked_resp.status_code, 302)
        self.assertIn(reverse('admin_login'), blocked_resp.url)

        # Following redirect shows the suspension error message
        follow_resp = self.client.get(blocked_resp.url)
        self.assertContains(follow_resp, "suspended")

    def test_suspended_org_api_login_blocked(self):
        """API authentication for teacher of suspended org returns 403 Forbidden."""
        self.org.status = 'SUSPENDED'
        self.org.save()

        response = self.client.post(reverse('api_login'), {
            'username': 'janata_teacher',
            'password': 'teacherpassword123'
        }, content_type='application/json')

        self.assertEqual(response.status_code, 403)
        self.assertIn('organization_suspended', response.json().get('error', ''))

    def test_reactivation_restores_access(self):
        """Reactivating a suspended organization immediately restores full access."""
        self.org.status = 'SUSPENDED'
        self.org.save()

        # Blocked while suspended
        resp_blocked = self.client.post(reverse('admin_login'), {
            'username': 'janata_admin',
            'password': 'janatapassword123'
        })
        self.assertContains(resp_blocked, "suspended")

        # Reactivate
        self.org.status = 'ACTIVE'
        self.org.save()

        # Allowed immediately
        resp_allowed = self.client.post(reverse('admin_login'), {
            'username': 'janata_admin',
            'password': 'janatapassword123'
        })
        self.assertEqual(resp_allowed.status_code, 302)
        self.assertIn(reverse('dashboard'), resp_allowed.url)

        dash_resp = self.client.get(reverse('dashboard'))
        self.assertEqual(dash_resp.status_code, 200)


class PlatformAdminMobileAppAndAuditRestrictionTests(TestCase):
    """
    Tests mobile app configuration management via Super Admin PlatformSetting,
    and strict isolation of System Audit logs exclusively to Super Admin.
    """
    def setUp(self):
        self.client = Client()

        self.superadmin = User.objects.create_superuser(
            username='platform_super',
            email='super@platform.internal',
            password='secretpassword123'
        )
        self.superadmin.role = 'SUPER_ADMIN'
        self.superadmin.save()

        self.school_admin = User.objects.create_user(
            username='school_admin',
            email='admin@school.internal',
            password='adminpassword123',
            role='ADMIN'
        )

        self.setting = PlatformSetting.get_instance()
        self.setting.app_name = 'Custom School Mobile Portal'
        self.setting.app_version = '2.4.1'
        self.setting.app_description = 'Custom mobile app for teacher evaluations and student verification.'
        self.setting.app_designer_name = 'Enterprise ID Solutions'
        self.setting.app_designer_role = 'Lead App Architect'
        self.setting.app_contact_phone = '+977-9811223344'
        self.setting.app_contact_email = 'mobile-support@enterpriseid.com'
        self.setting.app_website = 'https://enterpriseid.com'
        self.setting.app_copyright_text = '2026-2027 Enterprise ID'
        self.setting.save()

    def test_api_app_config_reflects_platform_settings(self):
        """The /api/app-config/ endpoint dynamically returns Super Admin PlatformSetting values."""
        response = self.client.get(reverse('api_app_config'))
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['app_name'], 'Custom School Mobile Portal')
        self.assertEqual(data['version'], '2.4.1')
        self.assertEqual(data['description'], 'Custom mobile app for teacher evaluations and student verification.')
        self.assertEqual(data['designer_name'], 'Enterprise ID Solutions')
        self.assertEqual(data['designer_role'], 'Lead App Architect')
        self.assertEqual(data['contact_phone'], '+977-9811223344')
        self.assertEqual(data['contact_email'], 'mobile-support@enterpriseid.com')
        self.assertEqual(data['website'], 'https://enterpriseid.com')
        self.assertEqual(data['copyright_year'], '2026-2027 Enterprise ID')

    def test_super_admin_updates_mobile_app_settings(self):
        """Super Admin can update mobile app metadata from /platform-admin/settings/."""
        self.client.login(username='platform_super', password='secretpassword123')

        post_data = {
            'platform_name': 'Global ID SaaS',
            'support_email': 'ops@globalsas.com',
            'support_phone': '+1-800-PLATFORM',
            'default_trial_days': '45',
            'default_subscription_months': '24',
            'app_name': 'Updated Mobile App Name',
            'app_version': '3.0.0',
            'app_description': 'Newly released mobile version.',
            'app_designer_name': 'New Design Lead',
            'app_designer_role': 'Product Manager',
            'app_contact_phone': '+977-9899887766',
            'app_contact_email': 'app@updated.com',
            'app_website': 'https://updated.com',
            'app_copyright_text': '2027',
        }

        response = self.client.post(reverse('platform_admin:settings'), post_data)
        self.assertEqual(response.status_code, 302)

        self.setting.refresh_from_db()
        self.assertEqual(self.setting.app_name, 'Updated Mobile App Name')
        self.assertEqual(self.setting.app_version, '3.0.0')
        self.assertEqual(self.setting.app_website, 'https://updated.com')

        # Verify API returns the newly saved values
        api_resp = self.client.get(reverse('api_app_config'))
        self.assertEqual(api_resp.json()['app_name'], 'Updated Mobile App Name')
        self.assertEqual(api_resp.json()['version'], '3.0.0')

    def test_school_site_system_audit_forbidden_for_school_admin(self):
        """Normal school admin attempting to access /audit-logs/ receives HTTP 403 Forbidden."""
        self.client.login(username='school_admin', password='adminpassword123')
        response = self.client.get(reverse('audit_logs'))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "strictly restricted to Platform Super Administrators", status_code=403)

    def test_superadmin_accesses_platform_audit_logs(self):
        """Super Admin has full access to the dedicated platform audit logs console."""
        self.client.login(username='platform_super', password='secretpassword123')
        response = self.client.get(reverse('platform_admin:audit_logs'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Platform Audit Trail")

    def test_super_admin_creates_plan_with_clients_limit(self):
        """Super Admin can create a new plan including client capacity limit."""
        self.client.login(username='platform_super', password='secretpassword123')
        post_data = {
            'name': 'Studio Enterprise Elite',
            'code': 'STUDIO_ELITE_TEST',
            'price_per_year': '599.00',
            'max_students': '3000',
            'max_staff': '250',
            'max_clients': '35',
            'description': 'Designed for high-throughput commercial photo studios.',
            'is_active': 'on'
        }
        resp = self.client.post(reverse('platform_admin:plan_create'), post_data)
        self.assertRedirects(resp, reverse('platform_admin:plans_list'))

        plan = SubscriptionPlan.objects.get(code='STUDIO_ELITE_TEST')
        self.assertEqual(plan.name, 'Studio Enterprise Elite')
        self.assertEqual(plan.max_clients, 35)
        self.assertEqual(plan.max_students, 3000)
        self.assertEqual(float(plan.price_per_year), 599.00)
        self.assertTrue(plan.is_active)

    def test_super_admin_edits_subscription_plan(self):
        """Super Admin can edit existing plan parameters, capacity limits, and pricing."""
        self.client.login(username='platform_super', password='secretpassword123')
        plan = SubscriptionPlan.objects.create(
            name='Test Plan Original',
            code='TEST_ORIGINAL',
            price_per_year=199.00,
            max_students=500,
            max_staff=50,
            max_clients=1,
            is_active=True
        )

        edit_data = {
            'name': 'Test Plan Updated',
            'code': 'TEST_ORIGINAL',
            'price_per_year': '249.50',
            'max_students': '750',
            'max_staff': '75',
            'max_clients': '10',
            'description': 'Updated plan specs for growing institutions.',
            'is_active': 'on'
        }
        resp = self.client.post(reverse('platform_admin:plan_edit', args=[plan.id]), edit_data)
        self.assertRedirects(resp, reverse('platform_admin:plans_list'))

        plan.refresh_from_db()
        self.assertEqual(plan.name, 'Test Plan Updated')
        self.assertEqual(plan.max_clients, 10)
        self.assertEqual(plan.max_students, 750)
        self.assertEqual(float(plan.price_per_year), 249.50)

    def test_super_admin_toggles_plan_status(self):
        """Super Admin can toggle a plan between active and inactive."""
        self.client.login(username='platform_super', password='secretpassword123')
        plan = SubscriptionPlan.objects.create(
            name='Toggle Test Plan',
            code='TOGGLE_PLAN',
            price_per_year=99.00,
            is_active=True
        )

        # Deactivate
        resp = self.client.post(reverse('platform_admin:plan_toggle_status', args=[plan.id]))
        self.assertRedirects(resp, reverse('platform_admin:plans_list'))
        plan.refresh_from_db()
        self.assertFalse(plan.is_active)

        # Re-activate
        resp = self.client.post(reverse('platform_admin:plan_toggle_status', args=[plan.id]))
        self.assertRedirects(resp, reverse('platform_admin:plans_list'))
        plan.refresh_from_db()
        self.assertTrue(plan.is_active)

    def test_delete_plan_without_subscribers_succeeds(self):
        """Plan with 0 subscribers can be permanently deleted."""
        self.client.login(username='platform_super', password='secretpassword123')
        plan = SubscriptionPlan.objects.create(
            name='Zero Sub Plan',
            code='ZERO_SUB_PLAN',
            price_per_year=50.00
        )
        resp = self.client.post(reverse('platform_admin:plan_delete', args=[plan.id]))
        self.assertRedirects(resp, reverse('platform_admin:plans_list'))
        self.assertFalse(SubscriptionPlan.objects.filter(id=plan.id).exists())

    def test_delete_plan_with_active_subscribers_blocked(self):
        """Plan currently assigned to organizations cannot be deleted."""
        self.client.login(username='platform_super', password='secretpassword123')
        plan = SubscriptionPlan.objects.create(
            name='Active Sub Plan',
            code='ACTIVE_SUB_PLAN',
            price_per_year=150.00
        )
        org = Organization.objects.create(name='Subscriber School', org_type='SCHOOL')
        OrganizationSubscription.objects.create(
            organization=org,
            plan=plan,
            start_date=date.today(),
            expiry_date=date.today() + timedelta(days=365)
        )

        resp = self.client.post(reverse('platform_admin:plan_delete', args=[plan.id]))
        self.assertRedirects(resp, reverse('platform_admin:plans_list'))
        self.assertTrue(SubscriptionPlan.objects.filter(id=plan.id).exists())


class StudioMultiClientArchitectureTests(TestCase):
    """
    Validates end-to-end multi-client architecture for Commercial Studios & Printing Presses:
    - is_studio detection for Studio, Printing Press, and Corporate accounts
    - Client registration, auto code generation (CLT-00001, CLT-00002)
    - Linked School instance creation & branding synchronization
    - Client workspace switching and session scoping
    - Student directory scoping by active client
    - Dashboard metrics scoping by active client
    - Plan client limit enforcement
    - PDF card generation using client institution's branding
    """
    def setUp(self):
        self.client = Client()
        # Create Studio Organization
        self.studio_plan = SubscriptionPlan.objects.create(
            name='Commercial Studio Pro',
            code='STUDIO_PRO',
            price_per_year=1499.00,
            max_clients=3,
            max_students=5000,
            max_staff=200
        )
        self.studio_org = Organization.objects.create(
            name='Everest Digital Press & Lab',
            short_name='Everest Lab',
            org_type='STUDIO_PRESS',
            email='contact@everestpress.com',
            phone='+977-9811223344',
            status='ACTIVE'
        )
        self.studio_sub = OrganizationSubscription.objects.create(
            organization=self.studio_org,
            plan=self.studio_plan,
            start_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            status='ACTIVE'
        )
        self.studio_user = User.objects.create_user(
            username='studio_manager',
            email='manager@everestpress.com',
            password='studiopassword123',
            role='ADMIN',
            organization=self.studio_org
        )

        # Standard School Organization
        self.school_plan = SubscriptionPlan.objects.create(
            name='Standard School',
            code='SCHOOL_BASIC',
            price_per_year=299.00,
            max_clients=1,
            max_students=500,
            max_staff=50
        )
        self.school_org = Organization.objects.create(
            name='Sunrise Secondary School',
            short_name='Sunrise',
            org_type='SCHOOL',
            status='ACTIVE'
        )
        self.school_sub = OrganizationSubscription.objects.create(
            organization=self.school_org,
            plan=self.school_plan,
            start_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            status='ACTIVE'
        )
        self.school_user = User.objects.create_user(
            username='school_admin',
            email='admin@sunriseschool.edu.np',
            password='schoolpassword123',
            role='ADMIN',
            organization=self.school_org
        )

    def test_is_studio_property(self):
        """is_studio is True for STUDIO_PRESS, COMPANY, CORPORATE_AGENCY, False for standard SCHOOL."""
        self.assertTrue(self.studio_org.is_studio)
        self.assertFalse(self.school_org.is_studio)

    def test_client_code_auto_generation(self):
        """OrganizationClient auto-generates sequential codes like CLT-00001, CLT-00002."""
        c1 = OrganizationClient.objects.create(
            organization=self.studio_org,
            name='Client School Alpha'
        )
        self.assertEqual(c1.client_code, 'CLT-00001')

        c2 = OrganizationClient.objects.create(
            organization=self.studio_org,
            name='Client School Beta'
        )
        self.assertEqual(c2.client_code, 'CLT-00002')

    def test_client_management_hub_accessible_by_studio_admin(self):
        """Studio admin can access client management hub and see capacity."""
        self.client.login(username='studio_manager', password='studiopassword123')
        response = self.client.get(reverse('client_management'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Client Organizations Hub")
        self.assertContains(response, "Everest Digital Press")

    def test_standard_school_redirected_from_client_management(self):
        """Standard school admin accessing /clients/ is redirected to dashboard with informational notice."""
        self.client.login(username='school_admin', password='schoolpassword123')
        response = self.client.get(reverse('client_management'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))

    def test_studio_registers_new_client_school(self):
        """Studio admin can register a client institution via POST /clients/create/."""
        self.client.login(username='studio_manager', password='studiopassword123')

        post_data = {
            'name': 'Mount View High School',
            'short_name': 'MVHS',
            'client_type': 'SCHOOL',
            'address': 'Ward 5, Pokhara',
            'municipality': 'Pokhara Metro',
            'district': 'Kaski',
            'province': 'Gandaki',
            'country': 'Nepal',
            'phone': '+977-61-123456',
            'email': 'info@mountview.edu.np',
            'website': 'https://mountview.edu.np',
            'signatory_name': 'Principal Shyam Gurung',
            'signatory_title': 'Principal',
        }
        response = self.client.post(reverse('client_create'), post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('client_management'))

        client = OrganizationClient.objects.get(name='Mount View High School')
        self.assertEqual(client.organization, self.studio_org)
        self.assertEqual(client.client_code, 'CLT-00001')
        self.assertIsNotNone(client.school)
        self.assertEqual(client.school.name, 'Mount View High School')
        self.assertEqual(client.school.head_teacher_name, 'Principal Shyam Gurung')

        # Verify active_client was automatically set in session
        self.assertEqual(self.client.session['active_client_id'], client.id)

    def test_studio_workspace_switching_and_scoping(self):
        """Switching active client scopes students directory and dashboard."""
        c1 = OrganizationClient.objects.create(organization=self.studio_org, name='School Alpha')
        c2 = OrganizationClient.objects.create(organization=self.studio_org, name='School Beta')

        from apps.academic.models import AcademicYear, ClassLevel, Section
        year = AcademicYear.objects.create(name='2081/82', start_date=date.today(), end_date=date.today() + timedelta(days=365), is_active=True)
        cls = ClassLevel.objects.create(name='Class 10')
        sec = Section.objects.create(name='A', class_level=cls)

        # Student in Alpha
        s1 = Student.objects.create(
            student_id='STU-A-001',
            roll_number=1,
            full_name='Alpha Student 1',
            class_level=cls,
            section=sec,
            academic_year=year,
            client=c1
        )
        # Student in Beta (distinct roll number 2 to respect class/sec uniqueness)
        s2 = Student.objects.create(
            student_id='STU-B-001',
            roll_number=2,
            full_name='Beta Student 1',
            class_level=cls,
            section=sec,
            academic_year=year,
            client=c2
        )

        self.client.login(username='studio_manager', password='studiopassword123')

        # 1. Switch to School Alpha
        resp_switch = self.client.get(reverse('switch_client', kwargs={'pk': c1.id}))
        self.assertEqual(resp_switch.status_code, 302)
        self.assertEqual(self.client.session['active_client_id'], c1.id)

        # 2. View students list -> only Alpha student visible
        resp_list = self.client.get(reverse('students_list'))
        self.assertContains(resp_list, 'Alpha Student 1')
        self.assertNotContains(resp_list, 'Beta Student 1')

        # 3. Switch to All Clients (pk=0) -> both visible
        self.client.get(reverse('switch_client', kwargs={'pk': 0}))
        self.assertNotIn('active_client_id', self.client.session)
        resp_all = self.client.get(reverse('students_list'))
        self.assertContains(resp_all, 'Alpha Student 1')
        self.assertContains(resp_all, 'Beta Student 1')

    def test_studio_unlimited_clients_allowed(self):
        """Studios and printing presses can register client organizations without artificial limits."""
        self.client.login(username='studio_manager', password='studiopassword123')

        # Create 3 clients
        for i in range(1, 4):
            OrganizationClient.objects.create(organization=self.studio_org, name=f'Client {i}')

        # Attempt to create 4th client - succeeds without being blocked by plan limit
        post_data = {'name': 'Client Organization 4'}
        response = self.client.post(reverse('client_create'), post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('client_management'))

        # Count must now be 4
        self.assertEqual(self.studio_org.clients.count(), 4)

    def test_effective_school_branding_resolution(self):
        """PDF generator correctly resolves student client school branding."""
        from apps.idcards.services.pdf_generator import get_effective_school

        # Set default singleton school name
        default_inst = School.get_instance()
        default_inst.name = "Apex Academy Main"
        default_inst.save()

        client_school = School.objects.create(name='Branded Client Academy', head_teacher_name='Principal Client')
        c = OrganizationClient.objects.create(organization=self.studio_org, name='Client Corp', school=client_school)

        from apps.academic.models import AcademicYear, ClassLevel, Section
        year = AcademicYear.objects.create(name='2082/83', start_date=date.today(), end_date=date.today() + timedelta(days=365))
        cls = ClassLevel.objects.create(name='Class 9')
        sec = Section.objects.create(name='B', class_level=cls)

        student_with_client = Student.objects.create(
            student_id='STU-CLT-99',
            roll_number=99,
            full_name='Branded Student',
            class_level=cls,
            section=sec,
            academic_year=year,
            client=c
        )

        student_without_client = Student.objects.create(
            student_id='STU-NOCLT-99',
            roll_number=100,
            full_name='Regular Student',
            class_level=cls,
            section=sec,
            academic_year=year
        )

        # For student_with_client, effective school is client_school
        eff_school = get_effective_school(student_with_client)
        self.assertEqual(eff_school.name, 'Branded Client Academy')

        # For student_without_client, effective school is default School instance
        default_school = get_effective_school(student_without_client)
        self.assertEqual(default_school.name, 'Apex Academy Main')
        self.assertNotEqual(default_school.name, 'Branded Client Academy')

    def test_client_confirm_delete_view_renders(self):
        """Studio admin can access the delete confirmation page showing student and card counts."""
        self.client.force_login(self.studio_user)
        client = OrganizationClient.objects.create(organization=self.studio_org, name='Delete Target School')

        from apps.academic.models import AcademicYear, ClassLevel, Section
        year = AcademicYear.objects.create(name='2082/83-Del', start_date=date.today(), end_date=date.today() + timedelta(days=365))
        cls = ClassLevel.objects.create(name='Class Del')
        sec = Section.objects.create(name='A', class_level=cls)
        Student.objects.create(
            student_id='STU-DEL-01',
            roll_number=1,
            full_name='Student To Delete',
            class_level=cls,
            section=sec,
            academic_year=year,
            client=client
        )

        resp = self.client.get(f'/clients/{client.id}/delete/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Delete Target School')
        self.assertContains(resp, '1')  # 1 enrolled student

    def test_client_delete_executes_cascading_cleanup(self):
        """POST to client delete removes client, students, and clears active session workspace."""
        self.client.force_login(self.studio_user)
        School.get_instance()
        client_school = School.objects.create(name='Delete Me School Profile')
        client = OrganizationClient.objects.create(
            organization=self.studio_org,
            name='Delete Me School',
            school=client_school
        )

        from apps.academic.models import AcademicYear, ClassLevel, Section
        year = AcademicYear.objects.create(name='2082/83-Del2', start_date=date.today(), end_date=date.today() + timedelta(days=365))
        cls = ClassLevel.objects.create(name='Class Del2')
        sec = Section.objects.create(name='A', class_level=cls)
        stu = Student.objects.create(
            student_id='STU-DEL-02',
            roll_number=2,
            full_name='Student To Delete 2',
            class_level=cls,
            section=sec,
            academic_year=year,
            client=client
        )

        # Set as active client in session
        session = self.client.session
        session['active_client_id'] = client.id
        session.save()

        # Perform POST delete
        resp = self.client.post(f'/clients/{client.id}/delete/')
        self.assertRedirects(resp, '/clients/')

        # Verify client deleted
        self.assertFalse(OrganizationClient.objects.filter(id=client.id).exists())
        # Verify student deleted
        self.assertFalse(Student.objects.filter(id=stu.id).exists())
        # Verify school record deleted
        self.assertFalse(School.objects.filter(id=client_school.id).exists())
        # Verify active_client_id cleared from session
        self.assertIsNone(self.client.session.get('active_client_id'))

    def test_cross_org_client_delete_rejected(self):
        """Studio admin cannot delete a client belonging to another studio organization."""
        other_studio = Organization.objects.create(name='Other Studio', org_type='STUDIO_PRESS')
        other_client = OrganizationClient.objects.create(organization=other_studio, name='Rival Client')

        self.client.force_login(self.studio_user)
        resp = self.client.get(f'/clients/{other_client.id}/delete/')
        self.assertEqual(resp.status_code, 404)


class PlatformNotificationAndLeadInquiryTests(TestCase):
    """
    Tests for Super Admin Notification System & Lead Management:
    - Landing page Demo Requests and Package Orders create PlatformNotification records.
    - Super Admin dashboard displays unread badge, incoming inquiries, and quick actions.
    - Expiring subscriptions auto-trigger alerts.
    - Notification management: filtering, mark as read, workflow status updates.
    - Security: Non-superadmins are restricted.
    """
    def setUp(self):
        self.client = Client()
        self.superadmin = User.objects.create_superuser(
            username='super_notify_admin',
            email='super@notify.io',
            password='Password123!',
            role='SUPER_ADMIN'
        )

        self.teacher = User.objects.create_user(
            username='regular_teacher_notify',
            email='teacher@school.edu.np',
            password='Password123!',
            role='TEACHER'
        )

        self.plan = SubscriptionPlan.objects.create(
            name='Photo Studio Pro',
            code='STUDIO_PRO',
            price_per_year=15000.00,
            max_clients=10,
            max_students=5000,
            max_staff=20
        )

    def test_landing_page_demo_request_creates_notification(self):
        """Visitor submitting the landing page demo form creates a DEMO_REQUEST PlatformNotification."""
        response = self.client.post(reverse('landing_page'), {
            'name': 'Bikash Shrestha',
            'email': 'bikash@mountview.edu.np',
            'phone': '9841234567',
            'org_name': 'Mount View Academy',
            'org_type': 'SCHOOL',
            'plan_code': '',
            'message': 'We have 850 students and need cards printed by next month.'
        })
        self.assertEqual(response.status_code, 302)

        notif = PlatformNotification.objects.filter(sender_name='Bikash Shrestha').first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.notification_type, 'DEMO_REQUEST')
        self.assertEqual(notif.organization_name, 'Mount View Academy')
        self.assertEqual(notif.sender_phone, '9841234567')
        self.assertEqual(notif.sender_email, 'bikash@mountview.edu.np')
        self.assertFalse(notif.is_read)
        self.assertEqual(notif.status, 'PENDING')
        self.assertIn('850 students', notif.notes)

    def test_landing_page_package_order_creates_notification(self):
        """Visitor selecting a subscription package on the landing page creates a PACKAGE_ORDER PlatformNotification."""
        response = self.client.post(reverse('landing_page'), {
            'inquiry_type': 'PACKAGE_ORDER',
            'name': 'Suman Gurung',
            'email': 'suman@evereststudio.com.np',
            'phone': '9801987654',
            'org_name': 'Everest Photo Press',
            'org_type': 'STUDIO_PRESS',
            'plan_code': 'STUDIO_PRO',
            'message': 'Looking to manage 5 school clients with batch card export.'
        })
        self.assertEqual(response.status_code, 302)

        notif = PlatformNotification.objects.filter(sender_name='Suman Gurung').first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.notification_type, 'PACKAGE_ORDER')
        self.assertEqual(notif.plan_code, 'STUDIO_PRO')
        self.assertEqual(notif.plan_name, 'Photo Studio Pro')
        self.assertEqual(notif.priority, 'HIGH')
        self.assertFalse(notif.is_read)
        self.assertEqual(notif.status, 'PENDING')

    def test_demo_request_with_plan_selected_remains_demo_request(self):
        """If prospect selects an interested plan in the demo modal, it remains a DEMO_REQUEST."""
        response = self.client.post(reverse('landing_page'), {
            'inquiry_type': 'DEMO_REQUEST',
            'name': 'Ramesh Karki',
            'email': 'ramesh@school.np',
            'phone': '9812345678',
            'org_name': 'Greenwood School',
            'org_type': 'SCHOOL',
            'plan_code': 'STUDIO_PRO',
            'message': 'Curious about this tier.'
        })
        self.assertEqual(response.status_code, 302)

        notif = PlatformNotification.objects.filter(sender_name='Ramesh Karki').first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.notification_type, 'DEMO_REQUEST')
        self.assertIn('Interested in Plan: Photo Studio Pro', notif.message)

    def test_dashboard_displays_recent_inquiries_and_badge(self):
        """Dashboard renders incoming demo requests and package orders with contact details."""
        # Create an inquiry
        PlatformNotification.objects.create(
            notification_type='PACKAGE_ORDER',
            priority='HIGH',
            title='New Package Order: Photo Studio Pro by Suman Gurung',
            message='Inquiry for Photo Studio Pro',
            sender_name='Suman Gurung',
            sender_phone='9801987654',
            sender_email='suman@evereststudio.com.np',
            organization_name='Everest Photo Press',
            plan_name='Photo Studio Pro',
            plan_code='STUDIO_PRO',
            status='PENDING'
        )

        self.client.force_login(self.superadmin)
        response = self.client.get(reverse('platform_admin:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Incoming Demo Requests & Package Orders')
        self.assertContains(response, 'Suman Gurung')
        self.assertContains(response, 'Everest Photo Press')
        self.assertContains(response, '9801987654')
        self.assertContains(response, 'Photo Studio Pro')

    def test_organization_creation_triggers_notification(self):
        """Creating an organization in the platform admin triggers a NEW_ORGANIZATION notification."""
        self.client.force_login(self.superadmin)
        response = self.client.post(reverse('platform_admin:organization_create'), {
            'name': 'Himalayan High School',
            'org_type': 'SCHOOL',
            'admin_name': 'Anil Sharma',
            'admin_username': 'anil_admin',
            'admin_email': 'anil@himalayan.edu.np',
            'admin_password': 'AdminPassword123!',
            'plan': self.plan.id,
            'sub_status': 'ACTIVE',
        })
        self.assertEqual(response.status_code, 302)

        notif = PlatformNotification.objects.filter(
            notification_type='NEW_ORGANIZATION',
            organization_name='Himalayan High School'
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn('Himalayan High School', notif.title)
        self.assertEqual(notif.status, 'RESOLVED')

    def test_expiring_subscription_generates_alert(self):
        """Expiring subscriptions (within 7 days) automatically generate SUBSCRIPTION_EXPIRING notifications."""
        org = Organization.objects.create(name='Patan College', org_type='COLLEGE')
        OrganizationSubscription.objects.create(
            organization=org,
            plan=self.plan,
            start_date=date.today() - timedelta(days=360),
            expiry_date=date.today() + timedelta(days=4),  # Expiring in 4 days
            status='ACTIVE'
        )

        self.client.force_login(self.superadmin)
        response = self.client.get(reverse('platform_admin:dashboard'))
        self.assertEqual(response.status_code, 200)

        notif = PlatformNotification.objects.filter(
            notification_type='SUBSCRIPTION_EXPIRING',
            organization_name='Patan College'
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn('Patan College', notif.title)
        self.assertEqual(notif.priority, 'HIGH')

    def test_notifications_list_view_and_filtering(self):
        """Notifications console supports filtering by type, status, and search."""
        n1 = PlatformNotification.objects.create(
            notification_type='DEMO_REQUEST',
            title='Demo Request 1',
            sender_name='Gopal KC',
            organization_name='Gopal Academy',
            status='PENDING'
        )
        n2 = PlatformNotification.objects.create(
            notification_type='PACKAGE_ORDER',
            title='Order 1',
            sender_name='Hari Silwal',
            organization_name='Hari Press',
            status='CONTACTED'
        )

        self.client.force_login(self.superadmin)
        url = reverse('platform_admin:notifications_list')

        # Filter by type DEMO_REQUEST
        resp = self.client.get(url, {'type': 'DEMO_REQUEST'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Gopal KC')
        self.assertNotContains(resp, 'Hari Silwal')

        # Filter by status CONTACTED
        resp = self.client.get(url, {'status': 'CONTACTED'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Hari Silwal')
        self.assertNotContains(resp, 'Gopal KC')

        # Search query
        resp = self.client.get(url, {'search': 'Gopal'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Gopal Academy')
        self.assertNotContains(resp, 'Hari Press')

    def test_mark_notification_read_and_mark_all_read(self):
        """Endpoints mark a single notification or all notifications as read."""
        n1 = PlatformNotification.objects.create(title='Unread 1', is_read=False)
        n2 = PlatformNotification.objects.create(title='Unread 2', is_read=False)

        self.client.force_login(self.superadmin)

        # Mark single
        resp = self.client.get(reverse('platform_admin:notification_mark_read', args=[n1.pk]))
        self.assertEqual(resp.status_code, 302)
        n1.refresh_from_db()
        self.assertTrue(n1.is_read)
        self.assertIsNotNone(n1.read_at)

        # Mark all
        resp = self.client.get(reverse('platform_admin:notifications_mark_all_read'))
        self.assertEqual(resp.status_code, 302)
        n2.refresh_from_db()
        self.assertTrue(n2.is_read)
        self.assertEqual(PlatformNotification.objects.filter(is_read=False).count(), 0)

    def test_notification_update_status_and_notes(self):
        """Updating lead status and follow-up notes updates workflow."""
        n = PlatformNotification.objects.create(
            title='Inquiry from ABC School',
            sender_name='ABC Contact',
            status='PENDING',
            notes=''
        )

        self.client.force_login(self.superadmin)
        resp = self.client.post(reverse('platform_admin:notification_update_status', args=[n.pk]), {
            'status': 'CONTACTED',
            'notes': 'Called customer, sending proposal email.'
        })
        self.assertEqual(resp.status_code, 302)

        n.refresh_from_db()
        self.assertEqual(n.status, 'CONTACTED')
        self.assertEqual(n.notes, 'Called customer, sending proposal email.')
        self.assertTrue(n.is_read)

    def test_notifications_access_security(self):
        """Regular teachers and unauthenticated users cannot access notifications."""
        url = reverse('platform_admin:notifications_list')

        # Unauthenticated redirects to login
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/platform-admin/login/', resp.url)

        # Regular teacher gets 403 Forbidden
        self.client.force_login(self.teacher)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)



