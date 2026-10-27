"""Volumenströme Fußbodenheizung und Förderhöhe der Umwälzpumpe."""
import math
import re
from dataclasses import dataclass

C_WASSER = 1.163          # Wh/(kg·K)
RHO = 995.0               # kg/m³ bei ca. 32 °C
NU = 0.76e-6              # m²/s kinematische Viskosität bei ca. 32 °C
G = 9.81

ROHRE = {                 # Bezeichnung -> Innendurchmesser in mm
    "14×2": 10.0,
    "16×2": 12.0,
    "17×2": 13.0,
    "20×2": 16.0,
}


@dataclass
class Settings:
    spreizung: float = 5.0           # K
    rohr: str = "17×2"
    verlegeabstand: float = 15.0     # cm
    max_kreislaenge: float = 100.0   # m inkl. Anbindeleitung
    anbindung: float = 10.0          # m Vor- + Rücklauf Verteiler -> Raum
    dp_verteiler: float = 50.0       # mbar Ventil, Durchflussanzeiger, Verteiler
    dp_zusatz: float = 100.0         # mbar Wärmemengenzähler, Strangregulierventil, Armaturen
    netz_laenge: float = 0.0         # m Vor- + Rücklauf Keller -> ungünstigster Verteiler (0 = aus Gebäudehöhe)
    netz_r: float = 100.0            # Pa/m Auslegungs-Druckgefälle
    netz_zuschlag: float = 30.0      # % Einzelwiderstände Rohrnetz
    dp_erzeuger: float = 0.0         # mbar (0 bei Puffer / hydraulischer Weiche)
    sicherheit: float = 10.0         # % Sicherheitszuschlag
    grenze_messbereich: float = 0.4  # l/min


def l_min(q_watt: float, dt: float) -> float:
    return q_watt / (C_WASSER * dt) / 60.0 if q_watt > 0 else 0.0


def r_pa_m(v_lmin: float, di_mm: float) -> float:
    """Druckgefälle im glatten Kunststoffrohr (Darcy-Weisbach, Blasius / laminar)."""
    if v_lmin <= 0:
        return 0.0
    d = di_mm / 1000.0
    v = (v_lmin / 60000.0) / (math.pi * d * d / 4)
    re_ = v * d / NU
    lam = max(64 / re_, 0.3164 / re_ ** 0.25)
    return lam / d * RHO * v * v / 2


@dataclass
class Kreis:
    raum: str
    flaeche: float
    rohrlaenge_raum: float
    anzahl: int
    laenge: float
    volumenstrom: float
    dp_mbar: float


def kreis_fuer_raum(room, vs: float, s: Settings) -> Kreis:
    rohr_raum = room.flaeche * 100.0 / s.verlegeabstand
    nutz = max(s.max_kreislaenge - s.anbindung, 1.0)
    n = max(1, math.ceil(rohr_raum / nutz))
    laenge = rohr_raum / n + s.anbindung
    v_k = vs / n
    dp = r_pa_m(v_k, ROHRE[s.rohr]) * laenge * 1.10 / 100.0   # +10 % Bögen, mbar
    return Kreis(room.name, room.flaeche, rohr_raum, n, laenge, v_k, dp)


@dataclass
class Ergebnis:
    zeilen: list
    summe_w: float
    summe_lmin: float
    summe_m3h: float
    gebaeude_m3h: float
    worst: Kreis
    worst_room: object
    dp_kreis: float
    dp_verteiler: float
    dp_zusatz: float
    netz_laenge: float
    dp_netz: float
    dp_erzeuger: float
    dp_summe_ohne: float
    dp_sicherheit: float
    dp_gesamt: float
    foerderhoehe_m: float


def norm_etage(e: str) -> str:
    """Langnamen (Keller, Erdgeschoss, 1. Obergeschoss, Dachgeschoss …) auf Kurzform bringen."""
    t = e.strip()
    low = t.lower()
    m = re.match(r"^(\d+)\.?\s*", low)
    n = m.group(1) if m else ""
    if low.startswith(("keller", "untergeschoss")) or low in ("kg", "ug"):
        return "KG"
    if "erdgeschoss" in low:
        return "EG"
    if "obergeschoss" in low:
        return f"OG{n}" if n and n != "1" else "OG"
    if "dachgeschoss" in low:
        m2 = re.search(r"(\d+)", low)
        return f"DG{m2.group(1)}" if m2 else "DG"
    if "spitzboden" in low:
        return "SB"
    return t


def etage_rang(e: str) -> float:
    e = norm_etage(e)
    if re.match(r"^(KG|UG)", e):
        return -10
    if e == "EG":
        return 0
    m = re.match(r"^(?:(\d+)\.?OG|OG(\d*))$", e)
    if m:
        return int(m.group(1) or m.group(2) or 1)
    m = re.match(r"^DG(\d*)$", e)
    if m:
        return 20 + int(m.group(1) or 0)
    if re.match(r"^(SB|SP)", e):
        return 40
    return 30


def etage_name(e: str) -> str:
    e = norm_etage(e)
    if e == "EG":
        return "Erdgeschoss"
    m = re.match(r"^(?:(\d+)\.?OG|OG(\d*))$", e)
    if m:
        n = m.group(1) or m.group(2)
        return f"{n}. Obergeschoss" if n and n != "1" else "Obergeschoss"
    m = re.match(r"^DG(\d*)$", e)
    if m:
        return f"Dachgeschoss {m.group(1)}" if m.group(1) else "Dachgeschoss"
    return {"KG": "Kellergeschoss", "UG": "Untergeschoss", "SB": "Spitzboden"}.get(e, e)


def etage_kurz(e: str) -> str:
    e = norm_etage(e)
    return "OG" if e in ("OG1", "1OG", "1.OG") else e


def einheit_key(nr: str):
    m = re.search(r"(\d+)", nr)
    return (int(m.group(1)) if m else 0, nr)


def berechne(project, s: Settings) -> Ergebnis:
    rooms = sorted(project.rooms, key=lambda r: (etage_rang(r.etage), einheit_key(r.nr), -r.heizlast, r.order))
    zeilen = []
    for r in rooms:
        zeilen.append((r, l_min(r.heizlast, s.spreizung)))
    summe_w = sum(r.heizlast for r, _ in zeilen if r.heizlast > 0)
    summe_lmin = sum(v for _, v in zeilen)
    worst, worst_room = None, None
    for r, v in zeilen:
        if v <= 0 or r.flaeche <= 0:
            continue
        k = kreis_fuer_raum(r, v, s)
        if worst is None or k.dp_mbar > worst.dp_mbar:
            worst, worst_room = k, r
    dp_kreis = worst.dp_mbar if worst else 0.0
    netz_l = s.netz_laenge or 2 * ((project.gebaeudehoehe or 10.0) + 15.0)
    dp_netz = netz_l * s.netz_r * (1 + s.netz_zuschlag / 100) / 100.0
    ohne = dp_kreis + s.dp_verteiler + s.dp_zusatz + dp_netz + s.dp_erzeuger
    sich = ohne * s.sicherheit / 100
    ges = ohne + sich
    h = math.ceil(ges * 100 / (RHO * G) * 10) / 10      # mbar -> m, auf 0,1 m aufgerundet
    geb = project.norm_heizlast / (C_WASSER * s.spreizung) / 1000 if project.norm_heizlast else 0
    return Ergebnis(zeilen, summe_w, summe_lmin, summe_lmin * 0.06, geb, worst, worst_room, dp_kreis,
                    s.dp_verteiler, s.dp_zusatz, netz_l, dp_netz, s.dp_erzeuger, ohne, sich, ges, h)
