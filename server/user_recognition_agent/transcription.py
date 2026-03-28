"""Audio transcription + name/role/fun_fact extraction using Google Gemini."""
import asyncio
import io
import json
import logging
import os
import tempfile
import wave
from typing import Optional, Tuple

from google import genai

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000


def pcm_to_wav(pcm_chunks: list[bytes], sample_rate: int = SAMPLE_RATE) -> bytes:
    """Convert raw PCM 16-bit mono chunks to WAV bytes."""
    raw = b"".join(pcm_chunks)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)
    return buf.getvalue()


def _sync_transcribe_and_extract(pcm_chunks: list[bytes]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Synchronous version — runs Gemini API calls.
    Called via run_in_executor to avoid blocking the event loop.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not pcm_chunks or not api_key:
        log.warning("transcribe_and_extract: no audio chunks or no GEMINI_API_KEY")
        return None, None, None

    tmp_wav = None
    try:
        wav_bytes = pcm_to_wav(pcm_chunks)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            tmp_wav = f.name

        client = genai.Client(api_key=api_key)
        audio_file = client.files.upload(file=tmp_wav)

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                audio_file,
                """Listen to this audio of someone introducing themselves at a networking event or group introduction.

Extract the following information in JSON format:
{
  "name": "their full name",
  "role": "their job title and/or company",
  "fun_fact": "any interesting personal fact they mentioned"
}

Rules:
- If you can't determine a field, set it to null
- For "role", combine job title and company if both mentioned (e.g. "PM @ Google")
- For "fun_fact", pick the most memorable/interesting thing they said about themselves
- Return ONLY valid JSON, no other text, no markdown code blocks"""
            ]
        )

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].strip()
        if text.startswith("json"):
            text = text[4:].strip()

        result = json.loads(text)
        name = result.get("name")
        role = result.get("role")
        fun_fact = result.get("fun_fact")

        log.info("Gemini extracted: name=%s, role=%s, fun_fact=%s", name, role, fun_fact)
        return name, role, fun_fact

    except Exception as e:
        log.warning("transcribe_and_extract failed: %s", e)
        return None, None, None
    finally:
        if tmp_wav:
            try:
                os.unlink(tmp_wav)
            except OSError:
                pass


async def transcribe_and_extract(pcm_chunks: list[bytes]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Async wrapper — runs the blocking Gemini API calls in a thread executor
    so the event loop stays responsive during enrollment.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_transcribe_and_extract, pcm_chunks)
