"""
Modul: View.HBot
=================
3D-Visualisierung der H-Bot-Gravurgantry im gemeinsamen PyVista-Fenster.

Aufbau der 3D-Szene
--------------------
Die Gantry besteht aus vier STL-Teilen:

* **H-Bot 5.stl** – linke Führungsschiene (Basis, ortsfest)
* **H-Bot 1.stl** – rechte Führungsschiene (Basis, ortsfest)
* **H-Bot 2.stl** – Y-Brücke (bewegt sich in Y)
* **H-Bot 3.stl** – X-Schlitten / Laserkopf (bewegt sich in X und Y)

Bewegungsprinzip
----------------
``update_mesh_positions(x_pos, y_pos)`` wird jeden 100-Hz-Tick aus dem
Hauptloop aufgerufen.  Die Basis-Aktoren werden nur einmal positioniert;
Brücke und Werkzeug werden mit den aktuellen Istwerten der H-Bot-Achsen
(``ActualPosition``) verschoben.

Integration
-----------
Das Objekt wird in ``main.py`` erzeugt und teilt sich den gemeinsamen
``pv.Plotter`` mit den SCARA-Robotern und dem Magazin.

Abhängigkeiten
--------------
* ``pyvista`` – 3D-Visualisierungsbibliothek
* ``View/H_Bot_Modell/*.stl`` – STL-Modelldateien der Gantry
"""
import os
import pyvista as pv


class HBot:
    """
    Lädt die H-Bot-STL-Dateien und animiert sie im PyVista-Fenster.

    Parameter
    ---------
    data_folder_path : str oder None
        Pfad zum Ordner mit den STL-Dateien.  Bei None wird der Standardpfad
        ``./View/H_Bot_Modell`` relativ zum Arbeitsverzeichnis verwendet.
    pl : pyvista.Plotter oder None
        Gemeinsames PyVista-Fenster.  Bei None wird ein eigenes erstellt.
    position : tuple(float, float, float)
        Offset (x, y, z) aller Komponenten im Weltkoordinatensystem [mm].
    """

    def __init__(self, data_folder_path=None, pl=None, position=(0, 0, 0)):
        """Lädt die STL-Modelle, erzeugt Aktoren und setzt die Ausgangsstellung."""
        self.position = position

        # Pfad zu den STL-Dateien bestimmen
        if data_folder_path is None:
            cwd = os.getcwd()
            data_folder_path = os.path.join(cwd, "View", "H_Bot_Modell")

        file_base_left  = os.path.join(data_folder_path, "H-Bot 5.stl")
        file_base_right = os.path.join(data_folder_path, "H-Bot 1.stl")
        file_bridge     = os.path.join(data_folder_path, "H-Bot 2.stl")
        file_tool       = os.path.join(data_folder_path, "H-Bot 3.stl")

        # Meshes einlesen
        mesh_base_left  = pv.read(file_base_left)
        mesh_base_right = pv.read(file_base_right)
        mesh_bridge     = pv.read(file_bridge)
        mesh_tool       = pv.read(file_tool)

        # Plotter verwenden oder neues Fenster erstellen
        if pl is None:
            self.pl = pv.Plotter()
        else:
            self.pl = pl

        # Aktoren in die Szene einfügen
        self.base_l_actor  = self.pl.add_mesh(mesh_base_left,  color="lightblue", label="HBot Basis Links")
        self.base_r_actor  = self.pl.add_mesh(mesh_base_right, color="lightblue", label="HBot Basis Rechts")
        self.bridge_actor  = self.pl.add_mesh(mesh_bridge,     color="orange",    label="HBot Y-Brücke")
        self.tool_actor    = self.pl.add_mesh(mesh_tool,       color="green",     label="HBot X-Schlitten")

        # Ausgangsstellung setzen (noch kein render, Fenster noch nicht offen)
        self.update_mesh_positions(0.0, 0.0, render=False)

    def show(self):
        """Öffnet das eigenständige PyVista-Fenster (nur für Standalone-Tests)."""
        self.pl.show(interactive_update=True, auto_close=False)

    def update_mesh_positions(self, x_pos: float = 0.0,
                               y_pos: float = 0.0,
                               render: bool = True):
        """
        Verschiebt die beweglichen Komponenten der Gantry.

        Bewegungsregeln:
        * Basis-Schienen bleiben an der festen ``position``-Offset-Koordinate.
        * Y-Brücke folgt dem Y-Istwert der Gantry-Achse.
        * X-Schlitten / Laserkopf folgt sowohl X- als auch Y-Istwert.

        Parameter
        ---------
        x_pos : float
            Aktuelle X-Position des Laserkopfs (MCS ActualPosition) [mm].
        y_pos : float
            Aktuelle Y-Position der Brücke (MCS ActualPosition) [mm].
        render : bool
            Bei True wird ``pl.update()`` aufgerufen (nur wenn Fenster offen).
        """
        ox, oy, oz = self.position

        # Basis: ortsfest am konfigurierten Offset
        self.base_l_actor.position = [ox, oy, oz]
        self.base_r_actor.position = [ox, oy, oz]

        # Brücke: fährt nur in Y
        self.bridge_actor.position = [ox,        oy + y_pos, oz]

        # Laserkopf: fährt in X und Y
        self.tool_actor.position   = [ox + x_pos, oy + y_pos, oz]

        if render:
            try:
                self.pl.update()
            except RuntimeError:
                pass  # Fenster noch nicht vollständig initialisiert

    def close(self):
        """Schliesst das PyVista-Fenster."""
        self.pl.close()
