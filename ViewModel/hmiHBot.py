"""
Module: HmiHBot
Purpose: Tkinter HMI panel specialized for the H-Bot engraving gantry.
         Same design language and height as hmi.py — only X/Y axes, no coord selector,
         no Saugen button; adds sequence step indicator.
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
                 ).place(x=M, y=8, width=CW, height=26)

        # ── Betriebsart ───────────────────────────────────────────────────────
        tk.Label(self.root, text="Betriebsart:", bg=BG,
                 font=FONT_LBL).place(x=M, y=42)
        self._cmb_mode = ttk.Combobox(
            self.root, values=["Hand", "Automatisch"],
            state="readonly", width=14)
        self._cmb_mode.set("wählen")
        self._cmb_mode.bind("<<ComboboxSelected>>", on_mode)
        self._cmb_mode.place(x=M, y=58)

        # ── Modus-Streifen ────────────────────────────────────────────────────
        self._modebar = tk.Label(self.root, text="", bg=BG_MODEBAR,
                                 relief="sunken", font=("Arial", 8),
                                 anchor="center")
        self._modebar.place(x=M, y=82, width=CW, height=18)

        # ── ACHSEN (nur X / Y) ────────────────────────────────────────────────
        _sec_header(self.root, "ACHSEN", 106)
        self._val_x = self._axis_row("X  :", 128, "MoveXPlus", "MoveXNeg")
        self._val_y = self._axis_row("Y  :", 154, "MoveYPlus", "MoveYNeg")

        # ── SEQUENZ ───────────────────────────────────────────────────────────
        _sec_header(self.root, "SEQUENZ", 186)

        self._step_widgets = []
        n      = len(_STEP_NAMES)
        gap_w  = 10
        step_w = (CW - (n - 1) * gap_w) // n   # = (380 - 40) // 5 = 68
        x_pos  = M
        for i, name in enumerate(_STEP_NAMES):
            lbl = tk.Label(self.root, text=name,
                           bg=_CLR_OFF, relief="groove",
                           font=("Arial", 8, "bold"), anchor="center")
            lbl.place(x=x_pos, y=208, width=step_w, height=26)
            self._step_widgets.append(lbl)
            x_pos += step_w
            if i < n - 1:
                tk.Label(self.root, text="›", bg=BG,
                         font=("Arial", 9)).place(x=x_pos + 1, y=211, width=gap_w - 2)
                x_pos += gap_w

        # ── OVERRIDE ──────────────────────────────────────────────────────────
        _sec_header(self.root, "OVERRIDE", 244)
        tk.Label(self.root, text="0 %", bg=BG,
                 font=FONT_LBL).place(x=M, y=267)
        self._lbl_ov = tk.Label(self.root, text="100 %", bg=BG, font=FONT_VAL)
        self._lbl_ov.place(x=336, y=267)
        ov = ttk.Scale(self.root, from_=0, to=100, orient="horizontal",
                       length=280, command=on_override)
        ov.set(100)
        ov.place(x=34, y=268)

        # ── STATUS ────────────────────────────────────────────────────────────
        _sec_header(self.root, "STATUS", 294)
        self._lbl_status = tk.Label(
            self.root, text="Bereit", bg="lightgreen",
            relief="sunken", font=FONT_STAT, anchor="center")
        self._lbl_status.place(x=M, y=316, width=CW, height=34)

        # ── STEUERUNG ─────────────────────────────────────────────────────────
        _sec_header(self.root, "STEUERUNG", 358)
        tk.Button(self.root, text="Reset", width=9, font=FONT_BTN,
                  command=lambda: setattr(self.hmiControl, "Reset", True)
                  ).place(x=M, y=380)

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

    # ── Modus-Streifen ────────────────────────────────────────────────────────
    def _refresh_modebar(self):
        mode = self._cmb_mode.get()
        ov   = self.hmiControl.OverridePercent
        mt   = mode if mode != "wählen" else "—"
        ok   = mode != "wählen"
        bg   = ("#f9e79f" if ok and mode == "Automatisch" else
                "#d5f5e3" if ok else BG_MODEBAR)
        self._modebar.config(text=f"{mt}  |  Ov: {ov} %", bg=bg)

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
