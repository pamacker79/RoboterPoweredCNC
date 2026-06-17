"""
Module: hmi (Hmi)
Purpose: Tkinter HMI panel for one SCARA robot — jog controls, mode/coordinate selection,
         override, sequence indicator, status display, suction button.
Inputs:  Button/slider events from operator; hmiState from RobotController via setHmiState().
Outputs: hmiControl flags read by RobotController.
Dependencies: tkinter, ViewModel.hmiControl, ViewModel.hmiState
"""

import sys
sys.path.append('../ViewModel')

import tkinter as tk
from tkinter import ttk
from hmiControl import hmiControl
from hmiState   import hmiState

# ── Design-Tokens ─────────────────────────────────────────────────────────────
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

# ── Y-Raster (gleich wie hmiHBot.py) ──────────────────────────────────────────
_Y_TITLE     = 8
_Y_LBL       = 42
_Y_COMBO     = 58
_Y_MODEBAR   = 82
_Y_ACHSEN    = 106
_Y_AXIS1     = 128
_Y_AXIS2     = 154
_Y_AXIS3     = 180
_Y_AXIS4     = 206
_Y_SEQUENZ   = 232
_Y_SEQ_BOXES = 254
_Y_OVERRIDE  = 286
_Y_OV_CTRL   = 309
_Y_STATUS    = 336
_Y_STAT_LBL  = 358
_Y_STEUERUNG = 400
_Y_BUTTONS   = 422

# ── SCARA sequence step groups ─────────────────────────────────────────────────
# Each entry: (label, [auto-states that belong to this step], active-color)
_SCARA_STEPS = [
    ("Warten",    [0],       "lightgreen"),
    ("Anfahrt",   [1],       "#f9e79f"),
    ("Greifen",   [2, 3, 4], "orange"),
    ("Transport", [5],       "#f9e79f"),
    ("Ablegen",   [6, 7, 8], "orange"),
    ("Heimfahrt", [9],       "lightcyan"),
]


def _sec_header(parent, text, y):
    tk.Label(parent, text=f"  {text}", bg=BG_SEC, fg=FG_SEC,
             font=FONT_SEC, anchor="w").place(x=M, y=y, width=CW, height=18)


