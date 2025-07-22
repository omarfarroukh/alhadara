import os,re,hashlib,requests,yaml
from pathlib import Path
from django.core.cache import cache

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
LT_HOST = os.getenv("LT_HOST", "http://localhost:5000")      # Railway URL or local
GLOSSARY_PATH = Path(__file__).parent / "fixtures" / "glossary.yml"

# Load glossary once at import time
with GLOSSARY_PATH.open(encoding="utf-8") as f:
    GLOSSARY = {k.lower(): v for k, v in (yaml.safe_load(f) or {}).items()}

def translate_text(text: str, target_lang: str = "ar") -> str:
    """
    Translate English text to target language via LibreTranslate.
    Falls back to English or glossary override.
    Results cached 7 days.
    """
    if not text:
        return text
    if target_lang.lower() == "ar":
        return text

    # 1. Exact glossary hit
    key_exact = text.strip()
    if key_exact in GLOSSARY:
        return GLOSSARY[key_exact]

    # 2. Case-insensitive whole-word replacement
    def repl(match):
        return GLOSSARY.get(match.group(0).lower(), match.group(0))

    pattern = re.compile(
        r"\b(" + "|".join(map(re.escape, GLOSSARY.keys())) + r")\b",
        flags=re.IGNORECASE,
    )
    text = pattern.sub(repl, text)

    # 3. LibreTranslate for anything left
    cache_key = hashlib.md5(f"{text}#{target_lang}".encode()).hexdigest()
    if cached := cache.get(cache_key):
        return cached

    try:
        r = requests.post(
            f"{LT_HOST}/translate",
            data={"q": text, "source": "ar", "target": target_lang},
            timeout=10,
        )
        r.raise_for_status()
        translated = r.json()["translatedText"]
    except requests.RequestException:
        # Fail gracefully: return original text
        translated = text

    cache.set(cache_key, translated, 60 * 60 * 24 * 7)
    return translated