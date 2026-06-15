"""
Modul zur 3D-Visualisierung und kinematischen Steuerung eines Roboterarms.

Dieses Modul nutzt pyvista und vtk, um die STL-Modelle eines SCARA-Roboters
zu laden, grafisch darzustellen und durch Vorwärtskinematik zu animieren.

Neu:
- position=(x, y, z), damit mehrere Roboter im gleichen Fenster stehen können
- Vakuumsauger (Saugnapf) anstelle eines Parallelgreifers
- Sauger fährt und rotiert mit der Spindel mit
"""

import sys
sys.path.append('../View')

import os
import pyvista as pv
import vtk


class Scara:
    """
    Lädt die 3D-Modelle des Roboters und stellt eine interaktive Umgebung bereit.

    Args:
        data_folder_path (str, optional): Pfad zum STL-Ordner.
        pl (pyvista.Plotter, optional): Gemeinsames PyVista-Fenster.
        position (tuple): Verschiebung des ganzen Roboters, z.B. (0, 800, 0)
    """

    def __init__(self, data_folder_path=None, pl=None, position=(0, 0, 0)):
        """
        Initialisiert den SCARA-Roboter.
        """

        # --------------------------------------------------------
        # 1. Position / Offset des ganzen Roboters
        # --------------------------------------------------------
        self.position = position

        # --------------------------------------------------------
        # 2. Pfade konfigurieren
        # --------------------------------------------------------
        if data_folder_path is None:
            cwd = os.getcwd()
            data_folder_path = os.path.join(cwd, "View", "Scara_Modell")
            
        base_file = os.path.join(data_folder_path, "Base.stl")
        inner_arm_file = os.path.join(data_folder_path, "InnerArm.stl")
        outer_arm_file = os.path.join(data_folder_path, "OuterArm.stl")
        spindle_file = os.path.join(data_folder_path, "Spindle.stl")

        # --------------------------------------------------------
        # 3. Modelle einlesen
        # --------------------------------------------------------
        base_mesh = pv.read(base_file)
        inner_arm_mesh = pv.read(inner_arm_file)
        outer_arm_mesh = pv.read(outer_arm_file)
        spindle_mesh = pv.read(spindle_file)

        # --------------------------------------------------------
        # 4. Ganzen Roboter verschieben
        # Wichtig:
        # Meshes UND Drehpunkte werden verschoben.
        # --------------------------------------------------------
        base_mesh.translate(self.position, inplace=True)
        inner_arm_mesh.translate(self.position, inplace=True)
        outer_arm_mesh.translate(self.position, inplace=True)
        spindle_mesh.translate(self.position, inplace=True)

        # Spindel-Mesh speichern, damit der Sauger am unteren Ende gebaut werden kann
        self.spindle_mesh = spindle_mesh

        # --------------------------------------------------------
        # 5. Plotter verwenden oder eigenen erstellen
        # --------------------------------------------------------
        if pl is None:
            self.pl = pv.Plotter()
        else:
            self.pl = pl

        # --------------------------------------------------------
        # 6. Meshes in die Szene einfügen
        # --------------------------------------------------------
        self.base_actor = self.pl.add_mesh(base_mesh, color="lightblue")
        self.inner_arm_actor = self.pl.add_mesh(inner_arm_mesh, color="orange")
        self.outer_arm_actor = self.pl.add_mesh(outer_arm_mesh, color="green")
        self.spindle_actor = self.pl.add_mesh(spindle_mesh, color="gray")

        # --------------------------------------------------------
        # 7. Original-Drehpunkte aus CAD
        # --------------------------------------------------------
        original_origin_inner = (0.0, 0.0, 0.0)
        original_origin_outer = (-325.0, 0.0, 0.0)
        original_origin_spindle = (-550.0, 0.0, 0.0)

        # --------------------------------------------------------
        # 8. Drehpunkte ebenfalls verschieben
        # --------------------------------------------------------
        self.origin_inner = (
            original_origin_inner[0] + self.position[0],
            original_origin_inner[1] + self.position[1],
            original_origin_inner[2] + self.position[2]
        )

        self.origin_outer = (
            original_origin_outer[0] + self.position[0],
            original_origin_outer[1] + self.position[1],
            original_origin_outer[2] + self.position[2]
        )

        self.origin_spindle = (
            original_origin_spindle[0] + self.position[0],
            original_origin_spindle[1] + self.position[1],
            original_origin_spindle[2] + self.position[2]
        )

        # PyVista Origins setzen
        self.inner_arm_actor.origin = self.origin_inner
        self.outer_arm_actor.origin = self.origin_outer
        self.spindle_actor.origin = self.origin_spindle

        # --------------------------------------------------------
        # 9. Sauger hinzufügen
        # --------------------------------------------------------
        self._add_suction_cup()

        # Initiale Transformation setzen, aber noch NICHT rendern
        self.update_joints(0, 0, 0, render=False)

        # --------------------------------------------------------
        # 10. Kamera einstellen
        # --------------------------------------------------------
        self.pl.camera_position = [
            (200.0, -1800.0, 1000.0),
            (0.0, 400.0, 0.0),
            (0.0, 0.0, 1.0)
        ]

    # ============================================================
    # VAKUUM-SAUGER
    # ============================================================
    def _add_suction_cup(self):
        """
        Erstellt einen Vakuumsauger am unteren Ende der Spindel.
        """
        b = self.spindle_mesh.bounds

        # Mitte der Spindel
        cx = (b[0] + b[1]) / 2.0
        cy = (b[2] + b[3]) / 2.0

        # Unterstes Ende der Spindel
        tip_z = b[4]

        tx = cx
        ty = cy
        tz = tip_z

        # World-Z of suction cup tip when acsAxis3 = 0 (used by RobotController for Z targeting)
        self.tcp_z_ref = tz

        # Halterung (kleiner Zylinder, der aus der Spindel kommt)
        mount = pv.Cylinder(
            center=(tx, ty, tz - 10),
            direction=(0, 0, 1),
            radius=6,
            height=20
        )

        # Saugnapf (Kegel / Cone)
        cup = pv.Cone(
            center=(tx, ty, tz - 22.5),
            direction=(0, 0, -1),
            height=5,
            radius=15
        )

        # Actors hinzufügen
        self.suction_mount_actor = self.pl.add_mesh(
            mount,
            color="dimgray"
        )

        self.suction_cup_actor = self.pl.add_mesh(
            cup,
            color="red"
        )

        # Workpiece actor — hidden until suction is active
        # Das Dummy-Rohteil wird direkt unter den Sauger platziert
        part_mesh = pv.Box(bounds=(
            tx - 40, tx + 40,
            ty - 30, ty + 30,
            tz - 45, tz - 25,
        ))
        self._part_actor = self.pl.add_mesh(part_mesh, color="saddlebrown")
        self._part_actor.SetVisibility(False)

    def attach_part(self, visible: bool):
        """Zeigt oder versteckt das simulierte Bauteil am Sauger."""
        self._part_actor.SetVisibility(visible)

    def set_gripper(self, closed=False):
        """
        Schaltet das Vakuum ein oder aus (Name 'set_gripper' für Kompatibilität mit HMI).

        closed=False -> Vakuum aus (Rot)
        closed=True  -> Vakuum an (Grün)
        """
        if closed:
            self.suction_cup_actor.GetProperty().SetColor(pv.Color("limegreen").float_rgb)
        else:
            self.suction_cup_actor.GetProperty().SetColor(pv.Color("red").float_rgb)

    # ============================================================
    # ANZEIGE
    # ============================================================
    def show(self):
        """
        Öffnet das 3D-Fenster.
        """
        self.pl.show(interactive_update=True, auto_close=False)

    def update_joints(self, inner_angle=0, outer_angle=0, spindle_angle=0, z_height=0.0, render=True):
        """
        Aktualisiert die Gelenkwinkel.
        """
        ix, iy, iz = self.origin_inner
        ox, oy, oz = self.origin_outer
        sx, sy, sz = self.origin_spindle

        # Joint1Frame: innerer Arm dreht um Gelenk 1
        t_j1 = vtk.vtkTransform()
        t_j1.PostMultiply()
        t_j1.Translate(-ix, -iy, -iz)
        t_j1.RotateZ(inner_angle)
        t_j1.Translate(ix, iy, iz)
        self.inner_arm_actor.SetUserTransform(t_j1)

        # Joint2Frame: äußerer Arm dreht lokal um Gelenk 2, folgt Gelenk 1
        t_j2 = vtk.vtkTransform()
        t_j2.PostMultiply()
        t_j2.Translate(-ox, -oy, -oz)
        t_j2.RotateZ(outer_angle)
        t_j2.Translate(ox, oy, oz)
        t_j2.Translate(-ix, -iy, -iz)
        t_j2.RotateZ(inner_angle)
        t_j2.Translate(ix, iy, iz)
        self.outer_arm_actor.SetUserTransform(t_j2)

        # ToolFrame (TCP): Spindel dreht lokal, folgt J2 und J1, Z-Bewegung zuletzt
        t_tcp = vtk.vtkTransform()
        t_tcp.PostMultiply()
        t_tcp.Translate(-sx, -sy, -sz)
        t_tcp.RotateZ(spindle_angle)
        t_tcp.Translate(sx, sy, sz)
        t_tcp.Translate(-ox, -oy, -oz)
        t_tcp.RotateZ(outer_angle)
        t_tcp.Translate(ox, oy, oz)
        t_tcp.Translate(-ix, -iy, -iz)
        t_tcp.RotateZ(inner_angle)
        t_tcp.Translate(ix, iy, iz)
        t_tcp.Translate(0.0, 0.0, z_height)
        self.spindle_actor.SetUserTransform(t_tcp)

        # --------------------------------------------------------
        # Sauger folgt TCP-Frame
        # --------------------------------------------------------
        self.suction_mount_actor.SetUserTransform(t_tcp)
        self.suction_cup_actor.SetUserTransform(t_tcp)
        self._part_actor.SetUserTransform(t_tcp)

        # --------------------------------------------------------
        # Fenster aktualisieren
        # --------------------------------------------------------
        if render:
            try:
                self.pl.update()
            except RuntimeError:
                pass

    def close(self):
        """
        Schliesst das PyVista-Fenster.
        """
        self.pl.close()


# ================================================================
# TEST
# ================================================================
if __name__ == "__main__":
    import time

    plotter = pv.Plotter()

    # Roboter 1
    robot1 = Scara(
        pl=plotter,
        position=(0, 0, 0)
    )

    # Roboter 2 daneben
    robot2 = Scara(
        pl=plotter,
        position=(0, 800, 0)
    )

    plotter.show_axes()

    plotter.show(
        interactive_update=True,
        auto_close=False
    )

    print("Starte Bewegungstest...")

    for i in range(500):
        robot1.update_joints(
            inner_angle=i,
            outer_angle=-i * 0.5,
            spindle_angle=i * 2
        )

        robot2.update_joints(
            inner_angle=i + 80,
            outer_angle=-i * 0.5 + 60,
            spindle_angle=i * 2
        )

        # Test: Vakuum abwechselnd ein-/ausschalten
        if i % 100 < 50:
            robot1.set_gripper(closed=False)
            robot2.set_gripper(closed=True)
            robot1.attach_part(False)
            robot2.attach_part(True)
        else:
            robot1.set_gripper(closed=True)
            robot2.set_gripper(closed=False)
            robot1.attach_part(True)
            robot2.attach_part(False)

        time.sleep(0.05)

    print("Test beendet.")