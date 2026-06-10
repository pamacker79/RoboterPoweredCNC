"""
View-Modell: Stapelmagazin mit Rohteilen befüllen
==================================================
Geometrie (aus den STL-Dateien ermittelt):
  Magazin : 120 x 56 x 501 mm, vertikaler Schacht
            Innenraum X 5..115, Y 0..50, Boden bei Z = 5
  Rohteil : Quader 100 x 50 x 25 mm
  -> Teile werden in Z-Richtung gestapelt, max. 19 Stück

Benötigte Pakete:  pip install numpy matplotlib
Die STL-Dateien können lokal liegen oder direkt von GitHub
(raw-URL) geladen werden.
"""

import io
import urllib.request
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# ----------------------------------------------------------
# 1) KONFIGURATION
# ----------------------------------------------------------
# Ordner, in dem dieses Skript liegt – dadurch werden lokale
# STL-Dateien unabhängig vom Arbeitsverzeichnis gefunden.
SKRIPT_ORDNER = Path(__file__).parent

# Die STL-Dateien werden direkt aus deinem GitHub-Repo geladen
# (Raw-URLs, Ordner "View"):
MAGAZIN_QUELLE = (
    "https://raw.githubusercontent.com/pamacker79/RoboterPoweredCNC"
    "/main/View/Magazin.stl"
)
ROHTEIL_QUELLE = (
    "https://raw.githubusercontent.com/pamacker79/RoboterPoweredCNC"
    "/main/View/Roh_Teil.stl"
)

# Alternative: lokale Dateien verwenden (Repo liegt ja auf deinem Mac).
# Dazu die beiden Zeilen oben auskommentieren und diese aktivieren –
# das funktioniert auch offline und ist schneller:
# MAGAZIN_QUELLE = str(SKRIPT_ORDNER.parent / "View" / "Magazin.stl")
# ROHTEIL_QUELLE = str(SKRIPT_ORDNER.parent / "View" / "Roh_Teil.stl")

ANZAHL_TEILE = 19          # max. 19 (Schachthöhe 495 mm / 25 mm Teilhöhe)
POSITION_X   = 10.0        # zentriert: (110 - 100) / 2 + 5 = 10
POSITION_Y   = 0.0
BODEN_Z      = 5.0         # Oberkante Bodenplatte
TEIL_HOEHE   = 25.0

# Export des gefüllten Magazins (None = kein Export)
EXPORT_DATEI = str(SKRIPT_ORDNER / "Magazin_gefuellt.stl")


# ----------------------------------------------------------
# 2) ASCII-STL lesen und schreiben (ohne Zusatzbibliotheken)
# ----------------------------------------------------------
def lade_stl(quelle: str) -> np.ndarray:
    """Liest eine ASCII-STL -> Array der Form (n, 3, 3)."""
    if quelle.startswith("http"):
        with urllib.request.urlopen(quelle) as antwort:
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

    mesh = np.array(facetten)
    abm = mesh.reshape(-1, 3).max(axis=0) - mesh.reshape(-1, 3).min(axis=0)
    print(f"Geladen: {quelle}")
    print(f"   {len(mesh)} Dreiecke  |  Abmessungen (X,Y,Z): {abm.round(1)}")
    return mesh


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
# 3) Magazin befüllen
# ----------------------------------------------------------
magazin = lade_stl(MAGAZIN_QUELLE)
rohteil = lade_stl(ROHTEIL_QUELLE)

if ANZAHL_TEILE > 19:
    print("Warnung: mehr als 19 Teile ragen über das Magazin hinaus!")

teile = []
for i in range(ANZAHL_TEILE):
    versatz = np.array([POSITION_X, POSITION_Y, BODEN_Z + i * TEIL_HOEHE])
    teile.append(rohteil + versatz)

print(f"{len(teile)} Rohteile platziert "
      f"(Z = {BODEN_Z} bis {BODEN_Z + ANZAHL_TEILE * TEIL_HOEHE}).")


# ----------------------------------------------------------
# 4) 3D-Ansicht
# ----------------------------------------------------------
fig = plt.figure(figsize=(7, 11))
ax = fig.add_subplot(111, projection="3d")

ax.add_collection3d(
    Poly3DCollection(magazin, facecolor="lightgray", edgecolor="gray", alpha=0.25)
)
for t in teile:
    ax.add_collection3d(
        Poly3DCollection(t, facecolor="steelblue", edgecolor="navy", alpha=0.9)
    )

ax.set_xlim(0, 120)
ax.set_ylim(-30, 90)
ax.set_zlim(0, 510)
ax.set_box_aspect((120, 120, 510))
ax.set_xlabel("X [mm]")
ax.set_ylabel("Y [mm]")
ax.set_zlabel("Z [mm]")
ax.set_title(f"Magazin mit {len(teile)} Rohteilen")
ax.view_init(elev=12, azim=-65)
plt.tight_layout()
plt.show()


# ----------------------------------------------------------
# 5) Export des gefüllten Magazins
# ----------------------------------------------------------
if EXPORT_DATEI:
    gesamt = np.concatenate([magazin] + teile)
    schreibe_stl(EXPORT_DATEI, gesamt, name="Magazin_gefuellt")
