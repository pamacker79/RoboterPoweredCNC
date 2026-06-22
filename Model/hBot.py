"""
Modul: Model.hBot
=================
Kinematisches Modell der CoreXY / H-Bot Gravur-Gantry.

Funktionsprinzip
----------------
Der H-Bot ist eine 2-Achsen-Portalanlage, bei der zwei Motoren (A und B)
die kartesischen Bewegungen gemeinsam erzeugen (CoreXY-Kinematik).
In dieser Simulation wird die Bewegung direkt auf den kartesischen
MCS-Achsen gerechnet; die Motorachsen (acsAxis_a, acsAxis_b) sind als
Datenbehälter vorhanden, werden aber aktuell nicht für die Positionssteuerung
genutzt.

Bewegungssteuerung
------------------
Die Sollposition wird direkt auf ``mcsAxisX.Sollposition`` und
``mcsAxisY.Sollposition`` geschrieben.  Die Methode ``cyclic()`` ruft dann
``Axis.cyclic(override)`` auf, die ActualPosition mit der konfigurierten
Maximalgeschwindigkeit (5 mm/Tick = 500 mm/s) und dem Override-Faktor
nachführt.  Der Override-Wert kommt vom HMI-Schieberegler.

Abhängigkeiten
--------------
* ``Model.Axis``       – Einzelachse mit Begrenzung und Rampe
* ``Model.RobotConfig`` – Achsgrenzen und Geschwindigkeiten
"""
import sys
sys.path.append('../Model')

from Model.Axis import Axis
from Model.RobotConfig import HBOT_LIMITS


class hBot:
    """
    Kinematisches Modell der H-Bot Gravur-Gantry.

    Attribute
    ---------
    mcsAxisX : Axis
        Kartesische X-Position des Laserkopfs [mm].
    mcsAxisY : Axis
        Kartesische Y-Position des Laserkopfs [mm].
    acsAxis_a : Axis
        Motor A (= X + Y) – derzeit nur als Datenbehälter [mm].
    acsAxis_b : Axis
        Motor B (= X − Y) – derzeit nur als Datenbehälter [mm].
    """

    def __init__(self):
        """Initialisiert alle Achsen mit den Grenzen aus RobotConfig."""
        self.mcsAxisX  = Axis(*HBOT_LIMITS["mcsAxisX"])
        self.mcsAxisY  = Axis(*HBOT_LIMITS["mcsAxisY"])
        self.acsAxis_a = Axis(*HBOT_LIMITS["acsAxis_a"])
        self.acsAxis_b = Axis(*HBOT_LIMITS["acsAxis_b"])

    def cyclic(self, override: float = 1.0):
        """
        Führt die Lageregelung der Gantry-Achsen durch (100-Hz-Tick).

        Bewegt ``ActualPosition`` beider MCS-Achsen schrittweise auf den
        jeweiligen Sollwert zu.  Die effektive Geschwindigkeit entspricht
        ``velocity × override``.

        Parameter
        ---------
        override : float
            Geschwindigkeitsskalierung [0.0 … 1.0], gesteuert durch den
            HMI-Override-Schieberegler.  0.0 = Stillstand, 1.0 = Vollgas.
        """
        self.mcsAxisX.cyclic(override)
        self.mcsAxisY.cyclic(override)
