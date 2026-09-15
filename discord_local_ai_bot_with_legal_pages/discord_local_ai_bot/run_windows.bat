@echo off
chcp 65001 > nul
cd /d "%~dp0"

if not exist ".venv" (
    echo [1/3] Python 가상환경 생성...
    py -m venv .venv
)

echo [2/3] 패키지 설치/확인...
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt

echo [3/3] Discord Local AI Bot 시작...
python bot.py

pause
