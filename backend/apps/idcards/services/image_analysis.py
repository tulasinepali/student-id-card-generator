"""
Image Quality and DPI Analysis Service for ID Card Backgrounds.
Calculates print resolution (dots per inch) relative to physical card millimeter dimensions.
"""

from PIL import Image


def analyze_card_image(image_file_or_path, width_mm, height_mm):
    """
    Analyzes an uploaded ID card background image.
    Calculates exact DPI relative to physical card mm dimensions (25.4 mm = 1 inch).
    Returns dictionary with resolution, DPI, quality classification, and warning text.
    """
    try:
        if hasattr(image_file_or_path, 'read'):
            image_file_or_path.seek(0)
            img = Image.open(image_file_or_path)
            image_file_or_path.seek(0)
        else:
            img = Image.open(image_file_or_path)

        w_px, h_px = img.size

        # Physical width & height in inches
        w_in = width_mm / 25.4
        h_in = height_mm / 25.4

        if w_in <= 0 or h_in <= 0:
            return {
                'success': False,
                'error': 'Invalid card dimensions.'
            }

        dpi_x = w_px / w_in
        dpi_y = h_px / h_in
        effective_dpi = int(round(min(dpi_x, dpi_y)))

        # Quality assessment
        if effective_dpi >= 250:
            is_suitable = True
            rating = "SUITABLE"
            badge_class = "success"
            message = "✓ Suitable (High Resolution / Print Ready)"
        elif effective_dpi >= 150:
            is_suitable = True
            rating = "ACCEPTABLE"
            badge_class = "warning"
            message = "⚠ Acceptable Quality (Standard Resolution)"
        else:
            is_suitable = False
            rating = "LOW_RESOLUTION"
            badge_class = "danger"
            message = "⚠ Low-resolution design: The image may appear blurry when printed."

        return {
            'success': True,
            'width_px': w_px,
            'height_px': h_px,
            'resolution_str': f"{w_px} × {h_px} px",
            'dpi': effective_dpi,
            'dpi_x': int(round(dpi_x)),
            'dpi_y': int(round(dpi_y)),
            'card_mm_str': f"{width_mm} × {height_mm} mm",
            'is_suitable': is_suitable,
            'rating': rating,
            'badge_class': badge_class,
            'message': message,
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Failed to analyze image: {str(e)}"
        }
