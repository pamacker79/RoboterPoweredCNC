"""
View: Stapelmagazin mit Rohteilen und Schieber
===============================================
Lädt drei STL-Dateien:
  - Magazin_V2.stl       (Magazinschacht)
  - Roh_Teil.stl          (Rohteil, wird gestapelt)
  - Magazin_Schieber.stl  (Schieber zur Vereinzelung)

Benötigte Pakete:  pip install numpy matplotlib
"""

import io
import urllib.request
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


# ----------------------------------------------------------
# Hilfsfunktionen (zustandslos)
# ----------------------------------------------------------
def lade_stl(quelle: str) -> np.ndarray:
    """Liest eine ASCII-STL -> Array der Form (n, 3, 3)."""
    if str(quelle).startswith("http"):
        with urllib.request.urlopen(str(quelle)) as antwort:
            text = antwort.read().decode("utf-8", errors="replace")
        zeilen = io.StringIO(text)
    else:
        if not Path(quelle).exists():
            raise FileNotFoundError(
                f"'{quelle}' nicht gefunden.\n"
                f"Liegt die Datei im richtigen Ordner und stimmt der "
                f"Dateiname exakt (Gross-/Kleinschreibung)?"
            )
        zeilen = open(quelle)

    facetten, aktuelle = [], []
    with zeilen as f:
        for zeile in f:
            zeile = zeile.strip()
            if zeile.startswith("vertex"):
                t = zeile.split()
                aktuelle.append([float(t[1]), float(t[2]), float(t[3])])
                if len(aktuelle) == 3:
                    facetten.append(aktuelle)
                    aktuelle = []

    if not facetten:
        raise ValueError(
            f"'{quelle}' enthält keine Dreiecke – ist es eine ASCII-STL? "
            f"(Binär-STLs müssten erst konvertiert werden.)"
        )
    return np.array(facetten)


def masse(mesh: np.ndarray, name: str):
    """Bounding-Box eines Meshs ermitteln und ausgeben."""
    v = mesh.reshape(-1, 3)
    vmin, vmax = v.min(axis=0), v.max(axis=0)
    print(f"{name}: {len(mesh)} Dreiecke")
    print(f"   Min (X,Y,Z): {vmin.round(2)}   Max: {vmax.round(2)}")
    print(f"   Abmessungen: {(vmax - vmin).round(2)}")
    return vmin, vmax


def schreibe_stl(pfad: str, mesh: np.ndarray, name: str = "modell"):
    """Schreibt ein (n, 3, 3)-Array als ASCII-STL mit berechneten Normalen."""
    with open(pfad, "w") as f:
        f.write(f"solid {name}\n")
        for dreieck in mesh:
            n = np.cross(dreieck[1] - dreieck[0], dreieck[2] - dreieck[0])
            laenge = np.linalg.norm(n)
            n = n / laenge if laenge > 0 else n
            f.write(f"  facet normal {n[0]:.6e} {n[1]:.6e} {n[2]:.6e}\n")
            f.write("    outer loop\n")
            for v in dreieck:
                f.write(f"      vertex {v[0]:.6e} {v[1]:.6e} {v[2]:.6e}\n")
            f.write("    endloop\n  endfacet\n")
        f.write(f"endsolid {name}\n")
    print(f"Exportiert: {pfad}")


