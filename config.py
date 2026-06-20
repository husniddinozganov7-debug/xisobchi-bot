"""Sozlamalar — .env faylidan o'qiladi."""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
CURRENCY = os.getenv("CURRENCY", "so'm").strip()

# OpenAI mavjudligini bir joyda aniqlaymiz
USE_OPENAI = bool(OPENAI_API_KEY)

_BASE = os.path.dirname(os.path.abspath(__file__))

# Vosk (bepul, lokal ovoz modeli) mavjudligini aniqlaymiz
VOSK_MODEL_PATH = os.path.join(_BASE, "model_uz")
USE_VOSK = os.path.isdir(VOSK_MODEL_PATH)

# Groq (bepul ovoz)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
USE_GROQ = bool(GROQ_API_KEY)

# Ovozli xabar umuman yoqilganmi?
VOICE_ENABLED = USE_OPENAI or USE_VOSK or USE_GROQ

# Baza fayli
DB_PATH = os.path.join(_BASE, "harajatlar.db")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi! .env faylini yarating va @BotFather'dan olgan tokenni qo'ying."
    )
