"""
STT (Speech-to-Text) Provider Abstraction
Designed for easy switching between Web Speech API and Deepgram
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class STTProvider(ABC):
    """STT Provider abstract class"""

    @abstractmethod
    def get_provider_type(self) -> str:
        """Return provider type (webspeech / deepgram)"""
        pass

    @abstractmethod
    def get_client_config(self) -> Optional[Dict[str, Any]]:
        """Return configuration for client use"""
        pass


class WebSpeechProvider(STTProvider):
    """Web Speech API Provider (browser built-in)"""

    def __init__(self, language: str = "Korean"):
        """Initialize with language preference

        Args:
            language: Language preference ("Korean", "Traditional_Chinese", "English")
        """
        self.language = language

    def get_provider_type(self) -> str:
        return "webspeech"

    def get_client_config(self) -> Optional[Dict[str, Any]]:
        """Web Speech is handled entirely on client side, minimal config needed"""
        # Language code mapping
        lang_codes = {
            "Korean": "ko-KR",
            "Traditional_Chinese": "zh-TW",
            "English": "en-US"
        }
        lang_code = lang_codes.get(self.language, "ko-KR")

        return {
            "type": "webspeech",
            "lang": lang_code,
            "continuous": False,  # Continuous recognition
            "interimResults": True  # Show interim results
        }


class DeepgramProvider(STTProvider):
    """Deepgram API Provider (for future implementation)"""

    def __init__(self, api_key: str, language: str = "Korean"):
        self.api_key = api_key
        self.language = language

    def get_provider_type(self) -> str:
        return "deepgram"

    def get_client_config(self) -> Optional[Dict[str, Any]]:
        """Return Deepgram configuration"""
        # Language code mapping for Deepgram
        lang_codes = {
            "Korean": "ko",
            "Traditional_Chinese": "zh",
            "English": "en"
        }
        lang_code = lang_codes.get(self.language, "ko")

        return {
            "type": "deepgram",
            "api_key": self.api_key,
            "language": lang_code,
            "model": "nova-2",  # Latest model
            "smart_format": True  # Auto-add punctuation
        }


# Select current provider
def get_stt_provider(language: str = "Korean") -> STTProvider:
    """Return current STT Provider

    Args:
        language: Language preference ("Korean", "Traditional_Chinese", "English")
    """
    # TODO: Make configurable via environment variable or settings
    # Currently using Web Speech API
    return WebSpeechProvider(language=language)

    # To switch to Deepgram:
    # from app.config.settings import get_settings
    # settings = get_settings()
    # return DeepgramProvider(api_key=settings.DEEPGRAM_API_KEY, language=language)
