"""
Modul: ViewModel.hmiHBot (HmiHBot)
====================================
Tkinter-HMI-Panel spezialisiert für die H-Bot-Gravurgantry.

Unterschiede zum SCARA-Panel (hmi.py)
--------------------------------------
* Nur X/Y-Achsen (Z/R nicht vorhanden) — Zeilen bei Y=180 und Y=206 frei.
* Kein Koordinatensystem-Dropdown (H-Bot operiert immer im MCS X/Y).
* Kein Saugen-Taster (H-Bot trägt kein Bauteil).
* Sequenz zeigt 5 H-Bot-spezifische Schritte statt 6 SCARA-Schritte.
* ``setSequenceState()`` zeigt bei Schritt "Gravur" einen Zähler
  (aktueller Wegpunkt / Gesamtzahl) im Kästchen an.

Gemeinsames Y-Raster
---------------------
Alle Y-Konstanten sind identisch zu ``hmi.py`` (SCARA-Panel), sodass
die drei nebeneinander stehenden Panels optisch ausgerichtet sind.
Die Zeilen Y=180 und Y=206 bleiben beim H-Bot absichtlich leer.

Sequenz-Zustände
----------------
Die 5 Zustände spiegeln die ``_HB_*``-Konstanten aus ``main.py``:

+----------+------+-----------+-----------------------------------+
| Zustand  | Wert | Kästchen  | Bedeutung                        |
+----------+------+-----------+-----------------------------------+
| IDLE     |  0   | Warten    | Wartet auf Bauteil               |
| APPROACH |  4   | Anfahrt   | Fährt zur Gravurposition         |
| ENGRAVE  |  1   | Gravur    | Gravurmuster wird abgefahren     |
| RETURN   |  2   | Park      | Rückfahrt zur Parkposition       |
| DONE     |  3   | Fertig    | Bauteil graviert, Roboter 3 kann greifen |
+----------+------+-----------+-----------------------------------+

Abhängigkeiten
--------------
* ``tkinter`` — GUI-Toolkit
* ``ViewModel.hmiControl`` — Steuerbefehle
* ``ViewModel.hmiState``   — Rückmeldeistwerte
"""

import sys
sys.path.append('../ViewModel')

import tkinter as tk
from tkinter import ttk
from hmiControl import hmiControl
from hmiState   import hmiState

# ── Design-Tokens (identisch zu hmi.py) ───────────────────────────────────────
BG         = "lightblue"
BG_SEC     = "#7fb3c8"
BG_MODEBAR = "#b8dce8"
FG_SEC     = "#1a3a4a"
FONT_TITLE = ("Arial", 12, "bold")
FONT_SEC   = ("Arial",  8, "bold")
FONT_LBL   = ("Arial",  9)
FONT_VAL   = ("Arial",  9, "bold")
FONT_STAT  = ("Arial", 10, "bold")
FONT_BTN   = ("Arial",  9)
W, H       = 400, 465
M          = 10
CW         = W - 2 * M      # 380 px

_CLR_OFF   = "#cccccc"       # Farbe inaktiver Sequenz-Kästchen

# ── H-Bot Sequenz-Zustandskodiierung (spiegelt main.py) ──────────────────────
_HB_IDLE     = 0
_HB_ENGRAVE  = 1
_HB_RETURN   = 2
_HB_DONE     = 3
_HB_APPROACH = 4

# Reihenfolge der Kästchen von links nach rechts
_STEP_ORDER  = [_HB_IDLE, _HB_APPROACH, _HB_ENGRAVE, _HB_RETURN, _HB_DONE]
_STEP_NAMES  = ["Warten",  "Anfahrt",   "Gravur",    "Park",     "Fertig"]
_STEP_COLORS = {
    _HB_IDLE:     "lightgreen",
    _HB_APPROACH: "#f9e79f",
    _HB_ENGRAVE:  "orange",
    _HB_RETURN:   "#f9e79f",
    _HB_DONE:     "lightcyan",
}

