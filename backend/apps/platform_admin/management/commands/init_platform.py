import os
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.platform_admin.models import SubscriptionPlan, Organization, PlatformSetting
from apps.core.models import School

User = get_user_model()


class Command(BaseCommand):
    help = "Initializes default platform subscription plans, superadmin, and settings for production deployment."

    def handle(self, *args, **options):
        self.stdout.write("Initializing platform for deployment...")

        # 1. Default Subscription Plans in NPR
        plans_data = [
            {
                'name': 'Starter School Tier',
                'code': 'starter_school',
                'description': 'Ideal for primary and elementary schools managing up to 500 students.',
                'price_per_year': Decimal('15000.00'),
                'max_students': 500,
                'max_staff': 15,
                'max_clients': 1,
                'is_active': True,
            },
            {
                'name': 'Standard School Tier',
                'code': 'standard_school',
                'description': 'Designed for secondary and higher secondary schools with up to 1,500 students.',
                'price_per_year': Decimal('25000.00'),
                'max_students': 1500,
                'max_staff': 40,
                'max_clients': 1,
                'is_active': True,
            },
            {
                'name': 'Studio & Printing Press Pro',
                'code': 'studio_press_pro',
                'description': 'Multi-client workspace for photo studios managing up to 25 schools and 6,000 students.',
                'price_per_year': Decimal('45000.00'),
                'max_students': 6000,
                'max_staff': 60,
                'max_clients': 25,
                'is_active': True,
            },
            {
                'name': 'Commercial Press Unlimited Tier',
                'code': 'commercial_enterprise',
                'description': 'High-volume commercial printing presses with unlimited client schools and high-throughput batch printing.',
                'price_per_year': Decimal('85000.00'),
                'max_students': 25000,
                'max_staff': 150,
                'max_clients': 100,
                'is_active': True,
            },
        ]

        for p_data in plans_data:
            plan, created = SubscriptionPlan.objects.get_or_create(
                code=p_data['code'],
                defaults=p_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f" [OK] Created Plan: {plan.name} (NPR {plan.price_per_year})"))
            else:
                self.stdout.write(f" [EXISTS] Plan: {plan.name}")

        # 2. Default Platform Superadmin
        superadmin_user = os.getenv('SUPERADMIN_USERNAME', 'superadmin')
        superadmin_email = os.getenv('SUPERADMIN_EMAIL', 'admin@cardcraft.pro')
        superadmin_pass = os.getenv('SUPERADMIN_PASSWORD', 'Admin@123456')

        admin_user = User.objects.filter(username=superadmin_user).first()
        if not admin_user:
            admin_user = User.objects.create(
                username=superadmin_user,
                email=superadmin_email,
                role='SUPER_ADMIN',
                is_superuser=True,
                is_staff=True,
                organization=None
            )
            admin_user.set_password(superadmin_pass)
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f" [OK] Created Super Admin: '{superadmin_user}' (Password: '{superadmin_pass}')"))
        else:
            self.stdout.write(f" [EXISTS] Super Admin '{superadmin_user}' already exists.")

        # 3. Default Platform Setting
        PlatformSetting.get_instance()
        self.stdout.write(self.style.SUCCESS(" [OK] Platform settings initialized."))

        # 4. Ensure at least one demo organization exists for immediate evaluation
        if not Organization.objects.exists():
            school = School.get_instance()
            school.name = "Apex Model Academy"
            school.short_name = "AMA"
            school.save()

            org = Organization.objects.create(
                name="Apex Model Academy",
                short_name="AMA",
                org_type="SCHOOL",
                status="ACTIVE",
                school=school,
                uses_mobile_app=True
            )
            demo_admin = User.objects.create(
                username="admin",
                email="admin@apexschool.edu.np",
                role="ADMIN",
                is_superuser=False,
                is_staff=False,
                organization=org
            )
            demo_admin.set_password("Admin@123456")
            demo_admin.save()
            org.primary_admin = demo_admin
            org.save()
            self.stdout.write(self.style.SUCCESS(" [OK] Created default demo organization and admin: 'admin' (Password: 'Admin@123456')"))

        self.stdout.write(self.style.SUCCESS("\nPlatform initialization complete!"))
