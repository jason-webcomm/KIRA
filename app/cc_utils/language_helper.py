"""
Language Detection Utility

Helper functions to detect text language
"""

import re
from app.config.settings import get_settings


def detect_language(text: str) -> str:
    """Detect language by counting character occurrences

    Args:
        text: Text to analyze

    Returns:
        str: "Korean", "Traditional Chinese", or "English"

    This function first checks if RESPONSE_LANGUAGE_SETTING is configured.
    If configured, it returns that setting. Otherwise, it auto-detects
    by counting characters and returns the language with the highest count.
    """
    # Check if language is explicitly configured in settings
    settings = get_settings()
    if settings.RESPONSE_LANGUAGE_SETTING:
        return settings.RESPONSE_LANGUAGE_SETTING

    # Auto-detect language by counting characters
    # Count Korean characters (Hangul)
    korean_count = len(re.findall(r'[가-힣]', text))
    # Count Chinese characters (CJK Unified Ideographs)
    # This covers both Simplified and Traditional Chinese
    chinese_count = len(re.findall(r'[\u4E00-\u9FFF]', text))
    # Count English letters
    english_count = len(re.findall(r'[a-zA-Z]', text))

    # Return the language with the highest count
    if korean_count >= chinese_count and korean_count >= english_count:
        return "Korean"
    elif chinese_count >= english_count:
        return "Traditional Chinese"
    else:
        return "English"
