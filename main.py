"""
Modul: main (Machine)
======================
Anwendungseinstiegspunkt und zentraler 100-Hz-Steuerkreis.

Systemarchitektur
-----------------
Die Klasse ``Machine`` verdrahtet alle MVC-Schichten und läuft im
Hauptthread in einer 100-Hz-Endlosschleife (time.sleep(0.01)):

    ┌──────────────────────────────────────────────────────────────┐
    │  Main Loop (100 Hz)                                          │
    │                                                              │
    │  update_hmi_window()    — Tkinter-Events verarbeiten         │
    │  update_hmi_hbot()      — H-Bot HMI + Automatik-Sequenz     │
    │  for ctrl in scaras:                                         │
    │      ctrl.update_hmi()       — HMI → Steuerung              │
    │      ctrl.update_kinematics() — FK / IK berechnen           │
    │      ctrl.cyclic()           — Bewegungsrampe               │
    │      ctrl.update_view()      — 3D-Scene aktualisieren       │
    │  update_views()         — H-Bot 3D aktualisieren            │
    └──────────────────────────────────────────────────────────────┘

Roboterkonfiguration
---------------------
* **Roboter 1** (SCARA links):  Greift Rohteile aus dem Magazin und legt
  sie auf die H-Bot-Arbeitsfläche.  Startet nur wenn Roboter 3 in der
  Heimatposition ist (``_robot1_pickup_allowed()``).
* **H-Bot** (Mitte):           Graviert das Bauteil mit einem Laserkopf.
  Fährt eine Sequenz von 7 Wegpunkten ab (Rechteck um das Bauteilzentrum).
* **Roboter 3** (SCARA rechts): Greift das gravierte Bauteil vom H-Bot
  und legt es in den Endstapel rechts.  Startet nur wenn der H-Bot in
  Parkposition ist (``_robot3_pickup_allowed()``).

Weltkoordinaten-Referenz
-------------------------
+-------------------+---------------------------+
| Konstante         | Bedeutung                |
+-------------------+---------------------------+
| _HBOT_WORLD       | H-Bot Arbeitsfläche (Welt)|
| _HBOT_ENGRAVE_CENTER | H-Bot MCS beim Gravieren |
| _DEPOSIT_WORLD    | Ablage Roboter 3 (Welt)  |
| _MAG_PICKUP_WORLD | Magazin-Mitte (Welt)     |
+-------------------+---------------------------+

H-Bot Automatik-Zustandsmaschine
----------------------------------
_HB_IDLE     (0) — Wartet auf Bauteil und Freigabe durch Roboter 1.
_HB_APPROACH (4) — Fährt zur Gravur-Startposition (MCS).
_HB_ENGRAVE  (1) — Fährt alle 7 Gravur-Wegpunkte ab.
_HB_RETURN   (2) — Fährt in Parkposition (300, 100).
_HB_DONE     (3) — Gravur fertig; wartet auf Abholung durch Roboter 3.

Übergänge werden ankunftsbasiert ausgelöst (``_hbot_at_target()``),
sodass Override die Geschwindigkeit skaliert ohne Zustände zu überspringen.

Abhängigkeiten
--------------
* ``Model.hBot``              — H-Bot Kinematik
* ``Model.Scara``             — SCARA Kinematik
* ``Model.WorkpieceManager``  — Bauteilregistrierung
* ``Model.RobotConfig``       — SCARA_HOME-Position
* ``View.Scara``              — SCARA 3D-Visualisierung
* ``View.HBot``               — H-Bot 3D-Visualisierung
* ``View.MagazinViewPV``      — Magazin 3D-Visualisierung
* ``ViewModel.hmi``           — SCARA HMI-Panels
* ``ViewModel.hmiHBot``       — H-Bot HMI-Panel
* ``ViewModel.hmiState``      — Istwert-DTOs
* ``ViewModel.RobotController`` — SCARA-Orchestrierung
* ``tkinter``                 — HMI-Fenster
* ``pyvista``                 — 3D-Szene
"""
import os
import sys

# Tcl/Tk Bibliotheken explizit setzen (verhindert Fehler bei Python-Installations
# die kein System-Tk haben)
python_base = sys.base_prefix
tcl_path = os.path.join(python_base, "tcl", "tcl8.6")
tk_path  = os.path.join(python_base, "tcl", "tk8.6")
if os.path.exists(tcl_path):
    os.environ["TCL_LIBRARY"] = tcl_path
