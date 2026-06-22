"""
Modul: ViewModel.hmiState
==========================
Datentransferobjekt (DTO) für ausgehende HMI-Zustandsinformationen.

Datenfluss
----------
``RobotController._update_hmi_state()`` schreibt in dieses Objekt.
``Hmi.setHmiState()`` liest daraus und aktualisiert die Anzeigefelder.

Felder (Istwerte — immer ``ActualPosition``, nie ``Sollposition``)
------------------------------------------------------------------
axisXPosition : float
    TCP X-Koordinate im Weltkoordinatensystem [mm].
axisYPosition : float
    TCP Y-Koordinate im Weltkoordinatensystem [mm].
axisZPosition : float
    TCP Z-Koordinate (= acsAxis3 Istwert) [mm].
axisRPosition : float
    TCP-Weltrotation (Summe acsAxis1 + acsAxis2 + acsAxis4) [Grad].
axisJ1–J4Position : float
    Gelenk-Istwerte (acsAxis1–4) — werden im HMI bei Koordinatensystem
    "Joint" angezeigt.
"""
import sys
sys.path.append('../ViewModel')


class hmiState:
    """
    Datencontainer für Achsistwerte — vom Regler zum HMI.

    Alle Felder werden von ``RobotController._update_hmi_state()``
    beschrieben und von ``Hmi.setHmiState()`` angezeigt.
    Nur Lesezugriff durch das HMI — keine Steuerlogik.
    """

    def __init__(self):
        """Initialisiert alle Istwerte auf Null."""
        # Kartesische Istwerte im Weltkoordinatensystem
        self.axisXPosition = 0.0
        self.axisYPosition = 0.0
        self.axisZPosition = 0.0
        self.axisRPosition = 0.0

        # Gelenkistwerte (ACS)
        self.axisJ1Position = 0.0
        self.axisJ2Position = 0.0
        self.axisJ3Position = 0.0
        self.axisJ4Position = 0.0
