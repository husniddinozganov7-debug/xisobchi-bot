"""Ovozli xabarni matnga aylantirish.

Ikki rejim:
  1) OpenAI Whisper (agar OPENAI_API_KEY bo'lsa) — eng aniq.
  2) Vosk (lokal, bepul o'zbekcha model) — internetsiz ishlaydi.

Telegram ovozi .ogg (opus) formatida keladi. Vosk uchun uni ffmpeg orqali
16 kHz, mono WAV ga aylantiramiz (ffmpeg binari imageio-ffmpeg bilan keladi).
"""
import os
import json
import wave
import subprocess
import tempfile

from config import USE_OPENAI, USE_VOSK, OPENAI_API_KEY, VOSK_MODEL_PATH

# Vosk modeli bir marta yuklanadi (sekin, shuning uchun keshlaymiz)
_vosk_model = None


def _get_vosk_model():
    global _vosk_model
    if _vosk_model is None:
        from vosk import Model
        _vosk_model = Model(VOSK_MODEL_PATH)
    return _vosk_model


def _ogg_to_wav(src: str) -> str:
    """OGG/Opus faylni 16kHz mono WAV ga aylantiradi. WAV yo'lini qaytaradi."""
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    wav_path = src + ".wav"
    subprocess.run(
        [ffmpeg, "-y", "-i", src, "-ar", "16000", "-ac", "1", "-f", "wav", wav_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return wav_path


def _transcribe_vosk(file_path: str) -> str | None:
    """Vosk bilan ovozni matnga aylantiradi."""
    from vosk import KaldiRecognizer

    wav_path = None
    try:
        wav_path = _ogg_to_wav(file_path)
        wf = wave.open(wav_path, "rb")
        rec = KaldiRecognizer(_get_vosk_model(), wf.getframerate())
        rec.SetWords(False)

        parts = []
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                parts.append(json.loads(rec.Result()).get("text", ""))
        parts.append(json.loads(rec.FinalResult()).get("text", ""))
        wf.close()

        text = " ".join(p for p in parts if p).strip()
        return text or None
    except Exception as e:  # noqa: BLE001
        print(f"[voice] Vosk xatosi: {e}")
        return None
    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)


def _transcribe_openai(file_path: str) -> str | None:
    """OpenAI Whisper bilan ovozni matnga aylantiradi."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)
        with open(file_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1", file=f, language="uz"
            )
        return (result.text or "").strip() or None
    except Exception as e:  # noqa: BLE001
        print(f"[voice] Whisper xatosi: {e}")
        return None


def transcribe(file_path: str) -> str | None:
    """Ovozli faylni matnga aylantiradi. Mavjud rejimga qarab tanlaydi."""
    if USE_OPENAI:
        text = _transcribe_openai(file_path)
        if text:
            return text
    if USE_VOSK:
        return _transcribe_vosk(file_path)
    return None