if os.path.exists(tk_path):
    os.environ["TK_LIBRARY"] = tk_path

sys.path.append('./Model')
sys.path.append('./ViewModel')
sys.path.append('./View')

import time
import tkinter as tk
import pyvista as pv

from Model.hBot             import hBot
from Model.Scara            import Scara
from Model.WorkpieceManager import WorkpieceManager

from View.Scara         import Scara as ScaraView
from View.HBot          import HBot  as HBotView
from View.MagazinViewPV import MagazinViewPV

from Model.RobotConfig         import SCARA_HOME

from ViewModel.hmi             import Hmi
from ViewModel.hmiHBot         import HmiHBot
from ViewModel.hmiState        import hmiState
from ViewModel.RobotController import RobotController

# ── Weltkoordinaten-Referenzpunkte ────────────────────────────────────────────
_HBOT_WORLD          = (381.0,  195.0)   # Arbeitsfläche des H-Bots (Weltkoordinaten)
_HBOT_ENGRAVE_CENTER = ( 80.0, -155.0)  # H-Bot MCS-Koordinaten beim Gravieren
_DEPOSIT_WORLD       = (900.0, -720.0)  # Ablageposition Roboter 3
_MAG_PICKUP_WORLD    = (-300.0, -325.0)  # Magazin-Zentrum

# ── H-Bot Automatik-Zustände ──────────────────────────────────────────────────
_HB_IDLE      = 0   # Wartet auf Bauteil
_HB_APPROACH  = 4   # Fährt zur Gravurposition
_HB_ENGRAVE   = 1   # Gravurmuster wird abgefahren
_HB_RETURN    = 2   # Rückfahrt zur Parkposition
_HB_DONE      = 3   # Gravur fertig, Roboter 3 kann greifen


