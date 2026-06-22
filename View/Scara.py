"""
Modul: View.Scara
==================
3D-Visualisierung und kinematische Animation eines SCARA-Roboterarms.

Aufbau der 3D-Szene
--------------------
Jeder SCARA-Roboter besteht aus vier STL-Teilen plus einem dynamisch
erzeugten Vakuumsauger:

* **Base.stl**      – Sockelprofil (ortsfest)
* **InnerArm.stl**  – Oberarm (dreht um Schultergelenk J1)
* **OuterArm.stl**  – Unterarm (dreht um Ellbogengelenk J2, folgt J1)
* **Spindle.stl**   – Hubspindel + Werkzeugdrehachse J4 (dreht und hebt)
* Vakuumsauger      – Halterung + Saugnapf aus PyVista-Primitiven

Kinematische Transformationskette
----------------------------------
Die Transformationen werden mit ``vtk.vtkTransform`` verkettigt:

* J1-Frame: Rotation um Schultergelenk (+ Montagedrehung ``rotation_z``)
* J2-Frame: Rotation um Ellbogengelenk, danach J1-Frame anwenden
* TCP-Frame: J4-Rotation, dann J2-Frame, dann J1-Frame, dann Z-Hub

Diese Reihenfolge entspricht der Vorwärtskinematik im Modell (Scara.py)
und stellt sicher, dass sich jedes Segment korrekt gegenüber seinem
Vorgänger bewegt.

Montagedrehung (rotation_z)
----------------------------
Da die STL-Modelle in Nullstellung in -X zeigen, die Kinematik jedoch
+X als Referenz nimmt, wird ``rotation_z=180°`` verwendet, um die Basis
korrekt auszurichten.  Für Roboter 3 (spiegelverkehrt montiert) kann ein
separater ``base_rotation_z`` für das Gehäuse gesetzt werden.

TCP-Referenz (tcp_z_ref)
-------------------------
``tcp_z_ref`` ist die Z-Weltkoordinate der Saugnapf-Spitze bei
``acsAxis3 = 0`` (Spindel vollständig oben).  Der RobotController nutzt
diesen Wert, um die Solltauchtiefe korrekt aus der Weltkoordinate des
Bauteils zu berechnen.

Abhängigkeiten
--------------
* ``pyvista`` — 3D-Visualisierungsbibliothek
* ``vtk``     — Transformationsverkettung mit vtkTransform
* ``View/Scara_Modell/*.stl`` — STL-Arm-Dateien
"""

import sys
sys.path.append('../View')

import os
import pyvista as pv
import vtk


