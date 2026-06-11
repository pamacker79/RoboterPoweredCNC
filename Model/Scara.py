"""
Module: Scara
Purpose: Kinematic model for a 4-DOF SCARA robot.
Responsibilities: Forward kinematics (ACS→MCS), inverse kinematics (MCS→ACS), cyclic axis update.
Inputs:  acsAxis1–4 (joint angles / hub height) or mcsAxisX/Y/Z/R (Cartesian target).
Outputs: Updated opposite coordinate set after forward() or backward() call.
Dependencies: Model.Axis, Model.RobotConfig
"""
import sys
sys.path.append('../Model')

import math
from Model.Axis import Axis
from Model.RobotConfig import SCARA_LIMITS

class Scara:
    def __init__(self):
        self.L1 = 325
        self.L2 = 225
        self.L3 = 0

        # Gelenkachsen (ACS)
        self.acsAxis1 = Axis(*SCARA_LIMITS["acsAxis1"]) # Gelenk 1
        self.acsAxis2 = Axis(*SCARA_LIMITS["acsAxis2"]) # Gelenk 2
        self.acsAxis3 = Axis(*SCARA_LIMITS["acsAxis3"]) # Hubachse
        self.acsAxis4 = Axis(*SCARA_LIMITS["acsAxis4"]) # Werkzeugdrehachse

        # Kartesische Achsen (MCS)
        self.mcsAxisX = Axis(*SCARA_LIMITS["mcsAxisX"]) # X Achse
        self.mcsAxisY = Axis(*SCARA_LIMITS["mcsAxisY"]) # Y Achse
        self.mcsAxisZ = Axis(*SCARA_LIMITS["mcsAxisZ"]) # Z Achse
        self.mcsAxisR = Axis(*SCARA_LIMITS["mcsAxisR"]) # Rotationsachse

    def forward(self): # Vorwärtskinematik berechnen # Winkel von Grad in Bogenmaß umrechnen
        axis1 = math.radians(self.acsAxis1.Sollposition)
        axis2 = math.radians(self.acsAxis2.Sollposition)
        axis3 = self.acsAxis3.Sollposition # Lineare Bewegung
        axis4 = math.radians(self.acsAxis4.Sollposition)

        self.mcsAxisX.Sollposition = self.L1 * math.cos(axis1) + self.L2 * math.cos(axis1 + axis2) # Berechnung der X-Koordinate
        self.mcsAxisY.Sollposition = self.L1 * math.sin(axis1) + self.L2 * math.sin(axis1 + axis2) # Berechnung der Y-Koordinate
        self.mcsAxisZ.Sollposition = self.L3 + axis3 # Berechnung der Z-Koordinate
        self.mcsAxisR.Sollposition = self.acsAxis1.Sollposition + self.acsAxis2.Sollposition + self.acsAxis4.Sollposition # Berechnung der Rotationsachse

    def backward(self): # Rueckwärtskinematik berechen

        d = math.sqrt(self.mcsAxisX.Sollposition**2 + self.mcsAxisY.Sollposition**2) # Abstand von Ursprung zu Punkt (x, y)

        if d > self.L1 + self.L2 or d < abs(self.L1 - self.L2):
            raise ValueError("Punkt außerhalb der Reichweite des Roboters") # Prüfen ob Punkt erreichbar ist
        
        cos_axis2 = (self.mcsAxisX.Sollposition**2 + self.mcsAxisY.Sollposition**2 - self.L1**2 - self.L2**2) / (2 * self.L1 * self.L2)
        cos_axis2 = max(-1.0, min(1.0, cos_axis2))  # Gleitkomma-Absicherung am Arbeitsraumrand
        axis2_up   =  math.acos(cos_axis2)  # Elbow-up-Lösung  (≥ 0)
        axis2_down = -axis2_up               # Elbow-down-Lösung (≤ 0)
        current_a2 = math.radians(self.acsAxis2.ActualPosition)
        axis2 = axis2_down if abs(axis2_down - current_a2) < abs(axis2_up - current_a2) else axis2_up

        k1 = self.L1 + self.L2 * math.cos(axis2) # Hilfsgröße für Berechnung von Gelenk 1
        k2 = self.L2 * math.sin(axis2) # Hilfsgröße für Berechnung von Gelenk 1
        axis1 = math.atan2(self.mcsAxisY.Sollposition, self.mcsAxisX.Sollposition) - math.atan2(k2, k1) # Winkel von Gelenk 1

        axis3 = self.mcsAxisZ.Sollposition - self.L3 # Hubhöhe berechnen

        axis4 = self.mcsAxisR.Sollposition - math.degrees(axis1) - math.degrees(axis2) # Winkel der Werkzeugdrehachse berechnen

        axis1_deg = math.degrees(axis1)
        axis2_deg = math.degrees(axis2)

        self.acsAxis1.Sollposition = axis1_deg
        self.acsAxis2.Sollposition = axis2_deg
        self.acsAxis3.Sollposition = axis3
        self.acsAxis4.Sollposition = axis4

    def jog_joint(self, da1=0.0, da2=0.0, da3=0.0, da4=0.0):
        self.acsAxis1.Sollposition += da1
        self.acsAxis2.Sollposition += da2
        self.acsAxis3.Sollposition += da3
        self.acsAxis4.Sollposition += da4

    def jog_world(self, dx=0.0, dy=0.0, dz=0.0, dr=0.0):
        new_x = self.mcsAxisX.Sollposition + dx
        new_y = self.mcsAxisY.Sollposition + dy
        # Schritt blockieren wenn der Zielpunkt außerhalb des erreichbaren Rings liegt
        if abs(self.L1 - self.L2) <= math.sqrt(new_x**2 + new_y**2) <= self.L1 + self.L2:
            self.mcsAxisX.Sollposition = new_x
            self.mcsAxisY.Sollposition = new_y
        self.mcsAxisZ.Sollposition += dz
        self.mcsAxisR.Sollposition += dr

    def jog_tool(self, dx=0.0, dy=0.0, dz=0.0, dr=0.0):
        r = math.radians(self.mcsAxisR.ActualPosition)
        new_x = self.mcsAxisX.Sollposition + dx * math.cos(r) - dy * math.sin(r)
        new_y = self.mcsAxisY.Sollposition + dx * math.sin(r) + dy * math.cos(r)
        # Schritt blockieren wenn der Zielpunkt außerhalb des erreichbaren Rings liegt
        if abs(self.L1 - self.L2) <= math.sqrt(new_x**2 + new_y**2) <= self.L1 + self.L2:
            self.mcsAxisX.Sollposition = new_x
            self.mcsAxisY.Sollposition = new_y
        self.mcsAxisZ.Sollposition += dz
        self.mcsAxisR.Sollposition += dr

    def cyclic(self):
        self.acsAxis1.cyclic();
        self.acsAxis2.cyclic();
        self.acsAxis3.cyclic();
        self.acsAxis4.cyclic();
        self.mcsAxisX.cyclic();
        self.mcsAxisY.cyclic();
        self.mcsAxisZ.cyclic();
        self.mcsAxisR.cyclic();

