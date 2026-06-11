"""
Module: hmiControl
Purpose: Data transfer object for incoming HMI commands (button/switch states from operator).
Responsibilities: Holds jog, Start/Stop/Reset, mode, and override values; written by Hmi, read by RobotController.
Inputs:  Button/slider events from Hmi widget handlers.
Outputs: Control flags consumed by RobotController.update_hmi().
Dependencies: none
"""
import sys
sys.path.append('../ViewModel')


class hmiControl:
    def __init__(self):
        self.MoveXPlus = False
        self.MoveXNeg = False
        self.MoveYPlus = False
        self.MoveYNeg = False
        self.MoveZPlus = False
        self.MoveZNeg = False
        self.MoveRPlus = False
        self.MoveRNeg = False

        self.MoveJ1Plus = False
        self.MoveJ1Neg = False
        self.MoveJ2Plus = False
        self.MoveJ2Neg = False
        self.MoveJ3Plus = False
        self.MoveJ3Neg = False
        self.MoveJ4Plus = False
        self.MoveJ4Neg = False

        self.Start = False
        self.Stop = False
        self.Reset = False

        self.OperationMode = 0  # 0=Manual / 1=Automatic
        self.CoordSystem = "wählen"
        self.OverridePercent = 100  # 0–100 %, speed override for CNC execution

