"""
Modul: Model.WorkpieceManager
==============================
Zentrale Verwaltung aller freien Werkstücke in der 3D-Szene.

Rolle im Gesamtsystem
---------------------
Der WorkpieceManager ist die Datenbank aller Bauteile, die sich weder
im Magazin noch am Sauger eines Roboters befinden.  Er hält die Welt-
koordinaten (X, Y) und den aktuellen Stapelzustand (top_z) jedes Teils.

Teile-Lebenszyklus
------------------
1. Roboter 1 greift aus Magazin  → ``MagazinViewPV.pick_top_part()``
2. Roboter 1 legt auf H-Bot-Tisch → ``WorkpieceManager.add_part()``
3. H-Bot prüft Vorhandensein      → ``WorkpieceManager.has_part_at()``
4. Roboter 3 greift das Teil      → ``WorkpieceManager.remove_part()``
5. Roboter 3 legt in Ablagestapel → ``WorkpieceManager.add_part()``

Stapeln
-------
Mehrere Teile auf denselben Weltkoordinaten stapeln sich in Z.
``get_stack_top()`` liefert die Oberkante des höchsten Teils innerhalb
eines Radius — so landet jedes neue Teil exakt auf dem vorherigen.

Abhängigkeiten
--------------
* ``pyvista`` — Erzeugung und Einblendung der Box-Meshes in der 3D-Szene
"""

import math
import pyvista as pv


