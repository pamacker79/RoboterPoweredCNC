# RoboterPoweredCNC

3D-Simulation und HMI-Steuerung einer Mehrroboter-Fertigungszelle:
zwei SCARA-Arme und eine H-Bot-Gravurgantry, mit Tkinter-Bedienpanel
und vollautomatischem Pick-and-Place-Ablauf.

---

## Voraussetzungen

| Anforderung | Version / Hinweis |
|---|---|
| **Betriebssystem** | Windows 10 / 11 (Tcl/Tk-Pfade werden automatisch gesetzt) |
| **Python** | 3.11 oder neuer |
| **PyVista** | `pip install "pyvista[all]>=0.43.0"` |

---

## Starten

```
python main.py
```

Es öffnen sich gleichzeitig zwei Fenster:

- **HMI-Fenster** — drei nebeneinander stehende Tkinter-Panels (je eines pro Roboter)
- **3D-Fenster** — gemeinsame PyVista-Szene mit allen Robotern und dem Magazin

---

## Systemarchitektur (MVC)

```
main.py  (Machine — 100-Hz-Steuerkreis)
│
├── Model/                  Kinematik & Datenmodelle (keine UI)
│   ├── Axis.py             Einzelachse: Softwarebegrenzung + Bewegungsrampe
│   ├── Scara.py            4-DOF SCARA: Vorwärts-/Rückwärtskinematik, Jog
│   ├── hBot.py             CoreXY H-Bot: MCS-Steuerung + cyclic()
│   ├── RobotConfig.py      Zentrale Achsgrenzen und Heimatposition
│   └── WorkpieceManager.py Bauteil-Stapelregister mit räumlichen Abfragen
│
├── View/                   PyVista 3D-Visualisierung (lädt STL-Dateien)
│   ├── Scara.py            SCARA-Arm: Mesh-Rendering, Gelenktransformationen, Vakuumsauger
│   ├── HBot.py             H-Bot-Gantry: Basis, Y-Brücke, X-Schlitten
│   └── MagazinViewPV.py    Rohteil-Stapelmagazin in der gemeinsamen 3D-Szene
│
└── ViewModel/              Tkinter HMI-Panels (Eingabe → Modell → Anzeige)
    ├── hmi.py              SCARA-Bedienpanel (Jog, Modus, Koordinaten, Sequenz, Status)
    ├── hmiHBot.py          H-Bot-Bedienpanel (Jog X/Y, Modus, Sequenz, Status)
    ├── hmiControl.py       DTO: Bedienereingaben → RobotController
    ├── hmiState.py         DTO: Achsistwerte → HMI-Anzeige
    └── RobotController.py  Pro-Roboter-Orchestrierung (HMI ↔ Kinematik ↔ View)
```

---

## Ablaufbeschreibung (Automatikbetrieb)

```
Magazin
  │  Rohteil (stapelbar, bis 6 Stück)
  │
  ▼
Roboter 1 (SCARA links)
  │  Greift oberstes Rohteil aus Magazin
  │  Legt es auf H-Bot-Arbeitsfläche ab
  │  Startet nur wenn Roboter 3 in Heimatposition
  │
  ▼
H-Bot (Gravurgantry, Mitte)
  │  Erkennt Bauteil via WorkpieceManager
  │  Fährt Gravurmuster (7 Wegpunkte, Rechteck 50 mm)
  │  Fährt in Parkposition
  │  Startet nur wenn Roboter 1 fertig (idle)
  │
  ▼
Roboter 3 (SCARA rechts)
  │  Greift graviertes Bauteil von H-Bot-Arbeitsfläche
  │  Legt es im Endlager rechts ab (stapelbar)
  │  Startet nur wenn H-Bot in Parkposition (Gravur fertig)
  │
  ▼
Endlager (Ablagestapel rechts)
```

---

## HMI-Bedienelemente

### SCARA-Panels (Roboter 1 und Roboter 3)

