# crypto_assistant/__init__.py

from .audio_processing import convert_audio_to_text
from .assistant_interaction import interact_with_assistant

__all__ = [
    "convert_audio_to_text",
    "interact_with_assistant",
]
