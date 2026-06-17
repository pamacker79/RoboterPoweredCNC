"""
Module: HmiHBot
Purpose: Tkinter HMI panel specialized for the H-Bot engraving gantry.
         Identical section y-positions as hmi.py (SCARA) for visual alignment.
         Only X/Y axes; no coord-system selector; no Saugen button.
Inputs:  Operator button/slider events; sequence state from Machine via setSequenceState().
Outputs: hmiControl flags read by Machine.update_hmi_hbot().
Dependencies: tkinter, ViewModel.hmiControl, ViewModel.hmiState
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
FONT_SEC   = ("Arial", 8,  "bold")
FONT_LBL   = ("Arial", 9)
FONT_VAL   = ("Arial", 9,  "bold")
FONT_STAT  = ("Arial", 10, "bold")
FONT_BTN   = ("Arial", 9)
W, H       = 400, 465
M          = 10
CW         = W - 2 * M      # 380 px

_CLR_OFF   = "#cccccc"

# ── H-Bot Sequenz-Zustände (spiegelt main.py) ─────────────────────────────────
_HB_IDLE     = 0
_HB_ENGRAVE  = 1
_HB_RETURN   = 2
_HB_DONE     = 3
_HB_APPROACH = 4

_STEP_ORDER  = [_HB_IDLE, _HB_APPROACH, _HB_ENGRAVE, _HB_RETURN, _HB_DONE]
_STEP_NAMES  = ["Warten", "Anfahrt", "Gravur", "Park", "Fertig"]
_STEP_COLORS = {
    _HB_IDLE:     "lightgreen",
    _HB_APPROACH: "#f9e79f",
    _HB_ENGRAVE:  "orange",
    _HB_RETURN:   "#f9e79f",
    _HB_DONE:     "lightcyan",
}

# ── Y-Raster (gleich wie hmi.py) ──────────────────────────────────────────────
_Y_TITLE     = 8
_Y_LBL       = 42
_Y_COMBO     = 58
_Y_MODEBAR   = 82
_Y_ACHSEN    = 106
_Y_AXIS1     = 128
_Y_AXIS2     = 154
_Y_SEQUENZ   = 232   # = gleich wie SCARA (nach 4 Achszeilen)
_Y_SEQ_BOXES = 254
_Y_OVERRIDE  = 286
_Y_OV_CTRL   = 309
_Y_STATUS    = 336
_Y_STAT_LBL  = 358
_Y_STEUERUNG = 400
_Y_BUTTONS   = 422


def _sec_header(parent, text, y):
    tk.Label(parent, text=f"  {text}", bg=BG_SEC, fg=FG_SEC,
             font=FONT_SEC, anchor="w").place(x=M, y=y, width=CW, height=18)


class HmiHBot:
    def __init__(self, parent, title="H-Bot (Gravur)"):
        self.root = tk.Frame(parent, bg=BG, width=W, height=H,
                             relief="ridge", borderwidth=2)
        self.root.pack(side="left", padx=5)
        self.root.pack_propagate(False)

        self.hmiControl = hmiControl()
        self.hmiState   = hmiState()

        # ── Events ────────────────────────────────────────────────────────────
        def on_mode(event):
            self.hmiControl.OperationMode = (
                0 if self._cmb_mode.get() == "Hand" else 1)
            self._refresh_modebar()

        def on_override(val):
            pct = int(float(val))
            self.hmiControl.OverridePercent = pct
            self._lbl_ov.config(text=f"{pct} %")
            self._refresh_modebar()

        # ── Titel ─────────────────────────────────────────────────────────────
        tk.Label(self.root, text=title, bg=BG,
                 font=FONT_TITLE, anchor="center"
                 ).place(x=M, y=_Y_TITLE, width=CW, height=26)

        # ── Betriebsart ───────────────────────────────────────────────────────
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

        # ── ACHSEN (X / Y — Z / R nicht vorhanden) ───────────────────────────
        _sec_header(self.root, "ACHSEN  —  X / Y", _Y_ACHSEN)
        self._val_x = self._axis_row("X  :", _Y_AXIS1, "MoveXPlus", "MoveXNeg")
        self._val_y = self._axis_row("Y  :", _Y_AXIS2, "MoveYPlus", "MoveYNeg")
        # y=180 und y=206 (Z/R) bleiben frei → sauberer Abstand zur SEQUENZ-Zeile

        # ── SEQUENZ  (y=232 = identisch zu SCARA) ────────────────────────────
        _sec_header(self.root, "SEQUENZ", _Y_SEQUENZ)

        self._step_widgets = []
        n      = len(_STEP_NAMES)
        gap_w  = 10
        step_w = (CW - (n - 1) * gap_w) // n   # (380 - 40) // 5 = 68
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

        # ── OVERRIDE  (y=286 = identisch zu SCARA) ───────────────────────────
        _sec_header(self.root, "OVERRIDE", _Y_OVERRIDE)
        tk.Label(self.root, text="0 %", bg=BG,
                 font=FONT_LBL).place(x=M, y=_Y_OV_CTRL)
        self._lbl_ov = tk.Label(self.root, text="100 %", bg=BG, font=FONT_VAL)
        self._lbl_ov.place(x=336, y=_Y_OV_CTRL)
        ov = ttk.Scale(self.root, from_=0, to=100, orient="horizontal",
                       length=280, command=on_override)
        ov.set(100)
        ov.place(x=34, y=_Y_OV_CTRL + 1)

        # ── STATUS  (y=336 = identisch zu SCARA) ─────────────────────────────
        _sec_header(self.root, "STATUS", _Y_STATUS)
        self._lbl_status = tk.Label(
            self.root, text="Bereit", bg="lightgreen",
            relief="sunken", font=FONT_STAT, anchor="center")
        self._lbl_status.place(x=M, y=_Y_STAT_LBL, width=CW, height=34)

        # ── STEUERUNG  (y=400 = identisch zu SCARA) ──────────────────────────
        _sec_header(self.root, "STEUERUNG", _Y_STEUERUNG)
        tk.Button(self.root, text="Reset", width=9, font=FONT_BTN,
                  command=lambda: setattr(self.hmiControl, "Reset", True)
                  ).place(x=M, y=_Y_BUTTONS)

        self._refresh_modebar()

    # ── Achszeile ─────────────────────────────────────────────────────────────
    def _axis_row(self, label, y, attr_p, attr_n):
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

    # ── Modus-Streifen (gleiche 3-Felder-Struktur wie SCARA) ─────────────────
    def _refresh_modebar(self):
        mode = self._cmb_mode.get()
        ov   = self.hmiControl.OverridePercent
        mt   = mode if mode != "wählen" else "—"
        ok   = mode != "wählen"
        bg   = ("#f9e79f" if ok and mode == "Automatisch" else
                "#d5f5e3" if ok else BG_MODEBAR)
        self._modebar.config(text=f"{mt}  |  MCS X/Y  |  Ov: {ov} %", bg=bg)

    # ── Öffentliche Schnittstelle ─────────────────────────────────────────────
    def getHmiControl(self):
        return self.hmiControl

    def setHmiState(self, state: hmiState):
        self.hmiState = state
        self._val_x.config(text=f"{state.axisXPosition:8.1f}")
        self._val_y.config(text=f"{state.axisYPosition:8.1f}")

    def setStatus(self, text: str, color: str = "lightgreen"):
        self._lbl_status.config(text=text, bg=color)

    def set_saugen_enabled(self, enabled: bool):
        pass  # H-Bot hat keinen Sauger

    def setSequenceState(self, state: int,
                         engrave_step: int = 0, engrave_total: int = 0):
        """Hebt den aktiven Schritt im Sequenz-Indikator hervor."""
        for i, (step_state, widget) in enumerate(zip(_STEP_ORDER, self._step_widgets)):
            if step_state == state:
                color = _STEP_COLORS.get(state, "#f9e79f")
                name  = _STEP_NAMES[i]
                if state == _HB_ENGRAVE and engrave_total > 0:
                    name = f"Gravur\n{engrave_step}/{engrave_total}"
                widget.config(bg=color, text=name)
            else:
                widget.config(bg=_CLR_OFF, text=_STEP_NAMES[i])
