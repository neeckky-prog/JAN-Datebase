@echo off
REM ── Y&Y JAN Nutrition Database — one-click start ──────────────────────────
cd /d "%~dp0"

echo Installing dependencies (first run only)...
python -m pip install -r requirements.txt

echo.
echo Your PC's IP addresses (use one of these on your phone, port 8000):
ipconfig | findstr /C:"IPv4"
echo.

python app.py
pause
