@echo off
echo ========================================================
echo  Starting TalentAI Resume-Job Matching System...
echo ========================================================
cd /d "%~dp0"
call .\.venv\Scripts\activate.bat
python app.py
pause
