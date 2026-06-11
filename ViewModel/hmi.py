"""
Module: hmi (Hmi)
Purpose: Tkinter HMI panel for one robot — jog controls, mode selection, status display.
Responsibilities: Render all operator controls, translate widget events into hmiControl flags,
                  display axis positions from hmiState, show fault/status feedback.
Inputs:  Button/slider events from operator; hmiState from RobotController via setHmiState().
Outputs: hmiControl flags read by RobotController; status label shown to operator.
Dependencies: tkinter, ViewModel.hmiControl, ViewModel.hmiState
"""

import sys
sys.path.append('../ViewModel')

import tkinter as tk
from tkinter import ttk
from hmiControl import hmiControl
from hmiState import hmiState


class Hmi:
    def __init__(self, parent, nameofHmi):
        self.root = tk.Frame(
            parent,
            bg="lightblue",
            width=400,
            height=370,
            relief="ridge",
            borderwidth=2
        )

        self.root.pack(side="left", padx=5)
        self.root.pack_propagate(False)

        self.hmiControl = hmiControl()
        self.hmiState = hmiState()

        links = 10
        rechts = 250

        # ---------------- EVENTS ----------------

        def on_coord_changed(event):
            selected = self._combo_axis.get()
            self.hmiControl.CoordSystem = selected
            if selected == "Joint":
                self.LabelPos1.config(text="J1:")
                self.LabelPos2.config(text="J2:")
                self.LabelPos3.config(text="Z :")
                self.LabelPos4.config(text="J4:")
            else:
                self.LabelPos1.config(text="X :")
                self.LabelPos2.config(text="Y :")
                self.LabelPos3.config(text="Z :")
                self.LabelPos4.config(text="R :")
            self._update_mode_display()

        def on_mode_changed(event):
            selected = self._combo_mode.get()
            self.hmiControl.OperationMode = 0 if selected == "Hand" else 1
            self._update_mode_display()

        def on_start_click():
            self.hmiControl.Start = True
            self.hmiControl.Stop = False

        def on_stop_click():
            self.hmiControl.Start = False
            self.hmiControl.Stop = True

        def on_reset_click():
            self.hmiControl.Reset = True
            self.hmiControl.Start = False

        def on_override_changed(val):
            pct = int(float(val))
            self.hmiControl.OverridePercent = pct
            self._override_value_label.config(text=f"{pct}%")
            self._update_mode_display()

        # ---------------- UI ----------------

        titel = tk.Label(
            self.root,
            text=nameofHmi,
            bg="lightblue",
            font=("Arial", 12, "bold")
        )
        titel.pack(pady=5)

        # Koordinatensystem
        self._combo_axis = ttk.Combobox(
            self.root,
            values=["Welt", "Joint", "Werkzeug"],
            state="readonly"
        )
        self._combo_axis.set("wählen")
        self._combo_axis.bind("<<ComboboxSelected>>", on_coord_changed)
        self._combo_axis.place(x=links, y=40)

        # Betriebsart
        self._combo_mode = ttk.Combobox(
            self.root,
            values=["Hand", "Automatisch"],
            state="readonly"
        )
        self._combo_mode.set("wählen")
        self._combo_mode.bind("<<ComboboxSelected>>", on_mode_changed)
        self._combo_mode.place(x=rechts, y=40)

        # Aktiv-Modus-Anzeige (Betriebsart | Koordinatensystem | Override)
        self.mode_label = tk.Label(
            self.root,
            text="",
            bg="lightsalmon",
            relief="sunken",
            font=("Arial", 8),
            anchor="center"
        )
        self.mode_label.place(x=links, y=68, width=380, height=20)

        # Achszeilen X / Y / Z / R
        self.LabelPos1, self.ButtonXPlus, self.ButtonXNeg, self.x_label = \
            self._create_axis_row("X :", 100, self.x_plus, self.x_minus)
        self.LabelPos2, self.ButtonYPlus, self.ButtonYNeg, self.y_label = \
            self._create_axis_row("Y :", 130, self.y_plus, self.y_minus)
        self.LabelPos3, self.ButtonZPlus, self.ButtonZNeg, self.z_label = \
            self._create_axis_row("Z :", 160, self.z_plus, self.z_minus)
        self.LabelPos4, self.ButtonRPlus, self.ButtonRNeg, self.r_label = \
            self._create_axis_row("R :", 190, self.r_plus, self.r_minus)

        # Override-Schieberegler
        override_label = tk.Label(self.root, text="Override:", bg="lightblue")
        override_label.place(x=links, y=228)

        self._override_value_label = tk.Label(self.root, text="100%", bg="lightblue", width=5)
        self._override_value_label.place(x=345, y=228)

        override_slider = ttk.Scale(
            self.root,
            from_=0, to=100,
            orient="horizontal",
            length=240,
            command=on_override_changed
        )
        override_slider.set(100)
        override_slider.place(x=90, y=228)

        # Statusanzeige
        self.status_label = tk.Label(
            self.root,
            text="Bereit",
            bg="lightgreen",
            relief="sunken",
            font=("Arial", 10, "bold"),
            anchor="center"
        )
        self.status_label.place(x=links, y=262, width=380, height=28)

        # Schaltflächen Start / Reset / Stop
        button_start = tk.Button(
            self.root, text="Start", width=10, command=on_start_click
        )
        button_start.place(x=10, y=305)

        button_reset = tk.Button(
            self.root, text="Reset", width=10, command=on_reset_click
        )
        button_reset.place(x=140, y=305)

        button_stop = tk.Button(
            self.root, text="Stop", width=10, command=on_stop_click
        )
        button_stop.place(x=270, y=305)

        # Initialzustand der Modus-Anzeige setzen
        self._update_mode_display()

    # ============================================================
    # MODUS-ANZEIGE
    # ============================================================
    def _update_mode_display(self):
        """Aktualisiert die Modus-Anzeigeleiste (Betriebsart | Koordinaten | Override)."""
        betrieb = self._combo_mode.get()
        koord   = self._combo_axis.get()
        ov      = self.hmiControl.OverridePercent

        betrieb_text = betrieb if betrieb != "wählen" else "—"
        koord_text   = koord   if koord   != "wählen" else "—"

        unvollstaendig = betrieb == "wählen" or koord == "wählen"

        if unvollstaendig:
            bg = "lightsalmon"
        elif betrieb == "Automatisch":
            bg = "lightyellow"
        else:
            bg = "lightcyan"

        self.mode_label.config(
            text=f"{betrieb_text}  |  {koord_text}  |  Ov: {ov} %",
            bg=bg
        )

    # ============================================================
    # AXIS ROW HELPER
    # ============================================================
    def _create_axis_row(self, label_text, y_pos, plus_handler, minus_handler):
        name_label = tk.Label(self.root, text=label_text, bg="lightblue")
        name_label.place(x=10, y=y_pos)

        value_label = tk.Label(self.root, text="0", bg="lightblue")
        value_label.place(x=200, y=y_pos)

        btn_plus = tk.Button(self.root, text="+", width=3)
        btn_plus.place(x=80, y=y_pos - 5)
        btn_plus.bind("<Button-1>", lambda event: plus_handler(True))
        btn_plus.bind("<ButtonRelease-1>", lambda event: plus_handler(False))

        btn_neg = tk.Button(self.root, text="-", width=3)
        btn_neg.place(x=120, y=y_pos - 5)
        btn_neg.bind("<Button-1>", lambda event: minus_handler(True))
        btn_neg.bind("<ButtonRelease-1>", lambda event: minus_handler(False))

        return name_label, btn_plus, btn_neg, value_label

    # ============================================================
    # JOG HANDLERS
    # ============================================================
    def is_hand_mode(self):
        return self.hmiControl.OperationMode == 0

    def x_plus(self, value):
        self.hmiControl.MoveXPlus = value

    def x_minus(self, value):
        self.hmiControl.MoveXNeg = value

    def y_plus(self, value):
        self.hmiControl.MoveYPlus = value

    def y_minus(self, value):
        self.hmiControl.MoveYNeg = value

    def z_plus(self, value):
        self.hmiControl.MoveZPlus = value

    def z_minus(self, value):
        self.hmiControl.MoveZNeg = value

    def r_plus(self, value):
        self.hmiControl.MoveRPlus = value

    def r_minus(self, value):
        self.hmiControl.MoveRNeg = value

    # ============================================================
    # STATE IN / OUT
    # ============================================================
    def getHmiControl(self):
        return self.hmiControl

    def setHmiState(self, hmiState):
        self.hmiState = hmiState
        if self.hmiControl.CoordSystem == "Joint":
            self.x_label["text"] = round(self.hmiState.axisJ1Position, 1)
            self.y_label["text"] = round(self.hmiState.axisJ2Position, 1)
            self.z_label["text"] = round(self.hmiState.axisJ3Position, 1)
            self.r_label["text"] = round(self.hmiState.axisJ4Position, 1)
        else:
            self.x_label["text"] = round(self.hmiState.axisXPosition, 1)
            self.y_label["text"] = round(self.hmiState.axisYPosition, 1)
            self.z_label["text"] = round(self.hmiState.axisZPosition, 1)
            self.r_label["text"] = round(self.hmiState.axisRPosition, 1)

    def setStatus(self, text, color="lightgreen"):
        """Update the status label shown to the operator."""
        self.status_label.config(text=text, bg=color)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("HMI Test")
    root.geometry("1250x415")

    frame1 = tk.Frame(root)
    frame1.pack(side="left", padx=5)
    frame2 = tk.Frame(root)
    frame2.pack(side="left", padx=5)
    frame3 = tk.Frame(root)
    frame3.pack(side="left", padx=5)

    hmi1 = Hmi(frame1, "Roboter Scara 1")
    hmi2 = Hmi(frame2, "Roboter H-Bot")
    hmi3 = Hmi(frame3, "Roboter Scara 2")

    root.mainloop()
