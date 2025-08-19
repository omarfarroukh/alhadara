# accounts/captcha_utils.py
from io import BytesIO
from captcha.image import ImageCaptcha
from django.utils.crypto import get_random_string
from PIL import ImageDraw
from .models import Captcha
import base64
import random
import string


def generate_captcha():
    """Readable 6-char CAPTCHA with a faint strike-through."""
    text = get_random_string(6, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')

    # Use ImageCaptcha for the text itself
    image = ImageCaptcha(width=280, height=90)
    img = image.generate_image(text)

    # Light tilt
    img = img.rotate(random.randint(-5, 5), fillcolor="#FFF")

    # One thin diagonal line
    draw = ImageDraw.Draw(img)
    draw.line(
        [(20, random.randint(20, 70)), (260, random.randint(20, 70))],
        fill="#777",
        width=1,
    )

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    key = get_random_string(32)
    Captcha.objects.create(key=key, text=text)

    b64 = base64.b64encode(buf.read()).decode()
    return key, f"data:image/png;base64,{b64}"


def validate_captcha(key: str, answer: str) -> bool:
    try:
        captcha = Captcha.objects.get(key=key)
        ok = captcha.text.upper() == answer.strip().upper() and not captcha.is_expired()
        captcha.delete()
        return ok
    except Captcha.DoesNotExist:
        return False