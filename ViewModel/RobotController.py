"""
Module: RobotController
Purpose: Per-robot orchestration layer that bridges HMI input, kinematics, and 3D view.
Responsibilities: Process HMI commands each tick, run forward/inverse kinematics, advance CNC
                  path with override, update 3D view, surface fault state to HMI status label.
Inputs:  hmiControl flags (from Hmi), kinematics model (Scara), view (View.Scara), hmiState.
Outputs: Updated axis positions, actor transforms, hmiState, HMI status display.
Dependencies: ViewModel.hmiControl, ViewModel.hmiState, Model.Scara, View.Scara, Model.RobotConfig
"""

import math
from Model.RobotConfig import SCARA_HOME


class RobotController:
    def __init__(self, robot_trafo, robot_view, hmi, hmi_state,
                 cnc_control=None, cnc_program_path=None):
        self.robot_trafo = robot_trafo
        self.robot_view = robot_view
        self.hmi = hmi
        self.hmi_state = hmi_state
        self.cnc_control = cnc_control
        self.cnc_program_path = cnc_program_path

        self._gripper_closed = False
        self._joint_mode = True
        self._manual_mode = True
        self._interpolated_path = None
        self._fault = False
        self._override_tick = 0

        if hasattr(self.robot_view, "set_gripper"):
            self.robot_view.set_gripper(closed=self._gripper_closed)

    def update_hmi(self):
        hmi_ctrl = self.hmi.getHmiControl()

        # Reset: clear fault and drive all axes to home position
        if getattr(hmi_ctrl, "Reset", False):
            self._fault = False
            self.robot_trafo.acsAxis1.Sollposition = SCARA_HOME["acsAxis1"]
            self.robot_trafo.acsAxis2.Sollposition = SCARA_HOME["acsAxis2"]
            self.robot_trafo.acsAxis3.Sollposition = SCARA_HOME["acsAxis3"]
            self.robot_trafo.acsAxis4.Sollposition = SCARA_HOME["acsAxis4"]
            hmi_ctrl.Reset = False  # consume pulse

        # Determine operating context for status check
        is_manual = hmi_ctrl.OperationMode == 0
        coord_ok  = hmi_ctrl.CoordSystem in ["Joint", "Welt", "Werkzeug"]

        # Status priority: fault > limit > missing coord > normal
        if self._fault:
            self.hmi.setStatus("STÖRUNG — Reset drücken", "red")
        elif self._any_at_limit():
            self.hmi.setStatus("Achse an Grenzwert", "orange")
        elif is_manual and not coord_ok:
            self.hmi.setStatus("Koordinatensystem wählen!", "orange")
        else:
            self.hmi.setStatus("Bereit", "lightgreen")

        if self._fault:
            self._update_hmi_state()
            self.hmi.setHmiState(self.hmi_state)
            return

        self._manual_mode = is_manual

        if self._manual_mode:
            # Only jog if the operator has selected a coordinate system
            if coord_ok:
                self._joint_mode = self._handle_manual_control(hmi_ctrl)
            # else: keep _joint_mode as-is; forward() keeps MCS in sync, no motion
            self._handle_gripper(hmi_ctrl)
        else:
            self._joint_mode = False
            if self.cnc_control is not None and getattr(hmi_ctrl, "Start", False):
                self.cnc_control.load_from_path(self.cnc_program_path)
                self._interpolated_path = iter(
                    self.cnc_control.interpolate_path(step_size=3.0)
                )
                hmi_ctrl.Start = False

        self._update_hmi_state()
        self.hmi.setHmiState(self.hmi_state)

    def update_kinematics(self):
        try:
            if self._joint_mode:
                self.robot_trafo.forward()
            else:
                self.robot_trafo.backward()
                self.robot_trafo.forward()  # MCS mit erreichter Position synchronisieren
        except ValueError as e:
            print(f"Kinematik Fehler: {e}")
            for axis in [
                self.robot_trafo.acsAxis1, self.robot_trafo.acsAxis2,
                self.robot_trafo.acsAxis3, self.robot_trafo.acsAxis4,
                self.robot_trafo.mcsAxisX, self.robot_trafo.mcsAxisY,
                self.robot_trafo.mcsAxisZ, self.robot_trafo.mcsAxisR,
            ]:
                axis.Sollposition = axis.ActualPosition
            self._fault = True

    def update_cnc_path(self):
        if self.cnc_control is None or self._interpolated_path is None:
            return

        # Speed override: 100% = 1 waypoint/tick, 50% = 1 per 2 ticks, etc.
        override = getattr(self.hmi.getHmiControl(), "OverridePercent", 100)
        ticks_per_step = max(1, round(100 / max(1, override)))
        self._override_tick += 1
        if self._override_tick < ticks_per_step:
            return
        self._override_tick = 0

        self.cnc_control.position = {
            "X": self.robot_trafo.mcsAxisX.ActualPosition,
            "Y": self.robot_trafo.mcsAxisY.ActualPosition,
            "Z": self.robot_trafo.mcsAxisZ.ActualPosition,
        }

        point = next(self._interpolated_path, None)
        if point is not None:
            self.robot_trafo.mcsAxisX.Sollposition = point["X"]
            self.robot_trafo.mcsAxisY.Sollposition = point["Y"]
            self.robot_trafo.mcsAxisZ.Sollposition = point["Z"]

    def update_view(self):
        self.robot_view.update_joints(
            self.robot_trafo.acsAxis1.getSetPosition(),
            self.robot_trafo.acsAxis2.getSetPosition(),
            self.robot_trafo.acsAxis4.getSetPosition(),
            z_height=self.robot_trafo.acsAxis3.getSetPosition()
        )

    # ============================================================
    # PRIVATE HELPERS
    # ============================================================
    def _any_at_limit(self):
        return any(a.is_at_limit() for a in [
            self.robot_trafo.acsAxis1, self.robot_trafo.acsAxis2,
            self.robot_trafo.acsAxis3, self.robot_trafo.acsAxis4,
        ])

    def _handle_manual_control(self, hmi_ctrl, step_joint=1, step_world=2):
        coord_system = getattr(hmi_ctrl, "CoordSystem", "Joint")
        if coord_system not in ["Joint", "Welt", "Werkzeug"]:
            coord_system = "Joint"

        if coord_system == "Joint":
            da1, da2, da3, da4 = self._jog_delta(hmi_ctrl, step_joint)
            self.robot_trafo.jog_joint(da1, da2, da3, da4)
            return True

        dx, dy, dz, dr = self._jog_delta(hmi_ctrl, step_world)
        if coord_system == "Welt":
            self.robot_trafo.jog_world(dx, dy, dz, dr)
        else:  # Werkzeug
            self.robot_trafo.jog_tool(dx, dy, dz, dr)
        return False

    def _jog_delta(self, hmi_ctrl, step):
        dx = (step if hmi_ctrl.MoveXPlus else 0.0) - (step if hmi_ctrl.MoveXNeg else 0.0)
        dy = (step if hmi_ctrl.MoveYPlus else 0.0) - (step if hmi_ctrl.MoveYNeg else 0.0)
        dz = (step if hmi_ctrl.MoveZPlus else 0.0) - (step if hmi_ctrl.MoveZNeg else 0.0)
        dr = (step if hmi_ctrl.MoveRPlus else 0.0) - (step if hmi_ctrl.MoveRNeg else 0.0)
        return dx, dy, dz, dr

    def _handle_gripper(self, hmi_ctrl):
        if getattr(hmi_ctrl, "Start", False):
            self._gripper_closed = True
        if getattr(hmi_ctrl, "Stop", False):
            self._gripper_closed = False
        if hasattr(self.robot_view, "set_gripper"):
            self.robot_view.set_gripper(closed=self._gripper_closed)
        if hasattr(self.robot_view, "attach_part"):
            self.robot_view.attach_part(self._gripper_closed)

    def _update_hmi_state(self):
        self.hmi_state.axisJ1Position = self.robot_trafo.acsAxis1.ActualPosition
        self.hmi_state.axisJ2Position = self.robot_trafo.acsAxis2.ActualPosition
        self.hmi_state.axisJ3Position = self.robot_trafo.acsAxis3.ActualPosition
        self.hmi_state.axisJ4Position = self.robot_trafo.acsAxis4.ActualPosition
        self.hmi_state.axisXPosition = self.robot_trafo.mcsAxisX.ActualPosition
        self.hmi_state.axisYPosition = self.robot_trafo.mcsAxisY.ActualPosition
        self.hmi_state.axisZPosition = self.robot_trafo.mcsAxisZ.ActualPosition
        self.hmi_state.axisRPosition = self.robot_trafo.mcsAxisR.ActualPosition
