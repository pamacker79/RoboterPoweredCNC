"""
Module: hBot
Purpose: Kinematic model for the CoreXY / H-Bot gantry robot.
Responsibilities: XY axis limit enforcement, cyclic velocity ramp.
Inputs:  Cartesian X/Y targets via mcsAxisX/Y Sollposition.
Outputs: mcsAxisX/Y ActualPosition updated by cyclic().
Dependencies: Model.Axis, Model.RobotConfig
"""
import sys
sys.path.append('../Model')

from Model.Axis import Axis
from Model.RobotConfig import HBOT_LIMITS

class hBot:

    def __init__(self):
        self.mcsAxisX = Axis(*HBOT_LIMITS["mcsAxisX"])
        self.mcsAxisY = Axis(*HBOT_LIMITS["mcsAxisY"])
        self.acsAxis_a = Axis(*HBOT_LIMITS["acsAxis_a"])
        self.acsAxis_b = Axis(*HBOT_LIMITS["acsAxis_b"])

    def cyclic(self, override: float = 1.0):
        """Move ActualPosition toward Sollposition at override-scaled velocity (100 Hz)."""
        self.mcsAxisX.cyclic(override)
        self.mcsAxisY.cyclic(override)