class Machine:
    """
    Zentrale Maschinenklasse — verdrahtet alle Modell-, View- und ViewModel-Objekte.

    Erzeugt alle Modelle, Views, HMI-Panels und Controller; enthält ausserdem
    die H-Bot-Zustandsmaschine direkt (da der H-Bot keinen eigenen Controller hat).
    """

    def __init__(self):
        """Initialisiert alle Systemkomponenten und richtet die 3D-Szene ein."""
        self.running = True

        # ── Modelle ───────────────────────────────────────────────────────────
        self.robot1Trafo = Scara()
        self.robot3Trafo = Scara()

        # SCARA-Roboter auf Heimatposition initialisieren
        for trafo in (self.robot1Trafo, self.robot3Trafo):
            for attr, val in SCARA_HOME.items():
                ax = getattr(trafo, attr)
                ax.Sollposition   = val
                ax.ActualPosition = val

        self.CncTrafo = hBot()
        self.wpm      = WorkpieceManager()

        # H-Bot Startposition (auf der Arbeitsfläche)
        _HBOT_START_X = _HBOT_WORLD[0]
        _HBOT_START_Y = _HBOT_WORLD[1]
        self.hbotX = _HBOT_START_X
        self.hbotY = _HBOT_START_Y
        self.CncTrafo.mcsAxisX.Sollposition   = _HBOT_START_X
        self.CncTrafo.mcsAxisX.ActualPosition = _HBOT_START_X
        self.CncTrafo.mcsAxisY.Sollposition   = _HBOT_START_Y
        self.CncTrafo.mcsAxisY.ActualPosition = _HBOT_START_Y

        # H-Bot Automatik-Zustand
        self._hb_state    = _HB_IDLE
        self._hb_tick     = 0
        self.hbot_at_home = True   # Roboter 3 prüft diesen Flag vor dem Griff

        # Gravurmuster: Rechteck mit 50 mm Radius um den Gravur-Mittelpunkt
        cx, cy = _HBOT_ENGRAVE_CENTER
        r      = 50.0
        self._hb_engrave_moves = [
            (cx,     cy    ),   # Mitte (Bauteil-Zentrum)
            (cx,     cy + r),   # Nord
            (cx + r, cy + r),   # Nord-Ost
            (cx + r, cy - r),   # Süd-Ost
            (cx - r, cy - r),   # Süd-West
            (cx - r, cy + r),   # Nord-West
            (cx,     cy    ),   # zurück zur Mitte
        ]
        self._hb_move_idx = 0

        # ── HMI-Fenster ───────────────────────────────────────────────────────
        self.hmiRoot = tk.Tk()
        self.hmiRoot.title("3 Roboter")
        self.hmiRoot.geometry("1250x475")
        self.hmiRoot.protocol("WM_DELETE_WINDOW", self.close_program)

        self.frame1 = tk.Frame(self.hmiRoot)
        self.frame1.pack(side="left", padx=5)
        self.frame2 = tk.Frame(self.hmiRoot)
        self.frame2.pack(side="left", padx=5)
        self.frame3 = tk.Frame(self.hmiRoot)
        self.frame3.pack(side="left", padx=5)

        self.hmiRobot1 = Hmi(self.frame1, "Roboter 1 SCARA")
        self.hmiCnc    = HmiHBot(self.frame2, "H-Bot (Gravur)")
        self.hmiRobot3 = Hmi(self.frame3, "Roboter 3 SCARA")

        self.hmi1State   = hmiState()
        self.hmi3State   = hmiState()
        self.hmiCncState = hmiState()

        # ── Gemeinsame 3D-Szene ───────────────────────────────────────────────
        self.sharedPlotter = pv.Plotter()

        self.scaraView1  = ScaraView(pl=self.sharedPlotter, position=(-150,  250, 0), rotation_z=180.0)
        self.cncView     = HBotView( pl=self.sharedPlotter, position=(    0,    0, 150))
        self.scaraView3  = ScaraView(pl=self.sharedPlotter, position=( 900,  170, 0), rotation_z=180.0, base_rotation_z=0.0)
        self.magazinView = MagazinViewPV(pl=self.sharedPlotter, position=(-300, -325, 0))

        self.sharedPlotter.show_axes()
        self.sharedPlotter.camera_position = [
            (  0.0, -1500.0, 1000.0),
            (  0.0,     0.0,    0.0),
            (  0.0,     0.0,    1.0),
        ]
        self.sharedPlotter.show(interactive_update=True, auto_close=False)

        # ── SCARA-Controller ──────────────────────────────────────────────────
        # Roboter 1: Magazin → H-Bot-Arbeitsfläche
        # pickup_gate: Roboter 3 muss in Heimatposition sein
        self.robot1_ctrl = RobotController(
            robot_trafo       = self.robot1Trafo,
            robot_view        = self.scaraView1,
            hmi               = self.hmiRobot1,
            hmi_state         = self.hmi1State,
            workpiece_manager = self.wpm,
            magazin_view      = self.magazinView,
            pickup_world      = _MAG_PICKUP_WORLD,
            place_world       = _HBOT_WORLD,
            pickup_gate       = self._robot1_pickup_allowed,
        )

        # Roboter 3: H-Bot-Arbeitsfläche → Endlager rechts
        # pickup_gate: H-Bot muss in Parkposition sein (Gravur fertig)
        self.robot3_ctrl = RobotController(
            robot_trafo       = self.robot3Trafo,
            robot_view        = self.scaraView3,
            hmi               = self.hmiRobot3,
            hmi_state         = self.hmi3State,
            workpiece_manager = self.wpm,
            magazin_view      = None,
            pickup_world      = _HBOT_WORLD,
            place_world       = _DEPOSIT_WORLD,
            pickup_gate       = self._robot3_pickup_allowed,
            place_is_sink     = True,   # Endlager: kein Belegtheitsprüfung
        )

        self.scara_controllers = [self.robot1_ctrl, self.robot3_ctrl]

    # =========================================================================
    # Programmende
    # =========================================================================

    def close_program(self):
        """
        Beendet das Programm sauber.

        Setzt ``running=False``, schliesst den PyVista-Plotter und
        zerstört das Tkinter-Hauptfenster.
        """
        self.running = False
        try:
            self.sharedPlotter.close()
        except Exception:
            pass
        try:
            self.hmiRoot.destroy()
        except Exception:
            pass

    # =========================================================================
    # Tkinter-Update
    # =========================================================================

    def update_hmi_window(self):
        """
        Verarbeitet ausstehende Tkinter-Events und zeichnet das HMI-Fenster neu.

        Muss jeden Loop-Tick aufgerufen werden, damit die GUI responsiv bleibt.
        Setzt ``running=False`` bei TclError (Fenster wurde geschlossen).
        """
        try:
            self.hmiRoot.update_idletasks()
            self.hmiRoot.update()
        except tk.TclError:
            self.running = False

    # =========================================================================
    # H-Bot-Steuerung (Handbetrieb + Automatik)
    # =========================================================================

    def update_hmi_hbot(self):
        """
        Verarbeitet H-Bot-HMI-Eingaben und führt die Automatik-Sequenz aus.

        Ablauf pro Tick:
        1. hmiControl lesen.
        2. Falls kein Modus gewählt: Hinweismeldung, keine Bewegung.
        3. Automatikbetrieb: ``_update_hbot_auto()`` aufrufen.
        4. Handbetrieb: Jog-Inkremente auf Sollposition addieren.
        5. ``CncTrafo.cyclic(override)`` — Bewegungsrampe anwenden.
        6. Istwerte aus ActualPosition in hmiState und View übernehmen.
        """
        hmi_ctrl = self.hmiCnc.getHmiControl()
        is_auto  = (hmi_ctrl.OperationMode == 1)
        override = hmi_ctrl.OverridePercent / 100.0

        if not hmi_ctrl.mode_selected:
            self.hmiCnc.setStatus("Betriebsmodus wählen!", "orange")
        elif is_auto:
            self._update_hbot_auto()
        else:
            # Handbetrieb: Sollposition direkt inkrementieren
            if hmi_ctrl.MoveXPlus: self.CncTrafo.mcsAxisX.Sollposition += 5
            if hmi_ctrl.MoveXNeg:  self.CncTrafo.mcsAxisX.Sollposition -= 5
            if hmi_ctrl.MoveYPlus: self.CncTrafo.mcsAxisY.Sollposition += 5
            if hmi_ctrl.MoveYNeg:  self.CncTrafo.mcsAxisY.Sollposition -= 5
            self.hmiCnc.setStatus("Handbetrieb — Bereit", "lightgreen")

        # Bewegungsrampe: ActualPosition folgt Sollposition mit Override-Skalierung
        self.CncTrafo.cyclic(override)

        # View und HMI folgen immer ActualPosition (nicht Sollposition)
        self.hbotX = self.CncTrafo.mcsAxisX.ActualPosition
        self.hbotY = self.CncTrafo.mcsAxisY.ActualPosition

        self.hmiCncState.axisXPosition = self.hbotX
        self.hmiCncState.axisYPosition = self.hbotY
        self.hmiCncState.axisZPosition = 0.0
        self.hmiCncState.axisRPosition = 0.0
        self.hmiCnc.setHmiState(self.hmiCncState)

    def _hbot_at_target(self, tol: float = 1.0) -> bool:
        """
        Gibt True zurück wenn ActualPosition auf Sollposition angekommen ist.

        Parameter
        ---------
        tol : float
            Ankunftstoleranz [mm].

        Rückgabe
        --------
        bool
            True wenn beide Achsen innerhalb der Toleranz sind.
        """
        return (
            abs(self.CncTrafo.mcsAxisX.ActualPosition
                - self.CncTrafo.mcsAxisX.Sollposition) <= tol
            and
            abs(self.CncTrafo.mcsAxisY.ActualPosition
                - self.CncTrafo.mcsAxisY.Sollposition) <= tol
        )

    def _update_hbot_auto(self):
        """
        Führt die H-Bot-Gravur-Automatiksequenz aus (5 Zustände).

        Übergänge sind ankunftsbasiert: jeder Bewegungszustand setzt ein Sollziel
        und wartet auf ``_hbot_at_target()``.  So skaliert Override die reale
        Verfahrgeschwindigkeit, ohne Zustände zu überspringen.

        Zustandsübergänge:
        _HB_IDLE → _HB_APPROACH (wenn Teil vorhanden und Roboter 1 idle)
        _HB_APPROACH → _HB_ENGRAVE (wenn Gravurstartposition erreicht)
        _HB_ENGRAVE → _HB_RETURN   (wenn alle Wegpunkte abgefahren)
        _HB_RETURN → _HB_DONE      (wenn Parkposition erreicht)
        _HB_DONE → _HB_IDLE        (wenn Teil von Roboter 3 abgeholt)
        """
        self._hb_tick += 1

        if self._hb_state == _HB_IDLE:
            part_ready   = self.wpm.has_part_at(_HBOT_WORLD[0], _HBOT_WORLD[1], radius=60.0)
            robot1_clear = self.robot1_ctrl.is_idle
            if part_ready and robot1_clear:
                # Gravur-Startposition als Ziel setzen und Sequenz starten
                self.CncTrafo.mcsAxisX.Sollposition = _HBOT_ENGRAVE_CENTER[0]
                self.CncTrafo.mcsAxisY.Sollposition = _HBOT_ENGRAVE_CENTER[1]
                self._hb_state    = _HB_APPROACH
                self._hb_tick     = 0
                self.hbot_at_home = False
                self.hmiCnc.setStatus("Fahre auf Werkstück...", "lightyellow")
            elif part_ready:
                self.hmiCnc.setStatus("Warte auf Roboter 1...", "lightsalmon")
            else:
                self.hmiCnc.setStatus("Automatik — wartet auf Teil", "lightcyan")

        elif self._hb_state == _HB_APPROACH:
            # Warten bis der Laserkopf physisch an der Gravurposition angekommen ist
            if self._hbot_at_target():
                self._hb_state    = _HB_ENGRAVE
                self._hb_tick     = 0
                self._hb_move_idx = 0
                self.hmiCnc.setStatus("Gravur läuft...", "lightyellow")

        elif self._hb_state == _HB_ENGRAVE:
            if self._hb_move_idx < len(self._hb_engrave_moves):
                # Wegpunkt als Sollposition halten bis angekommen
                tx, ty = self._hb_engrave_moves[self._hb_move_idx]
                self.CncTrafo.mcsAxisX.Sollposition = tx
                self.CncTrafo.mcsAxisY.Sollposition = ty
                if self._hbot_at_target():
                    self._hb_move_idx += 1   # Nächster Wegpunkt
            else:
                # Alle Wegpunkte fertig — Rückkehr zur Parkposition
                self.CncTrafo.mcsAxisX.Sollposition = 300
                self.CncTrafo.mcsAxisY.Sollposition = 100
                self._hb_state = _HB_RETURN
                self._hb_tick  = 0

        elif self._hb_state == _HB_RETURN:
            if self._hbot_at_target():
                self._hb_state    = _HB_DONE
                self._hb_tick     = 0
                self.hbot_at_home = True
                self.hmiCnc.setStatus("Gravur fertig — warte auf Roboter 3", "lightcyan")

        elif self._hb_state == _HB_DONE:
            # Warten bis Roboter 3 das Teil abgeholt hat
            if not self.wpm.has_part_at(_HBOT_WORLD[0], _HBOT_WORLD[1], radius=60.0):
                self._hb_state = _HB_IDLE
                self._hb_tick  = 0
                self.hmiCnc.setStatus("Bereit", "lightgreen")

        # Sequenz-Indikator im HMI aktualisieren
        self.hmiCnc.setSequenceState(
            self._hb_state,
            engrave_step  = self._hb_move_idx,
            engrave_total = len(self._hb_engrave_moves),
        )

    # =========================================================================
    # 3D-Szene aktualisieren
    # =========================================================================

    def update_views(self):
        """
        Aktualisiert die H-Bot-3D-Szene mit den aktuellen ActualPosition-Werten.

        RuntimeError wird abgefangen — tritt auf wenn das PyVista-Fenster
        noch nicht vollständig initialisiert ist.
        """
        try:
            self.cncView.update_mesh_positions(x_pos=self.hbotX, y_pos=self.hbotY)
        except RuntimeError:
            pass

    # =========================================================================
    # Handshake-Guards (Kollisionsvermeidung)
    # =========================================================================

    def _robot1_pickup_allowed(self) -> bool:
        """
        Erlaubt Roboter 1 den Start nur wenn Roboter 3 in der Heimatposition ist.

        Verhindert Kollisionen wenn beide Roboter mit unterschiedlichem
        Override in der Nähe der gemeinsamen H-Bot-Arbeitsfläche operieren.
        """
        return self.robot3_ctrl.is_idle

    def _robot3_pickup_allowed(self) -> bool:
        """
        Erlaubt Roboter 3 den Start nur wenn der H-Bot im Zustand _HB_DONE ist.

        Stellt sicher, dass die Gravur vollständig abgeschlossen und der
        Laserkopf in die Parkposition zurückgefahren ist, bevor Roboter 3
        das Bauteil von der Arbeitsfläche greift.
        """
        return self._hb_state == _HB_DONE


# =============================================================================
# Hauptprogramm
# =============================================================================
if __name__ == "__main__":
    machine = Machine()

    while machine.running:
        machine.update_hmi_window()
        machine.update_hmi_hbot()

        for ctrl in machine.scara_controllers:
            ctrl.update_hmi()
            ctrl.update_kinematics()
            ctrl.cyclic()
            ctrl.update_view()

        machine.update_views()
        time.sleep(0.01)   # 100 Hz Steuerkreis

    print("Programm beendet.")
