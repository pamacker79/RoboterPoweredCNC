"""
Module: main (Machine)
Purpose: Application entry point; owns the 100 Hz control loop and wires all MVC layers.
Responsibilities: Create model/view/HMI objects, run the cyclic loop (HMI→kinematics→view),
                  manage window lifecycle, coordinate H-Bot auto-sequence.
Inputs:  Operator input via Tkinter HMI windows; G-Code file for auto mode.
Outputs: 3D PyVista scene updates; HMI state display updates.
Dependencies: Model.*, View.*, ViewModel.*, tkinter, pyvista
"""
import os
import sys

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

from Model.hBot            import hBot
from Model.Scara           import Scara
from Model.CncInterpreter  import CncInterpreter
from Model.WorkpieceManager import WorkpieceManager

from View.Scara        import Scara as ScaraView
from View.HBot         import HBot  as HBotView
from View.MagazinViewPV import MagazinViewPV

from ViewModel.hmi            import Hmi
from ViewModel.hmiState       import hmiState
from ViewModel.RobotController import RobotController

# ── World-coordinate landmarks ────────────────────────────────────────────────
_HBOT_WORLD       = (381.0, 195.0)  # H-Bot work-surface centre (Weltkoordinaten)
_DEPOSIT_WORLD    = (900.0, 720.0)  # Robot 3 deposit position (to the right)
_MAG_PICKUP_WORLD = (-300.0, -325.0)  # Magazine centre (matches MagazinViewPV position)

# ── H-Bot auto-sequence states ────────────────────────────────────────────────
_HB_IDLE      = 0
_HB_APPROACH  = 4   # move to workpiece centre before engraving
_HB_ENGRAVE   = 1   # simulated engraving moves
_HB_RETURN    = 2   # return head to parking position
_HB_DONE      = 3   # ready for Robot 3 pickup

_HB_TICKS_PER_MOVE = 40   # ticks for each simulated engraving move


