"""Erzeugt die HBS-Auslegungsunterlage als PDF."""
import os
import sys
from datetime import date
from itertools import groupby

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

from .calc import etage_kurz, etage_name

INK = colors.HexColor("#111C26")
GREY = colors.HexColor("#4A5763")
LINE = colors.HexColor("#D5DAE0")
ACCENT = colors.HexColor("#C2410C")
SOFT = colors.HexColor("#F4F5F7")

FIRMA = "HBS GmbH · Heizungsbau und Service"
ADRESSE = "Grouvener Straße 75 · 50189 Elsdorf"
WEB = "www.heizungs-bau-service.de"


def asset(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(base, "assets", name)
    if not os.path.exists(p):
        p = os.path.join(base, "hbs_heizlast", "assets", name)
    return p


_fonts_done = False


def _fonts():
    global _fonts_done
    if _fonts_done:
        return
    for n in ["Inter-Regular", "Inter-SemiBold", "InterDisplay-SemiBold", "InterDisplay-Bold", "InterDisplay-ExtraBold"]:
        pdfmetrics.registerFont(TTFont(n, asset(n + ".ttf")))
    pdfmetrics.registerFontFamily("Inter-Regular", normal="Inter-Regular", bold="Inter-SemiBold",
                                  italic="Inter-Regular", boldItalic="Inter-SemiBold")
    _fonts_done = True


def de(x, d=0):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def S(name, **kw):
    base = dict(fontName="Inter-Regular", fontSize=9.2, leading=13.4, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)


ST = {
    "body": S("body"),
    "small": S("small", fontSize=8, leading=11, textColor=GREY),
    "meta": S("meta", fontSize=8.2, leading=12.2, textColor=GREY, alignment=TA_RIGHT),
    "kicker": S("kicker", fontName="InterDisplay-SemiBold", fontSize=8, leading=10, textColor=ACCENT),
    "h1": S("h1", fontName="InterDisplay-ExtraBold", fontSize=21, leading=24),
    "sub": S("sub", fontSize=10.5, leading=14, textColor=GREY),
    "h2": S("h2", fontName="InterDisplay-ExtraBold", fontSize=12.5, leading=16, spaceBefore=0, spaceAfter=0),
    "dt": S("dt", fontName="InterDisplay-SemiBold", fontSize=7.4, leading=13.4, textColor=ACCENT),
    "kv": S("kv", fontName="InterDisplay-ExtraBold", fontSize=16, leading=19),
    "kl": S("kl", fontSize=7.8, leading=10, textColor=GREY),
    "th": S("th", fontName="InterDisplay-SemiBold", fontSize=7.4, leading=9, textColor=colors.white),
    "thr": S("thr", fontName="InterDisplay-SemiBold", fontSize=7.4, leading=9, textColor=colors.white, alignment=TA_RIGHT),
    "td": S("td", fontSize=9, leading=11.5),
    "tdr": S("tdr", fontSize=9, leading=11.5, alignment=TA_RIGHT),
    "tdb": S("tdb", fontName="Inter-SemiBold", fontSize=9, leading=11.5),
    "tdbr": S("tdbr", fontName="Inter-SemiBold", fontSize=9, leading=11.5, alignment=TA_RIGHT),
    "grp": S("grp", fontName="InterDisplay-Bold", fontSize=9, leading=11, textColor=ACCENT),
    "num": S("num", fontName="InterDisplay-ExtraBold", fontSize=9.2, leading=13.4, textColor=ACCENT),
}


def caps(t):
    return t.upper()


class NumberedCanvas(rl_canvas.Canvas):
    def __init__(self, *a, footer="", **kw):
        super().__init__(*a, **kw)
        self._saved = []
        self._footer = footer

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._saved)
        for st in self._saved:
            self.__dict__.update(st)
            self.setFont("Inter-Regular", 7)
            self.setFillColor(GREY)
            self.drawString(17 * mm, 10 * mm, self._footer)
            self.drawRightString(A4[0] - 17 * mm, 10 * mm, f"Seite {self._pageNumber} von {n}")
            super().showPage()
        super().save()


def _sp(h):
    return Spacer(1, h * mm)


