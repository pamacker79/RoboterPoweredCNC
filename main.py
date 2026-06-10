import os
os.environ["TCL_LIBRARY"] = r"C:\Users\anco\AppData\Local\Programs\Python\Python313\tcl\tcl8.6"
os.environ["TK_LIBRARY"]  = r"C:\Users\anco\AppData\Local\Programs\Python\Python313\tcl\tk8.6"
import sys
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

from ViewModel.hmi import Hmi
from ViewModel.hmiState import hmiState


class Machine:
    def __init__(self):
        # ========================================================
        # PROGRAMM LÄUFT
        # ========================================================
        self.running = True

        # ========================================================
        # MODELLE
        # ========================================================
        self.robot1Trafo = Scara()
        self.robot2Trafo = Scara()

        self.robot1CncControl = CncInterpreter()
        self.interpolated_path = None

        self.CncTrafo = hBot()

        # H-Bot Positionen
        self.hbotX = 0.0
        self.hbotY = 0.0

        # ========================================================
        # GREIFER STATUS
        # ========================================================
        self.robot1GripperClosed = False
        self.robot2GripperClosed = False

        # ========================================================
        # MODI
        # ========================================================
        self.Robot1JointMode = True
        self.Robot1Manual = True

        self.Robot2JointMode = True
        self.Robot2Manual = True

        # ========================================================
        # HMI STATES
        # ========================================================
        self.hmi1State = hmiState()
        self.hmi2State = hmiState()
        self.hmiCncState = hmiState()

        # ========================================================
        # HMI FENSTER ERSTELLEN
        # ========================================================
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
        self.hmiCnc = Hmi(self.frame2, "Roboter 2 H-Bot")
        self.hmiRobot2 = Hmi(self.frame3, "Roboter 3 SCARA")

        # ========================================================
        # GEMEINSAMES PYVISTA-FENSTER
        # ========================================================
        self.sharedPlotter = pv.Plotter()

        # Reihenfolge:
        # SCARA 1 links
        self.scaraView1 = ScaraView(
            pl=self.sharedPlotter,
            position=(-1000, 250, 0)
        )

        # H-Bot in der Mitte
        self.cncView = HBotView(
            pl=self.sharedPlotter,
            position=(0, 0, 200)
        )

        # SCARA 2 rechts
        self.scaraView2 = ScaraView(
            pl=self.sharedPlotter,
            position=(1300, 250, 0)
        )

        # Greifer Startzustand setzen
        if hasattr(self.scaraView1, "set_gripper"):
            self.scaraView1.set_gripper(closed=self.robot1GripperClosed)

        if hasattr(self.scaraView2, "set_gripper"):
            self.scaraView2.set_gripper(closed=self.robot2GripperClosed)

        # Kamera / Ansicht
        self.sharedPlotter.show_axes()

        self.sharedPlotter.camera_position = [
            (400.0, -2700.0, 1600.0),
            (250.0, 250.0, 0.0),
            (0.0, 0.0, 1.0)
        ]

        self.sharedPlotter.show(
            interactive_update=True,
            auto_close=False
        )

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
    # SCARA MANUELLE STEUERUNG
    # ============================================================
    def handle_scara_manual_control(self, robotTrafo, hmiControl, step_joint=1, step_world=2):
        """
        Steuert einen SCARA-Roboter im Joint- oder Weltkoordinatensystem.
        """

        coord_system = getattr(hmiControl, "CoordSystem", "Joint")

        # Falls im HMI noch "wählen" steht, standardmässig Joint verwenden
        if coord_system not in ["Joint", "Welt", "Werkzeug"]:
            coord_system = "Joint"

        joint_mode = coord_system == "Joint"

        if joint_mode:
            # Joint-Modus
            if hmiControl.MoveXPlus:
                robotTrafo.acsAxis1.Sollposition += step_joint
            if hmiControl.MoveXNeg:
                robotTrafo.acsAxis1.Sollposition -= step_joint

            if hmiControl.MoveYPlus:
                robotTrafo.acsAxis2.Sollposition += step_joint
            if hmiControl.MoveYNeg:
                robotTrafo.acsAxis2.Sollposition -= step_joint

            if hmiControl.MoveZPlus:
                robotTrafo.acsAxis3.Sollposition += step_joint
            if hmiControl.MoveZNeg:
                robotTrafo.acsAxis3.Sollposition -= step_joint

            if hmiControl.MoveRPlus:
                robotTrafo.acsAxis4.Sollposition += step_joint
            if hmiControl.MoveRNeg:
                robotTrafo.acsAxis4.Sollposition -= step_joint

        else:
            # Weltkoordinaten-Modus
            if hmiControl.MoveXPlus:
                robotTrafo.mcsAxisX.Sollposition += step_world
            if hmiControl.MoveXNeg:
                robotTrafo.mcsAxisX.Sollposition -= step_world

            if hmiControl.MoveYPlus:
                robotTrafo.mcsAxisY.Sollposition += step_world
            if hmiControl.MoveYNeg:
                robotTrafo.mcsAxisY.Sollposition -= step_world

            if hmiControl.MoveZPlus:
                robotTrafo.mcsAxisZ.Sollposition += step_world
            if hmiControl.MoveZNeg:
                robotTrafo.mcsAxisZ.Sollposition -= step_world

            if hmiControl.MoveRPlus:
                robotTrafo.mcsAxisR.Sollposition += step_world
            if hmiControl.MoveRNeg:
                robotTrafo.mcsAxisR.Sollposition -= step_world

        return joint_mode

    # ============================================================
    # HMI STATUS SCARA
    # ============================================================
    def update_scara_hmi_state(self, robotTrafo, state):
        state.axisJ1Position = robotTrafo.acsAxis1.ActualPosition
        state.axisJ2Position = robotTrafo.acsAxis2.ActualPosition
        state.axisJ3Position = robotTrafo.acsAxis3.ActualPosition
        state.axisJ4Position = robotTrafo.acsAxis4.ActualPosition

        state.axisXPosition = robotTrafo.mcsAxisX.ActualPosition
        state.axisYPosition = robotTrafo.mcsAxisY.ActualPosition
        state.axisZPosition = robotTrafo.mcsAxisZ.ActualPosition
        state.axisRPosition = robotTrafo.mcsAxisR.ActualPosition

    # ============================================================
    # GREIFER STEUERUNG
    # ============================================================
    def handle_gripper_control_robot1(self, hmiControl):
        """
        Roboter 1:
        Start = Greifer schliessen
        Stop  = Greifer öffnen
        """

        if getattr(hmiControl, "Start", False):
            self.robot1GripperClosed = True

        if getattr(hmiControl, "Stop", False):
            self.robot1GripperClosed = False

        if hasattr(self.scaraView1, "set_gripper"):
            self.scaraView1.set_gripper(closed=self.robot1GripperClosed)

    def handle_gripper_control_robot2(self, hmiControl):
        """
        Roboter 2:
        Start = Greifer schliessen
        Stop  = Greifer öffnen
        """

        if getattr(hmiControl, "Start", False):
            self.robot2GripperClosed = True

        if getattr(hmiControl, "Stop", False):
            self.robot2GripperClosed = False

        if hasattr(self.scaraView2, "set_gripper"):
            self.scaraView2.set_gripper(closed=self.robot2GripperClosed)

    # ============================================================
    # HMI ROBOTER 1 AUSLESEN
    # ============================================================
    def update_hmi_robot1(self):
        hmiControl = self.hmiRobot1.getHmiControl()

        self.Robot1Manual = hmiControl.OperationMode == 0

        if self.Robot1Manual:
            self.Robot1JointMode = self.handle_scara_manual_control(
                self.robot1Trafo,
                hmiControl
            )

            self.handle_gripper_control_robot1(hmiControl)

        else:
            # Automatik nur in Weltkoordinaten
            self.Robot1JointMode = False

            if hmiControl.Start:
                self.robot1CncControl.load_from_path("Model\\programm.nc")
                self.interpolated_path = iter(
                    self.robot1CncControl.interpolate_path(step_size=3.0)
                )
                hmiControl.Start = False

        self.update_scara_hmi_state(
            self.robot1Trafo,
            self.hmi1State
        )

        self.hmiRobot1.setHmiState(self.hmi1State)

    # ============================================================
    # HMI ROBOTER 2 / RECHTER SCARA AUSLESEN
    # ============================================================
    def update_hmi_robot2(self):
        hmiControl = self.hmiRobot2.getHmiControl()

        self.Robot2Manual = hmiControl.OperationMode == 0

        if self.Robot2Manual:
            self.Robot2JointMode = self.handle_scara_manual_control(
                self.robot2Trafo,
                hmiControl
            )

            self.handle_gripper_control_robot2(hmiControl)

        else:
            # Rechter SCARA aktuell ohne CNC-Automatik
            self.Robot2JointMode = False

        self.update_scara_hmi_state(
            self.robot2Trafo,
            self.hmi2State
        )

        self.hmiRobot2.setHmiState(self.hmi2State)

    # ============================================================
    # HMI H-BOT AUSLESEN
    # ============================================================
    def update_hmi_hbot(self):
        hmiControl = self.hmiCnc.getHmiControl()

        # H-Bot:
        # X+ / X- bewegt Schlitten
        # Y+ / Y- bewegt Brücke
        if hmiControl.MoveXPlus:
            self.hbotX += 5
        if hmiControl.MoveXNeg:
            self.hbotX -= 5

        if hmiControl.MoveYPlus:
            self.hbotY += 5
        if hmiControl.MoveYNeg:
            self.hbotY -= 5

        # Begrenzung
        if self.hbotX > 300:
            self.hbotX = 300
        if self.hbotX < -300:
            self.hbotX = -300

        if self.hbotY > 300:
            self.hbotY = 300
        if self.hbotY < -300:
            self.hbotY = -300

        # HMI Anzeige für H-Bot
        self.hmiCncState.axisXPosition = self.hbotX
        self.hmiCncState.axisYPosition = self.hbotY
        self.hmiCncState.axisZPosition = 0.0
        self.hmiCncState.axisRPosition = 0.0

        self.hmiCnc.setHmiState(self.hmiCncState)

    # ============================================================
    # ALLE HMIs AUSLESEN
    # ============================================================
    def update_hmis(self):
        self.update_hmi_robot1()
        self.update_hmi_hbot()
        self.update_hmi_robot2()

    # ============================================================
    # KINEMATIK ROBOTER 1
    # ============================================================
    def update_robot1_kinematics(self):
        try:
            if self.Robot1JointMode:
                self.robot1Trafo.forward()
            else:
                self.robot1Trafo.backward()

        except ValueError as e:
            print("Roboter 1 Fehler:", e)

            self.robot1Trafo.mcsAxisX.Sollposition = self.robot1Trafo.mcsAxisX.ActualPosition
            self.robot1Trafo.mcsAxisY.Sollposition = self.robot1Trafo.mcsAxisY.ActualPosition
            self.robot1Trafo.mcsAxisZ.Sollposition = self.robot1Trafo.mcsAxisZ.ActualPosition
            self.robot1Trafo.mcsAxisR.Sollposition = self.robot1Trafo.mcsAxisR.ActualPosition

    # ============================================================
    # KINEMATIK ROBOTER 2
    # ============================================================
    def update_robot2_kinematics(self):
        try:
            if self.Robot2JointMode:
                self.robot2Trafo.forward()
            else:
                self.robot2Trafo.backward()

        except ValueError as e:
            print("Roboter 2 Fehler:", e)

            self.robot2Trafo.mcsAxisX.Sollposition = self.robot2Trafo.mcsAxisX.ActualPosition
            self.robot2Trafo.mcsAxisY.Sollposition = self.robot2Trafo.mcsAxisY.ActualPosition
            self.robot2Trafo.mcsAxisZ.Sollposition = self.robot2Trafo.mcsAxisZ.ActualPosition
            self.robot2Trafo.mcsAxisR.Sollposition = self.robot2Trafo.mcsAxisR.ActualPosition

    # ============================================================
    # CNC PFAD ROBOTER 1
    # ============================================================
    def update_robot1_cnc_path(self):
        self.robot1CncControl.position = {
            "X": self.robot1Trafo.mcsAxisX.ActualPosition,
            "Y": self.robot1Trafo.mcsAxisY.ActualPosition,
            "Z": self.robot1Trafo.mcsAxisZ.ActualPosition
        }

        if self.interpolated_path is not None:
            point = next(self.interpolated_path, None)

            if point is not None:
                self.robot1Trafo.mcsAxisX.Sollposition = point["X"]
                self.robot1Trafo.mcsAxisY.Sollposition = point["Y"]
                self.robot1Trafo.mcsAxisZ.Sollposition = point["Z"]

    # ============================================================
    # 3D VIEW AKTUALISIEREN
    # ============================================================
    def update_views(self):
        try:
            # SCARA 1 links
            self.scaraView1.update_joints(
                self.robot1Trafo.acsAxis1.getSetPosition(),
                self.robot1Trafo.acsAxis2.getSetPosition(),
                self.robot1Trafo.acsAxis4.getSetPosition()
            )

            # H-Bot Mitte
            self.cncView.update_mesh_positions(
                x_pos=self.hbotX,
                y_pos=self.hbotY
            )

            # SCARA 2 rechts
            self.scaraView2.update_joints(
                self.robot2Trafo.acsAxis1.getSetPosition(),
                self.robot2Trafo.acsAxis2.getSetPosition(),
                self.robot2Trafo.acsAxis4.getSetPosition()
            )

        except RuntimeError:
            pass


# ================================================================
# HAUPTPROGRAMM
# ================================================================
if __name__ == "__main__":
    machine = Machine()

    while machine.running:
        # HMI-Fenster aktualisieren
        machine.update_hmi_window()

        # HMI-Werte auslesen
        machine.update_hmis()

        # Roboter 1 Kinematik
        machine.update_robot1_kinematics()

        # CNC-Pfad Roboter 1
        machine.update_robot1_cnc_path()

        # Roboter 1 Achsen zyklisch bewegen
        machine.robot1Trafo.cyclic()

        # Roboter 2 Kinematik
        machine.update_robot2_kinematics()

        # Roboter 2 Achsen zyklisch bewegen
        machine.robot2Trafo.cyclic()

        # 3D-Fenster aktualisieren
        machine.update_views()

        time.sleep(0.01)

    print("Programm beendet.")