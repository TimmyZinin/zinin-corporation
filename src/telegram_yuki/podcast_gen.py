"""Podcast audio generation — ElevenLabs TTS + post-processing.

Pipeline: script text → chunk → TTS API → concatenate → normalize → ID3 tags → MP3.
Uses raw HTTP calls (same pattern as _call_llm in smm_tools.py).
"""

import io
import json
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import HTTPError

logger = logging.getLogger(__name__)

PODCASTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "yuki_podcasts")
AUDIO_DIR = os.path.join(PODCASTS_DIR, "audio")

MAX_CHUNK_CHARS = 4500  # ElevenLabs limit is 5000, leave margin


def _split_text_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text at sentence boundaries, respecting max_chars."""
    sentences = re.split(r'(?<=[.!?…])\s+', text.strip())
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 > max_chars:
            if current:
                chunks.append(current.strip())
            # If a single sentence exceeds max_chars, split at comma/semicolon
            if len(sentence) > max_chars:
                parts = re.split(r'(?<=[,;:])\s+', sentence)
                sub = ""
                for part in parts:
                    if len(sub) + len(part) + 1 > max_chars:
                        if sub:
                            chunks.append(sub.strip())
                        sub = part
                    else:
                        sub = f"{sub} {part}" if sub else part
                if sub:
                    current = sub
            else:
                current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _tts_chunk(text: str, voice_id: str, api_key: str) -> Optional[bytes]:
    """Call ElevenLabs TTS API for one chunk. Returns MP3 bytes."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    payload = json.dumps({
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }).encode("utf-8")

    req = Request(
        url,
        data=payload,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=120) as resp:
            return resp.read()
    except HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        logger.error(f"ElevenLabs TTS error: HTTP {e.code} — {error_body[:300]}")
        raise RuntimeError(f"ElevenLabs TTS failed: HTTP {e.code}") from e
    except Exception as e:
        logger.error(f"ElevenLabs TTS error: {e}")
        raise


def _concatenate_audio(chunks: list[bytes]) -> "AudioSegment":
    """Concatenate MP3 byte chunks into single AudioSegment."""
    from pydub import AudioSegment

    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=300)  # 300ms between chunks

    for i, chunk_bytes in enumerate(chunks):
        segment = AudioSegment.from_mp3(io.BytesIO(chunk_bytes))
        if i > 0:
            combined += silence
        combined += segment

    return combined


def _postprocess(audio: "AudioSegment") -> "AudioSegment":
    """Normalize loudness and add silence padding."""
    from pydub import AudioSegment

    # Add 0.5s silence at start and end
    padding = AudioSegment.silent(duration=500)
    audio = padding + audio + padding

    # Simple loudness normalization (target -16 dBFS for podcasts)
    target_dbfs = -16.0
    change = target_dbfs - audio.dBFS
    audio = audio.apply_gain(change)

    return audio


def _set_id3_tags(filepath: str, title: str, episode_number: int = 1):
    """Set ID3 tags on the MP3 file."""
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, TDRC, TCON

        audio = MP3(filepath, ID3=ID3)

        try:
            audio.add_tags()
        except Exception:
            pass

        audio.tags.add(TIT2(encoding=3, text=[title]))
        audio.tags.add(TPE1(encoding=3, text=["AI Corporation"]))
        audio.tags.add(TALB(encoding=3, text=["AI Corporation Podcast"]))
        audio.tags.add(TRCK(encoding=3, text=[str(episode_number)]))
        audio.tags.add(TDRC(encoding=3, text=[datetime.now().strftime("%Y")]))
        audio.tags.add(TCON(encoding=3, text=["Podcast"]))

        audio.save()
        logger.info(f"ID3 tags set for: {filepath}")
    except Exception as e:
        logger.warning(f"Failed to set ID3 tags: {e}")


def generate_podcast_audio(
    script: str,
    title: str,
    episode_number: int = 1,
) -> tuple[str, dict]:
    """Full pipeline: script text → MP3 file.

    Returns (filepath, metadata_dict).
    metadata_dict: duration_sec, file_size_bytes, chunks_count.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY", "")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "")

    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not set")
    if not voice_id:
        raise RuntimeError("ELEVENLABS_VOICE_ID not set")

    # Clean script: remove metadata headers from CrewAI output
    clean_script = _clean_script(script)

    # Split into chunks
    chunks_text = _split_text_chunks(clean_script)
    logger.info(f"Podcast script split into {len(chunks_text)} chunks ({len(clean_script)} chars)")

    # Generate audio for each chunk
    audio_chunks = []
    for i, chunk_text in enumerate(chunks_text):
        logger.info(f"TTS chunk {i + 1}/{len(chunks_text)} ({len(chunk_text)} chars)...")
        audio_bytes = _tts_chunk(chunk_text, voice_id, api_key)
        if audio_bytes:
            audio_chunks.append(audio_bytes)

    if not audio_chunks:
        raise RuntimeError("No audio generated — all TTS calls failed")

    # Concatenate
    combined = _concatenate_audio(audio_chunks)

    # Post-process
    final = _postprocess(combined)

    # Save
    os.makedirs(AUDIO_DIR, exist_ok=True)
    post_id = uuid.uuid4().hex[:8]
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_str}_{post_id}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)

    final.export(filepath, format="mp3", bitrate="128k")

    # ID3 tags
    _set_id3_tags(filepath, title, episode_number)

    # Metadata
    duration_sec = len(final) / 1000.0
    file_size = os.path.getsize(filepath)

    metadata = {
        "duration_sec": int(duration_sec),
        "file_size_bytes": file_size,
        "chunks_count": len(chunks_text),
        "chars_total": len(clean_script),
        "filename": filename,
        "post_id": post_id,
    }

    logger.info(
        f"Podcast audio generated: {filepath} "
        f"({int(duration_sec)}s, {file_size // 1024}KB, {len(chunks_text)} chunks)"
    )

    return filepath, metadata


def _clean_script(text: str) -> str:
    """Remove CrewAI metadata headers from script output."""
    # Remove lines like "POST GENERATED (score: 0.85 ✅)" or "REFINED ⚠️ ..."
    lines = text.split("\n")
    clean_lines = []
    skip_header = True

    for line in lines:
        if skip_header:
            if line.startswith("---"):
                skip_header = False
                continue
            if any(line.startswith(p) for p in [
                "POST GENERATED", "REFINED", "CONTENT ALREADY",
                "Author:", "Topic:", "Length:", "Score:",
            ]):
                continue
            # If no header pattern found, include all lines
            skip_header = False

        clean_lines.append(line)

    result = "\n".join(clean_lines).strip()
    return result if result else text.strip()
