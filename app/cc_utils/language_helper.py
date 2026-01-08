"""
Language Detection Utility

Helper functions to detect text language
"""

import re


def detect_language(text: str) -> str:
    """Detect language by checking for Korean or Traditional Chinese characters

    Args:
        text: Text to analyze

    Returns:
        str: "Korean", "Traditional_Chinese", or "English"
    """
    if re.search(r'[가-힣]', text):
        return "Korean"
    if re.search(r'[\u4E00-\u9FFF]+', text):
        return "Traditional_Chinese"
    return "English"