class Scara:
    """
    Lädt die SCARA-STL-Modelle und animiert sie im gemeinsamen PyVista-Fenster.

    Parameter
    ---------
    data_folder_path : str oder None
        Pfad zum STL-Ordner.  Bei None wird ``./View/Scara_Modell`` verwendet.
    pl : pyvista.Plotter oder None
        Gemeinsames PyVista-Fenster.  Bei None wird ein eigenes erstellt.
    position : tuple(float, float, float)
        Weltposition der Roboterbasis [mm].  Alle Gelenk-Drehpunkte werden
        um diesen Offset verschoben.
    rotation_z : float
        Kinematische Montagedrehung [Grad].  Dreht den gesamten Arm inkl.
        Arbeitsbereichsausrichtung.  Typischerweise 180° für beide SCARA-Roboter
        (STL-Nulllage zeigt in -X, Kinematik erwartet +X).
    base_rotation_z : float oder None
        Rein visuelle Drehung des Basisgehäuses.  Wenn None, wird
        ``rotation_z`` verwendet.  Nützlich wenn Gehäuse und Arm
        unterschiedlich ausgerichtet sein sollen (Roboter 3).
    """

    def __init__(self, data_folder_path=None, pl=None, position=(0, 0, 0),
                 rotation_z=0.0, base_rotation_z=None):
        """Lädt STL-Modelle, erstellt Aktoren und setzt die Ausgangsstellung."""
        self.position = position
        self.rotation_z = rotation_z
        self._base_rotation_z = base_rotation_z if base_rotation_z is not None else rotation_z

        # ── STL-Pfade ─────────────────────────────────────────────────────────
        if data_folder_path is None:
            cwd = os.getcwd()
            data_folder_path = os.path.join(cwd, "View", "Scara_Modell")

        base_file       = os.path.join(data_folder_path, "Base.stl")
        inner_arm_file  = os.path.join(data_folder_path, "InnerArm.stl")
        outer_arm_file  = os.path.join(data_folder_path, "OuterArm.stl")
        spindle_file    = os.path.join(data_folder_path, "Spindle.stl")

        # ── Meshes einlesen und auf Roboterposition verschieben ───────────────
        base_mesh      = pv.read(base_file)
        inner_arm_mesh = pv.read(inner_arm_file)
        outer_arm_mesh = pv.read(outer_arm_file)
        spindle_mesh   = pv.read(spindle_file)

        for mesh in (base_mesh, inner_arm_mesh, outer_arm_mesh, spindle_mesh):
            mesh.translate(self.position, inplace=True)

        self.spindle_mesh = spindle_mesh  # Referenz für Saugnapf-Erzeugung

        # ── Plotter ───────────────────────────────────────────────────────────
        if pl is None:
            self.pl = pv.Plotter()
        else:
            self.pl = pl

        # ── Visuelle Basisgehäuse-Drehung (unabhängig von Arm-Kinematik) ──────
        if abs(self._base_rotation_z) > 0.01:
            rx, ry, rz = self.position
            base_mesh.rotate_z(self._base_rotation_z, point=(rx, ry, rz), inplace=True)

        # ── Aktoren einfügen ──────────────────────────────────────────────────
        self.base_actor      = self.pl.add_mesh(base_mesh,      color="lightblue")
        self.inner_arm_actor = self.pl.add_mesh(inner_arm_mesh, color="orange")
        self.outer_arm_actor = self.pl.add_mesh(outer_arm_mesh, color="green")
        self.spindle_actor   = self.pl.add_mesh(spindle_mesh,   color="gray")

        # ── Gelenk-Drehpunkte aus CAD-Koordinaten (verschoben um position) ────
        # CAD-Ursprünge vor dem Verschieben:
        #   J1 = (0, 0, 0), J2 = (-325, 0, 0), Spindel = (-550, 0, 0)
        px, py, pz = self.position
        self.origin_inner   = (    0.0 + px,  0.0 + py, 0.0 + pz)  # Schultergelenk
        self.origin_outer   = (-325.0 + px,  0.0 + py, 0.0 + pz)  # Ellbogengelenk
        self.origin_spindle = (-550.0 + px,  0.0 + py, 0.0 + pz)  # TCP-Drehpunkt

        self.inner_arm_actor.origin = self.origin_inner
        self.outer_arm_actor.origin = self.origin_outer
        self.spindle_actor.origin   = self.origin_spindle

        # ── Vakuumsauger erzeugen ─────────────────────────────────────────────
        self._add_suction_cup()

        # Ausgangsstellung (noch kein render, Fenster noch nicht offen)
        self.update_joints(0, 0, 0, render=False)

        # ── Kameraposition ────────────────────────────────────────────────────
        self.pl.camera_position = [
            (200.0, -1800.0, 1000.0),
            (  0.0,   400.0,    0.0),
            (  0.0,     0.0,    1.0),
        ]

    # ------------------------------------------------------------------
    # Vakuumsauger
    # ------------------------------------------------------------------

    def _add_suction_cup(self):
        """
        Erzeugt den Vakuumsauger am unteren Ende der Spindel.

        Besteht aus:
        * Halterungszylinder (``suction_mount_actor``)
        * Saugnapf-Kegel    (``suction_cup_actor``)
        * Bauteil-Dummy     (``_part_actor`` — unsichtbar bis Vakuum aktiv)

        Setzt ``tcp_z_ref``: die Z-Weltkoordinate der Saugnapf-Spitze
        bei ``acsAxis3 = 0`` (wird von ``RobotController._world_z_to_mcs()``
        genutzt).
        """
        b   = self.spindle_mesh.bounds
        cx  = (b[0] + b[1]) / 2.0
        cy  = (b[2] + b[3]) / 2.0
        tz  = b[4]   # unteres Ende der Spindel in der Ausgangsstellung

        # Saugnapf-Spitze liegt 25 mm unter der Spindelunterkante
        self.tcp_z_ref = tz - 25

        # Halterung: Zylinder von tz-20 bis tz
        mount = pv.Cylinder(
            center=(cx, cy, tz - 10),
            direction=(0, 0, 1),
            radius=6,
            height=20,
        )

        # Saugnapf: Kegel mit Spitze bei tz-25
        cup = pv.Cone(
            center=(cx, cy, tz - 22.5),
            direction=(0, 0, -1),
            height=5,
            radius=15,
        )

        self.suction_mount_actor = self.pl.add_mesh(mount, color="dimgray")
        self.suction_cup_actor   = self.pl.add_mesh(cup,   color="red")

        # Bauteil-Dummy: unsichtbarer Block unter dem Sauger
        part_mesh = pv.Box(bounds=(
            cx - 50, cx + 50,
            cy - 25, cy + 25,
            tz - 50, tz - 25,
        ))
        self._part_actor = self.pl.add_mesh(part_mesh, color="saddlebrown")
        self._part_actor.SetVisibility(False)

    def attach_part(self, visible: bool):
        """
        Blendet das simulierte Bauteil am Sauger ein oder aus.

        Parameter
        ---------
        visible : bool
            True = Teil wird am Sauger angezeigt (Vakuum aktiv).
            False = Teil versteckt (Sauger leer).
        """
        self._part_actor.SetVisibility(visible)

    def set_gripper(self, closed: bool = False):
        """
        Schaltet die Vakuumanzeige ein oder aus.

        ``closed=True``  → Saugnapf grün (Vakuum aktiv).
        ``closed=False`` → Saugnapf rot  (Vakuum inaktiv).

        Parameter
        ---------
        closed : bool
            True = Vakuum ein, False = Vakuum aus.
        """
        if closed:
            self.suction_cup_actor.GetProperty().SetColor(pv.Color("limegreen").float_rgb)
        else:
            self.suction_cup_actor.GetProperty().SetColor(pv.Color("red").float_rgb)

    # ------------------------------------------------------------------
    # Anzeige / Hauptmethoden
    # ------------------------------------------------------------------

    def show(self):
        """Öffnet das 3D-Fenster (nur für Standalone-Tests)."""
        self.pl.show(interactive_update=True, auto_close=False)

    def update_joints(self, inner_angle: float = 0, outer_angle: float = 0,
                      spindle_angle: float = 0, z_height: float = 0.0,
                      render: bool = True):
        """
        Aktualisiert alle Gelenk-Transformationen der SCARA-Armsegmente.

        Die Winkel entsprechen den ACS-Istwerten aus ``RobotController.update_view()``.
        Der ``inner_angle`` wird um ``rotation_z`` korrigiert, damit der Arm
        in der 3D-Szene korrekt ausgerichtet ist.

        Transformationskette (PostMultiply = links-nach-rechts):
        1. J1-Frame: Schultergelenk + Montagedrehung
        2. J2-Frame: Ellbogengelenk, dann J1 folgen
        3. TCP-Frame: J4-Rotation, dann J2, dann J1, dann Z-Hub

        Alle Sauger-Aktoren (Halterung, Napf, Bauteil) folgen dem TCP-Frame.

        Parameter
        ---------
        inner_angle : float
            acsAxis1 (Schulter) + 180° Offset [Grad].
        outer_angle : float
            acsAxis2 (Ellbogen) [Grad].
        spindle_angle : float
            acsAxis4 (Werkzeugdrehung) [Grad].
        z_height : float
            acsAxis3 (Hub), negativ = abgesenkt [mm].
        render : bool
            Bei True wird ``pl.update()`` aufgerufen.
        """
        ix, iy, iz = self.origin_inner
        ox, oy, oz = self.origin_outer
        sx, sy, sz = self.origin_spindle

        base_angle = inner_angle + self.rotation_z  # Arm-Richtung inklusive Montage

        # J1-Frame: Schultergelenk-Drehung
        t_j1 = vtk.vtkTransform()
        t_j1.PostMultiply()
        t_j1.Translate(-ix, -iy, -iz)
        t_j1.RotateZ(base_angle)
        t_j1.Translate(ix, iy, iz)
        self.inner_arm_actor.SetUserTransform(t_j1)

        # J2-Frame: Ellbogengelenk, dann J1 folgen
        t_j2 = vtk.vtkTransform()
        t_j2.PostMultiply()
        t_j2.Translate(-ox, -oy, -oz)
        t_j2.RotateZ(outer_angle)
        t_j2.Translate(ox, oy, oz)
        t_j2.Translate(-ix, -iy, -iz)
        t_j2.RotateZ(base_angle)
        t_j2.Translate(ix, iy, iz)
        self.outer_arm_actor.SetUserTransform(t_j2)

        # TCP-Frame: J4 + J2 + J1 + Z-Hub
        t_tcp = vtk.vtkTransform()
        t_tcp.PostMultiply()
        t_tcp.Translate(-sx, -sy, -sz)
        t_tcp.RotateZ(spindle_angle)
        t_tcp.Translate(sx, sy, sz)
        t_tcp.Translate(-ox, -oy, -oz)
        t_tcp.RotateZ(outer_angle)
        t_tcp.Translate(ox, oy, oz)
        t_tcp.Translate(-ix, -iy, -iz)
        t_tcp.RotateZ(base_angle)
        t_tcp.Translate(ix, iy, iz)
        t_tcp.Translate(0.0, 0.0, z_height)
        self.spindle_actor.SetUserTransform(t_tcp)

        # Sauger folgt dem TCP-Frame
        self.suction_mount_actor.SetUserTransform(t_tcp)
        self.suction_cup_actor.SetUserTransform(t_tcp)
        self._part_actor.SetUserTransform(t_tcp)

        if render:
            try:
                self.pl.update()
            except RuntimeError:
                pass

    def close(self):
        """Schliesst das PyVista-Fenster."""
        self.pl.close()


# ================================================================
# Standalone-Test (python View/Scara.py)
# ================================================================
if __name__ == "__main__":
    import time

    plotter = pv.Plotter()
    robot1  = Scara(pl=plotter, position=(0,   0, 0))
    robot2  = Scara(pl=plotter, position=(0, 800, 0))
    plotter.show_axes()
    plotter.show(interactive_update=True, auto_close=False)

    print("Starte Bewegungstest...")
    for i in range(500):
        robot1.update_joints(inner_angle=i,      outer_angle=-i * 0.5, spindle_angle=i * 2)
        robot2.update_joints(inner_angle=i + 80, outer_angle=-i * 0.5 + 60, spindle_angle=i * 2)
        if i % 100 < 50:
            robot1.set_gripper(closed=False); robot2.set_gripper(closed=True)
            robot1.attach_part(False);        robot2.attach_part(True)
        else:
            robot1.set_gripper(closed=True);  robot2.set_gripper(closed=False)
            robot1.attach_part(True);         robot2.attach_part(False)
        time.sleep(0.05)

    print("Test beendet.")
