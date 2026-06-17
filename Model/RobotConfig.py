"""
Module: RobotConfig
Purpose: Central configuration for all robot axis limits and home positions.
Responsibilities: Single source of truth — edit only here to change limits system-wide.
Inputs:  —
Outputs: SCARA_LIMITS, HBOT_LIMITS, SCARA_HOME dicts imported by model modules.
Dependencies: none
"""

SCARA_LIMITS = {
    # (min, max, velocity_per_tick)
    # velocity at 100 Hz: 3 deg/tick = 300 deg/s, 2 mm/tick = 200 mm/s
    "acsAxis1": (-170.0,  170.0,  3.0),  # Gelenk 1          [Grad]
    "acsAxis2": (-145.0,  145.0,  3.0),  # Gelenk 2          [Grad]
    "acsAxis3": (-280.0,    0.0,  2.0),  # Hubachse           [mm]
    "acsAxis4": (-360.0,  360.0,  5.0),  # Werkzeugdrehachse  [Grad]
    # MCS axes are derived values — no velocity limit (instant update from kinematics)
    "mcsAxisX": (-875.0,  875.0),        # X-Achse            [mm]
    "mcsAxisY": (-875.0,  875.0),        # Y-Achse            [mm]
    "mcsAxisZ": (-280.0,    0.0),        # Z-Achse = acsAxis3 [mm]
    "mcsAxisR": (-360.0,  360.0),        # Rotationsachse     [Grad]
}

HBOT_LIMITS = {
    # velocity at 100 Hz: 5 mm/tick = 500 mm/s maximum
    "mcsAxisX":  (-700.0,  700.0, 5.0),  # X-Achse            [mm]
    "mcsAxisY":  (-300.0,  300.0, 5.0),  # Y-Achse            [mm]
    "acsAxis_a": (-700.0,  700.0),       # Motor A = X+Y      [mm]
    "acsAxis_b": (-700.0,  700.0),       # Motor B = X-Y      [mm]
}

SCARA_HOME = {
    "acsAxis1":  90.0,  # Gelenk 1 Heimposition [Grad] — Arm zeigt in +Y
    "acsAxis2": -90.0,  # Gelenk 2 Heimposition [Grad] — Arm zurückgeklappt
    "acsAxis3":   0.0,  # Hubachse Heimposition  [mm]  — Spindel oben
    "acsAxis4":   0.0,  # Werkzeugachse Heimpos. [Grad]
    # → TCP lokal bei (550, 325) mm, Radius 638 mm (72 % Reichweite)
}
