"""Kunlik harajat hisobini yurituvchi Telegram bot.

Foydalanuvchi matn yoki ovozli xabar yuboradi -> bot tahlil qilib saqlaydi.
Kunlik / oylik / yillik hisobot beradi.
"""
import os
import tempfile
import logging
from datetime import date

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN, CURRENCY, USE_OPENAI, USE_VOSK, VOICE_ENABLED
import database as db
from parser import parse_expenses
from voice import transcribe

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Oy nomlari (yillik hisobot uchun)
MONTHS_UZ = [
    "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]

# Pastdagi doimiy tugmalar
KEYBOARD = ReplyKeyboardMarkup(
    [
        ["📊 Bugun", "📆 Bu hafta"],
        ["📅 Bu oy", "🗓 Bu yil"],
        ["🗂 Oy / hafta tanlash"],
        ["↩️ Oxirgini o'chirish", "❓ Yordam"],
    ],
    resize_keyboard=True,
)


def esc(text: str) -> str:
    """Telegram Markdown (v1) maxsus belgilarini ekran qiladi."""
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, "\\" + ch)
    return text


def fmt_money(amount: float) -> str:
    """1234567.0 -> '1 234 567 so'm'"""
    return f"{int(round(amount)):,}".replace(",", " ") + f" {CURRENCY}"


def fmt_report(title: str, total: float, breakdown: list) -> str:
    """Hisobotni chiroyli matn ko'rinishida tayyorlaydi."""
    if not breakdown:
        return f"*{title}*\n\nBu davrda harajat yo'q. 🎉"
    lines = [f"*{title}*\n"]
    for cat, summa, cnt in breakdown:
        ulush = (summa / total * 100) if total else 0
        lines.append(f"• {cat}: *{fmt_money(summa)}*  ({ulush:.0f}%, {cnt} ta)")
    lines.append(f"\n💰 *Jami: {fmt_money(total)}*")
    return "\n".join(lines)


