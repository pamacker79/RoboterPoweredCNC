import os

# Legt fest, welches OpenGL-Fenster VTK unter Windows benutzen soll
os.environ["VTK_DEFAULT_OPENGL_WINDOW"] = "vtkWin32OpenGLRenderWindow"

import pyvista as pv   # Für 3D-Darstellung und STL-Dateien
import vtk             # Für Transformationen und Drehmatrizen
import time            # Für Pausen während der Animation


# Klasse für die Anzeige und Bewegung des Roboters
class RobotViewer:

    def __init__(self, data_folder_path=None):
        # Falls kein Pfad angegeben wird, wird automatisch der Ordner View/data verwendet
        if data_folder_path is None:
            cwd = os.getcwd()
            data_folder_path = os.path.join(cwd, "View", "data")

        # STL-Dateien der einzelnen Roboterteile laden
        base_mesh      = pv.read(os.path.join(data_folder_path, "Base.stl"))
        inner_arm_mesh = pv.read(os.path.join(data_folder_path, "InnerArm.stl"))
        outer_arm_mesh = pv.read(os.path.join(data_folder_path, "OuterArm.stl"))
        spindle_mesh   = pv.read(os.path.join(data_folder_path, "Spindle.stl"))

        # 3D-Fenster erstellen
        self.pl = pv.Plotter(lighting="none")

        # Einstellungen für die Darstellung
        self.pl.renderer.SetUseDepthPeeling(False)
        self.pl.renderer.SetMaximumNumberOfPeels(0)

        # Roboterteile ins 3D-Fenster einfügen und Farben zuweisen
        self.base_actor      = self.pl.add_mesh(base_mesh,      color="lightblue")
        self.inner_arm_actor = self.pl.add_mesh(inner_arm_mesh, color="orange")
        self.outer_arm_actor = self.pl.add_mesh(outer_arm_mesh, color="green")
        self.spindle_actor   = self.pl.add_mesh(spindle_mesh,   color="gray")

        # Gelenkpunkte des Roboters festlegen
        self.shoulder = (0,   0, 0)     # Drehpunkt vom InnerArm
        self.elbow    = (0, -500, 0)    # Drehpunkt vom OuterArm
        self.tip      = (0,  900, 0)    # Drehpunkt von der Spindel / Werkzeugspitze

        # InnerArm dreht sich um den Schulterpunkt
        self.inner_arm_actor.SetOrigin(*self.shoulder)

        # Kameraansicht einstellen
        self.pl.camera_position = [
            (0.0, -1500.0, 850.0),  # Position der Kamera
            (0.0,    0.0,   0.0),   # Punkt, auf den die Kamera schaut
            (0.0,    1.0,   0.0),   # Oben-Richtung der Kamera
        ]

    @staticmethod
    def _build_transform(own_angle, own_pivot, parent_angle, parent_pivot):
        """
        Erstellt eine Transformation für ein Roboterteil.
        Das Teil dreht sich zuerst um sein eigenes Gelenk
        und danach zusätzlich mit dem vorherigen Armteil mit.
        """

        # Koordinaten vom eigenen Gelenk
        ox, oy, oz = own_pivot

        # Koordinaten vom übergeordneten Gelenk
        px, py, pz = parent_pivot

        # Neue Transformation erstellen
        t = vtk.vtkTransform()
        t.PostMultiply()

        # Teil zum eigenen Drehpunkt verschieben
        t.Translate(-ox, -oy, -oz)

        # Teil um die Z-Achse drehen
        t.RotateZ(own_angle)

        # Teil wieder zurück verschieben
        t.Translate(ox, oy, oz)

        # Teil zum Drehpunkt des Elternteils verschieben
        t.Translate(-px, -py, -pz)

        # Teil zusätzlich mit dem Elternteil mitdrehen
        t.RotateZ(parent_angle)

        # Teil wieder zurück verschieben
        t.Translate(px, py, pz)

        # Fertige Transformation zurückgeben
        return t

    def show(self):
        # 3D-Fenster öffnen und spätere Updates erlauben
        self.pl.show(interactive_update=True, auto_close=False)

    def update_joints(self, inner_angle=0, outer_angle=0, spindle_angle=0):
        # InnerArm um die Schulter drehen
        self.inner_arm_actor.SetOrientation(0, 0, inner_angle)

        # Transformation für den OuterArm berechnen
        # Er dreht sich um den Ellbogen und bewegt sich mit dem InnerArm mit
        t_outer = self._build_transform(
            own_angle=outer_angle,
            own_pivot=self.elbow,
            parent_angle=inner_angle,
            parent_pivot=self.shoulder,
        )

        # Transformation auf OuterArm anwenden
        self.outer_arm_actor.SetUserTransform(t_outer)

        # Transformation für die Spindel berechnen
        # Sie bewegt sich mit InnerArm und OuterArm mit
        t_spindle = self._build_transform(
            own_angle=spindle_angle,
            own_pivot=self.tip,
            parent_angle=inner_angle + outer_angle,
            parent_pivot=self.shoulder,
        )

        # Transformation auf Spindel anwenden
        self.spindle_actor.SetUserTransform(t_spindle)

        # 3D-Ansicht aktualisieren
        self.pl.update()

    def animate(self, target_inner=90, target_outer=0, target_spindle=0,
                max_steps=200, duration_s=3.0):
        # Animation in kleine Schritte aufteilen
        for step in range(max_steps + 1):

            # Fortschritt von 0 bis 1 berechnen
            t = step / max_steps

            # Gelenkwinkel schrittweise bis zum Zielwert erhöhen
            self.update_joints(
                inner_angle   = target_inner   * t,
                outer_angle   = target_outer   * t,
                spindle_angle = target_spindle * t,
            )

            # Kurze Pause, damit die Bewegung sichtbar ist
            time.sleep(duration_s / max_steps)

    def close(self):
        # 3D-Fenster schliessen
        self.pl.close()


# Roboter-Viewer erstellen
robot = RobotViewer()

# Fenster anzeigen
robot.show()

# InnerArm auf 90 Grad animieren
robot.animate(target_inner=90)

# Fenster offen lassen
robot.pl.show()