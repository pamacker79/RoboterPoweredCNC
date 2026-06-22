"""
Modul: Model.Scara
==================
Kinematisches Modell eines 4-DOF-SCARA-Roboters.

Aufbau und Koordinatensysteme
------------------------------
ACS (Achskoordinatensystem / Joint Space):
    acsAxis1  – Schultergelenk-Winkel [Grad]
    acsAxis2  – Ellbogengelenk-Winkel [Grad]
    acsAxis3  – Hubachse / Spindel [mm], 0 = oben, negativ = abgesenkt
    acsAxis4  – Werkzeugdrehachse [Grad]

MCS (Maschinenkoordinatensystem / Cartesian Space):
    mcsAxisX  – TCP X-Koordinate [mm]
    mcsAxisY  – TCP Y-Koordinate [mm]
    mcsAxisZ  – TCP Z-Koordinate = acsAxis3 (keine eigene Kinematik)
    mcsAxisR  – TCP-Rotation = acsAxis1 + acsAxis2 + acsAxis4 [Grad]

Kinematik-Paar (forward / backward)
-------------------------------------
* ``forward()``  – ACS → MCS: Berechnet aus Gelenkwinkeln die kartesische
  TCP-Position (wird nach Jog-Befehlen und nach cyclic() aufgerufen).
* ``backward()`` – MCS → ACS: Inverse Kinematik, berechnet Gelenkwinkel
  für eine gewünschte kartesische Zielposition.  Wählt die Elbow-up /
  Elbow-down-Lösung, die der aktuellen Stellung am nächsten liegt.

Bewegungsaufruf im Regelkreis
-------------------------------
Jeder 100-Hz-Tick in ``RobotController.update_kinematics()`` ruft
``forward()`` oder ``backward()`` auf, um die Koordinatensysteme
konsistent zu halten.  Anschliessend ruft ``RobotController.cyclic()``
die Methode ``Scara.cyclic()`` auf, die alle ACS-Achsen mit Override
schrittweise an ihre Sollpositionen heranführt.

Jog-Methoden
------------
Diese Methoden inkrementieren Sollpositionen direkt und werden von
``RobotController._handle_manual_control()`` im Handbetrieb aufgerufen:
* ``jog_joint()``  – Jog im Gelenkkoordinatensystem
* ``jog_world()``  – Jog im kartesischen Weltkoordinatensystem
* ``jog_tool()``   – Jog im TCP-Werkzeugkoordinatensystem (rotiert mit dem Tool)
"""
import sys
sys.path.append('../Model')

import math
from Model.Axis import Axis
from Model.RobotConfig import SCARA_LIMITS


