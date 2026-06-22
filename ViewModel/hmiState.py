"""
Module: hmiState
Purpose: Data transfer object for outgoing HMI state (axis positions displayed to operator).
Responsibilities: Holds current actual positions; written by RobotController, read by Hmi.setHmiState().
Inputs:  Position values from RobotController._update_hmi_state().
Outputs: Values consumed by Hmi label widgets.
Dependencies: none
"""
import sys
sys.path.append('../ViewModel')


class hmiState:
    def __init__(self):
        self.axisXPosition = 0
        self.axisYPosition = 0
        self.axisZPosition = 0
        self.axisRPosition = 0

        self.axisJ1Position = 0
        self.axisJ2Position = 0
        self.axisJ3Position = 0
        self.axisJ4Position = 0

