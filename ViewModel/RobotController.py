"""
Module: RobotController
Purpose: Per-robot orchestration layer that bridges HMI input, kinematics, and 3D view.
Responsibilities:
  - Manual mode: jog control, suction-range check on "Saugen", part release to Z=0.
  - Auto mode:   state-machine sequence (approach → lower → grab → lift → place → lift).
  - Mode switch: auto-sequence aborts immediately on switch to manual.
Inputs:  hmiControl flags, kinematics model (Scara), view (View.Scara), WorkpieceManager,
         optional MagazinViewPV (Robot 1 only).
Outputs: Updated axis positions, actor transforms, hmiState, HMI status display.
Dependencies: ViewModel.hmiControl, ViewModel.hmiState, Model.Scara, View.Scara,
              Model.RobotConfig, Model.WorkpieceManager
"""

import math
from Model.RobotConfig import SCARA_HOME

# ── Auto-sequence states ─────────────────────────────────────────────────────
_A_IDLE             = 0
_A_MOVE_ABOVE_PICK  = 1
_A_LOWER_TO_PICK    = 2
_A_GRAB             = 3
_A_LIFT_AFTER_PICK  = 4
_A_MOVE_ABOVE_PLACE = 5
_A_LOWER_TO_PLACE   = 6
_A_RELEASE          = 7
_A_LIFT_AFTER_PLACE = 8
_A_GO_HOME          = 9   # return to SCARA_HOME after each placement

_GRAB_TICKS      = 10     # ticks for vacuum engage/release dwell (~100 ms)
_AUTO_TIMEOUT    = 600    # ticks before a motion state triggers fault (~6 s)
_ARRIVED_TOL_DEG = 1.5    # deg — arrival tolerance for angular axes
_ARRIVED_TOL_MM  = 1.5    # mm  — arrival tolerance for linear axes
_SUCTION_RADIUS    = 60.0   # mm — max XY distance for manual suction
_SUCTION_RADIUS_Z  = 30.0   # mm — max Z distance for manual suction
# WPM parts rest on the floor with top surface at this world Z (part height = 20 mm)
_WPM_PART_TOP    = 20.0


