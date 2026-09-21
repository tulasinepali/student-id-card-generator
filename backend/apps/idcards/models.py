import uuid
from datetime import date
from django.db import models
from django.conf import settings
from apps.students.models import Student
from apps.academic.models import AcademicYear


class IDCardTemplate(models.Model):
    CARD_TYPE_CHOICES = (
        ('STUDENT', 'Student ID'),
        ('TEACHER', 'Teacher ID'),
        ('STAFF', 'Staff ID'),
    )

    ORIENTATION_CHOICES = (
        ('PORTRAIT', 'Portrait (54 x 86 mm)'),
        ('LANDSCAPE', 'Landscape (86 x 54 mm)'),
    )

    DUPLEX_CHOICES = (
        ('FRONT_ONLY', 'Front Only'),
        ('BACK_ONLY', 'Back Only'),
        ('FRONT_BACK', 'Front & Back'),
    )

    DESIGN_MODE_CHOICES = (
        ('SCRATCH', 'Design From Scratch'),
        ('IMAGE_UPLOAD', 'Upload Existing Design'),
    )

    BG_FIT_CHOICES = (
        ('FILL', 'Fill (Exact dimensions)'),
        ('FIT', 'Fit (Maintain aspect ratio, letterbox)'),
        ('CROP', 'Crop (Maintain aspect ratio, center-crop)'),
    )

    name = models.CharField(max_length=100)
    card_type = models.CharField(max_length=20, choices=CARD_TYPE_CHOICES, default='STUDENT')
    orientation = models.CharField(max_length=20, choices=ORIENTATION_CHOICES, default='PORTRAIT')
    width_mm = models.FloatField(default=54.0, help_text="Card width in millimeters (CR80 portrait is 54mm)")
    height_mm = models.FloatField(default=86.0, help_text="Card height in millimeters (CR80 portrait is 86mm)")
    
    design_mode = models.CharField(max_length=20, choices=DESIGN_MODE_CHOICES, default='SCRATCH')
    background_color = models.CharField(max_length=20, default="#FFFFFF", help_text="Front background hex color")
    background_image = models.ImageField(upload_to='templates/backgrounds/', blank=True, null=True)
    bg_fit_mode = models.CharField(max_length=10, choices=BG_FIT_CHOICES, default='FILL')
    front_image_dpi = models.IntegerField(null=True, blank=True)
    front_resolution_w = models.IntegerField(null=True, blank=True)
    front_resolution_h = models.IntegerField(null=True, blank=True)

    back_background_color = models.CharField(max_length=20, default="#F8FAFC", help_text="Back background hex color")
    back_background_image = models.ImageField(upload_to='templates/backgrounds/', blank=True, null=True)
    back_bg_fit_mode = models.CharField(max_length=10, choices=BG_FIT_CHOICES, default='FILL')
    back_image_dpi = models.IntegerField(null=True, blank=True)
    back_resolution_w = models.IntegerField(null=True, blank=True)
    back_resolution_h = models.IntegerField(null=True, blank=True)

    duplex_mode = models.CharField(max_length=20, choices=DUPLEX_CHOICES, default='FRONT_BACK')
    version = models.IntegerField(default=1)
    parent_template = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='versions'
    )
    organization = models.ForeignKey(
        'platform_admin.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='card_templates',
        help_text="Tenant organization this template belongs to"
    )
    client = models.ForeignKey(
        'platform_admin.OrganizationClient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='templates',
        help_text="Associated client school when managed by a Studio / Press account"
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', 'name']

    def save(self, *args, **kwargs):
        if self.is_default:
            qs = IDCardTemplate.objects.filter(card_type=self.card_type, is_default=True).exclude(pk=self.pk)
            if self.organization:
                qs = qs.filter(organization=self.organization)
            else:
                qs = qs.filter(organization__isnull=True)
            qs.update(is_default=False)
        super().save(*args, **kwargs)

    def duplicate(self, new_name=None):
        """Creates an exact clone of the template and its associated elements."""
        cloned = IDCardTemplate.objects.get(pk=self.pk)
        cloned.pk = None
        cloned.id = None
        cloned.name = new_name or f"{self.name} (Copy)"
        cloned.is_default = False
        cloned.save()

        for el in self.elements.all():
            el.pk = None
            el.id = None
            el.template = cloned
            el.save()

        return cloned

    def create_new_version(self):
        """Spawns an incremented version of this template while preserving current for historical cards."""
        new_version = self.duplicate(new_name=f"{self.name} (v{self.version + 1})")
        new_version.version = self.version + 1
        new_version.parent_template = self.parent_template or self
        new_version.save()
        return new_version

    @property
    def front_bg_url(self):
        if self.background_image:
            try:
                return self.background_image.url
            except ValueError:
                return ""
        return ""

    @property
    def back_bg_url(self):
        if self.back_background_image:
            try:
                return self.back_background_image.url
            except ValueError:
                return ""
        return ""

    def __str__(self):
        default_badge = " [Default]" if self.is_default else ""
        ver_badge = f" v{self.version}" if self.version > 1 else ""
        return f"{self.name}{ver_badge} ({self.get_orientation_display()}){default_badge}"


class TemplateElement(models.Model):
    SIDE_CHOICES = (
        ('FRONT', 'Front Side'),
        ('BACK', 'Back Side'),
    )

    ELEMENT_TYPE_CHOICES = (
        ('TEXT', 'Static Text'),
        ('DYNAMIC_FIELD', 'Dynamic Field'),
        ('STUDENT_PHOTO', 'Student Photo'),
        ('SCHOOL_LOGO', 'School Logo'),
        ('QR_CODE', 'QR Code'),
        ('SIGNATURE', 'Head Teacher Signature'),
        ('RECTANGLE', 'Rectangle / Header Card'),
        ('LINE', 'Divider Line'),
        ('IMAGE', 'Custom Image'),
    )

    ALIGNMENT_CHOICES = (
        ('LEFT', 'Left'),
        ('CENTER', 'Center'),
        ('RIGHT', 'Right'),
    )

    FONT_STYLE_CHOICES = (
        ('NORMAL', 'Normal'),
        ('ITALIC', 'Italic'),
    )

    QR_ERROR_CHOICES = (
        ('L', 'L (7%)'),
        ('M', 'M (15%)'),
        ('Q', 'Q (25%)'),
        ('H', 'H (30%)'),
    )

    template = models.ForeignKey(IDCardTemplate, on_delete=models.CASCADE, related_name='elements')
    side = models.CharField(max_length=10, choices=SIDE_CHOICES, default='FRONT')
    element_type = models.CharField(max_length=30, choices=ELEMENT_TYPE_CHOICES)
    dynamic_field_key = models.CharField(
        max_length=100,
        blank=True,
        help_text="e.g. {{student.name}}, {{student.student_id}}, {{student.roll_no}}, {{student.class}}, {{student.section}}, {{student.dob}}, {{student.gender}}, {{student.address}}, {{student.guardian_name}}, {{school.name}}, {{school.logo}}, {{school.head_teacher_name}}, {{school.head_teacher_signature}}, {{valid_from}}, {{valid_until}}, {{qr_code}}"
    )
    label_text = models.CharField(max_length=255, blank=True, help_text="Static text or element display label")
    
    # Coordinate position & dimensions in millimeters
    x_mm = models.FloatField(default=5.0)
    y_mm = models.FloatField(default=5.0)
    width_mm = models.FloatField(default=44.0)
    height_mm = models.FloatField(default=10.0)

    # Styling attributes
    font_family = models.CharField(max_length=50, default="Helvetica")
    font_size = models.FloatField(default=10.0)
    font_weight = models.CharField(max_length=20, choices=[('NORMAL', 'Normal'), ('BOLD', 'Bold')], default='NORMAL')
    font_style = models.CharField(max_length=20, choices=FONT_STYLE_CHOICES, default='NORMAL')
    font_color = models.CharField(max_length=20, default="#0F172A")
    text_align = models.CharField(max_length=20, choices=ALIGNMENT_CHOICES, default='LEFT')
    fill_color = models.CharField(max_length=20, blank=True, default="", help_text="Hex color for rectangles")
    border_color = models.CharField(max_length=20, blank=True, default="")
    border_width = models.FloatField(default=0.0)
    border_radius = models.FloatField(default=0.0)
    opacity = models.FloatField(default=1.0)
    is_circular = models.BooleanField(default=False, help_text="Circular crop for student photo")
    qr_error_correction = models.CharField(max_length=5, choices=QR_ERROR_CHOICES, default='M')
    auto_shrink_text = models.BooleanField(default=True, help_text="Auto-reduce font size if text overflows")
    text_wrap = models.BooleanField(default=False, help_text="Wrap long text lines")
    z_index = models.IntegerField(default=1)

    class Meta:
        ordering = ['side', 'z_index', 'id']

    def __str__(self):
        field_desc = self.dynamic_field_key or self.label_text or self.get_element_type_display()
        return f"[{self.side}] {self.get_element_type_display()}: {field_desc} at ({self.x_mm}mm, {self.y_mm}mm)"


class IDCard(models.Model):
    CARD_STATUS_CHOICES = (
        ('NOT_GENERATED', 'Not Generated'),
        ('GENERATED', 'Generated'),
        ('PRINTED', 'Printed'),
    )

    VALIDITY_STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('REVOKED', 'Revoked'),
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='id_cards')
    template = models.ForeignKey(IDCardTemplate, on_delete=models.PROTECT, related_name='generated_cards')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name='id_cards')

    card_number = models.CharField(max_length=100, unique=True, db_index=True)
    secure_token = models.CharField(max_length=64, unique=True, db_index=True, default=uuid.uuid4)
    valid_from = models.DateField()
    valid_until = models.DateField()

    card_status = models.CharField(max_length=20, choices=CARD_STATUS_CHOICES, default='GENERATED')
    validity_status = models.CharField(max_length=20, choices=VALIDITY_STATUS_CHOICES, default='ACTIVE', db_index=True)
    revocation_reason = models.TextField(blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_cards'
    )

    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_cards'
    )
    printed_at = models.DateTimeField(null=True, blank=True)
    printed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='printed_cards'
    )

    class Meta:
        ordering = ['-generated_at']

    def is_currently_valid(self):
        if self.validity_status == 'REVOKED':
            return False, "REVOKED"
        today = date.today()
        if today > self.valid_until:
            return False, "EXPIRED"
        if today < self.valid_from:
            return False, "NOT_YET_VALID"
        return True, "ACTIVE"

    def __str__(self):
        return f"Card {self.card_number} for {self.student.full_name} ({self.validity_status})"


