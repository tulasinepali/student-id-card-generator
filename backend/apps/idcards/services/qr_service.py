import io
import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
from PIL import Image
from django.conf import settings
from django.urls import reverse


ERROR_LEVELS = {
    'L': ERROR_CORRECT_L,
    'M': ERROR_CORRECT_M,
    'Q': ERROR_CORRECT_Q,
    'H': ERROR_CORRECT_H,
}


def generate_qr_image(data_url, error_level='M', box_size=10, border=1):
    """
    Generates a high-contrast, sharp PIL Image QR code for the given data URL.
    """
    corr = ERROR_LEVELS.get(error_level, ERROR_CORRECT_M)
    qr = qrcode.QRCode(
        version=None,
        error_correction=corr,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    return img


def get_card_verification_url(card, request=None):
    """
    Constructs the absolute or relative verification URL for a given IDCard instance.
    Uses card.secure_token.
    """
    path = reverse('public_qr_verify', kwargs={'token': card.secure_token})
    if request:
        return request.build_absolute_uri(path)
    return path


def generate_card_qr_bytes(card, request=None, error_level='M', box_size=10):
    """
    Generates PNG bytes for the ID card QR code.
    """
    url = get_card_verification_url(card, request)
    img = generate_qr_image(url, error_level=error_level, box_size=box_size)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.getvalue()
