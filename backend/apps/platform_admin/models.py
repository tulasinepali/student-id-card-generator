from datetime import date
from django.db import models
from django.conf import settings
from django.utils import timezone


class Organization(models.Model):
    ORG_TYPE_CHOICES = (
        ('SCHOOL', 'School'),
        ('COLLEGE', 'College'),
        ('UNIVERSITY', 'University'),
        ('TRAINING_INSTITUTE', 'Training Institute'),
        ('COMPANY', 'Company / Corporate'),
        ('STUDIO_PRESS', 'Photo Studio / Printing Press'),
        ('CORPORATE_AGENCY', 'Corporate ID Agency'),
        ('NGO', 'NGO / Non-Profit'),
        ('OTHER', 'Other Institution'),
    )

    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('TRIAL', 'Trial'),
        ('SUSPENDED', 'Suspended'),
        ('EXPIRED', 'Expired'),
    )

    org_id = models.CharField(max_length=30, unique=True, db_index=True, editable=False, help_text="Immutable unique organization code (e.g. ORG-00001)")
    name = models.CharField(max_length=255, db_index=True)
    org_type = models.CharField(max_length=30, choices=ORG_TYPE_CHOICES, default='SCHOOL')
    short_name = models.CharField(max_length=50, blank=True)

    # Location & Contact
    address = models.CharField(max_length=255, blank=True)
    municipality = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default="Nepal")
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='organizations/logos/', blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE', db_index=True)

    # Primary administrator link
    primary_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_organizations'
    )

    # Optional linkage to existing institutional School record
    school = models.OneToOneField(
        'core.School',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='organization_profile'
    )

    uses_mobile_app = models.BooleanField(
        default=True,
        verbose_name="Uses Mobile App",
        help_text="Enable if this organization uses the mobile app for student photo capture and verification."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"

    def __str__(self):
        return f"{self.name} [{self.org_id}] ({self.get_status_display()})"

    @classmethod
    def generate_next_org_id(cls):
        """Generates sequential, immutable ORG-00001 format identifiers."""
        last_org = cls.objects.order_by('-id').first()
        if not last_org:
            return "ORG-00001"
        try:
            # Extract numeric portion from existing id or last record id
            last_num = int(last_org.org_id.replace('ORG-', ''))
            return f"ORG-{last_num + 1:05d}"
        except Exception:
            return f"ORG-{last_org.id + 1:05d}"

    def save(self, *args, **kwargs):
        if not self.org_id:
            self.org_id = self.generate_next_org_id()
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status == 'ACTIVE'

    @property
    def is_suspended(self):
        return self.status == 'SUSPENDED'

    @property
    def is_trial(self):
        return self.status == 'TRIAL'

    @property
    def is_studio(self):
        """Returns True if organization is a Photo Studio, Printing Press, or Corporate Agency with multi-client capabilities."""
        return self.org_type in ['STUDIO_PRESS', 'COMPANY', 'CORPORATE_AGENCY']

    @property
    def client_count(self):
        return self.clients.count()


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    max_clients = models.PositiveIntegerField(
        default=1,
        help_text="Maximum client schools/companies managed under this tier (1 for school, 5-50+ for studio/press)"
    )
    max_students = models.PositiveIntegerField(default=500, help_text="Maximum students allowed under this tier")
    max_staff = models.PositiveIntegerField(default=50, help_text="Maximum staff/teachers allowed under this tier")
    price_per_year = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['price_per_year', 'name']

    def __str__(self):
        return f"{self.name} (Max {self.max_students} students)"


class OrganizationSubscription(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('TRIAL', 'Trial'),
        ('SUSPENDED', 'Suspended'),
        ('EXPIRED', 'Expired'),
    )

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')
    start_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE', db_index=True)
    notes = models.TextField(blank=True, help_text="Internal super-admin notes, billing details, contract refs")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['expiry_date']

    def __str__(self):
        return f"{self.organization.name} - {self.plan.name} ({self.status}) until {self.expiry_date}"

    @property
    def is_expired(self):
        return date.today() > self.expiry_date or self.status == 'EXPIRED'

    @property
    def days_until_expiry(self):
        return (self.expiry_date - date.today()).days

    @property
    def days_remaining(self):
        days = (self.expiry_date - date.today()).days
        return max(0, days)

    @property
    def days_overdue(self):
        days = (date.today() - self.expiry_date).days
        return max(0, days)

    @property
    def expiry_bucket(self):
        """Categorizes into dashboard expiration buckets."""
        days = self.days_until_expiry
        if days < 0:
            return 'EXPIRED'
        elif days == 0:
            return 'TODAY'
        elif days <= 7:
            return 'IN_7_DAYS'
        elif days <= 30:
            return 'IN_30_DAYS'
        return 'HEALTHY'


class PlatformAuditLog(models.Model):
    ACTION_CHOICES = (
        ('ORG_CREATED', 'Organization Created'),
        ('ORG_UPDATED', 'Organization Updated'),
        ('ORG_SUSPENDED', 'Organization Suspended'),
        ('ORG_ACTIVATED', 'Organization Activated'),
        ('PLAN_CHANGED', 'Subscription Plan Changed'),
        ('SUBSCRIPTION_EXTENDED', 'Subscription Extended'),
        ('ADMIN_CREATED', 'Organization Admin Created'),
        ('ADMIN_PASSWORD_RESET', 'Admin Password Reset'),
        ('USER_STATUS_TOGGLED', 'User Status Changed'),
        ('SUPPORT_MODE_ENTERED', 'Support Mode Entered'),
        ('SUPPORT_MODE_EXITED', 'Support Mode Exited'),
        ('SETTINGS_UPDATED', 'Platform Settings Updated'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='platform_audit_events')
    action = models.CharField(max_length=60, choices=ACTION_CHOICES, db_index=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    target = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        username = self.user.username if self.user else "System"
        org_name = f" [{self.organization.name}]" if self.organization else ""
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {username} - {self.get_action_display()}{org_name}"

    @classmethod
    def log(cls, user, action, organization=None, target="", description="", request=None):
        """Helper to create standardized platform audit records."""
        ip = None
        if request:
            x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded:
                ip = x_forwarded.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')

        return cls.objects.create(
            user=user if user and user.is_authenticated else None,
            action=action,
            organization=organization,
            target=target,
            description=description,
            ip_address=ip
        )


class SupportSession(models.Model):
    super_admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_sessions')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='support_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        status = "Active" if self.is_active else "Closed"
        return f"Support Session: {self.super_admin.username} -> {self.organization.name} ({status})"

    def close(self):
        self.is_active = False
        self.ended_at = timezone.now()
        self.save()


class PlatformSetting(models.Model):
    # Platform / Web Settings
    platform_name = models.CharField(max_length=150, default="Antigravity ID Platform")
    platform_logo = models.ImageField(upload_to='platform/branding/', blank=True, null=True)
    support_email = models.EmailField(default="support@idplatform.io")
    support_phone = models.CharField(max_length=50, default="+1-800-ID-CARDS")
    default_trial_days = models.PositiveIntegerField(default=30)
    default_subscription_months = models.PositiveIntegerField(default=12)

    # Mobile Application & "About the App" Metadata Settings
    app_name = models.CharField(max_length=150, default="Apex ID - Teacher Portal", verbose_name="Mobile App Name")
    app_logo = models.ImageField(upload_to='platform/mobile_app/', blank=True, null=True, verbose_name="Mobile App Logo")
    app_version = models.CharField(max_length=50, default="1.0.0", verbose_name="Mobile App Version")
    app_description = models.TextField(
        default="An organization ID-card management and verification application.",
        blank=True,
        verbose_name="Mobile App Description"
    )
    app_designer_name = models.CharField(max_length=150, default="Apex Software Systems", blank=True, verbose_name="Developer / Designer Name")
    app_designer_role = models.CharField(max_length=150, default="Designer & Developer", blank=True, verbose_name="Developer Role")
    app_contact_phone = models.CharField(max_length=50, default="+977-9800000000", blank=True, verbose_name="Contact Phone")
    app_contact_email = models.EmailField(default="support@apexid.io", blank=True, verbose_name="Contact Email")
    app_website = models.URLField(default="https://apexid.io", blank=True, verbose_name="Official Website")
    app_copyright_text = models.CharField(max_length=150, default="2026", blank=True, verbose_name="Copyright Text / Year")

    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_instance(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

    def __str__(self):
        return self.platform_name


class OrganizationClient(models.Model):
    """
    Sub-tenant client institution managed by a Studio, Printing Press, or Corporate Subscriber.
    e.g. Studio 'Everest Digital Lab' manages Client 'Dhukurpani Secondary School'.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='clients')
    client_code = models.CharField(max_length=30, unique=True, editable=False, help_text="Unique client code (e.g. CLT-00001)")
    name = models.CharField(max_length=255, db_index=True)
    short_name = models.CharField(max_length=50, blank=True)
    client_type = models.CharField(max_length=30, choices=Organization.ORG_TYPE_CHOICES, default='SCHOOL')

    # Institutional branding for card output
    logo = models.ImageField(upload_to='clients/logos/', blank=True, null=True)
    authorized_signature = models.ImageField(upload_to='clients/signatures/', blank=True, null=True)
    signatory_name = models.CharField(max_length=150, blank=True, default="Principal")
    signatory_title = models.CharField(max_length=100, default="Principal")

    # Campus & Contact Coordinates
    address = models.CharField(max_length=255, blank=True)
    municipality = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default="Nepal")
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    # Linkage to dedicated School record for seamless card rendering & backward compatibility
    school = models.OneToOneField(
        'core.School',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_profile'
    )

    is_active = models.BooleanField(default=True)
    uses_mobile_app = models.BooleanField(
        default=True,
        verbose_name="Uses Mobile App",
        help_text="Enable if this client organization uses the mobile app for student photo capture and verification."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Organization Client"
        verbose_name_plural = "Organization Clients"

    def __str__(self):
        return f"{self.name} [{self.client_code}] ({self.organization.name})"

    @classmethod
    def generate_next_code(cls):
        last = cls.objects.order_by('-id').first()
        if not last:
            return "CLT-00001"
        try:
            num = int(last.client_code.replace('CLT-', ''))
            return f"CLT-{num + 1:05d}"
        except Exception:
            return f"CLT-{last.id + 1:05d}"

    def save(self, *args, **kwargs):
        if not self.client_code:
            self.client_code = self.generate_next_code()
        super().save(*args, **kwargs)

    @property
    def head_teacher_name(self):
        return self.signatory_name

    @property
    def head_teacher_signature(self):
        return self.authorized_signature

    @property
    def total_students(self):
        return self.students.count()

    @property
    def total_cards(self):
        from apps.idcards.models import IDCard
        return IDCard.objects.filter(student__client=self).count()
