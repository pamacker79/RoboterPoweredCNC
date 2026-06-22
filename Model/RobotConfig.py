"""
Modul: Model.RobotConfig
========================
Zentrale Konfigurationsdatei für alle Achsparameter und Heimatpositionen.

Dieses Modul ist die **einzige** Stelle, an der Achsgrenzen und Geschwindigkeiten
verändert werden dürfen.  Alle Modellklassen importieren ihre Parameter von hier,
sodass eine Anpassung sofort systemweit wirkt.

Aufbau der Limit-Tupel
----------------------
Jedes Tupel hat das Format ``(min_pos, max_pos, velocity_per_tick)`` oder
``(min_pos, max_pos)`` wenn die Achse unverzögert ist.

SCARA-Achskonventionen
----------------------
* acsAxis1/2 – Gelenkwinkel in Grad (Arm 1 = Schulter, Arm 2 = Ellbogen).
* acsAxis3   – Hubachse der Spindel in mm (0 = oben, negativer Wert = abgesenkt).
* acsAxis4   – Werkzeugdrehachse in Grad.
* mcsAxisX/Y – Kartesische TCP-Position in mm (berechnet aus Vorwärtskinematik).
* mcsAxisZ   – Identisch mit acsAxis3 (Lineare Achse, kein kinematischer Term).
* mcsAxisR   – Werkzeugrotation in der Welt (Summe aller Gelenke).

H-Bot-Achskonventionen
-----------------------
* mcsAxisX/Y – Kartesische Position des Laserkopfs in mm.
* acsAxis_a  – Motorachse A = X + Y (CoreXY-Formel).
* acsAxis_b  – Motorachse B = X − Y (CoreXY-Formel).
"""

# ------------------------------------------------------------------
# SCARA-Roboter (Roboter 1 und Roboter 3)
# ------------------------------------------------------------------
SCARA_LIMITS = {
    # Format: (min_pos, max_pos, velocity_per_tick)
    # Geschwindigkeiten bei 100 Hz:
    #   3 Grad/Tick  → 300 Grad/s  (Gelenkachsen)
    #   2 mm/Tick    → 200 mm/s    (Hubachse)
    #   5 Grad/Tick  → 500 Grad/s  (Werkzeugdrehachse)

    "acsAxis1": (-170.0,  170.0,  3.0),  # Schultergelenk           [Grad]
    "acsAxis2": (-145.0,  145.0,  3.0),  # Ellbogengelenk           [Grad]
    "acsAxis3": (-280.0,    0.0,  2.0),  # Hubachse (Spindel)       [mm]
    "acsAxis4": (-360.0,  360.0,  5.0),  # Werkzeugdrehachse        [Grad]

    # MCS-Achsen: keine eigene Geschwindigkeit, werden aus ACS berechnet
    "mcsAxisX": (-875.0,  875.0),        # TCP X-Koordinate         [mm]
    "mcsAxisY": (-875.0,  875.0),        # TCP Y-Koordinate         [mm]
    "mcsAxisZ": (-280.0,    0.0),        # TCP Z = acsAxis3         [mm]
    "mcsAxisR": (-360.0,  360.0),        # TCP Rotation             [Grad]
}

# ------------------------------------------------------------------
# H-Bot Gravur-Gantry
# ------------------------------------------------------------------
HBOT_LIMITS = {
    # Format: (min_pos, max_pos, velocity_per_tick)
    # Geschwindigkeit bei 100 Hz:
    #   5 mm/Tick → 500 mm/s maximale Verfahrgeschwindigkeit

    "mcsAxisX":  (-700.0,  700.0, 5.0),  # Laserkopf X-Position    [mm]
    "mcsAxisY":  (-300.0,  300.0, 5.0),  # Laserkopf Y-Position    [mm]

    # Motor-Achsen: werden derzeit nicht aktiv gesteuert
    # (Kinematik läuft direkt über mcsAxisX/Y)
    "acsAxis_a": (-700.0,  700.0),       # Motor A = X + Y         [mm]
    "acsAxis_b": (-700.0,  700.0),       # Motor B = X − Y         [mm]
}

# ------------------------------------------------------------------
# SCARA Heimatposition (SCARA_HOME)
# ------------------------------------------------------------------
SCARA_HOME = {
    # Startposition und Ruheposition nach jeder abgeschlossenen Sequenz.
    # Bei acsAxis1=90°, acsAxis2=-90° befindet sich der TCP kompakt über
    # der Basis und der Arm blockiert keinen Arbeitsbereich des anderen Roboters.

    "acsAxis1":  90.0,   # Schultergelenk  [Grad] – Arm zeigt in +Y-Richtung
    "acsAxis2": -90.0,   # Ellbogengelenk  [Grad] – Arm zurückgeklappt
    "acsAxis3":   0.0,   # Hubachse        [mm]   – Spindel vollständig oben
    "acsAxis4":   0.0,   # Werkzeugachse   [Grad] – keine Werkzeugdrehung

    # Ergibt TCP-Lokalposition ≈ (550, 325) mm, Abstand zur Basis ≈ 638 mm
}
