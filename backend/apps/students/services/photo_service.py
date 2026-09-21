import io
import os
import zipfile
from PIL import Image, ImageOps
from django.core.files.base import ContentFile
from django.conf import settings
from apps.students.models import Student
from apps.core.services.audit import log_action
from apps.core.utils import get_current_organization


ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
TARGET_RATIO = (3, 4)  # Width to Height ratio for ID card student photos
MAX_DIMENSION = 800     # Max px dimension for high quality without bloat
Image.MAX_IMAGE_PIXELS = 16_000_000  # Security: Prevent decompression bomb DoS attacks


def process_student_photo(file_obj, target_aspect_ratio=(3, 4), max_dimension=800):
    """
    Validates, crops to center target ratio, resizes, and optimizes a student photo.
    Returns a ContentFile ready to save to Student.photo.
    """
    try:
        file_obj.seek(0)
        img = Image.open(file_obj)
        img.verify()  # Validate image integrity
        
        file_obj.seek(0)
        img = Image.open(file_obj)
    except Exception as e:
        raise ValueError(f"Invalid or corrupted image file: {str(e)}")

    # Auto-orient using EXIF data (handles photos taken on phones)
    img = ImageOps.exif_transpose(img)

    # Convert to RGB mode if CMYK or RGBA (saving as JPEG)
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # Crop to target aspect ratio (3:4) centered
    w, h = img.size
    target_w_ratio, target_h_ratio = target_aspect_ratio
    current_ratio = w / h
    desired_ratio = target_w_ratio / target_h_ratio

    if current_ratio > desired_ratio:
        # Image is wider than desired ratio: crop width
        new_w = int(h * desired_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    elif current_ratio < desired_ratio:
        # Image is taller than desired ratio: crop height
        new_h = int(w / desired_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))

    # Resize if larger than max_dimension
    final_w, final_h = img.size
    if final_h > max_dimension or final_w > max_dimension:
        img.thumbnail((max_dimension, int(max_dimension * (target_h_ratio / target_w_ratio))), Image.Resampling.LANCZOS)

    # Save to optimized JPEG bytes
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=88, optimize=True)
    buffer.seek(0)
    return ContentFile(buffer.getvalue(), name="student_photo.jpg")


def process_bulk_photo_zip(zip_file_obj, class_level=None, section=None, academic_year=None, user=None, request=None):
    """
    Extracts student photos from a ZIP archive, matching filenames (e.g. STU1001.jpg) to Student.student_id.
    Returns detailed summary statistics and lists of matched/unmatched/missing items.
    """
    results = {
        'total_files_in_zip': 0,
        'matched_count': 0,
        'unmatched_files': [],
        'missing_students': [],
        'invalid_files': [],
        'processed_students': [],
    }

    try:
        with zipfile.ZipFile(zip_file_obj, 'r') as z:
            # Security: Prevent zip bomb attacks (cap total uncompressed size)
            MAX_UNCOMPRESSED_TOTAL = 300 * 1024 * 1024  # 300MB ceiling
            total_uncompressed = sum(info.file_size for info in z.infolist())
            if total_uncompressed > MAX_UNCOMPRESSED_TOTAL:
                raise ValueError(f"ZIP uncompressed content ({total_uncompressed // (1024 * 1024)}MB) exceeds maximum safe limit of 300MB.")

            namelist = z.namelist()
            results['total_files_in_zip'] = len([f for f in namelist if not f.endswith('/') and not f.startswith('__MACOSX')])

            # Get target students scope
            student_qs = Student.objects.all()
            org = None
            if request:
                org = get_current_organization(request)
            elif user:
                org = getattr(user, 'organization', None)
            if org:
                student_qs = student_qs.filter(organization=org)
            if class_level:
                student_qs = student_qs.filter(class_level=class_level)
            if section:
                student_qs = student_qs.filter(section=section)
            if academic_year:
                student_qs = student_qs.filter(academic_year=academic_year)

            students_by_id = {s.student_id.strip().upper(): s for s in student_qs}
            matched_student_ids = set()

            for filename in namelist:
                if filename.endswith('/') or filename.startswith('__MACOSX') or filename.startswith('.'):
                    continue

                basename = os.path.basename(filename)
                name_without_ext, ext = os.path.splitext(basename)
                ext = ext.lower()

                if ext not in ALLOWED_EXTENSIONS:
                    results['invalid_files'].append({
                        'filename': basename,
                        'reason': f"Unsupported extension '{ext}'. Must be JPG, PNG, or WebP."
                    })
                    continue

                student_key = name_without_ext.strip().upper()
                if student_key in students_by_id:
                    student = students_by_id[student_key]
                    try:
                        file_bytes = z.read(filename)
                        if len(file_bytes) > settings.MAX_IMAGE_UPLOAD_SIZE:
                            results['invalid_files'].append({
                                'filename': basename,
                                'reason': "File exceeds 5MB limit."
                            })
                            continue

                        processed_file = process_student_photo(io.BytesIO(file_bytes))
                        save_name = f"{student.student_id}.jpg"
                        student.photo.save(save_name, processed_file, save=True)

                        matched_student_ids.add(student_key)
                        results['matched_count'] += 1
                        results['processed_students'].append({
                            'student_id': student.student_id,
                            'name': student.full_name,
                            'filename': basename
                        })

                        log_action(
                            user=user,
                            action='PHOTO_CHANGED',
                            object_type='Student',
                            object_id=student.id,
                            object_repr=str(student),
                            details={'method': 'bulk_zip_upload', 'filename': basename},
                            request=request
                        )
                    except Exception as e:
                        results['invalid_files'].append({
                            'filename': basename,
                            'reason': f"Processing error: {str(e)}"
                        })
                else:
                    results['unmatched_files'].append(basename)

            # Determine which students in scope still don't have photos
            for s_id, student in students_by_id.items():
                if not student.has_photo:
                    results['missing_students'].append({
                        'student_id': student.student_id,
                        'name': student.full_name,
                        'class': student.class_level.name,
                        'section': student.section.name,
                        'roll_number': student.roll_number
                    })

    except zipfile.BadZipFile:
        raise ValueError("Uploaded file is not a valid ZIP archive.")

    return results
