"""Liest raumweise Heizlastberechnungen (DIN EN 12831) aus PDF.

Unterstützte Formate: Hottgenroth/HottCAD-Ausdruck, heiz.report (Heizungs Auslegung).
"""
import re
from dataclasses import dataclass, field
from pypdf import PdfReader

NUM = r"-?\d{1,3}(?:\.\d{3})*(?:,\d+)?|-?\d+(?:,\d+)?"


def de_num(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


@dataclass
class Room:
    etage: str
    nr: str
    name: str
    heizlast: float = 0.0
    flaeche: float = 0.0
    order: int = 0


@dataclass
class Project:
    objekt: str = ""
    planer: str = ""
    projekt_nr: str = ""
    datum: str = ""
    norm_heizlast: float = 0.0
    theta_e: str = ""
    gebaeudehoehe: float = 0.0
    software: str = ""
    norm: str = "DIN EN 12831-1:2020 mit nationalem Anhang"
    rooms: list = field(default_factory=list)


def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _pages(reader, progress):
    n = len(reader.pages)
    out = []
    for i, page in enumerate(reader.pages):
        if progress:
            progress(i + 1, n)
        try:
            text = page.extract_text(extraction_mode="layout")
        except Exception:
            text = page.extract_text() or ""
        out.append([l for l in (_clean(x) for x in text.splitlines()) if l])
    return out


def parse_pdf(path: str, progress=None) -> Project:
    reader = PdfReader(path)
    pages = _pages(reader, progress)
    if any(l in ("heiz.report", "Heizungs Auslegung") for pg in pages[:3] for l in pg):
        return _parse_heizreport(pages)
    return _parse_hottgenroth(reader, pages)


def _parse_heizreport(pages) -> Project:
    """heiz.report: eine Seite pro Raum, Kopf „Heizungs Auslegung“, darunter der Raumname."""
    p = Project(software="heiz.report")
    first = pages[0] if pages else []
    if "Projekt" in first:
        k = first.index("Projekt")
        addr = []
        for l in first[k + 1:]:
            if l == "Klimadaten" or re.match(r"^[\d +/()-]{6,}$", l) or "@" in l:
                break
            if l not in addr:
                addr.append(l)
        if addr:
            p.objekt = ", ".join(addr)
    if "Berechnung erstellt durch" in first:
        k = first.index("Berechnung erstellt durch")
        if k + 1 < len(first):
            p.planer = first[k + 1]
    for pg in pages:
        for l in pg:
            m = re.match(r"Normaußentemperatur: (" + NUM + r") ?°C", l)
            if m and not p.theta_e:
                p.theta_e = m.group(1)
            m = re.search(r"(\d{2}\.\d{2}\.\d{4}) \d{1,2}:\d{2} Uhr .*Projekt-ID (\S+)", l)
            if m and not p.datum:
                p.datum, p.projekt_nr = m.group(1), m.group(2)
            m = re.search(r"nach (DIN\S* ?\S*12831-1:\S+)", l)
            if m and p.norm.startswith("DIN EN 12831-1:2020 mit"):
                p.norm = m.group(1)
        if not any(l.startswith("Raumfläche Ar") for l in pg):
            continue
        name = ""
        if "Heizungs Auslegung" in pg:
            k = pg.index("Heizungs Auslegung")
            if k + 1 < len(pg):
                name = pg[k + 1]
        r = Room(etage="", nr="", name=name or f"Raum {len(p.rooms) + 1}", order=len(p.rooms))
        found = False
        for l in pg:
            m = re.match(r"Etage (.+?)(?: Raumvolumen.*)?$", l)
            if m and not r.etage:
                r.etage = m.group(1).strip()
            m = re.match(r"Raumfläche Ar (" + NUM + r") ?m", l)
            if m:
                r.flaeche = de_num(m.group(1))
            m = re.match(r"Heizlast .*QHL (" + NUM + r")\b", l)
            if m:
                r.heizlast = de_num(m.group(1))
                found = True
        if found:
            p.rooms.append(r)
    return p


def _parse_hottgenroth(reader, pages) -> Project:
    p = Project()
    cur = None
    for i, lines in enumerate(pages):
        if i == 0 and lines:
            p.planer = lines[0]
        for j, l in enumerate(lines):
            m = re.match(r"Geschoss (\S+) Raum-Nr\. (.*?) Bez\.: (.+)$", l)
            if m:
                name = re.sub(r"\s+\d{3}$", "", m.group(3).strip())
                cur = Room(m.group(1), m.group(2).strip(), name, order=len(p.rooms))
                continue
            if cur and cur.flaeche == 0:
                m = re.search(r"Raumfläche A ?NGF,i (" + NUM + r") m", l)
                if m:
                    cur.flaeche = de_num(m.group(1))
            m = re.search(r"Normheizlast .*Φ ?HL,i (" + NUM + r") W\b", l)
            if m and cur:
                cur.heizlast = de_num(m.group(1))
                p.rooms.append(cur)
                cur = None
                continue
            if not p.norm_heizlast:
                m = re.match(r"Norm-Heizlast Φ ?HL (" + NUM + r") W", l)
                if m:
                    p.norm_heizlast = de_num(m.group(1))
            if not p.projekt_nr and l.startswith("Projekt-Nr. / Bezeichnung"):
                rest = l[len("Projekt-Nr. / Bezeichnung"):].strip()
                if not rest and j + 1 < len(lines):
                    rest = lines[j + 1]
                if " / " in rest:
                    p.projekt_nr, obj = [x.strip() for x in rest.split(" / ", 1)]
                    p.objekt = p.objekt or obj
            if not p.datum:
                m = re.search(r"Datum: ?(\d{2}\.\d{2}\.\d{4})", l)
                if m:
                    p.datum = m.group(1)
                elif l == "Datum:" and j + 1 < len(lines) and re.match(r"\d{2}\.\d{2}\.\d{4}$", lines[j + 1]):
                    p.datum = lines[j + 1]
            if not p.theta_e:
                m = re.match(r"Auslegungsaußentemperatur θ ?e (" + NUM + r") ?°C", l)
                if m:
                    p.theta_e = m.group(1)
            if not p.gebaeudehoehe:
                m = re.search(r"Höhe h ?build (" + NUM + r") m", l)
                if m:
                    p.gebaeudehoehe = de_num(m.group(1))
            if not p.software and "Hottgenroth" in l:
                p.software = "Hottgenroth / HottCAD"
    if not p.objekt:
        for page in reader.pages[:2]:
            t = page.extract_text() or ""
            m = re.search(r"12831-1:2020\s*\n\s*(.+)", t)
            if m:
                p.objekt = _clean(m.group(1))
                break
    return p
