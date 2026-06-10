import os
import pyvista as pv


class HBot:
    """
    Lädt die H-Bot STL-Dateien und stellt sie in PyVista dar.
    Diese Version kann in ein gemeinsames PyVista-Fenster eingefügt werden.
    """

    def __init__(self, data_folder_path=None, pl=None, position=(0, 0, 0)):
        """
        Args:
            data_folder_path: Pfad zu den STL-Dateien
            pl: Gemeinsamer PyVista-Plotter
            position: Verschiebung des ganzen H-Bots im 3D-Fenster
        """

        self.position = position

        # 1. Pfad konfigurieren
        if data_folder_path is None:
            cwd = os.getcwd()
            data_folder_path = os.path.join(cwd, "View", "H_Bot_Modell")

        file_base_left = os.path.join(data_folder_path, "H-Bot 5.stl")
        file_base_right = os.path.join(data_folder_path, "H-Bot 1.stl")
        file_bridge = os.path.join(data_folder_path, "H-Bot 2.stl")
        file_tool = os.path.join(data_folder_path, "H-Bot 3.stl")

        # 2. Modelle einlesen
        mesh_base_left = pv.read(file_base_left)
        mesh_base_right = pv.read(file_base_right)
        mesh_bridge = pv.read(file_bridge)
        mesh_tool = pv.read(file_tool)

        # 3. Gemeinsames Fenster verwenden oder eigenes erstellen
        if pl is None:
            self.pl = pv.Plotter()
        else:
            self.pl = pl

        # 4. Meshes hinzufügen
        self.base_l_actor = self.pl.add_mesh(
            mesh_base_left,
            color="lightblue",
            label="HBot Basis Links"
        )

        self.base_r_actor = self.pl.add_mesh(
            mesh_base_right,
            color="lightblue",
            label="HBot Basis Rechts"
        )

        self.bridge_actor = self.pl.add_mesh(
            mesh_bridge,
            color="orange",
            label="HBot Y-Brücke"
        )

        self.tool_actor = self.pl.add_mesh(
            mesh_tool,
            color="green",
            label="HBot X-Schlitten"
        )

        # Wichtig:
        # Beim Erstellen nur Position setzen, aber noch NICHT self.pl.update() ausführen.
        # Das Fenster ist hier noch nicht initialisiert.
        self.update_mesh_positions(0.0, 0.0, render=False)

    def show(self):
        """
        Öffnet das Fenster, falls HBot einzeln getestet wird.
        """
        self.pl.show(interactive_update=True, auto_close=False)

    def update_mesh_positions(self, x_pos=0.0, y_pos=0.0, render=True):
        """
        Verschiebt die H-Bot-Komponenten.

        Basis bleibt fest.
        Brücke bewegt sich in Y.
        Werkzeug bewegt sich in X und Y.
        """

        offset_x = self.position[0]
        offset_y = self.position[1]
        offset_z = self.position[2]

        # Basis bleibt fix an der H-Bot-Gesamtposition
        self.base_l_actor.position = [offset_x, offset_y, offset_z]
        self.base_r_actor.position = [offset_x, offset_y, offset_z]

        # Brücke fährt nur in Y
        self.bridge_actor.position = [
            offset_x,
            offset_y + y_pos,
            offset_z
        ]

        # Werkzeug fährt in X und Y
        self.tool_actor.position = [
            offset_x + x_pos,
            offset_y + y_pos,
            offset_z
        ]

        # Nur updaten, wenn das Fenster bereits offen/initialisiert ist
        if render:
            try:
                self.pl.update()
            except RuntimeError:
                pass

    def close(self):
        """
        Schliesst das Fenster.
        """
        self.pl.close()