import sys
sys.path.append('../Model')

import math
from Model.Axis import Axis
from Model.CncInterpreter import CncInterpreter

class Scara:
    def __init__(self):
        self.L1 = 325
        self.L2 = 550
        self.L3 = 0

        # Gelenkachsen (ACS)
        self.acsAxis1 = Axis() # Gelenk 1
        self.acsAxis2 = Axis() # Gelenk 2
        self.acsAxis3 = Axis() # Hubachse
        self.acsAxis4 = Axis() # Werkzeugdrehachse

        # Kartesische Achsen (MCS)
        self.mcsAxisX = Axis() # X Achse
        self.mcsAxisY = Axis() # Y Achse
        self.mcsAxisZ = Axis() # Z Achse
        self.mcsAxisR = Axis() # Rotationsachse

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
        
        cos_axis2 = (self.mcsAxisX.Sollposition**2 + self.mcsAxisY.Sollposition**2 - self.L1**2 -self.L2**2) / (2 * self.L1 * self.L2) # Kosinus des Winkels von Gelenk 2
        axis2 = math.acos(cos_axis2) # Winkel von Gelenk 2

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

    def cyclic(self):
        self.acsAxis1.cyclic();
        self.acsAxis2.cyclic();
        self.acsAxis3.cyclic();
        self.acsAxis4.cyclic();
        self.mcsAxisX.cyclic();
        self.mcsAxisY.cyclic();
        self.mcsAxisZ.cyclic();
        self.mcsAxisR.cyclic();

if __name__ == "__main__":
    testaxis = Axis()
    print (testaxis.getActualPosition())

    robot = Scara()

    robot.setAxesJoint(30, 45, 50, 90)
    position = robot.forward()
    print("Forward:", position)

    achsen = robot.backward(position[0], position[1], position[2], position[3])
    print("Backward:", achsen)

    robot.setAxesJoint(achsen[0], achsen[1], achsen[2], achsen[3])
    position2 = robot.forward()
    print("Kontrolle:", position2)


   