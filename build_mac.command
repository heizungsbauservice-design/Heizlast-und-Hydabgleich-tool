#!/bin/bash
# HBS Heizlast-Tool: baut "HBS Heizlast.app" (einmalig auf dem Mac ausfuehren, Doppelklick)
# Voraussetzung: Python 3.11 oder neuer von python.org (enthaelt Tkinter)
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --noconfirm --clean --windowed --name "HBS Heizlast" --icon icon.icns \
  --add-data "hbs_heizlast/assets:assets" --collect-all tkinterdnd2 run_app.py
echo
echo "Fertig: dist/HBS Heizlast.app  ->  in den Ordner Programme ziehen"
read -p "Enter zum Schliessen"
