"""
Modul zur 3D-Visualisierung und kinematischen Steuerung eines Roboterarms.

Dieses Modul nutzt pyvista und vtk, um die STL-Modelle eines SCARA-Roboters
zu laden, grafisch darzustellen und durch Vorwärtskinematik zu animieren.

Neu:
- position=(x, y, z), damit mehrere Roboter im gleichen Fenster stehen können
- sichtbarer Greifer am Ende der Spindel
- Greifer fährt und rotiert mit der Spindel mit
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

        # Spindel-Mesh speichern, damit der Greifer am unteren Ende gebaut werden kann
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
        # 9. Greifer hinzufügen
        # --------------------------------------------------------
        self.gripper_half_width = 20.0
        self._add_gripper()

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
    # GREIFER
    # ============================================================
    def _add_gripper(self):
        """
        Erstellt einen einfachen Parallelgreifer am unteren Ende der Spindel.

        Der Greifer besteht aus:
        - Halterung
        - linker Finger
        - rechter Finger

        Wichtig:
        Die Finger werden zuerst mittig erstellt.
        Der Abstand links/rechts wird später in update_joints über eine zusätzliche
        lokale Verschiebung gemacht.
        """

        b = self.spindle_mesh.bounds

        # Mitte der Spindel
        cx = (b[0] + b[1]) / 2.0
        cy = (b[2] + b[3]) / 2.0

        # Unterstes Ende der Spindel
        tip_z = b[4]

        # Feinabgleich, falls Greifer nicht genau sitzt
        self.gripper_offset = (0.0, 0.0, 0.0)
        ox, oy, oz = self.gripper_offset

        tx = cx + ox
        ty = cy + oy
        tz = tip_z + oz

        # Greifer-Masse
        finger_len = 60.0

        # Halterung
        mount = pv.Cube(
            center=(tx, ty, tz + 10),
            x_length=40,
            y_length=70,
            z_length=20
        )

        # Finger-Grundkörper
        finger = pv.Cube(
            center=(tx, ty, tz - finger_len / 2.0),
            x_length=14,
            y_length=14,
            z_length=finger_len
        )

        # Actors hinzufügen
        self.gripper_mount_actor = self.pl.add_mesh(
            mount,
            color="dimgray"
        )

        self.gripper_finger_l_actor = self.pl.add_mesh(
            finger.copy(),
            color="red"
        )

        self.gripper_finger_r_actor = self.pl.add_mesh(
            finger.copy(),
            color="red"
        )

    def set_gripper(self, closed=False):
        """
        Greifer öffnen oder schliessen.

        closed=False -> Greifer offen
        closed=True  -> Greifer geschlossen
        """

        if closed:
            self.gripper_half_width = 7.0
        else:
            self.gripper_half_width = 20.0

    # ============================================================
    # TRANSFORMATIONEN
    # ============================================================
    def _create_rotation(self, origin, angle):
        """
        Erstellt eine Rotation um die Z-Achse um einen bestimmten Drehpunkt.
        """

        transform = vtk.vtkTransform()
        transform.PostMultiply()

        transform.Translate(-origin[0], -origin[1], -origin[2])
        transform.RotateZ(angle)
        transform.Translate(origin[0], origin[1], origin[2])

        return transform

    def _create_gripper_finger_transform(self, t_spindle, y_offset):
        """
        Erstellt eine Transformation für einen Greiferfinger.

        Zuerst wird der Finger lokal seitlich verschoben.
        Danach bekommt er die komplette Spindel-Transformation.
        Dadurch fährt und rotiert der Finger mit der Spindel mit.
        """

        t_finger = vtk.vtkTransform()
        t_finger.PostMultiply()

        # Lokale Öffnungsbewegung des Greifers
        t_finger.Translate(0.0, y_offset, 0.0)

        # Danach Spindelbewegung übernehmen
        t_finger.Concatenate(t_spindle)

        return t_finger

    # ============================================================
    # ANZEIGE
    # ============================================================
    def show(self):
        """
        Öffnet das 3D-Fenster.
        """

        self.pl.show(interactive_update=True, auto_close=False)

    def update_joints(self, inner_angle=0, outer_angle=0, spindle_angle=0, render=True):
        """
        Aktualisiert die Gelenkwinkel.

        Der äussere Arm folgt dem inneren Arm.
        Die Spindel folgt dem äusseren Arm.
        Der Greifer folgt der Spindel.
        """

        # --------------------------------------------------------
        # 1. Innerer Arm
        # --------------------------------------------------------
        t_inner = self._create_rotation(
            self.origin_inner,
            inner_angle
        )

        self.inner_arm_actor.SetUserTransform(t_inner)

        # --------------------------------------------------------
        # 2. Äusserer Arm folgt innerem Arm
        # --------------------------------------------------------
        t_outer = vtk.vtkTransform()
        t_outer.PostMultiply()

        t_outer.Concatenate(
            self._create_rotation(self.origin_outer, outer_angle)
        )

        t_outer.Concatenate(t_inner)

        self.outer_arm_actor.SetUserTransform(t_outer)

        # --------------------------------------------------------
        # 3. Spindel folgt äusserem Arm
        # --------------------------------------------------------
        t_spindle = vtk.vtkTransform()
        t_spindle.PostMultiply()

        t_spindle.Concatenate(
            self._create_rotation(self.origin_spindle, spindle_angle)
        )

        t_spindle.Concatenate(t_outer)

        self.spindle_actor.SetUserTransform(t_spindle)

        # --------------------------------------------------------
        # 4. Greifer folgt Spindel
        # --------------------------------------------------------
        self.gripper_mount_actor.SetUserTransform(t_spindle)

        t_finger_l = self._create_gripper_finger_transform(
            t_spindle,
            -self.gripper_half_width
        )

        t_finger_r = self._create_gripper_finger_transform(
            t_spindle,
            self.gripper_half_width
        )

        self.gripper_finger_l_actor.SetUserTransform(t_finger_l)
        self.gripper_finger_r_actor.SetUserTransform(t_finger_r)

        # --------------------------------------------------------
        # 5. Fenster aktualisieren
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

        # Test: Greifer abwechselnd öffnen/schliessen
        if i % 100 < 50:
            robot1.set_gripper(closed=False)
            robot2.set_gripper(closed=True)
        else:
            robot1.set_gripper(closed=True)
            robot2.set_gripper(closed=False)

        time.sleep(0.05)

    print("Test beendet.")