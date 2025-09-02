import os, re, hashlib, requests, yaml
from pathlib import Path
from django.core.cache import cache

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
LT_HOST = os.getenv("LT_HOST", "http://libretranslate:5000")  # Back to local instance
LT_API_KEY = os.getenv("LT_API_KEY", None)  # Optional API key
GLOSSARY_PATH = Path(__file__).parent / "fixtures" / "glossary.yml"

# Load glossary once at import time
with GLOSSARY_PATH.open(encoding="utf-8") as f:
    GLOSSARY = {k.lower(): v for k, v in (yaml.safe_load(f) or {}).items()}

def translate_text(text: str, target_lang: str = "en") -> str:
    """
    Translate Arabic text to target language via LibreTranslate.
    Falls back to original text or glossary override.
    Results cached 7 days.
    """
    print(f"DEBUG: translate_text called with text='{text}', target_lang='{target_lang}'")
    
    if not text:
        print("DEBUG: Empty text, returning as-is")
        return text
    
    # If target language is Arabic, return original text (since source is Arabic)
    if target_lang.lower() == "ar":
        print("DEBUG: Target is Arabic, returning original text")
        return text

    # 1. Exact glossary hit
    key_exact = text.strip().lower()
    if key_exact in GLOSSARY:
        print(f"DEBUG: Found exact glossary match: {GLOSSARY[key_exact]}")
        return GLOSSARY[key_exact]

    # 2. Case-insensitive whole-word replacement
    def repl(match):
        return GLOSSARY.get(match.group(0).lower(), match.group(0))

    pattern = re.compile(
        r"\b(" + "|".join(map(re.escape, GLOSSARY.keys())) + r")\b",
        flags=re.IGNORECASE,
    )
    text_with_glossary = pattern.sub(repl, text)
    print(f"DEBUG: After glossary replacement: '{text_with_glossary}'")

    # 3. LibreTranslate for anything left
    cache_key = f"translate_{hashlib.md5(f'{text}#{target_lang}'.encode()).hexdigest()}"
    if cached := cache.get(cache_key):
        print(f"DEBUG: Found cached translation: '{cached}'")
        # Check if cached result is actually translated (not same as original)
        if cached != text:
            return cached
        else:
            print("DEBUG: Cached result is same as original, clearing cache and retrying")
            cache.delete(cache_key)

    print(f"DEBUG: Making API call to {LT_HOST}/translate")

    try:
        # Prepare request data
        data = {
            "q": text_with_glossary, 
            "source": "ar",  # Source is Arabic
            "target": target_lang
        }
        
        # Add API key if available
        if LT_API_KEY:
            data["api_key"] = LT_API_KEY
        
        r = requests.post(
            f"{LT_HOST}/translate",
            data=data,
            timeout=10,
        )
        print(f"DEBUG: API response status: {r.status_code}")
        print(f"DEBUG: API response: {r.text}")
        r.raise_for_status()
        translated = r.json()["translatedText"]
        print(f"DEBUG: Translated text: '{translated}'")
    except requests.RequestException as e:
        print(f"Translation error: {e}")  # For debugging
        print(f"DEBUG: Falling back to original text")
        # Fail gracefully: return original text
        translated = text_with_glossary

    cache.set(cache_key, translated, 60 * 60 * 24 * 7)
    print(f"DEBUG: Final result: '{translated}'")
    return translated