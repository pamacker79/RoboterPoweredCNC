"""
Modul: View.MagazinViewPV
==========================
3D-Visualisierung des Rohteil-Stapelmagazins im gemeinsamen PyVista-Fenster.

Aufbau des Magazins
-------------------
Das Magazin besteht aus drei Typen von 3D-Objekten:

* **Magazingehäuse** (``Magazin_V2.stl``) – halbtransparentes Gehäuse,
  ortsfest an der konfigurierten ``position``.
* **Ausschiebeeinheit / Schieber** (``Magazin_Schieber.stl``) – animierbar
  in -X-Richtung via ``update_schieber(hub)``.
* **Rohteil-Stapel** (``Roh_Teil.stl``, bis zu ``CAPACITY`` Kopien) –
  Rohteile stapeln sich von unten nach oben im Magazin.

Füllstandssteuerung
-------------------
``update_part_count(count)`` blendet die oberen Teile aus und zeigt nur
noch die untersten ``count`` Teile an.  Der Aufruf kommt von
``MagazinViewPV.pick_top_part()`` → Roboter-1-Sequenz.

Entnahme-Koordinaten
---------------------
``get_pickup_coordinates()`` gibt die Weltposition des aktuell obersten
sichtbaren Teils zurück — der RobotController nutzt diese Z-Koordinate,
um die Spindel exakt auf die Rohteiloberkante abzusenken.

Abhängigkeiten
--------------
* ``pyvista`` — 3D-Visualisierungsbibliothek
* ``View/Magazin_Modell/*.stl`` — Magazin-STL-Dateien
"""

import os
import pyvista as pv


class MagazinViewPV:
    """
    PyVista-Magazin-Visualisierung — kompatibel mit dem gemeinsamen Plotter.

    Konstanten
    ----------
    CAPACITY : int
        Maximale Anzahl Rohteile im Magazin (entspricht der Anzahl
        vorinstanzierter Aktor-Meshes).

    Parameter
    ---------
    pl : pyvista.Plotter
        Gemeinsames PyVista-Fenster.
    position : tuple(float, float, float)
        Weltposition der Magazin-Basis [mm].
    """

    CAPACITY = 6  # Maximale Stapelhöhe

    def __init__(self, pl, position=(0, 0, 0)):
        """
        Lädt alle STL-Meshes und instanziert die Rohteil-Aktoren.

        Die Rohteil-Positionen werden automatisch aus den Bounds des
        Gehäuse-Meshes berechnet, sodass die Teile exakt mittig im
        Magazin stehen.
        """
        self.pl       = pl
        self.position = position

        cwd        = os.getcwd()
        modell_dir = os.path.join(cwd, "View", "Magazin_Modell")

        mag_path      = os.path.join(modell_dir, "Magazin_V2.stl")
        schieber_path = os.path.join(modell_dir, "Magazin_Schieber.stl")
        rohteil_path  = os.path.join(modell_dir, "Roh_Teil.stl")

        # ── Magazingehäuse ─────────────────────────────────────────────────────
        mag_mesh = pv.read(mag_path)
        mb       = mag_mesh.bounds          # (xmin, xmax, ymin, ymax, zmin, zmax)
        mag_cx   = (mb[0] + mb[1]) / 2.0   # Mitte in X
        mag_cy   = (mb[2] + mb[3]) / 2.0   # Mitte in Y
        boden_z  = mb[4] + 1.0             # 1 mm Freiraum über dem Boden

        mag_mesh.translate(position, inplace=True)
        self._magazin_actor = pl.add_mesh(mag_mesh, color="lightgray", opacity=0.45)

        # ── Ausschiebeeinheit (Schieber) ───────────────────────────────────────
        schieber_mesh = pv.read(schieber_path)
        schieber_mesh.translate(position, inplace=True)
        self._schieber_actor = pl.add_mesh(schieber_mesh, color="darkorange")
        self._schieber_hub   = 0.0

        # ── Rohteil-Stapel (Vorinstanzierung aller CAPACITY Teile) ─────────────
        rohteil_template = pv.read(rohteil_path)
        rb          = rohteil_template.bounds
        part_height = rb[5] - rb[4]       # Bauteilhöhe [mm]
        rt_cx = (rb[0] + rb[1]) / 2.0
        rt_cy = (rb[2] + rb[3]) / 2.0

        # Versatz: Rohteil-Mitte auf Magazin-Mitte ausrichten
        dx = mag_cx - rt_cx
        dy = mag_cy - rt_cy

        self._part_actors = []
        for i in range(self.CAPACITY):
            part = rohteil_template.copy()
            dz   = boden_z - rb[4] + i * part_height  # Stapelposition in Z
            part.translate(
                (dx + position[0], dy + position[1], dz + position[2]),
                inplace=True
            )
            actor = pl.add_mesh(part, color="steelblue")
            self._part_actors.append(actor)

        self._part_count = self.CAPACITY

    # ------------------------------------------------------------------
    # Öffentliche Steuer-Methoden
    # ------------------------------------------------------------------

    def update_part_count(self, count: int):
        """
        Setzt den Füllstand des Magazins und aktualisiert die Sichtbarkeit.

        Die untersten ``count`` Teile werden angezeigt; alle übrigen
        ausgeblendet.

        Parameter
        ---------
        count : int
            Neuer Füllstand [0 … CAPACITY].
        """
        self._part_count = max(0, min(count, self.CAPACITY))
        for i, actor in enumerate(self._part_actors):
            actor.SetVisibility(i < self._part_count)

    def update_schieber(self, hub: float):
        """
        Verschiebt die Ausschiebeeinheit in -X-Richtung.

        Parameter
        ---------
        hub : float
            Ausfahrhub [mm] — 0.0 = eingefahren, positiv = ausgefahren.
        """
        self._schieber_hub = hub
        self._schieber_actor.position = [-hub, 0.0, 0.0]

    def get_pickup_coordinates(self):
        """
        Gibt die Weltkoordinaten der Oberkante des obersten Rohteils zurück.

        Diese Koordinaten werden vom RobotController verwendet, um die
        Spindel exakt auf die Teiloberkante abzusenken.

        Rückgabe
        --------
        tuple(float, float, float) oder None
            (cx, cy, top_z) in Weltkoordinaten [mm].
            None wenn das Magazin leer ist.
        """
        if self._part_count == 0:
            return None

        top_actor = self._part_actors[self._part_count - 1]
        b  = top_actor.bounds
        cx = (b[0] + b[1]) / 2.0
        cy = (b[2] + b[3]) / 2.0
        return (cx, cy, b[5])   # b[5] = Oberkante (zmax)

    def pick_top_part(self) -> bool:
        """
        Simuliert die Entnahme des obersten Rohteils durch den Roboter.

        Blendet das oberste sichtbare Teil aus und reduziert den Füllstand
        um 1.

        Rückgabe
        --------
        bool
            True bei erfolgreicher Entnahme, False wenn Magazin leer.
        """
        if self._part_count > 0:
            self._part_count -= 1
            self.update_part_count(self._part_count)
            return True
        return False