# --- Buyruqlar ---------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = "ovoz va matn" if VOICE_ENABLED else "matn"
    text = (
        "Assalomu alaykum! 👋\n\n"
        "Men *Xisobchi* — kunlik harajatlaringizni yozib boradigan botman.\n\n"
        "✍️ Shunchaki harajatingizni yozing yoki ayting, masalan:\n"
        "  • `non 5000`\n"
        "  • `taksi 12 ming`\n"
        "  • `obed 25000 so'm`\n"
        "  • `internet 1.2 mln`\n\n"
        "🧾 Bir nechta narsani birato'la yozsangiz, *vergul* bilan ajrating:\n"
        "  `non 5000, cola 6 ming, taksi 12000`\n\n"
        "Men summani va kategoriyani avtomatik aniqlab saqlayman.\n\n"
        "📊 Hisobotlar uchun pastdagi tugmalardan foydalaning:\n"
        "  /bugun — kunlik\n"
        "  /oy — oylik\n"
        "  /yil — yillik\n\n"
        f"_Hozirgi rejim: {mode}_"
    )
    await update.message.reply_markdown(text, reply_markup=KEYBOARD)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*Yordam* ❓\n\n"
        "*Harajat qo'shish:*\n"
        "Matn yoki ovozli xabar yuboring. Misollar:\n"
        "  • `non 5000`\n"
        "  • `taksi 12 ming`\n"
        "  • `dorixona 45000 som`\n\n"
        "*Buyruqlar:*\n"
        "  /bugun — bugungi hisobot\n"
        "  /hafta — bu hafta hisoboti\n"
        "  /oy — joriy oy hisoboti\n"
        "  /yil — joriy yil hisoboti\n"
        "  /tanlash — istalgan oy va haftani tanlash\n"
        "  /ochirish — oxirgi yozuvni o'chirish\n"
        "  /start — boshlash\n\n"
        + ("🎤 Ovozli xabar yoqilgan — aytib yuborsangiz ham bo'ladi."
           if VOICE_ENABLED else "🎤 Ovoz hozircha o'chiq.")
    )
    await update.message.reply_markdown(text, reply_markup=KEYBOARD)


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total, breakdown = db.report_day(update.effective_user.id)
    title = f"📊 Bugungi hisobot ({date.today():%d.%m.%Y})"
    await update.message.reply_markdown(fmt_report(title, total, breakdown), reply_markup=KEYBOARD)


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bu hafta (joriy oyning hozirgi haftasi)."""
    today = date.today()
    week = db.current_week_of_month(today)
    total, breakdown, (d1, d2) = db.report_week_of_month(
        update.effective_user.id, today.year, today.month, week
    )
    title = f"📆 Bu hafta ({week}-hafta: {d1}–{d2} {MONTHS_UZ[today.month]})"
    await update.message.reply_markdown(fmt_report(title, total, breakdown), reply_markup=KEYBOARD)


def _month_keyboard() -> InlineKeyboardMarkup:
    """12 oy tugmalari (joriy yil uchun)."""
    year = date.today().year
    rows, row = [], []
    for m in range(1, 13):
        row.append(InlineKeyboardButton(MONTHS_UZ[m], callback_data=f"m:{year}:{m}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def _week_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    """Tanlangan oy uchun: hafta tugmalari + orqaga."""
    n = db.weeks_in_month(year, month)
    rows, row = [], []
    for w in range(1, n + 1):
        row.append(InlineKeyboardButton(f"{w}-hafta", callback_data=f"w:{year}:{month}:{w}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 Oylar", callback_data="months")])
    return InlineKeyboardMarkup(rows)


async def cmd_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Oy tanlash menyusini ochadi."""
    await update.message.reply_markdown(
        f"🗂 *{date.today().year}-yil* — qaysi oyni ko'rmoqchisiz?",
        reply_markup=_month_keyboard(),
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline tugmalar bosilganda."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "months":
        await query.edit_message_text(
            f"🗂 {date.today().year}-yil — qaysi oyni ko'rmoqchisiz?",
            reply_markup=_month_keyboard(),
        )
        return

    parts = data.split(":")

    # Oy hisoboti:  m:YEAR:MONTH
    if parts[0] == "m":
        year, month = int(parts[1]), int(parts[2])
        total, breakdown = db.report_month(user_id, year, month)
        title = f"📅 {MONTHS_UZ[month]} {year} hisoboti"
        text = fmt_report(title, total, breakdown)
        text += "\n\n_Haftalik ko'rish uchun pastdan tanlang:_"
        await query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=_week_keyboard(year, month)
        )
        return

    # Hafta hisoboti:  w:YEAR:MONTH:WEEK
    if parts[0] == "w":
        year, month, week = int(parts[1]), int(parts[2]), int(parts[3])
        total, breakdown, (d1, d2) = db.report_week_of_month(user_id, year, month, week)
        title = f"📆 {MONTHS_UZ[month]} {year}, {week}-hafta ({d1}–{d2})"
        text = fmt_report(title, total, breakdown)
        await query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=_week_keyboard(year, month)
        )
        return


async def cmd_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = date.today()
    total, breakdown = db.report_month(update.effective_user.id)
    title = f"📅 {MONTHS_UZ[today.month]} {today.year} hisoboti"
    await update.message.reply_markdown(fmt_report(title, total, breakdown), reply_markup=KEYBOARD)


async def cmd_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    year = date.today().year
    total, breakdown = db.report_year(user_id)
    title = f"🗓 {year}-yil hisoboti"
    text = fmt_report(title, total, breakdown)

    # Oylar kesimida ham ko'rsatamiz
    months = db.monthly_by_category(user_id, year)
    if months:
        text += "\n\n*Oylar kesimida:*"
        for ym, summa in months:
            m = int(ym.split("-")[1])
            text += f"\n• {MONTHS_UZ[m]}: {fmt_money(summa)}"

    await update.message.reply_markdown(text, reply_markup=KEYBOARD)


