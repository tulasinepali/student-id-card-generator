from django.db import models
from django.conf import settings


class School(models.Model):
    name = models.CharField(max_length=255, default="Apex International Academy")
    short_name = models.CharField(max_length=50, default="AIA")
    address = models.CharField(max_length=255, blank=True, default="123 Education Lane")
    municipality = models.CharField(max_length=100, blank=True, default="Kathmandu Metropolitan")
    district = models.CharField(max_length=100, blank=True, default="Kathmandu")
    province = models.CharField(max_length=100, blank=True, default="Bagmati")
    country = models.CharField(max_length=100, default="Nepal")
    phone = models.CharField(max_length=50, blank=True, default="+977-1-4567890")
    email = models.EmailField(blank=True, default="info@apexschool.edu.np")
    website = models.URLField(blank=True, default="https://apexschool.edu.np")
    logo = models.ImageField(upload_to='school/logo/', blank=True, null=True)
    head_teacher_name = models.CharField(max_length=150, default="Dr. John Doe")
    head_teacher_signature = models.ImageField(upload_to='school/signatures/', blank=True, null=True)
    default_id_validity_days = models.PositiveIntegerField(default=365)
    default_qr_correction_level = models.CharField(
        max_length=2,
        choices=[('L', 'L - 7%'), ('M', 'M - 15%'), ('Q', 'Q - 25%'), ('H', 'H - 30%')],
        default='M'
    )
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def logo_url(self):
        if self.logo:
            try:
                return self.logo.url
            except ValueError:
                return ""
        return ""

    @property
    def signature_url(self):
        if self.head_teacher_signature:
            try:
                return self.head_teacher_signature.url
            except ValueError:
                return ""
        return ""

    @classmethod
    def get_instance(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    ACTION_CHOICES = (
        ('ADMIN_LOGIN', 'Admin Login'),
        ('TEACHER_LOGIN', 'Teacher Login'),
        ('STUDENT_CREATED', 'Student Created'),
        ('STUDENT_EDITED', 'Student Edited'),
        ('PHOTO_CHANGED', 'Student Photo Changed'),
        ('VERIFICATION_SUBMITTED', 'Verification Submitted'),
        ('STUDENT_APPROVED', 'Student Approved'),
        ('STUDENT_REJECTED', 'Student Rejected'),
        ('TEMPLATE_CHANGED', 'Template Changed'),
        ('PDF_GENERATED', 'PDF Generated'),
        ('ID_REVOKED', 'ID Card Revoked'),
        ('SIGNATURE_CHANGED', 'Principal Signature Changed'),
        ('TEACHER_ASSIGNMENT_CHANGED', 'Teacher Assignment Changed'),
        ('EXCEL_IMPORT', 'Excel Students Imported'),
        ('BULK_PHOTOS', 'Bulk Photos Processed'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=60, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        username = self.user.username if self.user else "System"
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {username} - {self.get_action_display()}"
