"""Kommandozeile: python -m hbs_heizlast.cli eingabe.pdf ausgabe.pdf"""
import sys
from .parser import parse_pdf
from .calc import Settings, berechne
from .report import build_pdf, default_meta

if __name__ == "__main__":
    p = parse_pdf(sys.argv[1])
    s = Settings()
    build_pdf(sys.argv[2], p, s, berechne(p, s), default_meta(p))
    print("fertig:", sys.argv[2])
