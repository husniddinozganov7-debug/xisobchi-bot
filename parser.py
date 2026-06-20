"""Matndan harajatni ajratib oladi: summa, kategoriya, izoh.

Ikki rejim:
  1) OpenAI bor bo'lsa — GPT bilan aqlli tahlil (eng aniq).
  2) Bo'lmasa — o'zbek tilini tushunadigan regex-parser (offline, bepul).
"""
import re
import json

from config import USE_OPENAI

# --- Kategoriyalar va ularning kalit so'zlari --------------------------------
CATEGORIES = {
    "Oziq-ovqat": [
        "non", "sut", "tuxum", "go'sht", "gosht", "guruch", "yog'", "yog", "shakar",
        "choy", "qahva", "kofe", "ovqat", "obed", "nonushta", "kechki", "tushlik",
        "meva", "sabzavot", "kartoshka", "piyoz", "pomidor", "olma", "banan",
        "magazin", "do'kon", "dokon", "bozor", "produkt", "suv", "ichimlik", "shirinlik",
        "tort", "somsa", "lavash", "burger", "pitsa", "pizza", "kafe", "restoran",
    ],
    "Transport": [
        "taksi", "taxi", "avtobus", "metro", "marshrutka", "benzin", "yoqilg'i",
        "yoqilgi", "gaz", "yo'l", "yol", "transport", "poyezd", "samolyot", "bilet",
        "parковка", "parkovka", "moy",
    ],
    "Uy-ro'zg'or": [
        "kommunal", "svet", "elektr", "gaz puli", "ijara", "arenda", "kvartira",
        "mebel", "idish", "tozalash", "kir", "sovun", "shampun", "ro'zg'or", "rozgor",
        "internet", "wifi", "uy",
    ],
    "Aloqa": [
        "telefon", "aloqa", "balans", "internet paketi", "sim", "ucell", "beeline",
        "uzmobile", "mobi", "tarif",
    ],
    "Kiyim": [
        "kiyim", "shim", "ko'ylak", "koylak", "poyabzal", "krasovka", "etik", "kurtka",
        "futbolka", "jinsi", "paypoq", "sumka", "soat",
    ],
    "Salomatlik": [
        "dori", "dorixona", "apteka", "shifokor", "vrach", "shifoxona", "klinika",
        "analiz", "ukol", "tibbiy", "stomatolog", "tish",
    ],
    "Ko'ngilochar": [
        "kino", "teatr", "konsert", "park", "attraksion", "o'yin", "oyin", "game",
        "obuna", "podpiska", "netflix", "spotify", "youtube", "bowling", "bilyard",
    ],
    "Ta'lim": [
        "kurs", "o'qish", "oqish", "kitob", "darslik", "repetitor", "universitet",
        "kontrakt", "seminar", "trening", "ta'lim", "talim",
    ],
    "Sovg'a": [
        "sovg'a", "sovga", "tug'ilgan kun", "tugilgan kun", "to'y", "toy", "gul",
        "hadya", "podarok",
    ],
}

# --- O'zbekcha son so'zlari (ovoz / yozma matn uchun) ------------------------
# Birlik va o'nliklar (qo'shiladi): "o'n besh" = 10 + 5 = 15
NUM_WORDS = {
    "nol": 0, "bir": 1, "ikki": 2, "uch": 3, "tort": 4, "to'rt": 4,
    "besh": 5, "olti": 6, "yetti": 7, "etti": 7, "sakkiz": 8,
    "toqqiz": 9, "to'qqiz": 9,
    "on": 10, "o'n": 10, "yigirma": 20, "ottiz": 30, "o'ttiz": 30,
    "qirq": 40, "ellik": 50, "oltmish": 60, "yetmish": 70, "etmish": 70,
    "sakson": 80, "toqson": 90, "to'qson": 90,
    "yarim": 0.5,
}
HUNDRED_WORDS = {"yuz"}
# Ko'paytirgichlar (raqam bilan ham: "12 ming", so'z bilan ham: "o'n besh ming")
SCALE_WORDS = {
    "ming": 1_000, "minг": 1_000, "k": 1_000,
    "mln": 1_000_000, "million": 1_000_000, "milion": 1_000_000, "mil": 1_000_000,
    "mlrd": 1_000_000_000, "milliard": 1_000_000_000,
}
# Sanoqni bildiruvchi belgilar: "ikki TA non" -> 2 bu narx emas, dona soni
QTY_MARKERS = {"ta", "dona", "tup", "kg", "litr", "metr"}
# So'mni bildiradigan, summaga ta'sir qilmaydigan so'zlar
_CURRENCY_WORDS = {"so'm", "som", "sum", "soum", "uzs", "pul"}