class PrintLayout(models.Model):
    PAPER_SIZE_CHOICES = (
        ('A4', 'A4 (210 x 297 mm)'),
        ('A3', 'A3 (297 x 420 mm)'),
        ('LETTER', 'US Letter (215.9 x 279.4 mm)'),
        ('LEGAL', 'US Legal (215.9 x 355.6 mm)'),
        ('CUSTOM', 'Custom Dimensions'),
    )

    ORIENTATION_CHOICES = (
        ('PORTRAIT', 'Portrait'),
        ('LANDSCAPE', 'Landscape'),
    )

    name = models.CharField(max_length=100, default="Standard A4 Layout")
    paper_size = models.CharField(max_length=20, choices=PAPER_SIZE_CHOICES, default='A4')
    custom_width_mm = models.FloatField(null=True, blank=True, help_text="Used only if paper_size is CUSTOM")
    custom_height_mm = models.FloatField(null=True, blank=True, help_text="Used only if paper_size is CUSTOM")
    orientation = models.CharField(max_length=20, choices=ORIENTATION_CHOICES, default='PORTRAIT')

    margin_top_mm = models.FloatField(default=10.0)
    margin_bottom_mm = models.FloatField(default=10.0)
    margin_left_mm = models.FloatField(default=10.0)
    margin_right_mm = models.FloatField(default=10.0)

    gap_x_mm = models.FloatField(default=4.0, help_text="Horizontal spacing between cards")
    gap_y_mm = models.FloatField(default=4.0, help_text="Vertical spacing between cards")

    cols = models.IntegerField(default=3, help_text="Number of columns across sheet")
    rows = models.IntegerField(default=5, help_text="Number of rows down sheet")

    show_crop_marks = models.BooleanField(default=True)
    crop_mark_length_mm = models.FloatField(default=4.0)
    crop_mark_offset_mm = models.FloatField(default=2.0)
    duplex_alignment = models.CharField(
        max_length=20,
        choices=[('MIRROR_COLUMNS', 'Mirror Columns (Duplex Back)'), ('SAME_POSITION', 'Same Position')],
        default='MIRROR_COLUMNS'
    )

    def get_sheet_dimensions_mm(self):
        """Returns (width_mm, height_mm) of the selected paper size respecting orientation."""
        standards = {
            'A4': (210.0, 297.0),
            'A3': (297.0, 420.0),
            'LETTER': (215.9, 279.4),
            'LEGAL': (215.9, 355.6),
        }
        if self.paper_size == 'CUSTOM' and self.custom_width_mm and self.custom_height_mm:
            w, h = float(self.custom_width_mm), float(self.custom_height_mm)
        else:
            w, h = standards.get(self.paper_size, (210.0, 297.0))

        if self.orientation == 'LANDSCAPE':
            return (max(w, h), min(w, h))
        return (min(w, h), max(w, h))

    def calculate_auto_grid(self, card_w_mm, card_h_mm):
        """Calculates optimal rows and columns that fit within printable bounds."""
        sheet_w, sheet_h = self.get_sheet_dimensions_mm()
        avail_w = sheet_w - (self.margin_left_mm + self.margin_right_mm)
        avail_h = sheet_h - (self.margin_top_mm + self.margin_bottom_mm)

        if avail_w <= 0 or avail_h <= 0 or card_w_mm <= 0 or card_h_mm <= 0:
            return 1, 1, 1

        cols = max(1, int((avail_w + self.gap_x_mm) // (card_w_mm + self.gap_x_mm)))
        rows = max(1, int((avail_h + self.gap_y_mm) // (card_h_mm + self.gap_y_mm)))
        cards_per_page = cols * rows
        return cols, rows, cards_per_page

    def __str__(self):
        return f"{self.name} [{self.get_paper_size_display()}: {self.cols}x{self.rows}]"
