# 🧾 Xisobchi — Kunlik harajat boti

Telegram bot: matn yoki ovozli xabar orqali kunlik harajatlaringizni yozib boradi,
avtomatik tahlil qiladi va **kunlik / oylik / yillik** hisobot beradi.

## Imkoniyatlar

- ✍️ **Matnli xabar**: `non 5000`, `taksi 12 ming`, `internet 1.2 mln`
- 🎤 **Ovozli xabar**: aytib yuborasiz, bot eshitib yozib qo'yadi *(OpenAI kaliti bilan)*
- 🏷 **Avtomatik kategoriya**: Oziq-ovqat, Transport, Aloqa, Salomatlik va h.k.
- 📊 **Hisobotlar**: bugun / bu oy / bu yil (kategoriya va foizlar bilan)
- 🗑 Oxirgi yozuvni o'chirish
- 💾 Ma'lumotlar `harajatlar.db` (SQLite) faylida saqlanadi

---

## 1-qadam: Python o'rnatish

Kompyuteringizda Python yo'q. Quyidagidan o'rnating:

1. https://www.python.org/downloads/ saytiga kiring
2. **"Download Python 3.12"** tugmasini bosing
3. O'rnatishda **"Add Python to PATH"** belgisini ✅ qo'ying (juda muhim!)
4. "Install Now" bosing

O'rnatgach, PowerShell'da tekshiring:
```
python --version
```
`Python 3.12.x` chiqsa — tayyor.

---

## 2-qadam: Telegram bot tokenini olish

1. Telegramda **@BotFather** ni oching
2. `/newbot` yuboring
3. Botga nom va username bering (username `bot` bilan tugashi kerak)
4. BotFather sizga **token** beradi, masalan:
   `7123456789:AAH...xyz`

---

## 3-qadam: Sozlash

1. `.env.example` faylidan nusxa olib, nomini `.env` qiling.
2. `.env` faylini ochib tokenni qo'ying:

```
BOT_TOKEN=7123456789:AAH...xyz
OPENAI_API_KEY=
CURRENCY=so'm
```

> 🎤 **Ovozli xabar** va aqlli tahlil kerak bo'lsa, `OPENAI_API_KEY` ga
> https://platform.openai.com/api-keys dan olgan kalitni qo'ying.
> Bo'sh qoldirsangiz ham bot matn rejimida to'liq ishlayveradi.

---

## 4-qadam: Ishga tushirish

### Eng oson yo'l (Windows)
`ishga_tushirish.bat` faylini ikki marta bosing. U o'zi kutubxonalarni o'rnatib,
botni ishga tushiradi.

### Qo'lda (PowerShell)
```powershell
cd D:\xisobchi
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python bot.py
```

"Bot ishga tushdi" yozuvi chiqsa — Telegramda botingizni ochib `/start` bosing.

---

## Foydalanish

| Buyruq | Vazifasi |
|--------|----------|
| harajatni yozish | `taksi 12000`, `obed 25 ming` |
| 🎤 ovoz | harajatni aytib yuborish |
| `/bugun` | bugungi hisobot |
| `/oy` | joriy oy hisoboti |
| `/yil` | joriy yil hisoboti |
| `/ochirish` | oxirgi yozuvni o'chirish |
| `/yordam` | yordam |

Pastdagi tugmalar orqali ham boshqarish mumkin.

---

## Fayllar tuzilishi

```
xisobchi/
├── bot.py            # Asosiy bot (buyruqlar, tugmalar)
├── parser.py         # Matndan summa/kategoriyani ajratish
├── voice.py          # Ovozni matnga aylantirish (Whisper)
├── database.py       # SQLite baza va hisobotlar
├── config.py         # Sozlamalar (.env dan)
├── requirements.txt  # Kerakli kutubxonalar
├── .env              # Tokenlar (o'zingiz yaratasiz)
└── harajatlar.db     # Baza (avtomatik yaratiladi)
```
