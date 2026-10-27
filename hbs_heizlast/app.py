"""HBS Heizlast-Tool: Heizlastberechnung (PDF) rein, HBS-Auslegungsunterlage raus."""
import os
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import fields
from tkinter import filedialog, messagebox, ttk

from .calc import ROHRE, Settings, berechne, etage_kurz
from .parser import parse_pdf
from .report import asset, build_pdf, de, default_meta

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND = True
except Exception:  # Drag & Drop ist optional
    DND = False

ACCENT = "#C2410C"
INK = "#111C26"
GREY = "#4A5763"

PARAMS = [  # (feld, beschriftung, einheit)
    ("spreizung", "Temperaturspreizung", "K"),
    ("rohr", "Rohr Fußbodenheizung", "mm"),
    ("verlegeabstand", "Verlegeabstand", "cm"),
    ("max_kreislaenge", "Max. Heizkreislänge inkl. Anbindung", "m"),
    ("anbindung", "Anbindeleitung (Vor- + Rücklauf)", "m"),
    ("dp_verteiler", "Verteiler, Ventil, Durchflussanzeiger", "mbar"),
    ("dp_zusatz", "Zusätzl. Armaturen (WMZ, Strangregulierventil)", "mbar"),
    ("netz_laenge", "Rohrnetz Keller → Verteiler (0 = automatisch)", "m"),
    ("netz_r", "Druckgefälle Rohrnetz", "Pa/m"),
    ("netz_zuschlag", "Zuschlag Einzelwiderstände Rohrnetz", "%"),
    ("dp_erzeuger", "Druckverlust Wärmeerzeuger", "mbar"),
    ("sicherheit", "Sicherheitszuschlag", "%"),
]


def open_file(path):
    try:
        if sys.platform == "win32":
            os.startfile(path)  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