async def cmd_delete_last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = db.delete_last(update.effective_user.id)
    if row is None:
        await update.message.reply_text("O'chiradigan yozuv yo'q.", reply_markup=KEYBOARD)
    else:
        await update.message.reply_markdown(
            f"🗑 O'chirildi: *{esc(row['description'])}* — {fmt_money(row['amount'])} ({row['category']})",
            reply_markup=KEYBOARD,
        )


# --- Harajat qo'shish (matn) -------------------------------------------------

async def _save_and_reply(update: Update, text: str):
    items = parse_expenses(text)
    if not items:
        await update.message.reply_text(
            "🤔 Harajat summasini topa olmadim.\n"
            "Masalan shunday yozing: `non 5000` yoki `taksi 12 ming`.\n"
            "Bir nechta narsa bo'lsa, vergul bilan ajrating:\n"
            "`non 5000, cola 6 ming, taksi 12000`",
            reply_markup=KEYBOARD,
        )
        return

    user_id = update.effective_user.id
    for it in items:
        db.add_expense(user_id, it["amount"], it["category"], it["description"])

    if len(items) == 1:
        it = items[0]
        await update.message.reply_markdown(
            f"✅ Saqlandi!\n"
            f"  📝 {esc(it['description'])}\n"
            f"  💵 *{fmt_money(it['amount'])}*\n"
            f"  🏷 {it['category']}",
            reply_markup=KEYBOARD,
        )
    else:
        total = sum(it["amount"] for it in items)
        lines = [f"✅ *{len(items)} ta harajat* saqlandi!\n"]
        for it in items:
            lines.append(
                f"• {esc(it['description'])} — *{fmt_money(it['amount'])}*  ({it['category']})"
            )
        lines.append(f"\n💰 *Jami: {fmt_money(total)}*")
        await update.message.reply_markdown("\n".join(lines), reply_markup=KEYBOARD)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    # Tugma bosilganlarni mos buyruqqa yo'naltiramiz
    mapping = {
        "📊 Bugun": cmd_today,
        "📆 Bu hafta": cmd_week,
        "📅 Bu oy": cmd_month,
        "🗓 Bu yil": cmd_year,
        "🗂 Oy / hafta tanlash": cmd_pick,
        "↩️ Oxirgini o'chirish": cmd_delete_last,
        "❓ Yordam": cmd_help,
    }
    if text in mapping:
        await mapping[text](update, context)
        return

    await _save_and_reply(update, text)


# --- Harajat qo'shish (ovoz) -------------------------------------------------

async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not VOICE_ENABLED:
        await update.message.reply_text(
            "🎤 Ovozli xabar hozircha o'chiq.\n"
            "Harajatni *yozib* yuboring.",
            reply_markup=KEYBOARD,
        )
        return

    await update.message.chat.send_action("typing")
    voice = update.message.voice or update.message.audio
    tg_file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        await tg_file.download_to_drive(tmp_path)
        text = transcribe(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not text:
        await update.message.reply_text(
            "🎤 Ovozni tushuna olmadim, qaytadan urinib ko'ring yoki yozib yuboring.",
            reply_markup=KEYBOARD,
        )
        return

    await update.message.reply_markdown(f"🎤 Eshitdim: _{esc(text)}_")
    await _save_and_reply(update, text)


# --- Ishga tushirish ---------------------------------------------------------

def main():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("yordam", cmd_help))
    app.add_handler(CommandHandler("bugun", cmd_today))
    app.add_handler(CommandHandler("hafta", cmd_week))
    app.add_handler(CommandHandler("oy", cmd_month))
    app.add_handler(CommandHandler("yil", cmd_year))
    app.add_handler(CommandHandler("tanlash", cmd_pick))
    app.add_handler(CommandHandler("ochirish", cmd_delete_last))

    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    logger.info("Bot ishga tushdi. To'xtatish uchun Ctrl+C.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