# ── Y-Raster (identisch zu hmi.py) ────────────────────────────────────────────
_Y_TITLE     = 8
_Y_LBL       = 42
_Y_COMBO     = 58
_Y_MODEBAR   = 82
_Y_ACHSEN    = 106
_Y_AXIS1     = 128
_Y_AXIS2     = 154
# Y=180, Y=206: beim H-Bot leer (Z/R nicht vorhanden)
_Y_SEQUENZ   = 232   # identisch zu SCARA (nach Platz für 4 Achszeilen)
_Y_SEQ_BOXES = 254
_Y_OVERRIDE  = 286
_Y_OV_CTRL   = 309
_Y_STATUS    = 336
_Y_STAT_LBL  = 358
_Y_STEUERUNG = 400
_Y_BUTTONS   = 422


def _sec_header(parent, text: str, y: int):
    """
    Erzeugt einen farbigen Sektionskopf-Balken.

    Parameter
    ---------
    parent : tk.Widget
        Eltern-Widget (Panel-Frame).
    text : str
        Bezeichnung der Sektion.
    y : int
        Y-Startposition [px].
    """
    tk.Label(parent, text=f"  {text}", bg=BG_SEC, fg=FG_SEC,
             font=FONT_SEC, anchor="w").place(x=M, y=y, width=CW, height=18)


