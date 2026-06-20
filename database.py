"""SQLite baza bilan ishlash — harajatlarni saqlash va hisobotlar."""
import sqlite3
import calendar
from datetime import datetime, date
from contextlib import contextmanager

from config import DB_PATH


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Jadvallarni yaratadi (agar mavjud bo'lmasa)."""
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      REAL    NOT NULL,
                category    TEXT    NOT NULL,
                description TEXT,
                created_at  TEXT    NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_date ON expenses(user_id, created_at)"
        )


def add_expense(user_id: int, amount: float, category: str, description: str) -> int:
    """Yangi harajat qo'shadi, qo'shilgan yozuv id'sini qaytaradi."""
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, description, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, description, now),
        )
        return cur.lastrowid


def delete_last(user_id: int):
    """Foydalanuvchining oxirgi harajatini o'chiradi. O'chirilgan yozuvni qaytaradi (yoki None)."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM expenses WHERE id = ?", (row["id"],))
        return dict(row)


def _sum_between(user_id: int, start: str, end: str):
    """[start, end) oralig'idagi harajatlarni kategoriya bo'yicha yig'adi.
    Qaytaradi: (umumiy_summa, [(kategoriya, summa, soni), ...])"""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT category, SUM(amount) AS total, COUNT(*) AS cnt
            FROM expenses
            WHERE user_id = ? AND created_at >= ? AND created_at < ?
            GROUP BY category
            ORDER BY total DESC
            """,
            (user_id, start, end),
        ).fetchall()
    total = sum(r["total"] for r in rows)
    breakdown = [(r["category"], r["total"], r["cnt"]) for r in rows]
    return total, breakdown


def report_day(user_id: int, day: date | None = None):
    day = day or date.today()
    start = datetime(day.year, day.month, day.day).isoformat()
    # ertangi kun boshigacha
    end = datetime(day.year, day.month, day.day, 23, 59, 59).isoformat()
    return _sum_between(user_id, start, end)


def report_month(user_id: int, year: int | None = None, month: int | None = None):
    today = date.today()
    year = year or today.year
    month = month or today.month
    start = datetime(year, month, 1).isoformat()
    if month == 12:
        end = datetime(year + 1, 1, 1).isoformat()
    else:
        end = datetime(year, month + 1, 1).isoformat()
    return _sum_between(user_id, start, end)


def weeks_in_month(year: int, month: int) -> int:
    """Oydagi haftalar soni (har 7 kun = 1 hafta, oxirgisi qisqa bo'lishi mumkin)."""
    last = calendar.monthrange(year, month)[1]
    return (last + 6) // 7  # ceil(last / 7)


def report_week_of_month(user_id: int, year: int, month: int, week: int):
    """Oyning N-haftasi hisoboti. 1-hafta = 1-7 kun, 2-hafta = 8-14 kun, ...

    Qaytaradi: (umumiy_summa, breakdown, (boshlanish_kuni, tugash_kuni))
    """
    last = calendar.monthrange(year, month)[1]
    start_day = (week - 1) * 7 + 1
    end_day = min(week * 7, last)
    if start_day > last:  # bunday hafta yo'q
        return 0, [], (start_day, end_day)
    start = datetime(year, month, start_day).isoformat()
    end = datetime(year, month, end_day, 23, 59, 59).isoformat()
    total, breakdown = _sum_between(user_id, start, end)
    return total, breakdown, (start_day, end_day)


def current_week_of_month(day: date | None = None) -> int:
    """Bugungi kun oyning nechanchi haftasiga to'g'ri kelishini qaytaradi."""
    day = day or date.today()
    return (day.day - 1) // 7 + 1


def report_year(user_id: int, year: int | None = None):
    year = year or date.today().year
    start = datetime(year, 1, 1).isoformat()
    end = datetime(year + 1, 1, 1).isoformat()
    return _sum_between(user_id, start, end)


def monthly_by_category(user_id: int, year: int):
    """Yillik hisobot uchun: har oy bo'yicha umumiy summa."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT substr(created_at, 1, 7) AS ym, SUM(amount) AS total
            FROM expenses
            WHERE user_id = ? AND created_at >= ? AND created_at < ?
            GROUP BY ym
            ORDER BY ym
            """,
            (user_id, f"{year}-01-01", f"{year + 1}-01-01"),
        ).fetchall()
    return [(r["ym"], r["total"]) for r in rows]
