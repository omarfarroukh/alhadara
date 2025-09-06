# accounts/captcha_utils.py
from io import BytesIO
from captcha.image import ImageCaptcha
from django.utils.crypto import get_random_string
from PIL import ImageDraw

from core.translation import translate_text
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
        return ok
    except Captcha.DoesNotExist:
        return False
    
class TranslationMixin:
    """
    A serializer mixin that provides a utility method for conditional translation.
    
    Provides `get_translated_field(self, text_to_translate)` which handles:
    - Checking if the request method is GET.
    - Safely getting the 'lang' parameter.
    - Calling the translation function or returning the original text.
    """
    
    def _get_lang(self):
        """
        Safely get the language from the request context,
        falling back to 'en' if the request is not available.
        """
        request = self.context.get('request')
        if request and hasattr(request, 'GET'):
            return request.GET.get('lang', 'ar')
        return 'ar'

    def _should_translate(self):
        """

        Determines if translation should occur. Only translates for GET requests.
        """
        request = self.context.get('request')
        # Only translate if there is a request and its method is GET.
        if request and request.method == 'GET':
            return True
        # Do NOT translate for POST, PUT, PATCH, or if context is missing.
        return False

    def get_translated_field(self, text_to_translate):
        """
        Main utility method. Translates the given text if the request
        is a GET request, otherwise returns the original text.
        """
        # Ensure we don't try to translate None
        if text_to_translate is None:
            return None
            
        if self._should_translate():
            return translate_text(text_to_translate, self._get_lang())
        
        return text_to_translate