# ----------------------------------------------------------
# MagazinView-Klasse
# ----------------------------------------------------------
class MagazinView:
    """
    Lädt Magazin-STLs und berechnet die Bestückung.
    Kein Rendering beim Konstruieren – show() explizit aufrufen.
    """

    def __init__(
        self,
        magazin_quelle: str,
        rohteil_quelle: str,
        schieber_quelle: str,
        anzahl_teile=None,
        fuellgrad: float = 1.0,
        boden_z: float = 1.0,
        luft_oben: float = 1.0,
        schieber_hub: float = 0.0,
        position_x: float = 10.0,
        position_y: float = 0.0,
        export_datei: str = None,
    ):
        self._magazin      = lade_stl(magazin_quelle)
        rohteil_raw        = lade_stl(rohteil_quelle)
        self._schieber_raw = lade_stl(schieber_quelle)
        self._export_datei = export_datei

        # Rohteil normieren: Ecke (min) auf Ursprung legen
        v = rohteil_raw.reshape(-1, 3)
        rt_min, rt_max = v.min(axis=0), v.max(axis=0)
        self._rohteil_raw = rohteil_raw - rt_min
        rt_groesse = rt_max - rt_min

        mag_v = self._magazin.reshape(-1, 3)
        mag_min, mag_max = mag_v.min(axis=0), mag_v.max(axis=0)

        self._teil_hoehe = float(rt_groesse[2])
        nutzhoehe        = float(mag_max[2]) - boden_z - luft_oben
        kapazitaet       = max(int(nutzhoehe // self._teil_hoehe), 0)

        if anzahl_teile is not None:
            anzahl = anzahl_teile
        else:
            anzahl = max(int(round(kapazitaet * fuellgrad)), 0)

        if anzahl > kapazitaet:
            print(f"Warnung: {anzahl} Teile angefordert, "
                  f"aber nur {kapazitaet} passen ins Magazin!")

        self._teile = [
            self._rohteil_raw + np.array([position_x, position_y, boden_z + i * self._teil_hoehe])
            for i in range(anzahl)
        ]

        self._schieber_hub = schieber_hub
        self._schieber = self._schieber_raw + np.array([-schieber_hub, 0.0, 0.0])

    def set_schieber_hub(self, hub: float):
        self._schieber_hub = hub
        self._schieber = self._schieber_raw + np.array([-hub, 0.0, 0.0])

    def show(self):
        fig = plt.figure(figsize=(8, 11))
        ax  = fig.add_subplot(111, projection="3d")

        ax.add_collection3d(Poly3DCollection(
            self._magazin, facecolor="lightgray", edgecolor="gray", alpha=0.25))
        ax.add_collection3d(Poly3DCollection(
            self._schieber, facecolor="darkorange", edgecolor="sienna", alpha=0.95))
        for t in self._teile:
            ax.add_collection3d(Poly3DCollection(
                t, facecolor="steelblue", edgecolor="navy", alpha=0.9))

        szene  = [self._magazin, self._schieber] + self._teile
        alle_v = np.concatenate(szene).reshape(-1, 3)
        smin, smax = alle_v.min(axis=0), alle_v.max(axis=0)
        rand = 10
        ax.set_xlim(smin[0] - rand, smax[0] + rand)
        ax.set_ylim(smin[1] - rand, smax[1] + rand)
        ax.set_zlim(smin[2] - rand, smax[2] + rand)
        ax.set_box_aspect((smax - smin) + 2 * rand)
        ax.set_xlabel("X [mm]")
        ax.set_ylabel("Y [mm]")
        ax.set_zlabel("Z [mm]")
        ax.set_title(f"Magazin mit {len(self._teile)} Rohteilen und Schieber")
        ax.view_init(elev=12, azim=-65)
        plt.tight_layout()
        plt.show()

    def export(self, pfad: str = None):
        ziel = pfad or self._export_datei
        if ziel:
            gesamt = np.concatenate([self._magazin, self._schieber] + self._teile)
            schreibe_stl(ziel, gesamt, name="Magazin_gefuellt")


# ----------------------------------------------------------
# Demo (python View/magazin.py)
# ----------------------------------------------------------
if __name__ == "__main__":
    BASIS_URL = ("https://raw.githubusercontent.com/pamacker79/"
                 "RoboterPoweredCNC/main/View/Magazin_Modell/")

    mv = MagazinView(
        magazin_quelle  = BASIS_URL + "Magazin_V2.stl",
        rohteil_quelle  = BASIS_URL + "Roh_Teil.stl",
        schieber_quelle = BASIS_URL + "Magazin_Schieber.stl",
        fuellgrad       = 1.0,
        export_datei    = str(Path(__file__).parent / "Magazin_gefuellt.stl"),
    )
    mv.show()
    mv.export()