class Scara:
    """
    Kinematisches Modell eines 4-DOF-SCARA-Roboters.

    Die Armlängen L1 und L2 entsprechen den CAD-Massen der STL-Modelle.

    Attribute
    ---------
    L1 : float
        Länge des Oberarms (Schulter → Ellbogen) [mm].
    L2 : float
        Länge des Unterarms (Ellbogen → TCP) [mm].
    L3 : float
        Vertikal-Offset der Hubachse [mm] (aktuell 0).
    acsAxis1–4 : Axis
        Gelenkachsen im ACS.
    mcsAxisX/Y/Z/R : Axis
        Kartesische Achsen im MCS (abgeleitet, keine eigene Velocity).
    """

    def __init__(self):
        """Initialisiert den Roboter mit Achsparametern aus RobotConfig."""
        self.L1 = 325   # Oberarm-Länge [mm]
        self.L2 = 225   # Unterarm-Länge [mm]
        self.L3 = 0     # Hubachsen-Offset [mm]

        # Gelenkachsen (ACS) – haben Velocity für die Bewegungsrampe
        self.acsAxis1 = Axis(*SCARA_LIMITS["acsAxis1"])
        self.acsAxis2 = Axis(*SCARA_LIMITS["acsAxis2"])
        self.acsAxis3 = Axis(*SCARA_LIMITS["acsAxis3"])
        self.acsAxis4 = Axis(*SCARA_LIMITS["acsAxis4"])

        # Kartesische Achsen (MCS) – ohne Velocity, werden aus Kinematik berechnet
        self.mcsAxisX = Axis(*SCARA_LIMITS["mcsAxisX"])
        self.mcsAxisY = Axis(*SCARA_LIMITS["mcsAxisY"])
        self.mcsAxisZ = Axis(*SCARA_LIMITS["mcsAxisZ"])
        self.mcsAxisR = Axis(*SCARA_LIMITS["mcsAxisR"])

    # ------------------------------------------------------------------
    # Vorwärtskinematik: ACS → MCS
    # ------------------------------------------------------------------

    def forward(self):
        """
        Berechnet die kartesische TCP-Position aus den aktuellen Gelenkwinkeln.

        Liest ``Sollposition`` aller ACS-Achsen und schreibt das Ergebnis
        in ``Sollposition`` der MCS-Achsen.  Diese Methode wird nach jedem
        Jog-Befehl im Handbetrieb und nach dem cyclic()-Aufruf aufgerufen,
        damit der MCS-Istwert stets dem ACS-Istwert entspricht.

        Formeln (2D-SCARA, Standardgeometrie):
            X = L1·cos(θ1) + L2·cos(θ1 + θ2)
            Y = L1·sin(θ1) + L2·sin(θ1 + θ2)
            Z = L3 + θ3
            R = θ1 + θ2 + θ4
        """
        a1 = math.radians(self.acsAxis1.Sollposition)
        a2 = math.radians(self.acsAxis2.Sollposition)
        a3 = self.acsAxis3.Sollposition
        a4 = math.radians(self.acsAxis4.Sollposition)

        self.mcsAxisX.Sollposition = self.L1 * math.cos(a1) + self.L2 * math.cos(a1 + a2)
        self.mcsAxisY.Sollposition = self.L1 * math.sin(a1) + self.L2 * math.sin(a1 + a2)
        self.mcsAxisZ.Sollposition = self.L3 + a3
        self.mcsAxisR.Sollposition = (self.acsAxis1.Sollposition
                                      + self.acsAxis2.Sollposition
                                      + self.acsAxis4.Sollposition)

    # ------------------------------------------------------------------
    # Rückwärtskinematik: MCS → ACS
    # ------------------------------------------------------------------

    def backward(self):
        """
        Berechnet die Gelenkwinkel für eine vorgegebene kartesische Zielposition.

        Liest ``mcsAxisX.Sollposition`` und ``mcsAxisY.Sollposition`` und
        schreibt die Lösung in ``acsAxis1.Sollposition`` und
        ``acsAxis2.Sollposition``.

        Lösungsauswahl
        --------------
        Für jeden kartesischen Punkt gibt es zwei Lösungen (Elbow-up und
        Elbow-down).  Es wird die Lösung gewählt, die dem aktuellen
        ``ActualPosition`` von acsAxis2 am nächsten liegt – das vermeidet
        unnötige Konfigurationswechsel während der Bewegung.

        Ausnahme
        --------
        ``ValueError`` wenn der Zielpunkt ausserhalb des Arbeitsraums liegt
        (Distanz > L1 + L2 oder < |L1 − L2|).
        """
        x = self.mcsAxisX.Sollposition
        y = self.mcsAxisY.Sollposition
        d = math.sqrt(x ** 2 + y ** 2)

        if d > self.L1 + self.L2 + 1.0 or d < abs(self.L1 - self.L2) - 1.0:
            raise ValueError("Zielpunkt liegt ausserhalb des Arbeitsraums des Roboters")

        # cos(θ2) über Kosinussatz, numerisch abgesichert
        cos_a2 = (x ** 2 + y ** 2 - self.L1 ** 2 - self.L2 ** 2) / (2 * self.L1 * self.L2)
        cos_a2 = max(-1.0, min(1.0, cos_a2))

        a2_up   =  math.acos(cos_a2)   # Elbow-up  (≥ 0)
        a2_down = -a2_up               # Elbow-down (≤ 0)

        # Wähle die Lösung, die dem aktuellen Istwert am nächsten liegt
        current_a2 = math.radians(self.acsAxis2.ActualPosition)
        a2 = a2_down if abs(a2_down - current_a2) < abs(a2_up - current_a2) else a2_up

        # θ1 aus atan2 unter Berücksichtigung von θ2
        k1 = self.L1 + self.L2 * math.cos(a2)
        k2 = self.L2 * math.sin(a2)
        a1 = math.atan2(y, x) - math.atan2(k2, k1)

        # Hubachse: linearer Zusammenhang
        a3 = self.mcsAxisZ.Sollposition - self.L3

        # Werkzeugdrehachse: Kompensiert Gelenkrotationen, damit TCP-Orientierung stimmt
        a4 = (self.mcsAxisR.Sollposition
              - math.degrees(a1)
              - math.degrees(a2))

        self.acsAxis1.Sollposition = math.degrees(a1)
        self.acsAxis2.Sollposition = math.degrees(a2)
        self.acsAxis3.Sollposition = a3
        self.acsAxis4.Sollposition = a4

    # ------------------------------------------------------------------
    # Jog-Methoden (Handbetrieb)
    # ------------------------------------------------------------------

    def jog_joint(self, da1=0.0, da2=0.0, da3=0.0, da4=0.0):
        """
        Inkrementiert die Gelenkwinkel direkt (Jog im Gelenkkoordinatensystem).

        Parameter
        ---------
        da1–da4 : float
            Winkel-/Hub-Inkrement pro Tick [Grad bzw. mm].
        """
        self.acsAxis1.Sollposition += da1
        self.acsAxis2.Sollposition += da2
        self.acsAxis3.Sollposition += da3
        self.acsAxis4.Sollposition += da4

    def jog_world(self, dx=0.0, dy=0.0, dz=0.0, dr=0.0):
        """
        Jog im kartesischen Weltkoordinatensystem.

        Ein Schritt wird nur ausgeführt, wenn der neue Zielpunkt innerhalb
        des erreichbaren Rings liegt (|L1−L2| ≤ Abstand ≤ L1+L2).
        Das verhindert Kinematik-Fehler an der Singularität und am
        Arbeitsraumrand.

        Parameter
        ---------
        dx, dy, dz, dr : float
            Kartesisches Inkrement pro Tick [mm bzw. Grad].
        """
        new_x = self.mcsAxisX.Sollposition + dx
        new_y = self.mcsAxisY.Sollposition + dy
        dist  = math.sqrt(new_x ** 2 + new_y ** 2)
        if abs(self.L1 - self.L2) <= dist <= self.L1 + self.L2:
            self.mcsAxisX.Sollposition = new_x
            self.mcsAxisY.Sollposition = new_y
        self.mcsAxisZ.Sollposition += dz
        self.mcsAxisR.Sollposition += dr

    def jog_tool(self, dx=0.0, dy=0.0, dz=0.0, dr=0.0):
        """
        Jog im TCP-Werkzeugkoordinatensystem (Bewegung entlang der Werkzeugachse).

        Dreht das dx/dy-Inkrement um den aktuellen TCP-Orientierungswinkel,
        damit die Bewegung aus Sicht des Werkzeugs geradlinig ist.

        Parameter
        ---------
        dx, dy, dz, dr : float
            Werkzeug-Inkrement pro Tick [mm bzw. Grad].
        """
        r     = math.radians(self.mcsAxisR.ActualPosition)
        new_x = self.mcsAxisX.Sollposition + dx * math.cos(r) - dy * math.sin(r)
        new_y = self.mcsAxisY.Sollposition + dx * math.sin(r) + dy * math.cos(r)
        dist  = math.sqrt(new_x ** 2 + new_y ** 2)
        if abs(self.L1 - self.L2) <= dist <= self.L1 + self.L2:
            self.mcsAxisX.Sollposition = new_x
            self.mcsAxisY.Sollposition = new_y
        self.mcsAxisZ.Sollposition += dz
        self.mcsAxisR.Sollposition += dr

    # ------------------------------------------------------------------
    # Zyklische Aktualisierung (100 Hz)
    # ------------------------------------------------------------------

    def cyclic(self, override: float = 1.0):
        """
        Führt alle ACS-Achsen schrittweise an ihre Sollpositionen heran.

        Wird einmal pro 100-Hz-Tick von ``RobotController.cyclic()``
        aufgerufen.  Nur die ACS-Achsen (Gelenke) werden mit Override
        skaliert; die MCS-Achsen sind unverzögert und werden erst durch
        die Vorwärtskinematik (``forward()``) aktualisiert.

        Parameter
        ---------
        override : float
            Geschwindigkeitsskalierung [0.0 … 1.0] aus dem HMI-Schieberegler.
        """
        # ACS-Achsen bewegen sich mit Override-skalierter Geschwindigkeit
        self.acsAxis1.cyclic(override)
        self.acsAxis2.cyclic(override)
        self.acsAxis3.cyclic(override)
        self.acsAxis4.cyclic(override)

        # MCS-Achsen: unverzögert (velocity=None), werden von forward() befüllt
        self.mcsAxisX.cyclic()
        self.mcsAxisY.cyclic()
        self.mcsAxisZ.cyclic()
        self.mcsAxisR.cyclic()