class Hmi:
    def __init__(self, parent, nameofHmi):
        self.root = tk.Frame(parent, bg=BG, width=W, height=H,
                             relief="ridge", borderwidth=2)
        self.root.pack(side="left", padx=5)
        self.root.pack_propagate(False)

        self.hmiControl = hmiControl()
        self.hmiState   = hmiState()

        # ── Events ────────────────────────────────────────────────────────────
        def on_coord(event):
            sel = self._cmb_coord.get()
            self.hmiControl.CoordSystem = sel
            jnt = (sel == "Joint")
            self.LabelPos1.config(text="J1 :" if jnt else "X  :")
            self.LabelPos2.config(text="J2 :" if jnt else "Y  :")
            self.LabelPos3.config(text="Z  :")
            self.LabelPos4.config(text="J4 :" if jnt else "R  :")
            self._refresh_modebar()

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
        tk.Label(self.root, text=nameofHmi, bg=BG,
                 font=FONT_TITLE, anchor="center"
                 ).place(x=M, y=_Y_TITLE, width=CW, height=26)

        # ── Dropdowns: Betriebsart / Koordinaten ──────────────────────────────
        tk.Label(self.root, text="Betriebsart:", bg=BG,
                 font=FONT_LBL).place(x=M, y=_Y_LBL)
        self._cmb_mode = ttk.Combobox(
            self.root, values=["Hand", "Automatisch"],
            state="readonly", width=12)
        self._cmb_mode.set("wählen")
        self._cmb_mode.bind("<<ComboboxSelected>>", on_mode)
        self._cmb_mode.place(x=M, y=_Y_COMBO)

        tk.Label(self.root, text="Koordinaten:", bg=BG,
                 font=FONT_LBL).place(x=210, y=_Y_LBL)
        self._cmb_coord = ttk.Combobox(
            self.root, values=["Welt", "Joint", "Werkzeug"],
            state="readonly", width=12)
        self._cmb_coord.set("wählen")
        self._cmb_coord.bind("<<ComboboxSelected>>", on_coord)
        self._cmb_coord.place(x=210, y=_Y_COMBO)

        # ── Modus-Streifen ────────────────────────────────────────────────────
        self._modebar = tk.Label(self.root, text="", bg=BG_MODEBAR,
                                 relief="sunken", font=("Arial", 8),
                                 anchor="center")
        self._modebar.place(x=M, y=_Y_MODEBAR, width=CW, height=18)

        # ── ACHSEN ────────────────────────────────────────────────────────────
        _sec_header(self.root, "ACHSEN", _Y_ACHSEN)
        self.LabelPos1, self._val_x = self._axis_row(
            "X  :", _Y_AXIS1, "MoveXPlus", "MoveXNeg")
        self.LabelPos2, self._val_y = self._axis_row(
            "Y  :", _Y_AXIS2, "MoveYPlus", "MoveYNeg")
        self.LabelPos3, self._val_z = self._axis_row(
            "Z  :", _Y_AXIS3, "MoveZPlus", "MoveZNeg")
        self.LabelPos4, self._val_r = self._axis_row(
            "R  :", _Y_AXIS4, "MoveRPlus", "MoveRNeg")

        # ── SEQUENZ ───────────────────────────────────────────────────────────
        _sec_header(self.root, "SEQUENZ", _Y_SEQUENZ)

        self._seq_widgets = []
        n      = len(_SCARA_STEPS)
        gap_w  = 8
        step_w = (CW - (n - 1) * gap_w) // n   # (380 - 40) // 6 = 56
        x_pos  = M
        for i, (name, _, _clr) in enumerate(_SCARA_STEPS):
            lbl = tk.Label(self.root, text=name,
                           bg=_CLR_OFF, relief="groove",
                           font=("Arial", 7, "bold"), anchor="center")
            lbl.place(x=x_pos, y=_Y_SEQ_BOXES, width=step_w, height=24)
            self._seq_widgets.append(lbl)
            x_pos += step_w
            if i < n - 1:
                tk.Label(self.root, text="›", bg=BG,
                         font=("Arial", 8)).place(x=x_pos + 1, y=_Y_SEQ_BOXES + 3,
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
        self.status_label = tk.Label(
            self.root, text="Bereit", bg="lightgreen",
            relief="sunken", font=FONT_STAT, anchor="center")
        self.status_label.place(x=M, y=_Y_STAT_LBL, width=CW, height=34)

        # ── STEUERUNG ─────────────────────────────────────────────────────────
        _sec_header(self.root, "STEUERUNG", _Y_STEUERUNG)
        tk.Button(self.root, text="Reset", width=9, font=FONT_BTN,
                  command=lambda: setattr(self.hmiControl, "Reset", True)
                  ).place(x=M, y=_Y_BUTTONS)
        self._saugen_btn = tk.Button(
            self.root, text="Saugen", width=20, font=FONT_BTN, bg="#fffacd",
            command=lambda: setattr(self.hmiControl, "Saugen", True))
        self._saugen_btn.place(x=128, y=_Y_BUTTONS)

        self._refresh_modebar()

    # ── Achszeile ─────────────────────────────────────────────────────────────
    def _axis_row(self, label, y, attr_p, attr_n):
        name_lbl = tk.Label(self.root, text=label, bg=BG, font=FONT_LBL)
        name_lbl.place(x=M, y=y)

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
        return name_lbl, val

    # ── Modus-Streifen ────────────────────────────────────────────────────────
    def _refresh_modebar(self):
        mode  = self._cmb_mode.get()
        coord = self._cmb_coord.get()
        ov    = self.hmiControl.OverridePercent
        mt    = mode  if mode  != "wählen" else "—"
        ct    = coord if coord != "wählen" else "—"
        ok    = mode != "wählen" and coord != "wählen"
        bg    = ("#f9e79f" if ok and mode == "Automatisch" else
                 "#d5f5e3" if ok else BG_MODEBAR)
        self._modebar.config(text=f"{mt}  |  {ct}  |  Ov: {ov} %", bg=bg)

    # ── Öffentliche Schnittstelle ─────────────────────────────────────────────
    def getHmiControl(self):
        return self.hmiControl

    def setHmiState(self, state: hmiState):
        self.hmiState = state
        if self.hmiControl.CoordSystem == "Joint":
            self._val_x.config(text=f"{state.axisJ1Position:8.1f}")
            self._val_y.config(text=f"{state.axisJ2Position:8.1f}")
            self._val_z.config(text=f"{state.axisJ3Position:8.1f}")
            self._val_r.config(text=f"{state.axisJ4Position:8.1f}")
        else:
            self._val_x.config(text=f"{state.axisXPosition:8.1f}")
            self._val_y.config(text=f"{state.axisYPosition:8.1f}")
            self._val_z.config(text=f"{state.axisZPosition:8.1f}")
            self._val_r.config(text=f"{state.axisRPosition:8.1f}")

    def setSequenceState(self, state: int):
        """Hebt den aktiven Schritt im Sequenz-Indikator hervor."""
        for widget, (name, states, color) in zip(self._seq_widgets, _SCARA_STEPS):
            if state in states:
                widget.config(bg=color, text=name)
            else:
                widget.config(bg=_CLR_OFF, text=name)

    def setStatus(self, text: str, color: str = "lightgreen"):
        self.status_label.config(text=text, bg=color)

    def set_saugen_enabled(self, enabled: bool):
        self._saugen_btn.config(state="normal" if enabled else "disabled")

    # ── Kompatibilitäts-Stubs ─────────────────────────────────────────────────
    def is_hand_mode(self): return self.hmiControl.OperationMode == 0
    def x_plus(self, v):  self.hmiControl.MoveXPlus = v
    def x_minus(self, v): self.hmiControl.MoveXNeg  = v
    def y_plus(self, v):  self.hmiControl.MoveYPlus = v
    def y_minus(self, v): self.hmiControl.MoveYNeg  = v
    def z_plus(self, v):  self.hmiControl.MoveZPlus = v
    def z_minus(self, v): self.hmiControl.MoveZNeg  = v
    def r_plus(self, v):  self.hmiControl.MoveRPlus = v
    def r_minus(self, v): self.hmiControl.MoveRNeg  = v


if __name__ == "__main__":
    root = tk.Tk()
    root.title("HMI Test")
    root.geometry("1260x475")
    for name in ["Roboter 1 SCARA", "H-Bot (Gravur)", "Roboter 3 SCARA"]:
        f = tk.Frame(root)
        f.pack(side="left", padx=5)
        Hmi(f, name)
    root.mainloop()
