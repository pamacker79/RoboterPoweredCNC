"""
Module: hBot
Purpose: Kinematic model for the CoreXY / H-Bot gantry robot.
Responsibilities: XY↔Motor-A/B coordinate conversion, axis limit enforcement, move commands.
Inputs:  Cartesian X/Y targets via mcsAxisX/Y; motor positions via acsAxis_a/b.
Outputs: Updated axis positions; motor coordinates from inverse(), Cartesian from forward().
Dependencies: Model.Axis, Model.CncInterpreter, Model.RobotConfig
"""
import sys
sys.path.append('../Model')

from Model.Axis import Axis
from Model.CncInterpreter import CncInterpreter
from Model.RobotConfig import HBOT_LIMITS

class hBot:

    def __init__(self):

        # Motor axes
        self.acsAxis_a = Axis(*HBOT_LIMITS["acsAxis_a"])
        self.acsAxis_b = Axis(*HBOT_LIMITS["acsAxis_b"])

        # Cartesian coordinates
        self.mcsAxisX = Axis(*HBOT_LIMITS["mcsAxisX"])
        self.mcsAxisY = Axis(*HBOT_LIMITS["mcsAxisY"])

        self.CncInter = CncInterpreter()
    # --------------------------------
    # XY -> Motor coordinates
    # --------------------------------
    def inverse(self, mcsAxisX, mcsAxisY):

        motor_a = mcsAxisX + mcsAxisY
        motor_b = mcsAxisX - mcsAxisY

        return motor_a, motor_b

    # --------------------------------
    # Motor coordinates -> XY
    # --------------------------------
    def forward(self, motor_a, motor_b):

        mcsAxisX = (motor_a + motor_b) / 2.0
        mcsAxisY = (motor_a - motor_b) / 2.0

        return mcsAxisX, mcsAxisY

    # --------------------------------
    # Move command
    # --------------------------------
    def move_to(self, mcsAxisX, mcsAxisY):

        print(f"\nMove command -> X:{mcsAxisX} Y:{mcsAxisY}")

        # Convert XY to motor coordinates
        motor_a, motor_b = self.inverse(mcsAxisX, mcsAxisY)

        # Write target positions
        self.acsAxis_a.Sollposition = motor_a
        self.acsAxis_b.Sollposition = motor_b

        # Simulate movement
        self.acsAxis_a.ActualPosition = motor_a
        self.acsAxis_b.ActualPosition = motor_b

        # Update Cartesian coordinates
        self.mcsAxisX.Sollposition = mcsAxisX
        self.mcsAxisX.ActualPosition = mcsAxisX
        self.mcsAxisY.Sollposition = mcsAxisY
        self.mcsAxisY.ActualPosition = mcsAxisY

    # --------------------------------
    # Get actual XY position
    # --------------------------------
    def get_actual_position(self):

        motor_a = self.acsAxis_a.getActualPosition()
        motor_b = self.acsAxis_b.getActualPosition()

        return self.forward(motor_a, motor_b)

    # --------------------------------
    # Status output
    # --------------------------------
    def status(self):

        print("\n--- COREXY STATUS ---")

        print(f"Motor A Actual: {self.acsAxis_a.ActualPosition}")
        print(f"Motor B Actual: {self.acsAxis_b.ActualPosition}")

        mcsAxisX, mcsAxisY = self.get_actual_position()

        print(f"Calculated X: {mcsAxisX}")
        print(f"Calculated Y: {mcsAxisY}")

