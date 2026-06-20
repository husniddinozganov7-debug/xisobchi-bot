@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   XISOBCHI BOT - ishga tushirilmoqda...
echo ============================================

REM Virtual muhit yo'q bo'lsa yaratamiz
if not exist ".venv\" (
    echo [1/3] Virtual muhit yaratilmoqda...
    python -m venv .venv
)

echo [2/3] Kutubxonalar o'rnatilmoqda...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt

echo [3/3] Bot ishga tushmoqda...
python bot.py

pause