class App:
    def __init__(self, root):
        self.root = root
        self.project = None
        self.erg = None
        root.title("HBS Heizlast-Tool")
        root.geometry("1180x780")
        root.minsize(980, 640)
        root.configure(bg="white")
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure(".", background="white", foreground=INK)
        st.configure("TLabel", background="white", foreground=INK)
        st.configure("Grey.TLabel", foreground=GREY)
        st.configure("H.TLabel", font=("Helvetica", 15, "bold"))
        st.configure("K.TLabel", font=("Helvetica", 9, "bold"), foreground=ACCENT)
        st.configure("Big.TLabel", font=("Helvetica", 17, "bold"))
        st.configure("Accent.TButton", background=ACCENT, foreground="white", padding=(14, 7))
        st.map("Accent.TButton", background=[("active", "#9A3412"), ("disabled", "#E5B9A6")])
        st.configure("Treeview.Heading", background=INK, foreground="white", font=("Helvetica", 10, "bold"))
        st.configure("Treeview", rowheight=22)
        st.configure("TLabelframe", background="white")
        st.configure("TLabelframe.Label", background="white", foreground=ACCENT, font=("Helvetica", 10, "bold"))
        st.configure("TCheckbutton", background="white")

        # Kopf
        top = ttk.Frame(root, padding=(16, 12))
        top.pack(fill="x")
        try:
            self.logo = tk.PhotoImage(file=asset("hbs_logo.png"))
            ttk.Label(top, image=self.logo).pack(side="left")
        except Exception:
            ttk.Label(top, text="HBS", style="H.TLabel").pack(side="left")
        ttk.Label(top, text="  Heizlast-Tool · Raumheizlasten, Volumenströme, Pumpeneinstellung",
                  style="H.TLabel").pack(side="left")
        tk.Frame(root, height=2, bg=ACCENT).pack(fill="x", padx=16)

        # Drop-Zone
        self.drop = tk.Label(root, text=("Heizlastberechnung (PDF) hier hineinziehen oder klicken zum Auswählen"
                                         if DND else "Klicken, um die Heizlastberechnung (PDF) auszuwählen"),
                             bg="#F4F5F7", fg=GREY, font=("Helvetica", 12), height=3, cursor="hand2")
        self.drop.pack(fill="x", padx=16, pady=12)
        self.drop.bind("<Button-1>", lambda e: self.choose())
        if DND:
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind("<<Drop>>", self.on_drop)
        self.prog = ttk.Progressbar(root, mode="determinate")

        body = ttk.Frame(root, padding=(16, 0, 16, 0))
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 14))
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        # Projekt
        pf = ttk.Labelframe(left, text="Projekt", padding=8)
        pf.pack(fill="x")
        self.meta_vars = {}
        for key, lab in [("objekt", "Objekt"), ("objekt_zusatz", "Zusatz"), ("grundlage", "Grundlage"),
                         ("erstellt", "Erstellt")]:
            ttk.Label(pf, text=lab, style="Grey.TLabel").pack(anchor="w")
            v = tk.StringVar()
            ttk.Entry(pf, textvariable=v, width=48).pack(fill="x", pady=(0, 4))
            self.meta_vars[key] = v

        # Parameter
        af = ttk.Labelframe(left, text="Auslegung", padding=8)
        af.pack(fill="x", pady=(10, 0))
        d = Settings()
        self.vars = {}
        for r, (key, lab, unit) in enumerate(PARAMS):
            ttk.Label(af, text=lab).grid(row=r, column=0, sticky="w", pady=1)
            if key == "rohr":
                v = tk.StringVar(value=d.rohr)
                w = ttk.Combobox(af, textvariable=v, values=list(ROHRE), width=8, state="readonly")
            else:
                v = tk.StringVar(value=de(getattr(d, key), 1).rstrip("0").rstrip(","))
                w = ttk.Entry(af, textvariable=v, width=9, justify="right")
            w.grid(row=r, column=1, padx=6)
            ttk.Label(af, text=unit, style="Grey.TLabel").grid(row=r, column=2, sticky="w")
            self.vars[key] = v
            if key == "dp_erzeuger":
                self.erz_entry = w
        self.puffer = tk.BooleanVar(value=True)
        ttk.Checkbutton(af, text="Puffer / hydraulische Weiche vorhanden (Erzeuger entfällt)",
                        variable=self.puffer, command=self.toggle_puffer).grid(row=len(PARAMS), column=0,
                                                                              columnspan=3, sticky="w", pady=(6, 0))
        self.toggle_puffer()
        ttk.Button(af, text="Neu berechnen", command=self.recalc).grid(row=len(PARAMS) + 1, column=0, columnspan=3,
                                                                     sticky="we", pady=(8, 0))

        # Ergebnis
        kf = ttk.Frame(right)
        kf.pack(fill="x")
        self.k = {}
        for i, (key, lab) in enumerate([("w", "Norm-Heizlast Gebäude"), ("m3h", "Gesamtvolumenstrom"),
                                        ("h", "Förderhöhe Pumpe (Δp-c)"), ("lmin", "Summe Räume")]):
            f = ttk.Frame(kf)
            f.grid(row=0, column=i, sticky="w", padx=(0, 26))
            v = tk.StringVar(value="–")
            ttk.Label(f, textvariable=v, style="Big.TLabel").pack(anchor="w")
            ttk.Label(f, text=lab, style="Grey.TLabel").pack(anchor="w")
            self.k[key] = v
        self.worst = tk.StringVar()
        ttk.Label(right, textvariable=self.worst, style="Grey.TLabel", wraplength=640).pack(anchor="w", pady=(6, 6))

        cols = ("etage", "einheit", "raum", "flaeche", "heizlast", "lmin")
        heads = ("Etage", "Wohnung", "Raum", "Fläche [m²]", "Heizlast [W]", "Volumenstrom [l/min]")
        tf = ttk.Frame(right)
        tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, columns=cols, show="headings")
        for c, h, w, a in zip(cols, heads, (60, 110, 170, 90, 100, 150), ("w", "w", "w", "e", "e", "e")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor=a)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.tag_configure("grp", foreground=ACCENT, font=("Helvetica", 10, "bold"))
        self.tree.tag_configure("sum", background="#F4F5F7", font=("Helvetica", 10, "bold"))

        bf = ttk.Frame(root, padding=16)
        bf.pack(fill="x")
        self.status = tk.StringVar(value="Bereit.")
        ttk.Label(bf, textvariable=self.status, style="Grey.TLabel").pack(side="left")
        self.save_btn = ttk.Button(bf, text="HBS-PDF erstellen …", style="Accent.TButton", command=self.save,
                                   state="disabled")
        self.save_btn.pack(side="right")

        if len(sys.argv) > 1 and sys.argv[1].lower().endswith(".pdf"):
            root.after(200, lambda: self.load(sys.argv[1]))

    # --- Aktionen
    def toggle_puffer(self):
        if self.puffer.get():
            self.vars["dp_erzeuger"].set("0")
            self.erz_entry.state(["disabled"])
        else:
            self.erz_entry.state(["!disabled"])

    def on_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        if files:
            self.load(files[0])

    def choose(self):
        p = filedialog.askopenfilename(title="Heizlastberechnung auswählen", filetypes=[("PDF", "*.pdf")])
        if p:
            self.load(p)

    def load(self, path):
        self.status.set(f"Lese {os.path.basename(path)} …")
        self.prog.pack(fill="x", padx=16, after=self.drop)
        self.prog["value"] = 0
        self.save_btn.state(["disabled"])
        self.src = path

        def work():
            try:
                p = parse_pdf(path, progress=lambda i, n: self.root.after(0, self._prog, i, n))
                self.root.after(0, self.loaded, p, None)
            except Exception as e:
                self.root.after(0, self.loaded, None, e)
        threading.Thread(target=work, daemon=True).start()

    def _prog(self, i, n):
        self.prog["maximum"] = n
        self.prog["value"] = i

    def loaded(self, p, err):
        self.prog.pack_forget()
        if err or not p or not p.rooms:
            messagebox.showerror("HBS Heizlast-Tool",
                                 "In dieser Datei wurden keine Raumheizlasten gefunden.\n\n"
                                 "Das Tool erwartet den Ausdruck einer raumweisen Heizlastberechnung nach "
                                 "DIN EN 12831 aus Hottgenroth/HottCAD oder heiz.report."
                                 + (f"\n\nFehler: {err}" if err else ""))
            self.status.set("Keine Räume gefunden.")
            return
        self.project = p
        m = default_meta(p)
        for k, v in self.meta_vars.items():
            v.set(m.get(k, ""))
        self.drop.configure(text=f"✓ {os.path.basename(self.src)}  ·  {len(p.rooms)} Räume gelesen  ·  "
                                 "andere Datei: hineinziehen oder klicken", fg=INK)
        self.recalc()

    def settings(self):
        s = Settings()
        for f in fields(Settings):
            if f.name not in self.vars:
                continue
            raw = self.vars[f.name].get().strip()
            if f.name == "rohr":
                s.rohr = raw
                continue
            try:
                setattr(s, f.name, float(raw.replace(".", "").replace(",", ".")) if raw else 0.0)
            except ValueError:
                raise ValueError(f"Ungültiger Wert bei „{dict((a, b) for a, b, _ in PARAMS)[f.name]}“: {raw}")
        if self.puffer.get():
            s.dp_erzeuger = 0.0
        if s.spreizung <= 0:
            raise ValueError("Die Spreizung muss größer als 0 sein.")
        return s

    def recalc(self):
        if not self.project:
            return
        try:
            s = self.settings()
        except ValueError as e:
            messagebox.showerror("HBS Heizlast-Tool", str(e))
            return
        e = berechne(self.project, s)
        self.erg, self.s = e, s
        p = self.project
        self.k["w"].set(f"{de(p.norm_heizlast)} W" if p.norm_heizlast else "–")
        self.k["m3h"].set(f"{de(e.summe_m3h, 2)} m³/h")
        self.k["h"].set(f"{de(e.foerderhoehe_m, 1)} m")
        self.k["lmin"].set(f"{de(e.summe_lmin, 1)} l/min")
        if e.worst:
            r = e.worst_room
            self.worst.set(f"Ungünstigster Heizkreis: {', '.join(x for x in (etage_kurz(r.etage), r.nr, r.name) if x)} – ca. "
                           f"{de(e.worst.laenge)} m, {de(e.worst.volumenstrom, 2)} l/min, {de(e.dp_kreis)} mbar. "
                           f"Gesamtdruckverlust {de(e.dp_gesamt)} mbar.")
        self.tree.delete(*self.tree.get_children())
        last = None
        for r, v in e.zeilen:
            key = (r.etage, r.nr)
            if key != last:
                if last is not None:
                    self._sum(grp)
                self.tree.insert("", "end", values=(etage_kurz(r.etage), r.nr, "", "", "", ""), tags=("grp",))
                grp, last = [], key
            grp.append((r, v))
            self.tree.insert("", "end", values=(etage_kurz(r.etage), r.nr, r.name, de(r.flaeche, 2),
                                                de(r.heizlast), de(v, 2) if r.heizlast > 0 else "–"))
        if last is not None:
            self._sum(grp)
        self.save_btn.state(["!disabled"])
        self.status.set(f"{len(p.rooms)} Räume · Summe {de(e.summe_w)} W")

    def _sum(self, grp):
        r0 = grp[0][0]
        self.tree.insert("", "end", values=("", f"Summe {r0.nr or etage_kurz(r0.etage)}", "", "",
                                            de(sum(r.heizlast for r, _ in grp if r.heizlast > 0)),
                                            de(sum(v for _, v in grp), 2)), tags=("sum",))

    def save(self):
        if not self.erg:
            return
        self.recalc()
        meta = {k: v.get().strip() for k, v in self.meta_vars.items()}
        name = "HBS_Heizlast_Volumenstroeme_" + "".join(c for c in (meta["objekt"] or "Projekt").split(",")[0]
                                                         if c.isalnum() or c in "-_.")[:40] + ".pdf"
        path = filedialog.asksaveasfilename(title="HBS-PDF speichern", defaultextension=".pdf",
                                            initialfile=name, filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            build_pdf(path, self.project, self.s, self.erg, meta)
        except Exception as e:
            messagebox.showerror("HBS Heizlast-Tool", f"PDF konnte nicht erstellt werden:\n{e}")
            return
        self.status.set(f"Gespeichert: {path}")
        open_file(path)


def main():
    root = TkinterDnD.Tk() if DND else tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
