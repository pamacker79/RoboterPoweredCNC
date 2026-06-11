"""
Module: View.MagazinViewPV
Purpose: 3D visualization of the raw-part stack magazine in the shared PyVista scene.
Responsibilities: Load magazine STL meshes, stack part actors at correct Z positions,
                  expose update_part_count() and update_schieber() for runtime animation,
                  provide coordinates for robot pickup.
Inputs:  part_count and schieber hub from Machine control loop.
Outputs: Updated PyVista actor visibility and positions each frame.
Dependencies: pyvista, View/Magazin_Modell/*.stl
"""

import os
import pyvista as pv


class MagazinViewPV:
    """PyVista-based magazine view compatible with the shared 3D plotter."""

    CAPACITY = 6  # maximum parts that fit in the magazine

    def __init__(self, pl, position=(0, 0, 0)):
        self.pl = pl
        self.position = position

        cwd = os.getcwd()
        modell_dir = os.path.join(cwd, "View", "Magazin_Modell")

        mag_path       = os.path.join(modell_dir, "Magazin_V2.stl")
        schieber_path  = os.path.join(modell_dir, "Magazin_Schieber.stl")
        rohteil_path   = os.path.join(modell_dir, "Roh_Teil.stl")

        # --------------------------------------------------------
        # Magazine body
        # --------------------------------------------------------
        mag_mesh = pv.read(mag_path)
        # Compute interior geometry before translating
        mb = mag_mesh.bounds          # (xmin,xmax, ymin,ymax, zmin,zmax)
        mag_cx = (mb[0] + mb[1]) / 2.0
        mag_cy = (mb[2] + mb[3]) / 2.0
        boden_z = mb[4] + 1.0        # 1 mm clearance above floor

        mag_mesh.translate(position, inplace=True)
        self._magazin_actor = pl.add_mesh(mag_mesh, color="lightgray", opacity=0.45)

        # --------------------------------------------------------
        # Ejector schieber
        # --------------------------------------------------------
        schieber_mesh = pv.read(schieber_path)
        schieber_mesh.translate(position, inplace=True)
        self._schieber_actor = pl.add_mesh(schieber_mesh, color="darkorange")
        self._schieber_hub = 0.0

        # --------------------------------------------------------
        # Stacked raw parts (up to CAPACITY)
        # --------------------------------------------------------
        rohteil_template = pv.read(rohteil_path)
        rb = rohteil_template.bounds
        part_height = rb[5] - rb[4]
        rt_cx = (rb[0] + rb[1]) / 2.0
        rt_cy = (rb[2] + rb[3]) / 2.0

        dx = mag_cx - rt_cx
        dy = mag_cy - rt_cy

        self._part_actors = []
        for i in range(self.CAPACITY):
            part = rohteil_template.copy()
            dz = boden_z - rb[4] + i * part_height
            part.translate(
                (dx + position[0], dy + position[1], dz + position[2]),
                inplace=True
            )
            actor = pl.add_mesh(part, color="steelblue")
            self._part_actors.append(actor)

        self._part_count = self.CAPACITY

    def update_part_count(self, count: int):
        """Show the bottom `count` parts; hide the rest."""
        self._part_count = max(0, min(count, self.CAPACITY))
        for i, actor in enumerate(self._part_actors):
            actor.SetVisibility(i < self._part_count)

    def update_schieber(self, hub: float):
        """Translate the ejector slide by `hub` mm in -X direction."""
        self._schieber_hub = hub
        self._schieber_actor.position = [-hub, 0.0, 0.0]

    def get_pickup_coordinates(self):
        """
        Gibt die (X, Y, Z)-Weltkoordinaten des aktuell obersten Bauteils zurück.
        Wenn das Magazin leer ist, wird None zurückgegeben.
        """
        if self._part_count == 0:
            return None
        
        # Der Index des obersten sichtbaren Bauteils
        top_index = self._part_count - 1
        
        # Den Aktor des obersten Bauteils holen
        top_actor = self._part_actors[top_index]
        
        # Die Bounds [xmin, xmax, ymin, ymax, zmin, zmax] des Bauteils abfragen
        b = top_actor.bounds
        
        # Mitte des Bauteils auf X und Y berechnen
        cx = (b[0] + b[1]) / 2.0
        cy = (b[2] + b[3]) / 2.0
        
        # Z-Koordinate (Absolute Oberkante des Bauteils in der 3D-Welt)
        top_z = b[5]
        
        return (cx, cy, top_z)

    def pick_top_part(self):
        """
        Simuliert die Entnahme des obersten Bauteils durch den Roboter.
        Blendet das Teil aus und reduziert den Füllstand um 1.
        Gibt True zurück, wenn erfolgreich entnommen, False wenn das Magazin leer ist.
        """
        if self._part_count > 0:
            self._part_count -= 1
            # Sichtbarkeit aktualisieren (das oberste verschwindet)
            self.update_part_count(self._part_count)
            return True
        return False