class RobotController:
    def __init__(self, robot_trafo, robot_view, hmi, hmi_state,
                 workpiece_manager=None, magazin_view=None,
                 pickup_world=None, place_world=None,
                 pickup_gate=None,
                 cnc_control=None, cnc_program_path=None):
        """
        pickup_world : (wx, wy) world position the robot polls for a part (auto mode).
        place_world  : (wx, wy) world position the robot drops the part (auto mode).
        magazin_view : MagazinViewPV — supply only for the robot that serves the magazine.
        """
        self.robot_trafo   = robot_trafo
        self.robot_view    = robot_view
        self.hmi           = hmi
        self.hmi_state     = hmi_state
        self.wpm           = workpiece_manager
        self.magazin_view  = magazin_view
        self.pickup_world  = pickup_world   # (wx, wy) or None
        self.place_world   = place_world    # (wx, wy) or None
        self.pickup_gate   = pickup_gate    # optional callable() -> bool extra condition
        self.cnc_control   = cnc_control
        self.cnc_program_path = cnc_program_path

        self._gripper_closed  = False
        self._joint_mode      = True
        self._manual_mode     = True
        self._fault           = False
        self._override_tick   = 0

        # carried part tracking (manual mode)
        self._carried_part_id = None   # wpm part id, or "magazine" sentinel

        # auto-sequence state
        self._auto_state   = _A_IDLE
        self._auto_tick    = 0
        self._pick_wx      = 0.0
        self._pick_wy      = 0.0
        self._pick_wz      = 0.0   # mcsAxisZ to reach pickup surface
        self._place_wx     = 0.0
        self._place_wy     = 0.0
        self._place_wz     = 0.0   # mcsAxisZ to reach place surface
        self._pending_wpm_part = None  # part dict reserved during approach

        self._interpolated_path = None  # CNC path iterator (Robot 1 only)

        if hasattr(self.robot_view, "set_gripper"):
            self.robot_view.set_gripper(closed=False)

    # =========================================================================
    # PUBLIC — called from main loop
    # =========================================================================
    def update_hmi(self):
        hmi_ctrl = self.hmi.getHmiControl()
        is_auto  = (hmi_ctrl.OperationMode == 1)

        # ── Reset ────────────────────────────────────────────────────────────
        if getattr(hmi_ctrl, "Reset", False):
            self._fault = False
            self._auto_state = _A_IDLE
            self._cancel_vacuum()
            self.robot_trafo.acsAxis1.Sollposition = SCARA_HOME["acsAxis1"]
            self.robot_trafo.acsAxis2.Sollposition = SCARA_HOME["acsAxis2"]
            self.robot_trafo.acsAxis3.Sollposition = SCARA_HOME["acsAxis3"]
            self.robot_trafo.acsAxis4.Sollposition = SCARA_HOME["acsAxis4"]
            hmi_ctrl.Reset = False

        # ── Saugen button only active in manual mode ─────────────────────────
        if hasattr(self.hmi, "set_saugen_enabled"):
            self.hmi.set_saugen_enabled(not is_auto)

        # ── Status display ────────────────────────────────────────────────────
        if self._fault:
            self.hmi.setStatus("STÖRUNG — Reset drücken", "red")
        elif is_auto and self._auto_state != _A_IDLE:
            self.hmi.setStatus(f"Automatik — Schritt {self._auto_state}/9", "lightyellow")
        elif is_auto:
            self.hmi.setStatus("Automatik — wartet auf Teil", "lightcyan")
        elif self._any_at_limit():
            self.hmi.setStatus("Achse an Grenzwert", "orange")
        else:
            self.hmi.setStatus("Bereit", "lightgreen")

        if self._fault:
            self._update_hmi_state()
            self.hmi.setHmiState(self.hmi_state)
            return

        # ── Dispatch by mode ─────────────────────────────────────────────────
        if is_auto:
            self._manual_mode = False
            self._run_auto(hmi_ctrl)
        else:
            # Switching to manual: abort auto sequence and release vacuum immediately
            if not self._manual_mode:
                self._auto_state = _A_IDLE
                self._auto_tick  = 0
                self._cancel_vacuum()
                self._pending_wpm_part = None
            self._manual_mode = True
            self._run_manual(hmi_ctrl)

        self._update_hmi_state()
        self.hmi.setHmiState(self.hmi_state)

    def update_kinematics(self):
        try:
            if self._joint_mode:
                self.robot_trafo.forward()
            else:
                self.robot_trafo.backward()
                self.robot_trafo.forward()
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
        """CNC path execution (Robot 1 only, manual auto-mode via G-code — kept for compatibility)."""
        if self.cnc_control is None or self._interpolated_path is None:
            return
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
        # Use ActualPosition so the 3D model shows where the robot physically IS,
        # not where it wants to be (Sollposition may be ahead of actual motion).
        # +180° on axis1: STL arm points in -X at angle=0, kinematics assumes +X.
        self.robot_view.update_joints(
            self.robot_trafo.acsAxis1.ActualPosition + 180.0,
            self.robot_trafo.acsAxis2.ActualPosition,
            self.robot_trafo.acsAxis4.ActualPosition,
            z_height=self.robot_trafo.acsAxis3.ActualPosition
        )

    # =========================================================================
    # MANUAL MODE
    # =========================================================================
    def _run_manual(self, hmi_ctrl):
        coord_system = getattr(hmi_ctrl, "CoordSystem", "wählen")
        coord_ok = coord_system in ["Joint", "Welt", "Werkzeug"]

        if not coord_ok:
            self.hmi.setStatus("Koordinatensystem wählen!", "orange")
        else:
            self._joint_mode = self._handle_manual_control(hmi_ctrl)

        # "Saugen" toggle — one-shot flag consumed here
        if getattr(hmi_ctrl, "Saugen", False):
            hmi_ctrl.Saugen = False
            self._handle_saugen()

    def _handle_saugen(self):
        """Pick up or release a workpiece depending on current carry state."""
        if self._gripper_closed:
            # Release: drop part at (tcp_x, tcp_y, Z=0)
            self._release_part()
        else:
            # Attempt pickup: check all parts in scene
            self._attempt_pickup()

    def _attempt_pickup(self):
        tcp_wx, tcp_wy, tcp_wz = self._tcp_world_pos()

        # ① Check magazine top part
        if self.magazin_view is not None:
            mag_coords = self.magazin_view.get_pickup_coordinates()
            if mag_coords is not None:
                mx, my, mz = mag_coords
                dist_xy = math.sqrt((tcp_wx - mx) ** 2 + (tcp_wy - my) ** 2)
                dist_z  = abs(tcp_wz - mz)
                if dist_xy <= _SUCTION_RADIUS:
                    if dist_z <= _SUCTION_RADIUS_Z:
                        self.magazin_view.pick_top_part()
                        self._activate_vacuum()
                        self._carried_part_id = "magazine"
                        self.hmi.setStatus("Teil aus Magazin angesaugt", "lightgreen")
                    else:
                        self.hmi.setStatus(
                            f"Kein Rohteil in der Nähe des Saugers — Höhendifferenz: {dist_z:.0f} mm",
                            "orange"
                        )
                    return

        # ② Check free parts in WorkpieceManager
        if self.wpm is not None:
            part = self.wpm.pick_nearest(tcp_wx, tcp_wy, _SUCTION_RADIUS)
            if part is not None:
                part_wz = _WPM_PART_TOP  # free parts on floor: top surface at Z = part height
                dist_z  = abs(tcp_wz - part_wz)
                if dist_z <= _SUCTION_RADIUS_Z:
                    self.wpm.remove_part(part["id"])
                    self._activate_vacuum()
                    self._carried_part_id = part["id"]
                    self.hmi.setStatus("Rohteil angesaugt", "lightgreen")
                else:
                    self.hmi.setStatus(
                        f"Kein Rohteil in der Nähe des Saugers — Höhendifferenz: {dist_z:.0f} mm",
                        "orange"
                    )
                return

        # ③ Nothing within XY radius
        self.hmi.setStatus("Kein Rohteil in der Nähe des Saugers", "orange")

    def _release_part(self):
        """Drop carried part at TCP XY, Z=0, preserving current TCP rotation."""
        if self.wpm is not None:
            tcp_wx, tcp_wy, _ = self._tcp_world_pos()
            self.wpm.add_part(
                self.robot_view.pl,
                tcp_wx,
                tcp_wy,
                rotation_z=self._tcp_rotation(),
            )
        self._cancel_vacuum()
        self._carried_part_id = None
        self.hmi.setStatus("Teil abgelegt (Z=0)", "lightgreen")

    # =========================================================================
    # AUTO MODE
    # =========================================================================
    def _run_auto(self, hmi_ctrl):
        self._auto_tick += 1

        if self._auto_state == _A_IDLE:
            self._auto_try_start()
            self._auto_tick = 0   # don't let tick counter grow unbounded while idle

        elif self._auto_state == _A_MOVE_ABOVE_PICK:
            self._set_mcs_target(self._pick_wx, self._pick_wy, 0.0)
            if self._is_at_target():
                self._next_auto_state()
            elif self._auto_tick >= _AUTO_TIMEOUT:
                self._trigger_auto_fault("Timeout: Anfahrt Pickup-Position")

        elif self._auto_state == _A_LOWER_TO_PICK:
            self._set_mcs_target(self._pick_wx, self._pick_wy, self._pick_wz)
            if self._is_at_target():
                self._next_auto_state()
            elif self._auto_tick >= _AUTO_TIMEOUT:
                self._trigger_auto_fault("Timeout: Absenken zum Bauteil")

        elif self._auto_state == _A_GRAB:
            # One-shot: activate vacuum and remove part from source on first tick
            if self._auto_tick == 1:
                self._activate_vacuum()
                if self._pending_wpm_part is not None:
                    self.wpm.remove_part(self._pending_wpm_part["id"])
                    self._pending_wpm_part = None
                elif self.magazin_view is not None:
                    self.magazin_view.pick_top_part()
            if self._auto_tick >= _GRAB_TICKS:
                self._next_auto_state()

        elif self._auto_state == _A_LIFT_AFTER_PICK:
            self._set_mcs_target(self._pick_wx, self._pick_wy, 0.0)
            if self._is_at_target():
                self._next_auto_state()
            elif self._auto_tick >= _AUTO_TIMEOUT:
                self._trigger_auto_fault("Timeout: Anheben nach Pickup")

        elif self._auto_state == _A_MOVE_ABOVE_PLACE:
            self._set_mcs_target(self._place_wx, self._place_wy, 0.0)
            if self._is_at_target():
                self._next_auto_state()
            elif self._auto_tick >= _AUTO_TIMEOUT:
                self._trigger_auto_fault("Timeout: Anfahrt Ablageposition")

        elif self._auto_state == _A_LOWER_TO_PLACE:
            self._set_mcs_target(self._place_wx, self._place_wy, self._place_wz)
            if self._is_at_target():
                self._next_auto_state()
            elif self._auto_tick >= _AUTO_TIMEOUT:
                self._trigger_auto_fault("Timeout: Absenken zur Ablage")

        elif self._auto_state == _A_RELEASE:
            if self._auto_tick == 1:
                self._cancel_vacuum()
                if self.wpm is not None:
                    # Convert SCARA-local back to world (accounts for mounting rotation)
                    place_wx, place_wy = self._local_to_world(self._place_wx, self._place_wy)
                    self.wpm.add_part(
                        self.robot_view.pl,
                        place_wx,
                        place_wy,
                        rotation_z=self._tcp_rotation(),
                    )
            if self._auto_tick >= _GRAB_TICKS:
                self._next_auto_state()

        elif self._auto_state == _A_LIFT_AFTER_PLACE:
            self._set_mcs_target(self._place_wx, self._place_wy, 0.0)
            if self._is_at_target():
                self._next_auto_state()  # → _A_GO_HOME
            elif self._auto_tick >= _AUTO_TIMEOUT:
                self._trigger_auto_fault("Timeout: Anheben nach Ablage")

        elif self._auto_state == _A_GO_HOME:
            # Return arm to home position in joint mode after each placement
            self._joint_mode = True
            self.robot_trafo.acsAxis1.Sollposition = SCARA_HOME["acsAxis1"]
            self.robot_trafo.acsAxis2.Sollposition = SCARA_HOME["acsAxis2"]
            self.robot_trafo.acsAxis3.Sollposition = SCARA_HOME["acsAxis3"]
            self.robot_trafo.acsAxis4.Sollposition = SCARA_HOME["acsAxis4"]
            if self._is_at_target():
                self._auto_state = _A_IDLE
                self._auto_tick  = 0
            elif self._auto_tick >= _AUTO_TIMEOUT:
                self._trigger_auto_fault("Timeout: Heimfahrt")

    def _auto_try_start(self):
        """Poll pickup and place zones; start sequence only when both conditions are met."""
        if self.pickup_world is None or self.place_world is None:
            return

        pw_x, pw_y = self.pickup_world
        pl_x, pl_y = self.place_world

        # ── Guard 1: place target must be free ───────────────────────────────
        if self.wpm is not None and self.wpm.has_part_at(pl_x, pl_y, _SUCTION_RADIUS):
            self.hmi.setStatus("Automatik — Absetzplatz belegt, warte...", "lightsalmon")
            return

        # ── Guard 2: part must be available at pickup zone ───────────────────
        pick_z = None
        pending = None

        if self.magazin_view is not None:
            coords = self.magazin_view.get_pickup_coordinates()
            if coords is not None:
                pick_z = self._world_z_to_mcs(coords[2])

        if pick_z is None and self.wpm is not None:
            part = self.wpm.pick_nearest(pw_x, pw_y, _SUCTION_RADIUS)
            if part is not None:
                pick_z = self._world_z_to_mcs(_WPM_PART_TOP)  # suction contacts part top surface
                pending = part

        if pick_z is None:
            return  # nothing to pick yet

        # ── Guard 3: optional external gate (e.g. H-Bot at home) ─────────────
        if self.pickup_gate is not None and not self.pickup_gate():
            return

        # Convert world targets to SCARA-local MCS (accounts for mounting rotation).
        # Clamp to reachable ring so targets slightly beyond arm reach move to
        # the nearest reachable point; the 60 mm suction radius covers the gap.
        self._pick_wx,  self._pick_wy  = self._clamp_local_to_reach(
            *self._world_to_local(pw_x, pw_y))
        self._pick_wz   = pick_z
        self._place_wx, self._place_wy = self._clamp_local_to_reach(
            *self._world_to_local(pl_x, pl_y))
        self._place_wz  = self._world_z_to_mcs(_WPM_PART_TOP)  # lower until suction contacts part top
        self._pending_wpm_part = pending

        self._auto_state = _A_MOVE_ABOVE_PICK
        self._auto_tick  = 0
        self._joint_mode = False

    # =========================================================================
    # HELPERS
    # =========================================================================
    def _next_auto_state(self):
        self._auto_state += 1
        self._auto_tick   = 0

    def _is_at_target(self) -> bool:
        """True when all ACS actual positions are within tolerance of their set-points."""
        angular = [self.robot_trafo.acsAxis1,
                   self.robot_trafo.acsAxis2,
                   self.robot_trafo.acsAxis4]
        linear  = [self.robot_trafo.acsAxis3]
        return (
            all(abs(a.ActualPosition - a.Sollposition) <= _ARRIVED_TOL_DEG for a in angular)
            and
            all(abs(a.ActualPosition - a.Sollposition) <= _ARRIVED_TOL_MM  for a in linear)
        )

    def _trigger_auto_fault(self, reason: str):
        self._fault = True
        self._auto_state = _A_IDLE
        self._auto_tick  = 0
        self._cancel_vacuum()
        print(f"Auto-Fault: {reason}")

    def _set_mcs_target(self, local_x, local_y, local_z):
        self._joint_mode = False
        self.robot_trafo.mcsAxisX.Sollposition = local_x
        self.robot_trafo.mcsAxisY.Sollposition = local_y
        self.robot_trafo.mcsAxisZ.Sollposition = local_z

    def _activate_vacuum(self):
        self._gripper_closed = True
        if hasattr(self.robot_view, "set_gripper"):
            self.robot_view.set_gripper(closed=True)
        if hasattr(self.robot_view, "attach_part"):
            self.robot_view.attach_part(True)

    def _cancel_vacuum(self):
        self._gripper_closed = False
        if hasattr(self.robot_view, "set_gripper"):
            self.robot_view.set_gripper(closed=False)
        if hasattr(self.robot_view, "attach_part"):
            self.robot_view.attach_part(False)

    def _tcp_rotation(self) -> float:
        """TCP world rotation in degrees (joint sum + mounting rotation)."""
        joint_sum = (self.robot_trafo.acsAxis1.ActualPosition +
                     self.robot_trafo.acsAxis2.ActualPosition +
                     self.robot_trafo.acsAxis4.ActualPosition)
        return joint_sum + getattr(self.robot_view, 'rotation_z', 0.0)

    def _world_to_local(self, wx: float, wy: float):
        """World XY → robot-local MCS XY, accounts for mounting rotation."""
        vp = self.robot_view.position
        dx = wx - vp[0]
        dy = wy - vp[1]
        rot = getattr(self.robot_view, 'rotation_z', 0.0)
        if abs(rot) < 0.01:
            return dx, dy
        r = -math.radians(rot)   # inverse of mounting rotation
        return (
            dx * math.cos(r) - dy * math.sin(r),
            dx * math.sin(r) + dy * math.cos(r),
        )

    def _local_to_world(self, lx: float, ly: float):
        """Robot-local MCS XY → world XY, accounts for mounting rotation."""
        vp = self.robot_view.position
        rot = getattr(self.robot_view, 'rotation_z', 0.0)
        if abs(rot) < 0.01:
            return vp[0] + lx, vp[1] + ly
        r = math.radians(rot)
        dx = lx * math.cos(r) - ly * math.sin(r)
        dy = lx * math.sin(r) + ly * math.cos(r)
        return vp[0] + dx, vp[1] + dy

    def _tcp_world_pos(self):
        """
        Return (wx, wy, wz) of the suction cup tip in world coordinates,
        computed from ACS ActualPositions (where the robot physically IS).
        """
        a1  = math.radians(self.robot_trafo.acsAxis1.ActualPosition)
        a2  = math.radians(self.robot_trafo.acsAxis2.ActualPosition)
        L1  = self.robot_trafo.L1
        L2  = self.robot_trafo.L2
        lx  = L1 * math.cos(a1) + L2 * math.cos(a1 + a2)
        ly  = L1 * math.sin(a1) + L2 * math.sin(a1 + a2)
        wx, wy = self._local_to_world(lx, ly)
        ref = getattr(self.robot_view, "tcp_z_ref", self.robot_view.position[2])
        return wx, wy, ref + self.robot_trafo.acsAxis3.ActualPosition

    def _world_z_to_mcs(self, world_z: float) -> float:
        """Convert an absolute world Z to the required mcsAxisZ (= acsAxis3) value."""
        ref = getattr(self.robot_view, "tcp_z_ref", self.robot_view.position[2])
        return world_z - ref

    def _clamp_local_to_reach(self, lx: float, ly: float):
        """Clamp a local MCS target to the reachable ring, preserving direction.
        Used when the world target is slightly beyond the arm's reach so the robot
        moves as close as possible and the suction radius covers the remaining gap."""
        L_max = self.robot_trafo.L1 + self.robot_trafo.L2
        L_min = abs(self.robot_trafo.L1 - self.robot_trafo.L2)
        d = math.sqrt(lx ** 2 + ly ** 2)
        if d == 0.0:
            return lx, ly
        if d > L_max:
            f = L_max / d
            return lx * f, ly * f
        if d < L_min:
            f = L_min / d
            return lx * f, ly * f
        return lx, ly

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
        # Rotate world-frame jog deltas into robot-local frame (accounts for mounting rotation)
        rot = getattr(self.robot_view, 'rotation_z', 0.0)
        if abs(rot) > 0.01:
            r = -math.radians(rot)
            dx, dy = (dx * math.cos(r) - dy * math.sin(r),
                      dx * math.sin(r) + dy * math.cos(r))
        if coord_system == "Welt":
            self.robot_trafo.jog_world(dx, dy, dz, dr)
        else:
            self.robot_trafo.jog_tool(dx, dy, dz, dr)
        return False

    def _jog_delta(self, hmi_ctrl, step):
        dx = (step if hmi_ctrl.MoveXPlus else 0.0) - (step if hmi_ctrl.MoveXNeg else 0.0)
        dy = (step if hmi_ctrl.MoveYPlus else 0.0) - (step if hmi_ctrl.MoveYNeg else 0.0)
        dz = (step if hmi_ctrl.MoveZPlus else 0.0) - (step if hmi_ctrl.MoveZNeg else 0.0)
        dr = (step if hmi_ctrl.MoveRPlus else 0.0) - (step if hmi_ctrl.MoveRNeg else 0.0)
        return dx, dy, dz, dr

    def _update_hmi_state(self):
        a1_act = self.robot_trafo.acsAxis1.ActualPosition
        a2_act = self.robot_trafo.acsAxis2.ActualPosition
        a3_act = self.robot_trafo.acsAxis3.ActualPosition
        a4_act = self.robot_trafo.acsAxis4.ActualPosition
        self.hmi_state.axisJ1Position = a1_act
        self.hmi_state.axisJ2Position = a2_act
        self.hmi_state.axisJ3Position = a3_act
        self.hmi_state.axisJ4Position = a4_act
        # Compute actual Cartesian from ACS actual positions (not Sollposition-derived)
        r1 = math.radians(a1_act)
        r2 = math.radians(a2_act)
        L1 = self.robot_trafo.L1
        L2 = self.robot_trafo.L2
        self.hmi_state.axisXPosition = L1 * math.cos(r1) + L2 * math.cos(r1 + r2)
        self.hmi_state.axisYPosition = L1 * math.sin(r1) + L2 * math.sin(r1 + r2)
        self.hmi_state.axisZPosition = a3_act
        self.hmi_state.axisRPosition = a1_act + a2_act + a4_act
