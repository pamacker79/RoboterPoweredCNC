"""
View-Modell: Stapelmagazin mit Rohteilen und Schieber
======================================================
Lädt drei STL-Dateien:
  - Magazin_V2.stl       (Magazinschacht)
  - Roh_Teil.stl          (Rohteil, wird gestapelt)
  - Magazin_Schieber.stl  (Schieber zur Vereinzelung)

Das Skript misst die Geometrie beim Laden automatisch aus,
zentriert die Rohteile im Magazin und berechnet die maximale
Stapelkapazität selbst. Alle Werte lassen sich in der
Konfiguration übersteuern.

Benötigte Pakete:  pip install numpy matplotlib
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
SKRIPT_ORDNER = Path(__file__).parent

# --- Variante A: direkt aus dem GitHub-Repo laden ---
BASIS_URL = ("https://raw.githubusercontent.com/pamacker79/"
             "RoboterPoweredCNC/main/View/Magazin_Modell/")
MAGAZIN_QUELLE  = BASIS_URL + "Magazin_V2.stl"
ROHTEIL_QUELLE  = BASIS_URL + "Roh_Teil.stl"
SCHIEBER_QUELLE = BASIS_URL + "Magazin_Schieber.stl"

# --- Variante B: lokale Dateien (schneller, geht offline) ---
# Auskommentieren der Zeilen oben und diese aktivieren.
# Das Skript liegt in ViewModel, die STLs in View/Magazin_Modell:
# MODELL_ORDNER   = SKRIPT_ORDNER.parent / "View" / "Magazin_Modell"
# MAGAZIN_QUELLE  = str(MODELL_ORDNER / "Magazin_V2.stl")
# ROHTEIL_QUELLE  = str(MODELL_ORDNER / "Roh_Teil.stl")
# SCHIEBER_QUELLE = str(MODELL_ORDNER / "Magazin_Schieber.stl")

# Befüllung (Werte aus der V2-Geometrie ermittelt)
ANZAHL_TEILE   = None      # None = automatisch maximal befüllen
FUELLGRAD      = 1.0       # 1.0 = voll, 0.5 = halb voll (nur falls ANZAHL_TEILE = None)
BODEN_Z        = 1.0       # Oberkante Bodenplatte des V2-Schachts
LUFT_OBEN      = 1.0       # Sicherheitsabstand zur Oberkante in mm

# Position der Rohteile im Schacht (Innenraum X 5..115, Y 0..50):
# X = 10 -> Teil (100 mm) zentriert, 5 mm Spiel pro Seite. Y = 0 -> passgenau.
POSITION_X     = 10.0
POSITION_Y     = 0.0

# Schieber: Ruheposition liegt im CAD bei X 120..290, er schiebt in
# -X-Richtung durch das runde Loch (Ø25, Mitte Y=25/Z=25) in der
# rechten Schachtwand. Mit dem Hub simulierst du den Ausschiebevorgang:
# 0 = eingefahren, ca. 110-115 = unterstes Teil komplett ausgeschoben.
SCHIEBER_HUB   = 0.0       # Hub in mm (in -X-Richtung)

# Export des gefüllten Magazins (None = kein Export)
EXPORT_DATEI = str(SKRIPT_ORDNER / "Magazin_gefuellt.stl")


# ----------------------------------------------------------
# 2) ASCII-STL lesen und schreiben (ohne Zusatzbibliotheken)
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
# 3) Dateien laden und vermessen
# ----------------------------------------------------------
print("Lade STL-Dateien ...")
magazin  = lade_stl(MAGAZIN_QUELLE)
rohteil  = lade_stl(ROHTEIL_QUELLE)
schieber = lade_stl(SCHIEBER_QUELLE)

mag_min, mag_max = masse(magazin, "Magazin")
rt_min,  rt_max  = masse(rohteil, "Rohteil")
sch_min, sch_max = masse(schieber, "Schieber")

rt_groesse = rt_max - rt_min          # Abmessungen des Rohteils
mag_groesse = mag_max - mag_min

# Rohteil normieren: Ecke (min) auf den Ursprung legen,
# damit die Platzierung vorhersagbar ist
rohteil = rohteil - rt_min

# Schieber-Hub anwenden (Bewegung in -X-Richtung)
schieber = schieber + np.array([-SCHIEBER_HUB, 0.0, 0.0])


# ----------------------------------------------------------
# 4) Platzierung berechnen
# ----------------------------------------------------------
# X/Y: zentriert im Magazin (falls nicht manuell vorgegeben)
pos_x = POSITION_X if POSITION_X is not None else \
    mag_min[0] + (mag_groesse[0] - rt_groesse[0]) / 2
pos_y = POSITION_Y if POSITION_Y is not None else \
    mag_min[1] + (mag_groesse[1] - rt_groesse[1]) / 2

# Z: Stapelbeginn (falls nicht vorgegeben: Unterkante Magazin)
boden_z = BODEN_Z if BODEN_Z is not None else float(mag_min[2])

# Kapazität: wie viele Teile passen übereinander?
teil_hoehe = float(rt_groesse[2])
nutzhoehe = float(mag_max[2]) - boden_z - LUFT_OBEN
kapazitaet = max(int(nutzhoehe // teil_hoehe), 0)

if ANZAHL_TEILE is not None:
    anzahl = ANZAHL_TEILE
else:
    anzahl = max(int(round(kapazitaet * FUELLGRAD)), 0)

if anzahl > kapazitaet:
    print(f"Warnung: {anzahl} Teile angefordert, "
          f"aber nur {kapazitaet} passen ins Magazin!")

print(f"\nPlatzierung: X={pos_x:.1f}, Y={pos_y:.1f}, Stapelbeginn Z={boden_z:.1f}")
print(f"Kapazität: {kapazitaet} Teile à {teil_hoehe:.1f} mm "
      f"-> {anzahl} Teile werden platziert\n")

teile = []
for i in range(anzahl):
    versatz = np.array([pos_x, pos_y, boden_z + i * teil_hoehe])
    teile.append(rohteil + versatz)


# ----------------------------------------------------------
# 5) 3D-Ansicht
# ----------------------------------------------------------
fig = plt.figure(figsize=(8, 11))
ax = fig.add_subplot(111, projection="3d")

ax.add_collection3d(
    Poly3DCollection(magazin, facecolor="lightgray", edgecolor="gray", alpha=0.25)
)
ax.add_collection3d(
    Poly3DCollection(schieber, facecolor="darkorange", edgecolor="sienna", alpha=0.95)
)
for t in teile:
    ax.add_collection3d(
        Poly3DCollection(t, facecolor="steelblue", edgecolor="navy", alpha=0.9)
    )

# Achsen automatisch an die Gesamtszene anpassen
szene = [magazin, schieber] + teile
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
ax.set_title(f"Magazin mit {len(teile)} Rohteilen und Schieber")
ax.view_init(elev=12, azim=-65)
plt.tight_layout()
plt.show()


# ----------------------------------------------------------
# 6) Export des gefüllten Magazins (inkl. Schieber)
# ----------------------------------------------------------
if EXPORT_DATEI:
    gesamt = np.concatenate([magazin, schieber] + teile)
    schreibe_stl(EXPORT_DATEI, gesamt, name="Magazin_gefuellt")