def build_pdf(path, project, settings, erg, meta):
    """meta: dict mit objekt, objekt_zusatz, grundlage, erstellt"""
    _fonts()
    W = A4[0] - 34 * mm
    story = []

    # Kopf
    logo = Image(asset("hbs_logo.png"), width=40 * mm, height=40 * mm * 65 / 150)
    head = Table([[logo, Paragraph(f"{FIRMA}<br/>{ADRESSE}<br/>{WEB}", ST["meta"])]], colWidths=[W * 0.45, W * 0.55])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
                              ("LINEBELOW", (0, 0), (-1, 0), 1.6, ACCENT)]))
    story += [head, _sp(9), Paragraph(caps("Auslegungsunterlage zur Übergabe"), ST["kicker"]), _sp(2),
              Paragraph("Raumheizlasten, Volumenströme<br/>und Pumpeneinstellung", ST["h1"]), _sp(2),
              Paragraph("Fußbodenheizung: Einstellwerte für die Durchflussanzeiger am Heizkreisverteiler und "
                        "für die Umwälzpumpe im Keller", ST["sub"]), _sp(6)]

    facts = [("Objekt", meta["objekt"] + (f"<br/>{meta['objekt_zusatz']}" if meta.get("objekt_zusatz") else "")),
             ("Grundlage", meta["grundlage"]),
             ("Auslegung", f"Norm-Außentemperatur {project.theta_e.replace('-', '−')} °C · Temperaturspreizung "
                           f"Fußbodenheizung {de(settings.spreizung, 0 if settings.spreizung == int(settings.spreizung) else 1)} K"
              if project.theta_e else f"Temperaturspreizung Fußbodenheizung {de(settings.spreizung, 1)} K"),
             ("Erstellt", meta["erstellt"])]
    ft = Table([[Paragraph(caps(a), ST["dt"]), Paragraph(b, ST["body"])] for a, b in facts],
               colWidths=[34 * mm, W - 34 * mm])
    ft.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6 * mm)]))
    story += [ft, _sp(5)]

    def kpi(v, u, l):
        return [Paragraph(f'{v} <font name="InterDisplay-SemiBold" size="9" color="#4A5763">{u}</font>', ST["kv"]),
                Paragraph(l, ST["kl"])]
    k = [kpi(de(project.norm_heizlast), "W", "Norm-Heizlast Gebäude laut Berechnung") if project.norm_heizlast else
         kpi(de(erg.summe_w), "W", "Summe Raumheizlasten"),
         kpi(de(erg.summe_m3h, 2), "m³/h", "Gesamtvolumenstrom Gebäude, Förderstrom Pumpe"),
         kpi(de(erg.foerderhoehe_m, 1), "m", "Förderhöhe Umwälzpumpe, Konstantdruck Δp-c"),
         kpi(de(erg.summe_lmin, 1), "l/min", f"Summe aller Räume bei {de(settings.spreizung, 0)} K")]
    kt = Table([[c[0] for c in k], [c[1] for c in k]], colWidths=[W / 4] * 4)
    kt.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("TOPPADDING", (0, 0), (-1, 0), 4 * mm), ("BOTTOMPADDING", (0, 1), (-1, 1), 4 * mm),
                            ("TOPPADDING", (0, 1), (-1, 1), 0.8 * mm), ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
                            ("LINEABOVE", (0, 0), (-1, 0), 0.6, LINE), ("LINEBELOW", (0, 1), (-1, 1), 0.6, LINE)]))
    story += [kt, _sp(8)]

    # Pumpe
    w = erg.worst
    wr = erg.worst_room
    pump_rows = [
        ("Förderstrom (Auslegung)", f"{de(erg.summe_m3h, 2)} m³/h", "Summe aller Fußbodenheizkreise"),
        ("Förderhöhe (Sollwert)", f"{de(erg.foerderhoehe_m, 1)} m", f"entspricht {de(erg.dp_gesamt)} mbar"),
        ("Regelungsart", "Konstantdruck Δp-c", "Sollwert = Förderhöhe"),
    ]
    dp_rows = []
    if w:
        dp_rows.append((f"Ungünstigster Heizkreis: {etage_kurz(wr.etage)}, {wr.nr}, {wr.name} "
                        f"(ca. {de(w.laenge)} m, {de(w.volumenstrom, 2)} l/min)", erg.dp_kreis))
    dp_rows += [("Verteiler, Ventileinsatz, Durchflussanzeiger", erg.dp_verteiler),
                ("Zusätzliche Armaturen (Wärmemengenzähler, Strangregulierventil, Absperrungen)", erg.dp_zusatz),
                (f"Rohrnetz Keller bis ungünstigster Verteiler (ca. {de(erg.netz_laenge)} m Vor- und Rücklauf, "
                 f"{de(settings.netz_r)} Pa/m, +{de(settings.netz_zuschlag)} % Einzelwiderstände)", erg.dp_netz)]
    dp_rows.append(("Wärmeerzeuger" + (" (entfällt, Puffer / hydraulische Weiche)" if erg.dp_erzeuger == 0 else ""),
                    erg.dp_erzeuger))
    dp_rows.append((f"Sicherheitszuschlag {de(settings.sicherheit)} %", erg.dp_sicherheit))

    blk = [Paragraph("Einstellung Umwälzpumpe Heizkreis (Keller)", ST["h2"]), _sp(3)]
    pt = Table([[Paragraph(caps(a), ST["dt"]), Paragraph(f"<b>{b}</b>", ST["body"]), Paragraph(c, ST["small"])]
                for a, b, c in pump_rows], colWidths=[50 * mm, 40 * mm, W - 90 * mm])
    pt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("TOPPADDING", (0, 0), (-1, -1), 1.4 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.4 * mm),
                            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE)]))
    blk += [pt, _sp(4)]
    data = [[Paragraph(caps("Druckverlust"), ST["th"]), Paragraph(caps("mbar"), ST["thr"])]]
    for a, b in dp_rows:
        data.append([Paragraph(a, ST["td"]), Paragraph(de(b), ST["tdr"])])
    data.append([Paragraph(f"Summe, entspricht Förderhöhe {de(erg.foerderhoehe_m, 1)} m", ST["tdb"]),
                 Paragraph(de(erg.dp_gesamt), ST["tdbr"])])
    dt = Table(data, colWidths=[W - 30 * mm, 30 * mm])
    dt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), INK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 1.3 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.3 * mm),
                            ("LEFTPADDING", (0, 0), (-1, -1), 2.5 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm),
                            ("LINEBELOW", (0, 1), (-1, -2), 0.4, LINE), ("BACKGROUND", (0, -1), (-1, -1), SOFT)]))
    blk.append(dt)
    story.append(KeepTogether(blk))

    # Raumtabelle
    story += [PageBreak(), Paragraph("Raumheizlasten und Einstellwerte", ST["h2"]), _sp(3)]
    cw = [W * 0.42, W * 0.14, W * 0.20, W * 0.24]
    header = [Paragraph(caps("Raum"), ST["th"]), Paragraph(caps("Etage"), ST["th"]),
              Paragraph(caps("Heizlast [W]"), ST["thr"]), Paragraph(caps("Volumenstrom [l/min]"), ST["thr"])]
    first = True
    for (et, nr), grp in groupby(erg.zeilen, key=lambda z: (z[0].etage, z[0].nr)):
        grp = list(grp)
        rows = [header] if first else []
        title = etage_name(et) + (f" · {nr}" if nr else "")
        rows.append([Paragraph(title, ST["grp"]), "", "", ""])
        for r, v in grp:
            if r.heizlast <= 0:
                vt = '– <font color="#C2410C" size="7"><super>1</super></font>'
            elif v < settings.grenze_messbereich:
                vt = de(v, 2) + ' <font color="#C2410C" size="7"><super>2</super></font>'
            else:
                vt = de(v, 2)
            rows.append([Paragraph(r.name, ST["td"]), Paragraph(etage_kurz(r.etage), ST["td"]),
                         Paragraph(de(r.heizlast), ST["tdr"]), Paragraph(vt, ST["tdr"])])
        sw = sum(r.heizlast for r, _ in grp if r.heizlast > 0)
        sv = sum(v for _, v in grp)
        rows.append([Paragraph(f"Summe {nr or etage_name(et)}, {etage_kurz(et)}", ST["tdb"]), "",
                     Paragraph(de(sw), ST["tdbr"]), Paragraph(de(sv, 2), ST["tdbr"])])
        t = Table(rows, colWidths=cw, repeatRows=0)
        o = 1 if first else 0
        style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("LEFTPADDING", (0, 0), (-1, -1), 2.5 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm),
                 ("TOPPADDING", (0, 0), (-1, -1), 1.2 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2 * mm),
                 ("SPAN", (0, o), (-1, o)), ("TOPPADDING", (0, o), (-1, o), 3.6 * mm),
                 ("LINEBELOW", (0, o), (-1, o), 0.8, ACCENT),
                 ("LINEBELOW", (0, o + 1), (-1, -2), 0.4, LINE),
                 ("SPAN", (0, -1), (1, -1)), ("BACKGROUND", (0, -1), (-1, -1), SOFT)]
        if first:
            style += [("BACKGROUND", (0, 0), (-1, 0), INK), ("TOPPADDING", (0, 0), (-1, 0), 2.2 * mm),
                      ("BOTTOMPADDING", (0, 0), (-1, 0), 2.2 * mm)]
        t.setStyle(TableStyle(style))
        story.append(KeepTogether([t]))
        first = False
    story += [_sp(3), Paragraph(
        '<font color="#C2410C"><super>1</super></font> keine rechnerische Heizlast, Durchfluss auf Minimum · '
        f'<font color="#C2410C"><super>2</super></font> unter ca. {de(settings.grenze_messbereich, 1)} l/min, '
        'unterhalb des üblichen Messbereichs der Durchflussanzeiger, siehe Anmerkung 5', ST["small"])]

    # Anmerkungen
    story += [PageBreak(), Paragraph("Anmerkungen zur Auslegung", ST["h2"]), _sp(3)]
    dts = de(settings.spreizung, 0)
    bsp = erg.zeilen and max(erg.zeilen, key=lambda z: z[0].heizlast)
    notes = [
        ("Datengrundlage.", "Alle Heizlasten stammen unverändert aus der raumweisen Heizlastberechnung nach "
         "DIN EN 12831-1 des Planers. Angesetzt ist jeweils die Norm-Heizlast des Raumes einschließlich "
         "Aufheizzuschlag. HBS hat die Werte übernommen und daraus Volumenströme und Pumpeneinstellung abgeleitet, "
         "die Heizlastberechnung selbst wurde nicht neu erstellt."),
        ("Berechnung des Volumenstroms.", "Der Volumenstrom ergibt sich aus der Wärmemenge, die das Heizwasser bei "
         f"der gewählten Spreizung abgeben kann: <b>Volumenstrom [l/min] = Heizlast [W] ÷ (1,163 Wh/(kg·K) × {dts} K) ÷ 60</b>."
         + (f" Beispiel {bsp[0].name}, {bsp[0].nr}: {de(bsp[0].heizlast)} W ÷ {de(1.163 * settings.spreizung, 3)} ÷ 60 = "
            f"{de(bsp[1], 2)} l/min." if bsp else "")),
        (f"Warum {dts} K Spreizung.", "5 K ist der übliche Standardwert für Fußbodenheizungen nach DIN EN 1264. "
         "Die geringe Spreizung sorgt für eine gleichmäßige Oberflächentemperatur und ermöglicht niedrige "
         "Vorlauftemperaturen, was besonders für den effizienten Betrieb einer Wärmepumpe wichtig ist."),
        ("Werte gelten pro Raum.", "Hat ein Raum mehrere Heizkreise, wird der angegebene Volumenstrom im Verhältnis "
         "der Rohrlängen auf die Kreise aufgeteilt. Das betrifft vor allem große Räume, deren Werte über dem "
         "Messbereich eines einzelnen Durchflussanzeigers liegen."),
        ("Kleine und negative Werte.", "Dielen, Flure, WCs und einzelne Abstellräume haben nur eine sehr geringe "
         "Heizlast und werden über die angrenzenden, wärmeren Räume mitbeheizt. Werte unter etwa "
         f"{de(settings.grenze_messbereich, 1)} l/min lassen sich am Durchflussanzeiger nicht sinnvoll ablesen, "
         "diese Kreise werden auf den kleinsten einstellbaren Wert gesetzt. Negative Heizlasten bedeuten einen "
         "Wärmeüberschuss aus den Nachbarräumen."),
        ("Gesamtvolumenstrom.", f"Der Gesamtvolumenstrom von {de(erg.summe_m3h, 2)} m³/h ist die Summe aller "
         "Raumvolumenströme und damit der Förderstrom, den die Umwälzpumpe bei voll geöffneten Heizkreisen liefern "
         "muss. Die Summe der Raumheizlasten liegt über der Norm-Heizlast des Gebäudes, weil Aufheizzuschläge und "
         "Lüftungswärmeverluste auf Gebäudeebene anders angesetzt werden als je Raum."
         + (f" Bezogen auf die Gebäude-Heizlast ergeben sich {de(erg.gebaeude_m3h, 2)} m³/h, dieser Wert ist für "
            "die Auslegung des Wärmeerzeugers maßgeblich." if erg.gebaeude_m3h else "")),
        ("Förderhöhe.", "Die Förderhöhe ist die Summe der Druckverluste im ungünstigsten Strang: längster und am "
         "stärksten belasteter Fußbodenheizkreis, Verteiler mit Armaturen und Rohrnetz vom Keller bis zum "
         f"entferntesten Verteiler. Annahmen: Rohr {settings.rohr} mm, Verlegeabstand {de(settings.verlegeabstand)} cm, "
         f"Heizkreise maximal {de(settings.max_kreislaenge)} m inklusive {de(settings.anbindung)} m Anbindeleitung, "
         "ein Heizkreisverteiler je Wohnung. "
         + ("Durch Pufferspeicher bzw. hydraulische Weiche ist der Wärmeerzeuger hydraulisch entkoppelt und geht "
            "nicht in die Förderhöhe ein." if erg.dp_erzeuger == 0 else
            f"Der Wärmeerzeuger ist mit {de(erg.dp_erzeuger)} mbar berücksichtigt.")),
        ("Pumpe einstellen.", f"Die Umwälzpumpe wird auf Konstantdruck (Δp-c) mit {de(erg.foerderhoehe_m, 1)} m "
         "eingestellt. Bei Konstantdruck bleibt der Druck an den Verteilern auch dann stabil, wenn einzelne "
         "Stellantriebe schließen, und die eingestellten Durchflüsse stimmen. Ist der Arbeitspunkt mit der "
         "vorhandenen Pumpe nicht erreichbar, ist die Pumpe zu prüfen."),
        ("Hinweise zur Einregulierung.", "Die Volumenströme werden bei laufender Umwälzpumpe und vollständig "
         "geöffneten Stellantrieben eingestellt, beginnend am entferntesten Verteiler. Nach der Einregulierung "
         "prüfen wir die Rücklauftemperaturen der Heizkreise. Weicht die tatsächliche Anlage von den Annahmen ab, "
         "etwa bei Rohrlängen, Raumaufteilung oder Bodenbelägen, sind die Werte anzupassen."),
    ]
    for i, (t, b) in enumerate(notes, 1):
        nt = Table([[Paragraph(str(i), ST["num"]), Paragraph(f"<b>{t}</b> {b}", ST["body"])]],
                   colWidths=[7 * mm, W - 7 * mm])
        nt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm)]))
        story.append(nt)
    sig = Table([[Paragraph("Ort, Datum", ST["small"]), "", Paragraph("Unterschrift HBS GmbH", ST["small"])]],
                colWidths=[(W - 16 * mm) / 2, 16 * mm, (W - 16 * mm) / 2])
    sig.setStyle(TableStyle([("LINEABOVE", (0, 0), (0, 0), 0.6, INK), ("LINEABOVE", (2, 0), (2, 0), 0.6, INK),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm)]))
    story += [CondPageBreak(30 * mm), _sp(16), sig]

    footer = f"HBS GmbH · Raumheizlasten, Volumenströme und Pumpeneinstellung · {meta['objekt']}"
    doc = BaseDocTemplate(path, pagesize=A4, leftMargin=17 * mm, rightMargin=17 * mm, topMargin=16 * mm,
                          bottomMargin=20 * mm, title="Raumheizlasten, Volumenströme und Pumpeneinstellung",
                          author="HBS GmbH")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame])])
    doc.build(story, canvasmaker=lambda *a, **kw: NumberedCanvas(*a, footer=footer, **kw))


def default_meta(project):
    grund = "Raumweise Heizlastberechnung nach DIN EN 12831-1:2020 mit nationalem Anhang"
    if project.planer:
        grund += f", {project.planer}"
    if project.projekt_nr:
        grund += f", Projekt-Nr. {project.projekt_nr}"
    if project.datum:
        grund += f" vom {project.datum}"
    return {"objekt": project.objekt or "", "objekt_zusatz": "", "grundlage": grund,
            "erstellt": f"HBS GmbH, Elsdorf · {date.today().strftime('%d.%m.%Y')}"}