| Element | Beschreibung |
|---|---|
| **Betriebsart** | `Hand` = manuelles Jog, `Automatisch` = Pick-and-Place-Sequenz |
| **Koordinaten** | `Joint` / `Welt` / `Werkzeug` — aktiver Jog-Raum |
| **X/Y/Z/R +/−** | Jog-Tasten (halten = kontinuierliche Bewegung) |
| **Override** | Geschwindigkeitsskalierung 0–100 % (wirkt im Automatikbetrieb) |
| **Sequenz** | 6 farbige Kästchen — zeigt den aktuellen Sequenzschritt |
| **Status** | Statusmeldung mit Farbcode (Grün / Gelb / Orange / Rot) |
| **Saugen** | Vakuum ein/aus (nur im Handbetrieb aktiv) |
| **Reset** | Störung quittieren + Arm in Heimatposition fahren |

### H-Bot-Panel (Mitte)

| Element | Beschreibung |
|---|---|
| **Betriebsart** | `Hand` = Jog X/Y, `Automatisch` = Gravursequenz |
| **X/Y +/−** | Jog-Tasten für Laserkopf |
| **Override** | Gravur-Verfahrgeschwindigkeit 0–100 % |
| **Sequenz** | 5 Kästchen: Warten → Anfahrt → Gravur (n/m) → Park → Fertig |
| **Status** | Statusmeldung mit Farbcode |
| **Reset** | Störung quittieren |

---

## Koordinatensysteme

| System | Achsen | Beschreibung |
|---|---|---|
| **ACS** | `acsAxis1`–`acsAxis4` | Gelenkkoordinaten (Winkel [°] und Hub [mm]) |
| **MCS** | `mcsAxisX/Y/Z/R` | Kartesische TCP-Koordinaten [mm / °] |

Die SCARA-Kinematik berechnet beim Jog in "Welt" oder "Werkzeug" automatisch
via Rückwärtskinematik (IK) die Gelenkwinkel. Im "Joint"-Modus werden die
Gelenkwinkel direkt inkrementiert.

---

## Statusfarben

| Farbe | Bedeutung |
|---|---|
| Grün | Bereit / Handbetrieb OK |
| Hellgelb | Automatikbetrieb läuft |
| Cyan | Automatik wartet auf Vorbedingung |
| Orange | Achse an Grenzwert / Modus noch nicht gewählt |
| Lachs | Warte auf anderen Roboter |
| Rot | STÖRUNG — Reset drücken |

---

## Achsbegrenzungen anpassen

Alle Softwarebegrenzungen und Geschwindigkeiten sind ausschliesslich in
`Model/RobotConfig.py` definiert.  Eine Änderung dort wirkt sofort
systemweit — kein weiterer Code muss angepasst werden.

```python
# Beispiel: H-Bot Verfahrgeschwindigkeit erhöhen (500 → 1000 mm/s)
HBOT_LIMITS = {
    "mcsAxisX": (-700.0, 700.0, 10.0),   # 10 mm/Tick × 100 Hz = 1000 mm/s
    "mcsAxisY": (-300.0, 300.0, 10.0),
    ...
}
```

---

## Einzelne Dateien direkt ausführen

```bash
python Model/Axis.py        # Selbsttest der Bewegungsrampe
python View/Scara.py        # Bewegungstest der SCARA-3D-Visualisierung
python ViewModel/hmi.py     # HMI-Layout-Vorschau (alle drei Panels)
```

---

## Projektstruktur (vollständig)

```
RoboterPoweredCNC/
├── main.py
├── README.md
├── Model/
│   ├── Axis.py
│   ├── hBot.py
│   ├── RobotConfig.py
│   ├── Scara.py
│   └── WorkpieceManager.py
├── View/
│   ├── HBot.py
│   ├── MagazinViewPV.py
│   ├── Scara.py
│   ├── H_Bot_Modell/       STL-Dateien der H-Bot-Gantry
│   ├── Scara_Modell/       STL-Dateien des SCARA-Arms
│   └── Magazin_Modell/     STL-Dateien des Magazins
└── ViewModel/
    ├── hmi.py
    ├── hmiControl.py
    ├── hmiHBot.py
    ├── hmiState.py
    └── RobotController.py
```
