"""
🎙️ Zinin Corp — Voice Tools

Speech-to-text using faster-whisper (local, CPU-based).
Model is lazy-loaded on first use.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_model = None
_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")  # small = 244MB


def _get_model():
    """Lazy-load the WhisperModel. Returns None if faster-whisper not installed."""
    global _model
    if _model is not None:
        return _model

    try:
        from faster_whisper import WhisperModel
        logger.info(f"Loading faster-whisper model: {_MODEL_SIZE}")
        _model = WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")
        logger.info("faster-whisper model loaded")
        return _model
    except ImportError:
        logger.warning("faster-whisper not installed — voice transcription disabled")
        return None
    except Exception as e:
        logger.error(f"Failed to load faster-whisper model: {e}")
        return None


def transcribe_voice(file_path: str, language: str = "ru") -> Optional[str]:
    """Transcribe audio file to text.

    Args:
        file_path: Path to audio file (WAV, OGG, MP3, etc.)
        language: Language code (default: 'ru')

    Returns:
        Transcribed text or None if transcription failed.
    """
    if not os.path.exists(file_path):
        logger.error(f"Audio file not found: {file_path}")
        return None

    model = _get_model()
    if model is None:
        return None

    try:
        segments, info = model.transcribe(
            file_path,
            language=language,
            beam_size=5,
            vad_filter=True,
        )

        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        text = " ".join(text_parts).strip()
        if not text:
            logger.info("Transcription produced empty text")
            return None

        logger.info(
            f"Transcribed {info.duration:.1f}s audio: "
            f"{len(text)} chars, language={info.language}"
        )
        return text

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return None


def convert_ogg_to_wav(ogg_path: str, wav_path: Optional[str] = None) -> Optional[str]:
    """Convert OGG/OGA to WAV using pydub.

    Args:
        ogg_path: Path to input OGG file
        wav_path: Optional output path (default: same name with .wav)

    Returns:
        Path to WAV file or None if conversion failed.
    """
    if wav_path is None:
        wav_path = os.path.splitext(ogg_path)[0] + ".wav"

    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(ogg_path)
        audio.export(wav_path, format="wav")
        logger.info(f"Converted {ogg_path} → {wav_path}")
        return wav_path
    except ImportError:
        logger.warning("pydub not installed — OGG conversion disabled")
        return None
    except Exception as e:
        logger.error(f"OGG→WAV conversion failed: {e}")
        return None


def is_voice_available() -> bool:
    """Check if voice transcription is available."""
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False