# Eskicha moslik uchun (boshqa joyda ishlatilishi mumkin)
_MULTIPLIERS = SCALE_WORDS


def _normalize(text: str) -> str:
    """Kichik harf + apostroflarni bir xil qilish + raqam ajratgichlarini birlashtirish.

    Masalan: "5 000" -> "5000", "1.250" -> "1250", lekin "1.2" (kasr) tegmaydi.
    """
    t = text.lower()
    for ch in ["ʻ", "`", "´", "’", "‘", "ʼ", "´"]:
        t = t.replace(ch, "'")
    # Minglik ajratgichlarni (bo'shliq/nuqta/vergul + roppa-rosa 3 raqam) birlashtiramiz
    for _ in range(5):
        t = re.sub(r"(\d)[  .,](\d{3})(?=\D|$)", r"\1\2", t)
    return t


def _classify(tok: str):
    """Token raqam komponentimi? ('num', qiymat) / ('hund', 100) / ('scale', mult) / None"""
    tok = tok.strip(".,!?;:()-")
    if not tok or tok in _CURRENCY_WORDS:
        return None
    if tok in SCALE_WORDS:
        return ("scale", SCALE_WORDS[tok])
    if tok in HUNDRED_WORDS:
        return ("hund", 100)
    if tok in NUM_WORDS:
        return ("num", NUM_WORDS[tok])
    if re.fullmatch(r"\d+(?:[.,]\d+)?", tok):
        return ("num", float(tok.replace(",", ".")))
    return None


def _accum(comps) -> float:
    """Raqam komponentlaridan qiymat yig'adi. ["o'n","besh","ming"] -> 15000."""
    result = 0.0
    current = 0.0
    for typ, val in comps:
        if typ == "num":
            current += val
        elif typ == "hund":
            current = (current or 1) * 100
        elif typ == "scale":
            result += (current or 1) * val
            current = 0.0
    return result + current


def _extract(text: str):
    """Matndan summa + izoh + kategoriyani ajratadi. dict yoki None qaytaradi."""
    norm = _normalize(text)
    tokens = norm.split()
    comps = [_classify(t) for t in tokens]

    # Ketma-ket kelgan raqam tokenlarini "guruh" (run) qilamiz
    runs = []  # (qiymat, indekslar, sanoqmi)
    i = 0
    n = len(tokens)
    while i < n:
        if comps[i] is None:
            i += 1
            continue
        j = i
        group = []
        idxs = []
        while j < n and comps[j] is not None:
            group.append(comps[j])
            idxs.append(j)
            j += 1
        value = _accum(group)
        # Guruhdan keyingi so'z "ta/dona..." bo'lsa -> bu sanoq, narx emas
        nxt = tokens[j].strip(".,!?;:()-") if j < n else ""
        is_qty = nxt in QTY_MARKERS
        runs.append((value, idxs, is_qty))
        i = j

    # Narx = sanoq bo'lmagan guruhlardan eng kattasi
    price_runs = [r for r in runs if not r[2] and r[0] > 0]
    if not price_runs:
        return None
    amount, amount_idxs, _ = max(price_runs, key=lambda r: r[0])
    amount_set = set(amount_idxs)

    # Izoh: narx tokenlari va valyuta so'zlaridan tashqari hammasi
    desc_tokens = [
        tokens[k].strip(".,!?;:()-")
        for k in range(n)
        if k not in amount_set and tokens[k].strip(".,!?;:()-") not in _CURRENCY_WORDS
    ]
    description = re.sub(r"\s+", " ", " ".join(desc_tokens)).strip(" -.,")
    description = description.capitalize() if description else "Harajat"

    return {
        "amount": float(amount),
        "category": categorize(text),
        "description": description,
    }