class WorkpieceManager:
    """
    Zentrales Register aller freien Werkstücke in der 3D-Szene.

    Attribute
    ---------
    _parts : list[dict]
        Interne Liste aller registrierten Teile.  Jeder Eintrag enthält:
        ``id``, ``wx``, ``wy``, ``rz``, ``top_z``, ``actor``, ``plotter``.
    _next_id : int
        Laufende ID für das nächste neue Teil.
    """

    _PART_SIZE = (100, 50, 25)  # Bauteilmasse (dx, dy, dz) in mm — passt zur Roh_Teil.stl

    def __init__(self):
        """Initialisiert den leeren Werkstückspeicher."""
        self._parts   = []
        self._next_id = 0

    # ------------------------------------------------------------------
    # Stapelhilfen
    # ------------------------------------------------------------------

    def get_stack_top(self, world_x: float, world_y: float,
                      radius: float = 60.0) -> float:
        """
        Gibt die Oberkante (Z) des obersten Teils im Suchradius zurück.

        Parameter
        ---------
        world_x, world_y : float
            Suchzentrum in Weltkoordinaten [mm].
        radius : float
            Maximale horizontale Entfernung [mm].

        Rückgabe
        --------
        float
            Z-Koordinate der obersten Teileoberkante; 0.0 wenn kein Teil vorhanden.
        """
        top = 0.0
        for p in self._parts:
            d = math.sqrt((p["wx"] - world_x) ** 2 + (p["wy"] - world_y) ** 2)
            if d <= radius:
                top = max(top, p["top_z"])
        return top

    def get_place_z(self, world_x: float, world_y: float,
                    radius: float = 60.0) -> float:
        """
        Berechnet die Z-Position, auf die der Roboter das nächste Teil ablegen muss.

        Das Ergebnis ist die Oberkante des aktuellen Stapels plus die Höhe
        eines einzelnen Teils (_PART_SIZE[2]).

        Parameter
        ---------
        world_x, world_y : float
            Ablagestelle in Weltkoordinaten [mm].
        radius : float
            Suchradius für vorhandene Teile [mm].

        Rückgabe
        --------
        float
            Ziel-Z für den TCP beim Ablegen [mm].
        """
        return self.get_stack_top(world_x, world_y, radius) + self._PART_SIZE[2]

    # ------------------------------------------------------------------
    # Teile hinzufügen / entfernen
    # ------------------------------------------------------------------

    def add_part(self, plotter, world_x: float, world_y: float,
                 rotation_z: float = 0.0) -> int:
        """
        Legt ein neues Bauteil an der angegebenen Weltposition ab.

        Das Teil wird automatisch auf den vorhandenen Stapel gesetzt
        (``get_stack_top()`` bestimmt die untere Z-Koordinate).
        Das Mesh wird direkt dem PyVista-Plotter hinzugefügt.

        Parameter
        ---------
        plotter : pyvista.Plotter
            Der gemeinsame 3D-Plotter, in dem das Mesh erscheinen soll.
        world_x, world_y : float
            Ablagestelle in Weltkoordinaten [mm].
        rotation_z : float
            TCP-Weltrotation beim Ablegen [Grad] — bestimmt die Ausrichtung
            des Teils in der Szene.

        Rückgabe
        --------
        int
            Eindeutige Bauteil-ID.
        """
        dx, dy, dz = self._PART_SIZE
        bottom_z   = self.get_stack_top(world_x, world_y)

        # Mesh um eigene Mitte aufbauen, damit rotate_z um die Bauteilmitte dreht
        mesh = pv.Box(bounds=(-dx / 2, dx / 2, -dy / 2, dy / 2,
                               bottom_z, bottom_z + dz))
        if abs(rotation_z) > 0.01:
            mesh.rotate_z(rotation_z, inplace=True)
        mesh.translate((world_x, world_y, 0.0), inplace=True)

        actor   = plotter.add_mesh(mesh, color="saddlebrown")
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
        """
        Blendet ein Bauteil aus und entfernt es aus dem Register.

        Parameter
        ---------
        part_id : int
            ID des zu entfernenden Teils (aus ``add_part()``).

        Rückgabe
        --------
        bool
            True wenn das Teil gefunden und entfernt wurde, sonst False.
        """
        for i, p in enumerate(self._parts):
            if p["id"] == part_id:
                p["actor"].SetVisibility(False)
                self._parts.pop(i)
                return True
        return False

    # ------------------------------------------------------------------
    # Abfragen
    # ------------------------------------------------------------------

    def has_part_at(self, world_x: float, world_y: float,
                    radius: float = 60.0) -> bool:
        """
        Gibt True zurück, wenn mindestens ein freies Teil im Suchradius liegt.

        Parameter
        ---------
        world_x, world_y : float
            Suchzentrum in Weltkoordinaten [mm].
        radius : float
            Maximale horizontale Entfernung [mm].
        """
        return self._find_nearest(world_x, world_y, radius) is not None

    def pick_nearest(self, world_x: float, world_y: float,
                     radius: float = 60.0):
        """
        Gibt das nächste Bauteil innerhalb des Suchradius zurück.

        Das Teil wird NICHT entfernt — nach einem erfolgreichen Griff
        muss der Aufrufer ``remove_part(id)`` aufrufen.

        Parameter
        ---------
        world_x, world_y : float
            Suchzentrum in Weltkoordinaten [mm].
        radius : float
            Maximaler Suchradius [mm].

        Rückgabe
        --------
        dict oder None
            Teilbeschreibung (enthält ``id``, ``wx``, ``wy``, ``top_z``
            u.a.) oder None wenn kein Teil in Reichweite.
        """
        return self._find_nearest(world_x, world_y, radius)

    def get_all_positions(self) -> list:
        """
        Gibt eine Liste aller aktuellen Teilepositionen zurück.

        Rückgabe
        --------
        list[tuple[float, float]]
            Liste von (wx, wy)-Tupeln für alle registrierten Teile.
        """
        return [(p["wx"], p["wy"]) for p in self._parts]

    # ------------------------------------------------------------------
    # Interne Hilfsmethode
    # ------------------------------------------------------------------

    def _find_nearest(self, wx: float, wy: float, radius: float):
        """
        Interne Suche nach dem nächsten Teil innerhalb des Radius.

        Gibt das Teile-Dict zurück oder None wenn keins gefunden.
        """
        best      = None
        best_dist = float("inf")
        for p in self._parts:
            d = math.sqrt((p["wx"] - wx) ** 2 + (p["wy"] - wy) ** 2)
            if d <= radius and d < best_dist:
                best_dist = d
                best      = p
        return best
