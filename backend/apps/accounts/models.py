from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Administrator'),
        ('TEACHER', 'Class Teacher'),
        ('SUPER_ADMIN', 'Super Admin'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='ADMIN')
    phone = models.CharField(max_length=30, blank=True)
    organization = models.ForeignKey(
        'platform_admin.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text="The organization/institution this user belongs to"
    )

    def is_teacher(self):
        return self.role == 'TEACHER'

    def is_administrator(self):
        return self.role == 'ADMIN' or self.is_superuser

    def is_super_admin(self):
        return self.role == 'SUPER_ADMIN' or self.is_superuser


class TeacherProfile(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    client = models.ForeignKey(
        'platform_admin.OrganizationClient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='teachers',
        help_text="For studio/press accounts, the specific client school this teacher belongs to"
    )
    employee_id = models.CharField(max_length=50, unique=True)
    profile_photo = models.ImageField(upload_to='teachers/photos/', blank=True, null=True)
    assigned_class = models.ForeignKey(
        'academic.ClassLevel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_teachers'
    )
    assigned_section = models.ForeignKey(
        'academic.Section',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_teachers'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        assign_text = f"{self.assigned_class} - {self.assigned_section}" if self.assigned_class and self.assigned_section else "Unassigned"
        return f"{self.user.get_full_name() or self.user.username} ({self.employee_id}) [{assign_text}]"
