"""Explanation, translation, and actionable advice generator for TrustShop AI."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from app.extraction import CheckContext
from app.schemas import ReasonItem

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
I18N_DIR = PROJECT_ROOT / "i18n"

SUPPORTED_LANGUAGES = ("en", "ml", "hi")
DEFAULT_LANGUAGE = "en"

# In-memory cache for loaded translations
_TRANSLATION_CACHE: dict[str, dict[str, Any]] = {}


def load_translations(language: str) -> dict[str, Any]:
    """Load translation YAML for a given language code with fallback to English."""
    lang = language.lower() if language else DEFAULT_LANGUAGE
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    if lang in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[lang]

    yaml_file = I18N_DIR / f"{lang}.yaml"
    if not yaml_file.exists():
        # Fall back to English file
        yaml_file = I18N_DIR / f"{DEFAULT_LANGUAGE}.yaml"

    try:
        with open(yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            _TRANSLATION_CACHE[lang] = data
            return data
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("Could not load translation file %s: %s", yaml_file, exc)
        return {}


def get_reason_explanation(code: str, language: str = DEFAULT_LANGUAGE) -> str:
    """Get human-readable sentence for a reason code in requested language."""
    data = load_translations(language)
    reasons = data.get("reasons", {})
    if code in reasons:
        return str(reasons[code])

    # Fallback to English if not found in requested language
    if language != DEFAULT_LANGUAGE:
        en_data = load_translations(DEFAULT_LANGUAGE)
        en_reasons = en_data.get("reasons", {})
        if code in en_reasons:
            return str(en_reasons[code])

    return f"Check triggered code {code}."


def generate_explanation(
    context: CheckContext,
    verdict: str,
    reason_codes: list[str],
    language: str | None = None,
) -> dict[str, Any]:
    """Generate localized summary, reasons list, advice, and disclaimer."""
    lang = (language or context.language or DEFAULT_LANGUAGE).lower()
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    data = load_translations(lang)
    en_data = load_translations(DEFAULT_LANGUAGE) if lang != DEFAULT_LANGUAGE else data

    # 1. Resolve brand display name
    brand_name = "the claimed brand"
    if lang == "ml":
        brand_name = "അവകാശപ്പെട്ട ബ്രാൻഡ്"
    elif lang == "hi":
        brand_name = "कथित ब्रांड"

    if context.brand and context.brand.get("name"):
        brand_name = context.brand["name"]

    # 2. Build reasons list
    reasons_list: list[ReasonItem] = []
    for code in reason_codes:
        reasons_list.append(
            ReasonItem(code=code, text=get_reason_explanation(code, language=lang))
        )

    # 3. Localized summary with brand replacement
    summaries = data.get("summaries", {})
    summary_tmpl = summaries.get(verdict) or en_data.get("summaries", {}).get(verdict)
    if summary_tmpl:
        summary = summary_tmpl.format(brand_name=brand_name)
    else:
        summary = f"Verification complete. Verdict: {verdict}."

    # 4. Localized advice list with brand replacement
    advice_map = data.get("advice", {})
    advice_items = advice_map.get(verdict) or en_data.get("advice", {}).get(verdict) or []
    formatted_advice: list[str] = []
    for item in advice_items:
        formatted_advice.append(str(item).format(brand_name=brand_name))

    # 5. Localized disclaimer
    disclaimer = data.get("disclaimer") or en_data.get(
        "disclaimer",
        "Automated estimate, not proof. Always confirm through the brand's official website or app.",
    )

    return {
        "summary": summary,
        "reasons": reasons_list,
        "advice": formatted_advice,
        "disclaimer": disclaimer,
    }
