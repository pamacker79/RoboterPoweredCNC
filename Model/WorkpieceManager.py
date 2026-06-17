"""
Module: WorkpieceManager
Purpose: Central registry for all free workpieces in the 3D scene.
Responsibilities: Track part world positions, provide nearest-part queries for
                  suction range checks and robot handshake polling.
Inputs:  add_part / remove_part calls from RobotController and H-Bot logic.
Outputs: has_part_at / pick_nearest queries consumed by auto sequences and manual suction.
Dependencies: pyvista
"""

import math
import pyvista as pv


class WorkpieceManager:
    """Manages all workpieces that are not inside the magazine and not carried by a robot."""

    _PART_SIZE = (100, 50, 25)  # (dx, dy, dz) in mm — matches View/Magazin_Modell/Roh_Teil.stl

    def __init__(self):
        self._parts = []   # list of dicts: {id, wx, wy, actor, plotter}
        self._next_id = 0

    # ------------------------------------------------------------------
    # Add / remove
    # ------------------------------------------------------------------
    def get_stack_top(self, world_x: float, world_y: float, radius: float = 60.0) -> float:
        """Return the Z of the top surface of the highest part within radius, or 0.0."""
        top = 0.0
        for p in self._parts:
            d = math.sqrt((p["wx"] - world_x) ** 2 + (p["wy"] - world_y) ** 2)
            if d <= radius:
                top = max(top, p["top_z"])
        return top

    def get_place_z(self, world_x: float, world_y: float, radius: float = 60.0) -> float:
        """World Z the robot TCP must reach to place the next part onto the stack."""
        return self.get_stack_top(world_x, world_y, radius) + self._PART_SIZE[2]

    def add_part(self, plotter, world_x: float, world_y: float,
                rotation_z: float = 0.0) -> int:
        """
        Place a part at (world_x, world_y) stacked on top of any existing parts.
        rotation_z is the TCP world rotation in degrees at the moment of release.
        Returns the part id.
        """
        dx, dy, dz = self._PART_SIZE
        bottom_z = self.get_stack_top(world_x, world_y)
        # Build centred at origin so rotate_z spins around the part's own centre
        mesh = pv.Box(bounds=(-dx / 2, dx / 2, -dy / 2, dy / 2, bottom_z, bottom_z + dz))
        if abs(rotation_z) > 0.01:
            mesh.rotate_z(rotation_z, inplace=True)
        mesh.translate((world_x, world_y, 0.0), inplace=True)
        actor = plotter.add_mesh(mesh, color="saddlebrown")
        part_id = self._next_id
        self._next_id += 1
        self._parts.append({
            "id":      part_id,
            "wx":      world_x,
            "wy":      world_y,
            "rz":      rotation_z,
            "top_z":   bottom_z + dz,
            "actor":   actor,
            "plotter": plotter,
        })
        return part_id

    def remove_part(self, part_id: int) -> bool:
        """Hide and unregister the part with the given id. Returns True if found."""
        for i, p in enumerate(self._parts):
            if p["id"] == part_id:
                p["actor"].SetVisibility(False)
                self._parts.pop(i)
                return True
        return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def has_part_at(self, world_x: float, world_y: float, radius: float = 60.0) -> bool:
        """Return True if any free part is within `radius` mm of (world_x, world_y)."""
        return self._find_nearest(world_x, world_y, radius) is not None

    def pick_nearest(self, world_x: float, world_y: float, radius: float = 60.0):
        """
        Return the nearest part dict within `radius` mm, or None.
        Does NOT remove the part — call remove_part(id) after a successful pick.
        """
        return self._find_nearest(world_x, world_y, radius)

    def get_all_positions(self) -> list:
        """Return list of (wx, wy) for all tracked parts."""
        return [(p["wx"], p["wy"]) for p in self._parts]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _find_nearest(self, wx, wy, radius):
        best = None
        best_dist = float("inf")
        for p in self._parts:
            d = math.sqrt((p["wx"] - wx) ** 2 + (p["wy"] - wy) ** 2)
            if d <= radius and d < best_dist:
                best_dist = d
                best = p
        return best
