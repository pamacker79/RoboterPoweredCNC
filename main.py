"""
Module: main (Machine)
Purpose: Application entry point; owns the 100 Hz control loop and wires all MVC layers.
Responsibilities: Create model/view/HMI objects, run the cyclic loop (HMI→kinematics→view),
                  manage window lifecycle.
Inputs:  Operator input via Tkinter HMI windows; G-Code file for auto mode.
Outputs: 3D PyVista scene updates; HMI state display updates.
Dependencies: Model.*, View.*, ViewModel.*, tkinter, pyvista
"""
import os
import sys

python_base = sys.base_prefix
tcl_path = os.path.join(python_base, "tcl", "tcl8.6")
tk_path = os.path.join(python_base, "tcl", "tk8.6")

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

from Model.hBot import hBot
from Model.Scara import Scara
from Model.CncInterpreter import CncInterpreter

from View.Scara import Scara as ScaraView
from View.HBot import HBot as HBotView
from View.MagazinViewPV import MagazinViewPV

from ViewModel.hmi import Hmi
from ViewModel.hmiState import hmiState
from ViewModel.RobotController import RobotController


class Machine:
    def __init__(self):
        self.running = True

        # ========================================================
        # MODELLE
        # ========================================================
        self.robot1Trafo = Scara()
        self.robot2Trafo = Scara()
        self.robot1CncControl = CncInterpreter()
        self.CncTrafo = hBot()

        # H-Bot Positionen
        self.hbotX = 0.0
        self.hbotY = 0.0

        # ========================================================
        # HMI FENSTER ERSTELLEN
        # ========================================================
        self.hmiRoot = tk.Tk()
        self.hmiRoot.title("3 Roboter")
        self.hmiRoot.geometry("1250x415")
        self.hmiRoot.protocol("WM_DELETE_WINDOW", self.close_program)

        self.frame1 = tk.Frame(self.hmiRoot)
        self.frame1.pack(side="left", padx=5)

        self.frame2 = tk.Frame(self.hmiRoot)
        self.frame2.pack(side="left", padx=5)

        self.frame3 = tk.Frame(self.hmiRoot)
        self.frame3.pack(side="left", padx=5)

        self.hmiRobot1 = Hmi(self.frame1, "Roboter 1 SCARA")
        self.hmiCnc    = Hmi(self.frame2, "Roboter 2 H-Bot")
        self.hmiRobot2 = Hmi(self.frame3, "Roboter 3 SCARA")

        self.hmi1State   = hmiState()
        self.hmi2State   = hmiState()
        self.hmiCncState = hmiState()

        # ========================================================
        # GEMEINSAMES PYVISTA-FENSTER
        # ========================================================
        self.sharedPlotter = pv.Plotter()

        self.scaraView1  = ScaraView(pl=self.sharedPlotter, position=(-1000, 250, 0))
        self.cncView     = HBotView(pl=self.sharedPlotter,  position=(0, 0, 200))
        self.scaraView2  = ScaraView(pl=self.sharedPlotter, position=(1300, 250, 0))
        self.magazinView = MagazinViewPV(pl=self.sharedPlotter, position=(150, 800, 0))

        self.sharedPlotter.show_axes()
        self.sharedPlotter.camera_position = [
            (400.0, -2700.0, 1600.0),
            (250.0,   250.0,    0.0),
            (  0.0,     0.0,    1.0)
        ]
        self.sharedPlotter.show(interactive_update=True, auto_close=False)

        # ========================================================
        # ROBOT CONTROLLERS
        # ========================================================
        self.robot1_ctrl = RobotController(
            self.robot1Trafo, self.scaraView1, self.hmiRobot1, self.hmi1State,
            cnc_control=self.robot1CncControl, cnc_program_path="Model\\programm.nc"
        )
        self.robot2_ctrl = RobotController(
            self.robot2Trafo, self.scaraView2, self.hmiRobot2, self.hmi2State
        )
        self.scara_controllers = [self.robot1_ctrl, self.robot2_ctrl]

    # ============================================================
    # PROGRAMM SCHLIESSEN
    # ============================================================
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

    # ============================================================
    # TKINTER HMI AKTUALISIEREN
    # ============================================================
    def update_hmi_window(self):
        try:
            self.hmiRoot.update_idletasks()
            self.hmiRoot.update()
        except tk.TclError:
            self.running = False

    # ============================================================
    # HMI H-BOT AUSLESEN
    # ============================================================
    def update_hmi_hbot(self):
        hmiControl = self.hmiCnc.getHmiControl()

        if hmiControl.MoveXPlus:
            self.CncTrafo.mcsAxisX.Sollposition += 5
        if hmiControl.MoveXNeg:
            self.CncTrafo.mcsAxisX.Sollposition -= 5

        if hmiControl.MoveYPlus:
            self.CncTrafo.mcsAxisY.Sollposition += 5
        if hmiControl.MoveYNeg:
            self.CncTrafo.mcsAxisY.Sollposition -= 5

        # Read back clamped values (limits enforced by Axis property setter)
        self.hbotX = self.CncTrafo.mcsAxisX.Sollposition
        self.hbotY = self.CncTrafo.mcsAxisY.Sollposition

        self.hmiCncState.axisXPosition = self.hbotX
        self.hmiCncState.axisYPosition = self.hbotY
        self.hmiCncState.axisZPosition = 0.0
        self.hmiCncState.axisRPosition = 0.0
        self.hmiCnc.setHmiState(self.hmiCncState)

    # ============================================================
    # 3D VIEW AKTUALISIEREN
    # ============================================================
    def update_views(self):
        try:
            self.cncView.update_mesh_positions(x_pos=self.hbotX, y_pos=self.hbotY)
        except RuntimeError:
            pass


# ================================================================
# HAUPTPROGRAMM
# ================================================================
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
