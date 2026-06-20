"""Ovozli xabarni matnga aylantirish.

Rejimlar (ustuvorlik tartibida):
  1) OpenAI Whisper (OPENAI_API_KEY bo'lsa)
  2) Groq Whisper (GROQ_API_KEY bo'lsa) — bepul
"""
import os

from config import USE_OPENAI, OPENAI_API_KEY

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
USE_GROQ = bool(GROQ_API_KEY)


def _transcribe_openai(file_path: str) -> str | None:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        with open(file_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1", file=f, language="uz"
            )
        return (result.text or "").strip() or None
    except Exception as e:
        print(f"[voice] OpenAI xatosi: {e}")
        return None


def _transcribe_groq(file_path: str) -> str | None:
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=(filename, f, "audio/ogg"),
                language="uz",
                response_format="text",
            )
        text = result if isinstance(result, str) else getattr(result, "text", "") or ""
        return text.strip() or None
    except Exception as e:
        print(f"[voice] Groq xatosi: {e}")
        return None


def transcribe(file_path: str) -> str | None:
    if USE_OPENAI:
        text = _transcribe_openai(file_path)
        if text:
            return text
    if USE_GROQ:
        return _transcribe_groq(file_path)
    return None