def categorize(text: str) -> str:
    """Matndan kategoriyani aniqlaydi."""
    low = " " + text.lower() + " "
    best_cat = "Boshqa"
    for cat, words in CATEGORIES.items():
        for w in words:
            if w in low:
                return cat
    return best_cat


def parse_with_regex(text: str):
    """Regex/so'z-parser orqali harajatni ajratadi. dict yoki None qaytaradi.

    Ham raqamli ('5000', '12 ming', '1.2 mln'), ham harf bilan yozilgan
    ('besh ming', 'o'n besh ming', 'yigirma besh ming') sonlarni tushunadi.
    """
    return _extract(text)


# Bir nechta harajatni ajratadigan belgilar: vergul, yangi qator, nuqta-vergul,
# "va", "hamda", "+", "&"
_SPLIT_RE = re.compile(r"[,\n;]+|\bva\b|\bhamda\b|[&+]")


def parse_with_openai(text: str):
    """GPT orqali bir yoki bir nechta harajatni ajratadi. Ro'yxat qaytaradi (yoki [])."""
    try:
        from openai import OpenAI
        from config import OPENAI_API_KEY

        client = OpenAI(api_key=OPENAI_API_KEY)
        cats = ", ".join(list(CATEGORIES.keys()) + ["Boshqa"])
        prompt = (
            "Sen o'zbek tilidagi harajat matnini tahlil qiluvchi yordamchisan. "
            "Matnda bir yoki bir nechta xarid bo'lishi mumkin (masalan: '2 ta non 10 ming, cola 6 ming'). "
            "HAR BIR xaridni alohida ajrat: summa (so'mda, butun son), kategoriya va qisqa izoh. "
            f"Kategoriya faqat shulardan biri bo'lsin: {cats}. "
            "'ming'=1000, 'mln'=1000000 ekanini hisobga ol. "
            "Faqat JSON qaytar: {\"items\": [{\"amount\": number, \"category\": string, \"description\": string}]}. "
            "Agar harajat bo'lmasa, items ni bo'sh ro'yxat qil.\n\n"
            f"Matn: {text}"
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        data = json.loads(resp.choices[0].message.content)
        items = []
        for it in data.get("items", []):
            amount = float(it.get("amount", 0) or 0)
            if amount <= 0:
                continue
            items.append({
                "amount": amount,
                "category": it.get("category", "Boshqa") or "Boshqa",
                "description": (it.get("description") or "Harajat").strip(),
            })
        return items
    except Exception as e:  # noqa: BLE001
        print(f"[parser] OpenAI xatosi, regex'ga o'tildi: {e}")
        return None  # None = xato (regex'ga o'tamiz), [] = harajat yo'q


def parse_expenses(text: str) -> list:
    """Asosiy funksiya: matndan BIR yoki BIR NECHTA harajatni ajratadi.

    OpenAI bor bo'lsa undan foydalanadi (eng aniq, ajratuvchisiz ham ishlaydi).
    Aks holda matnni vergul / yangi qator / 'va' bo'yicha bo'lib, har bir
    bo'lakni alohida harajat sifatida o'qiydi.
    """
    if USE_OPENAI:
        result = parse_with_openai(text)
        if result is not None:  # None = xato; ro'yxat (bo'sh bo'lsa ham) = natija
            return result

    # Regex rejimi: bo'laklarga ajratamiz
    parts = [p.strip() for p in _SPLIT_RE.split(text) if p.strip()]
    items = []
    for part in parts:
        r = parse_with_regex(part)
        if r:
            items.append(r)

    # Hech narsa topilmasa, butun matnni bitta harajat sifatida sinab ko'ramiz
    if not items:
        r = parse_with_regex(text)
        if r:
            items = [r]
    return items


def parse_expense(text: str):
    """Eskicha moslik uchun: bitta harajat qaytaradi (yoki None)."""
    items = parse_expenses(text)
    return items[0] if items else None
