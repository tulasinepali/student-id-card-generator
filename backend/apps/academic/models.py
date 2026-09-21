from django.db import models
from django.core.exceptions import ValidationError


class AcademicYear(models.Model):
    organization = models.ForeignKey(
        'platform_admin.Organization',
        on_delete=models.CASCADE,
        related_name='academic_years',
        null=True,
        blank=True,
        help_text="Tenant organization this academic session belongs to"
    )
    name = models.CharField(max_length=50, help_text="e.g. 2026/27")
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False, help_text="Only one academic year should normally be active per organization")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']
        constraints = [
            models.UniqueConstraint(fields=['organization', 'name'], name='unique_academic_year_per_org')
        ]

    def clean(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("Start date cannot be later than end date.")

    def save(self, *args, **kwargs):
        self.clean()
        if self.is_active:
            # Ensure only one active academic year within the same organization
            if self.organization:
                AcademicYear.objects.filter(organization=self.organization, is_active=True).exclude(pk=self.pk).update(is_active=False)
            else:
                AcademicYear.objects.filter(organization__isnull=True, is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        status = " (Active)" if self.is_active else ""
        return f"{self.name}{status}"


class ClassLevel(models.Model):
    organization = models.ForeignKey(
        'platform_admin.Organization',
        on_delete=models.CASCADE,
        related_name='class_levels',
        null=True,
        blank=True,
        help_text="Tenant organization this class level belongs to"
    )
    name = models.CharField(max_length=100, help_text="e.g. Grade 1, Grade 8, Kindergarten")
    numeric_order = models.PositiveIntegerField(default=1, help_text="Used for sorting classes in logical order")

    class Meta:
        ordering = ['numeric_order', 'name']
        verbose_name = "Class"
        verbose_name_plural = "Classes"
        constraints = [
            models.UniqueConstraint(fields=['organization', 'name'], name='unique_class_level_per_org')
        ]

    def __str__(self):
        return self.name


class Section(models.Model):
    class_level = models.ForeignKey(ClassLevel, on_delete=models.CASCADE, related_name='sections')
    name = models.CharField(max_length=20, help_text="e.g. A, B, C, Lily, Rose")

    class Meta:
        ordering = ['class_level__numeric_order', 'name']
        unique_together = ('class_level', 'name')

    def __str__(self):
        return f"{self.class_level.name} - Section {self.name}"