class Machine:
    def __init__(self):
        self.running = True

        # ── Models ───────────────────────────────────────────────────────────
        self.robot1Trafo = Scara()
        self.robot3Trafo = Scara()
        self.robot1CncControl = CncInterpreter()
        self.CncTrafo = hBot()
        self.wpm = WorkpieceManager()

        # H-Bot Startposition (Arm an Werkzeugposition)
        _HBOT_START_X = _HBOT_WORLD[0]
        _HBOT_START_Y = _HBOT_WORLD[1]
        self.hbotX = _HBOT_START_X
        self.hbotY = _HBOT_START_Y
        self.CncTrafo.mcsAxisX.Sollposition  = _HBOT_START_X
        self.CncTrafo.mcsAxisX.ActualPosition = _HBOT_START_X
        self.CncTrafo.mcsAxisY.Sollposition  = _HBOT_START_Y
        self.CncTrafo.mcsAxisY.ActualPosition = _HBOT_START_Y

        # H-Bot auto state
        self._hb_state = _HB_IDLE
        self._hb_tick  = 0
        # Gravurmuster: Quadrat mit 50 mm Radius um Werkzeugposition (_HBOT_WORLD)
        cx, cy = _HBOT_WORLD
        r = 50.0
        self._hb_engrave_moves = [
            (cx,     cy    ),  # Mitte (Bauteil-Zentrum)
            (cx,     cy + r),  # Nord
            (cx + r, cy + r),  # Nord-Ost
            (cx + r, cy - r),  # Süd-Ost
            (cx - r, cy - r),  # Süd-West
            (cx - r, cy + r),  # Nord-West
            (cx,     cy    ),  # zurück zur Mitte
        ]
        self._hb_move_idx = 0
        self.hbot_at_home = True   # Robot 3 checks this before picking

        # ── HMI window ───────────────────────────────────────────────────────
        self.hmiRoot = tk.Tk()
        self.hmiRoot.title("3 Roboter")
        self.hmiRoot.geometry("1250x450")
        self.hmiRoot.protocol("WM_DELETE_WINDOW", self.close_program)

        self.frame1 = tk.Frame(self.hmiRoot)
        self.frame1.pack(side="left", padx=5)
        self.frame2 = tk.Frame(self.hmiRoot)
        self.frame2.pack(side="left", padx=5)
        self.frame3 = tk.Frame(self.hmiRoot)
        self.frame3.pack(side="left", padx=5)

        self.hmiRobot1 = Hmi(self.frame1, "Roboter 1 SCARA")
        self.hmiCnc    = Hmi(self.frame2, "H-Bot (Gravur)")
        self.hmiRobot3 = Hmi(self.frame3, "Roboter 3 SCARA")

        self.hmi1State   = hmiState()
        self.hmi3State   = hmiState()
        self.hmiCncState = hmiState()

        # ── Shared PyVista scene ─────────────────────────────────────────────
        self.sharedPlotter = pv.Plotter()

        # Robot 3 repositioned to (400, 300, 0) so it can reach H-Bot at (0,0)
        self.scaraView1  = ScaraView(pl=self.sharedPlotter, position=(-150,  250, 0), rotation_z=180.0)
        self.cncView     = HBotView( pl=self.sharedPlotter, position=(    0,    0, 150))
        self.scaraView3  = ScaraView(pl=self.sharedPlotter, position=(900 ,  170, 0), rotation_z=180.0, base_rotation_z=0.0)
        self.magazinView = MagazinViewPV(pl=self.sharedPlotter, position=(-300, -325, 0))

        self.sharedPlotter.show_axes()
        self.sharedPlotter.camera_position = [
            (  0.0, -1500.0, 1000.0),
            (  0.0,     0.0,    0.0),
            (  0.0,     0.0,    1.0)
        ]
        self.sharedPlotter.show(interactive_update=True, auto_close=False)

        # ── Robot controllers ─────────────────────────────────────────────────
        # Robot 1: picks from magazine, places at H-Bot centre
        self.robot1_ctrl = RobotController(
            robot_trafo   = self.robot1Trafo,
            robot_view    = self.scaraView1,
            hmi           = self.hmiRobot1,
            hmi_state     = self.hmi1State,
            workpiece_manager = self.wpm,
            magazin_view  = self.magazinView,
            pickup_world  = _MAG_PICKUP_WORLD,
            place_world   = _HBOT_WORLD,
            cnc_control   = self.robot1CncControl,
            cnc_program_path = "Model\\programm.nc",
        )

        # Robot 3: picks from H-Bot centre, deposits to the right
        # pickup_gate: only start when H-Bot has returned to home position
        self.robot3_ctrl = RobotController(
            robot_trafo   = self.robot3Trafo,
            robot_view    = self.scaraView3,
            hmi           = self.hmiRobot3,
            hmi_state     = self.hmi3State,
            workpiece_manager = self.wpm,
            magazin_view  = None,
            pickup_world  = _HBOT_WORLD,
            place_world   = _DEPOSIT_WORLD,
            pickup_gate   = self._robot3_pickup_allowed,
        )

        self.scara_controllers = [self.robot1_ctrl, self.robot3_ctrl]

    # =========================================================================
    # CLOSE
    # =========================================================================
    def close_program(self):
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
    # HMI WINDOW
    # =========================================================================
    def update_hmi_window(self):
        try:
            self.hmiRoot.update_idletasks()
            self.hmiRoot.update()
        except tk.TclError:
            self.running = False

    # =========================================================================
    # H-BOT CONTROL (manual jogging + auto-sequence)
    # =========================================================================
    def update_hmi_hbot(self):
        hmi_ctrl = self.hmiCnc.getHmiControl()
        is_auto  = (hmi_ctrl.OperationMode == 1)

        if is_auto:
            self._update_hbot_auto()
        else:
            # Manual jogging
            if hmi_ctrl.MoveXPlus:
                self.CncTrafo.mcsAxisX.Sollposition += 5
            if hmi_ctrl.MoveXNeg:
                self.CncTrafo.mcsAxisX.Sollposition -= 5
            if hmi_ctrl.MoveYPlus:
                self.CncTrafo.mcsAxisY.Sollposition += 5
            if hmi_ctrl.MoveYNeg:
                self.CncTrafo.mcsAxisY.Sollposition -= 5

        self.hbotX = self.CncTrafo.mcsAxisX.Sollposition
        self.hbotY = self.CncTrafo.mcsAxisY.Sollposition

        self.hmiCncState.axisXPosition = self.hbotX
        self.hmiCncState.axisYPosition = self.hbotY
        self.hmiCncState.axisZPosition = 0.0
        self.hmiCncState.axisRPosition = 0.0
        self.hmiCnc.setHmiState(self.hmiCncState)

    def _update_hbot_auto(self):
        """H-Bot automatic engraving sequence."""
        self._hb_tick += 1

        if self._hb_state == _HB_IDLE:
            # Wait until a workpiece is placed at the H-Bot centre
            if self.wpm.has_part_at(_HBOT_WORLD[0], _HBOT_WORLD[1], radius=60.0):
                self._hb_state    = _HB_APPROACH
                self._hb_tick     = 0
                self.hbot_at_home = False
                self.hmiCnc.setStatus("Fahre auf Werkstück...", "lightyellow")

        elif self._hb_state == _HB_APPROACH:
            # Move to workpiece centre, then start engraving
            self.CncTrafo.mcsAxisX.Sollposition = _HBOT_WORLD[0]
            self.CncTrafo.mcsAxisY.Sollposition = _HBOT_WORLD[1]
            if self._hb_tick >= _HB_TICKS_PER_MOVE:
                self._hb_state    = _HB_ENGRAVE
                self._hb_tick     = 0
                self._hb_move_idx = 0
                self.hmiCnc.setStatus("Gravur läuft...", "lightyellow")

        elif self._hb_state == _HB_ENGRAVE:
            # Step through simulated engraving waypoints
            if self._hb_tick >= _HB_TICKS_PER_MOVE:
                self._hb_tick = 0
                if self._hb_move_idx < len(self._hb_engrave_moves):
                    tx, ty = self._hb_engrave_moves[self._hb_move_idx]
                    self.CncTrafo.mcsAxisX.Sollposition = tx
                    self.CncTrafo.mcsAxisY.Sollposition = ty
                    self._hb_move_idx += 1
                else:
                    self._hb_state = _HB_RETURN

        elif self._hb_state == _HB_RETURN:
            self.CncTrafo.mcsAxisX.Sollposition = 300
            self.CncTrafo.mcsAxisY.Sollposition = 100   
            if self._hb_tick >= _HB_TICKS_PER_MOVE:
                self._hb_state    = _HB_DONE
                self._hb_tick     = 0
                self.hbot_at_home = True
                self.hmiCnc.setStatus("Gravur fertig — warte auf Roboter 3", "lightcyan")

        elif self._hb_state == _HB_DONE:
            # Wait until Robot 3 has picked the part (part no longer at H-Bot centre)
            if not self.wpm.has_part_at(_HBOT_WORLD[0], _HBOT_WORLD[1], radius=60.0):
                self._hb_state = _HB_IDLE
                self._hb_tick  = 0
                self.hmiCnc.setStatus("Bereit", "lightgreen")

    # =========================================================================
    # 3D VIEW UPDATE
    # =========================================================================
    def update_views(self):
        try:
            self.cncView.update_mesh_positions(x_pos=self.hbotX, y_pos=self.hbotY)
        except RuntimeError:
            pass

    # =========================================================================
    # ROBOT 3 HANDSHAKE GUARD
    # =========================================================================
    def _robot3_pickup_allowed(self):
        """
        Robot 3 may only start its pickup sequence when:
          - a part is at the H-Bot centre, AND
          - the H-Bot has returned to home (hbot_at_home == True).
        Inject this check by temporarily overriding the pickup_world so
        _auto_try_start falls through when the guard is not satisfied.
        """
        return self.hbot_at_home


# =============================================================================
# MAIN LOOP
# =============================================================================
if __name__ == "__main__":
    machine = Machine()

    while machine.running:
        machine.update_hmi_window()
        machine.update_hmi_hbot()

        for ctrl in machine.scara_controllers:
            ctrl.update_hmi()
            ctrl.update_kinematics()
            ctrl.update_cnc_path()
            ctrl.robot_trafo.cyclic()
            ctrl.update_view()

        machine.update_views()
        time.sleep(0.01)

    print("Programm beendet.")
