@echo off
REM HBS Heizlast-Tool: baut HBS_Heizlast.exe (einmalig auf einem Windows-PC ausfuehren)
REM Voraussetzung: Python 3.11 oder neuer von python.org (beim Installieren "Add to PATH" anhaken)
cd /d "%~dp0"
py -3 -m venv .venv || python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --noconfirm --clean --onefile --windowed --name "HBS_Heizlast" --icon icon.ico ^
  --add-data "hbs_heizlast\assets;assets" --collect-all tkinterdnd2 run_app.py
echo.
echo Fertig: dist\HBS_Heizlast.exe
pause
