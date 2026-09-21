from django.db import models
from django.db.models import Q
from django.conf import settings
from apps.academic.models import ClassLevel, Section, AcademicYear


class Student(models.Model):
    GENDER_CHOICES = (
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
        ('OTHER', 'Other'),
    )

    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('TRANSFERRED', 'Transferred'),
        ('GRADUATED', 'Graduated'),
    )

    VERIFICATION_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('SUBMITTED', 'Submitted'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    )

    student_id = models.CharField(max_length=50, unique=True, db_index=True, help_text="Unique institutional Student ID")
    roll_number = models.PositiveIntegerField(help_text="Roll number within class/section")
    full_name = models.CharField(max_length=150)
    photo = models.ImageField(upload_to='students/photos/', blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='MALE')

    class_level = models.ForeignKey(ClassLevel, on_delete=models.PROTECT, related_name='students')
    section = models.ForeignKey(Section, on_delete=models.PROTECT, related_name='students')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name='students')

    address = models.TextField(blank=True)
    guardian_name = models.CharField(max_length=150, blank=True)
    guardian_phone = models.CharField(max_length=30, blank=True)
    blood_group = models.CharField(max_length=10, blank=True)
    emergency_contact = models.CharField(max_length=30, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    rejection_reason = models.TextField(blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_students'
    )

    # Multi-tenant isolation
    organization = models.ForeignKey(
        'platform_admin.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='students',
        help_text="Tenant organization this student record belongs to"
    )

    # Multi-client scoping for Photo Studio / Printing Press accounts
    client = models.ForeignKey(
        'platform_admin.OrganizationClient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
        help_text="Associated client school when managed by a Photo Studio / Printing Press account"
    )

    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_students'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['class_level__numeric_order', 'section__name', 'roll_number']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'roll_number', 'class_level', 'section', 'academic_year'],
                condition=Q(client__isnull=True),
                name='unique_roll_per_class_section_year_org'
            ),
            models.UniqueConstraint(
                fields=['organization', 'client', 'roll_number', 'class_level', 'section', 'academic_year'],
                condition=Q(client__isnull=False),
                name='unique_roll_per_class_section_year_client'
            ),
        ]

    def clean(self):
        super().clean()
        if self.section and self.class_level and self.section.class_level_id != self.class_level_id:
            self.class_level = self.section.class_level

    def save(self, *args, **kwargs):
        if getattr(self, 'client_id', None) and self.client and not getattr(self, 'organization_id', None):
            self.organization = self.client.organization
        if getattr(self, 'section_id', None) and self.section and self.class_level_id != self.section.class_level_id:
            self.class_level = self.section.class_level
        if not self.effective_uses_mobile_app and self.verification_status == 'PENDING':
            self.verification_status = 'VERIFIED'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.student_id})"

    @property
    def effective_uses_mobile_app(self):
        if getattr(self, 'client_id', None) and self.client:
            return getattr(self.client, 'uses_mobile_app', True)
        if getattr(self, 'organization_id', None) and self.organization:
            return getattr(self.organization, 'uses_mobile_app', True)
        return True

    @property
    def has_photo(self):
        return bool(self.photo and hasattr(self.photo, 'url'))

    @property
    def is_verified(self):
        if not self.effective_uses_mobile_app:
            return True
        return self.verification_status == 'VERIFIED'

    @property
    def is_print_eligible(self):
        return self.is_verified and self.has_photo and self.status == 'ACTIVE'

    @property
    def submitter_name(self):
        if self.submitted_by:
            return self.submitted_by.get_full_name() or self.submitted_by.username
        return "Class Teacher"


class VerificationRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='verification_history')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    previous_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    @property
    def actor_name(self):
        if self.actor:
            return self.actor.get_full_name() or self.actor.username
        return "System"

    def __str__(self):
        return f"{self.student.student_id}: {self.previous_status} -> {self.new_status} by {self.actor_name} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
