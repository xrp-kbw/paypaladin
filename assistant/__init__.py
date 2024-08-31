# crypto_assistant/__init__.py

from .audio_processing import convert_audio_to_text
from .assistant_manager import initialize_client, add_message_to_thread

__all__ = [
    "convert_audio_to_text",
    "initialize_client",
    "add_message_to_thread",
]