class HmiHBot:
    """
    Tkinter-HMI-Panel für die H-Bot-Gravurgantry.

    Wird in ``main.py`` für den H-Bot instanziert und in das gemeinsame
    Hauptfenster eingebettet.  Hat nur zwei Jog-Achsen (X/Y) und kein
    Koordinatensystem-Dropdown.

    Parameter
    ---------
    parent : tk.Widget
        Eltern-Frame (wird vom Hauptfenster bereitgestellt).
    title : str
        Titel der Panel-Kopfzeile.
    """

    def __init__(self, parent, title: str = "H-Bot (Gravur)"):
        """Baut das H-Bot-HMI-Panel auf."""
        self.root = tk.Frame(parent, bg=BG, width=W, height=H,
                             relief="ridge", borderwidth=2)
        self.root.pack(side="left", padx=5)
        self.root.pack_propagate(False)

        self.hmiControl = hmiControl()
        self.hmiState   = hmiState()

        # ── Event-Handler ─────────────────────────────────────────────────────

        def on_mode(event):
            """Betriebsart gewählt: OperationMode und mode_selected setzen."""
            self.hmiControl.OperationMode = (
                0 if self._cmb_mode.get() == "Hand" else 1)
            self.hmiControl.mode_selected = True
            self._refresh_modebar()

        def on_override(val):
            """Override-Schieberegler: OverridePercent und Beschriftung aktualisieren."""
            pct = int(float(val))
            self.hmiControl.OverridePercent = pct
            self._lbl_ov.config(text=f"{pct} %")
            self._refresh_modebar()

        # ── Titel ─────────────────────────────────────────────────────────────
        tk.Label(self.root, text=title, bg=BG,
                 font=FONT_TITLE, anchor="center"
                 ).place(x=M, y=_Y_TITLE, width=CW, height=26)

        # ── Betriebsart-Dropdown (kein Koordinaten-Dropdown beim H-Bot) ───────
        tk.Label(self.root, text="Betriebsart:", bg=BG,
                 font=FONT_LBL).place(x=M, y=_Y_LBL)
        self._cmb_mode = ttk.Combobox(
            self.root, values=["Hand", "Automatisch"],
            state="readonly", width=14)
        self._cmb_mode.set("wählen")
        self._cmb_mode.bind("<<ComboboxSelected>>", on_mode)
        self._cmb_mode.place(x=M, y=_Y_COMBO)

        # ── Modus-Streifen ────────────────────────────────────────────────────
        self._modebar = tk.Label(self.root, text="", bg=BG_MODEBAR,
                                 relief="sunken", font=("Arial", 8),
                                 anchor="center")
        self._modebar.place(x=M, y=_Y_MODEBAR, width=CW, height=18)

        # ── ACHSEN (nur X und Y) ──────────────────────────────────────────────
        _sec_header(self.root, "ACHSEN  —  X / Y", _Y_ACHSEN)
        self._val_x = self._axis_row("X  :", _Y_AXIS1, "MoveXPlus", "MoveXNeg")
        self._val_y = self._axis_row("Y  :", _Y_AXIS2, "MoveYPlus", "MoveYNeg")
        # Y=180 und Y=206 bleiben frei (Z/R beim H-Bot nicht vorhanden)

        # ── SEQUENZ ───────────────────────────────────────────────────────────
        _sec_header(self.root, "SEQUENZ", _Y_SEQUENZ)

        self._step_widgets = []
        n      = len(_STEP_NAMES)
        gap_w  = 10
        step_w = (CW - (n - 1) * gap_w) // n   # (380 - 40) // 5 = 68 px
        x_pos  = M
        for i, name in enumerate(_STEP_NAMES):
            lbl = tk.Label(self.root, text=name,
                           bg=_CLR_OFF, relief="groove",
                           font=("Arial", 8, "bold"), anchor="center")
            lbl.place(x=x_pos, y=_Y_SEQ_BOXES, width=step_w, height=24)
            self._step_widgets.append(lbl)
            x_pos += step_w
            if i < n - 1:
                tk.Label(self.root, text="›", bg=BG,
                         font=("Arial", 9)).place(x=x_pos + 1, y=_Y_SEQ_BOXES + 3,
                                                   width=gap_w - 2)
                x_pos += gap_w

        # ── OVERRIDE ──────────────────────────────────────────────────────────
        _sec_header(self.root, "OVERRIDE", _Y_OVERRIDE)
        tk.Label(self.root, text="0 %", bg=BG,
                 font=FONT_LBL).place(x=M, y=_Y_OV_CTRL)
        self._lbl_ov = tk.Label(self.root, text="100 %", bg=BG, font=FONT_VAL)
        self._lbl_ov.place(x=336, y=_Y_OV_CTRL)
        ov = ttk.Scale(self.root, from_=0, to=100, orient="horizontal",
                       length=280, command=on_override)
        ov.set(100)
        ov.place(x=34, y=_Y_OV_CTRL + 1)

        # ── STATUS ────────────────────────────────────────────────────────────
        _sec_header(self.root, "STATUS", _Y_STATUS)
        self._lbl_status = tk.Label(
            self.root, text="Bereit", bg="lightgreen",
            relief="sunken", font=FONT_STAT, anchor="center")
        self._lbl_status.place(x=M, y=_Y_STAT_LBL, width=CW, height=34)

        # ── STEUERUNG ─────────────────────────────────────────────────────────
        _sec_header(self.root, "STEUERUNG", _Y_STEUERUNG)
        tk.Button(self.root, text="Reset", width=9, font=FONT_BTN,
                  command=lambda: setattr(self.hmiControl, "Reset", True)
                  ).place(x=M, y=_Y_BUTTONS)

        self._refresh_modebar()

    # ── Hilfsmethoden ─────────────────────────────────────────────────────────

    def _axis_row(self, label: str, y: int, attr_p: str, attr_n: str) -> tk.Label:
        """
        Erzeugt eine Achszeile mit Beschriftung, +/−-Tasten und Positionsanzeige.

        Parameter
        ---------
        label : str
            Achsbeschriftung (z. B. "X  :").
        y : int
            Y-Position im Panel [px].
        attr_p : str
            Attributname des Plus-Flags in hmiControl (z. B. "MoveXPlus").
        attr_n : str
            Attributname des Minus-Flags in hmiControl (z. B. "MoveXNeg").

        Rückgabe
        --------
        tk.Label
            Wert-Anzeigelabel.
        """
        tk.Label(self.root, text=label, bg=BG, font=FONT_LBL).place(x=M, y=y)

        bp = tk.Button(self.root, text="+", width=3, font=FONT_BTN)
        bp.place(x=70, y=y - 3)
        bp.bind("<Button-1>",        lambda e: setattr(self.hmiControl, attr_p, True))
        bp.bind("<ButtonRelease-1>", lambda e: setattr(self.hmiControl, attr_p, False))

        bn = tk.Button(self.root, text="−", width=3, font=FONT_BTN)
        bn.place(x=112, y=y - 3)
        bn.bind("<Button-1>",        lambda e: setattr(self.hmiControl, attr_n, True))
        bn.bind("<ButtonRelease-1>", lambda e: setattr(self.hmiControl, attr_n, False))

        val = tk.Label(self.root, text="0.0", bg=BG, font=FONT_VAL, anchor="e")
        val.place(x=290, y=y, width=100)
        return val

    def _refresh_modebar(self):
        """
        Aktualisiert den Modus-Streifen mit Betriebsart und Override.

        3-Felder-Format identisch zum SCARA-Panel:
        ``<Betriebsart>  |  MCS X/Y  |  Ov: xx %``
        Das mittlere Feld ist beim H-Bot fix "MCS X/Y" (kein Koordinatensystem-Dropdown).
        """
        mode = self._cmb_mode.get()
        ov   = self.hmiControl.OverridePercent
        mt   = mode if mode != "wählen" else "—"
        ok   = mode != "wählen"
        bg   = ("#f9e79f" if ok and mode == "Automatisch" else
                "#d5f5e3" if ok else BG_MODEBAR)
        self._modebar.config(text=f"{mt}  |  MCS X/Y  |  Ov: {ov} %", bg=bg)

    # ── Öffentliche Schnittstelle ─────────────────────────────────────────────

    def getHmiControl(self) -> hmiControl:
        """Gibt das hmiControl-Objekt zurück (wird von Machine.update_hmi_hbot() gelesen)."""
        return self.hmiControl

    def setHmiState(self, state: hmiState):
        """
        Aktualisiert die X/Y-Positionsanzeigen.

        Parameter
        ---------
        state : hmiState
            Aktueller Istwert-DTO von Machine.update_hmi_hbot().
        """
        self.hmiState = state
        self._val_x.config(text=f"{state.axisXPosition:8.1f}")
        self._val_y.config(text=f"{state.axisYPosition:8.1f}")

    def setStatus(self, text: str, color: str = "lightgreen"):
        """
        Setzt den Text und die Hintergrundfarbe des Status-Labels.

        Parameter
        ---------
        text : str
            Anzuzeigender Statustext.
        color : str
            Tkinter-Farbname oder Hex-Wert.
        """
        self._lbl_status.config(text=text, bg=color)

    def set_saugen_enabled(self, enabled: bool):
        """Stub für API-Kompatibilität — H-Bot hat keinen Vakuumsauger."""
        pass

    def setSequenceState(self, state: int,
                         engrave_step: int = 0,
                         engrave_total: int = 0):
        """
        Hebt den aktiven Schritt im H-Bot-Sequenz-Indikator hervor.

        Beim Schritt "Gravur" (_HB_ENGRAVE) wird zusätzlich der Fortschritt
        als Bruch angezeigt (aktueller Wegpunkt / Gesamtzahl), sofern
        ``engrave_total > 0``.

        Parameter
        ---------
        state : int
            Aktueller H-Bot-Zustand (entspricht einem ``_HB_*``-Wert).
        engrave_step : int
            Aktuell abgearbeiteter Gravur-Wegpunkt-Index.
        engrave_total : int
            Gesamtzahl der Gravur-Wegpunkte.
        """
        for i, (step_state, widget) in enumerate(zip(_STEP_ORDER, self._step_widgets)):
            if step_state == state:
                color = _STEP_COLORS.get(state, "#f9e79f")
                name  = _STEP_NAMES[i]
                if state == _HB_ENGRAVE and engrave_total > 0:
                    name = f"Gravur\n{engrave_step}/{engrave_total}"
                widget.config(bg=color, text=name)
            else:
                widget.config(bg=_CLR_OFF, text=_STEP_NAMES[i])
