"""
Module: RobotConfig
Purpose: Central configuration for all robot axis limits and home positions.
Responsibilities: Single source of truth — edit only here to change limits system-wide.
Inputs:  —
Outputs: SCARA_LIMITS, HBOT_LIMITS, SCARA_HOME dicts imported by model modules.
Dependencies: none
"""

SCARA_LIMITS = {
    "acsAxis1": (-170.0,  170.0),   # Gelenk 1          [Grad]
    "acsAxis2": (-145.0,  145.0),   # Gelenk 2          [Grad]
    "acsAxis3": (-280.0,  0.0),   # Hubachse           [mm]
    "acsAxis4": (-360.0,  360.0),   # Werkzeugdrehachse  [Grad]
    "mcsAxisX": (-875.0,  875.0),   # X-Achse            [mm]
    "mcsAxisY": (-875.0,  875.0),   # Y-Achse            [mm]
    "mcsAxisZ": (-280.0,    0.0),   # Z-Achse = acsAxis3 [mm]  (0=oben, -280=unten)
    "mcsAxisR": (-360.0,  360.0),   # Rotationsachse     [Grad]
}

HBOT_LIMITS = {
    "mcsAxisX":  (-300.0,  300.0),  # X-Achse            [mm]
    "mcsAxisY":  (-300.0,  300.0),  # Y-Achse            [mm]
    "acsAxis_a": (-600.0,  600.0),  # Motor A            [mm]
    "acsAxis_b": (-600.0,  600.0),  # Motor B            [mm]
}

SCARA_HOME = {
    "acsAxis1":  90.0,  # Gelenk 1 Heimposition [Grad] — Arm zeigt in +Y
    "acsAxis2": -90.0,  # Gelenk 2 Heimposition [Grad] — Arm zurückgeklappt
    "acsAxis3":   0.0,  # Hubachse Heimposition  [mm]  — Spindel oben
    "acsAxis4":   0.0,  # Werkzeugachse Heimpos. [Grad]
    # → TCP lokal bei (550, 325) mm, Radius 638 mm (72 % Reichweite)
}
