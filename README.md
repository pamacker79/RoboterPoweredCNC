# RoboterPoweredCNC

3D simulation and HMI control for a multi-robot workcell: two SCARA arms and one H-Bot gantry, with a Tkinter operator panel and G-Code CNC interpreter.

## Requirements

- **Windows** (TCL/TK library paths are hardcoded for Windows in `main.py`)
- Python 3.13
- PyVista: `pip install "pyvista[all]>=0.43.0"`

## Run

```
python main.py
```

Two windows open simultaneously:
- **HMI window** — three Tkinter panels (one per robot)
- **3D window** — shared PyVista scene with all robots and the magazine

## Architecture

```
main.py (Machine)
│
├── Model/          — kinematics and logic only, no UI
│   ├── Axis.py           property-based axis with software limits
│   ├── Scara.py          4-DOF SCARA forward/inverse kinematics
│   ├── hBot.py           CoreXY H-Bot motor ↔ Cartesian conversion
│   ├── CncInterpreter.py G-Code parser and path interpolator
│   └── RobotConfig.py    axis limits and home positions (single source of truth)
│
├── View/           — PyVista 3D visualization, loads STL files
│   ├── Scara.py          SCARA arm mesh rendering and joint transforms
│   ├── HBot.py           H-Bot gantry mesh rendering
│   ├── MagazinViewPV.py  raw-part magazine in the shared 3D scene
│   └── magazin.py        standalone matplotlib magazine inspector
│
└── ViewModel/      — Tkinter HMI panels, bridges input→model and model→display
    ├── hmi.py            operator panel (jog, mode, override, status)
    ├── hmiControl.py     DTO: operator commands → RobotController
    ├── hmiState.py       DTO: axis positions → HMI display labels
    └── RobotController.py per-robot orchestration (HMI → kinematics → view)
```

## HMI Controls

Each robot panel has:

| Control | Description |
|---|---|
| Koordinatensystem | Joint / Welt / Werkzeug jog space |
| Betriebsart | Hand (manual jog) or Automatisch (CNC program) |
| X/Y/Z/R +/− | Jog buttons (hold to move) |
| Override slider | CNC execution speed 0–100 % |
| Status bar | Green=Bereit, Orange=Achse an Grenzwert, Red=STÖRUNG |
| Start | In Hand mode: close gripper. In Auto mode: run CNC program |
| Reset | Clear fault, drive all axes to home position (0°/0mm) |
| Stop | Open gripper, stop motion |

## Coordinate Systems

SCARA robots switch between:
- **ACS** (`acsAxis1`–`acsAxis4`) — joint/articulated angles and hub height
- **MCS** (`mcsAxisX/Y/Z/R`) — Cartesian machine coordinates

The jog coordinate system selector determines which space the +/− buttons operate in.

## Axis Limits

All software limits are defined in `Model/RobotConfig.py`. Edit that file to change any limit system-wide — no other changes needed.

## Running Individual Model Files

Model files can be run directly for quick inspection:

```
python Model/Scara.py      # kinematics test
python View/magazin.py     # matplotlib magazine inspector
python ViewModel/hmi.py    # HMI layout preview
```

## Known Limitations

- Motion is instant (no velocity ramps or acceleration profiles)
- G2/G3 arc interpolation is not fully implemented
- Pick-and-place sequences are not automated — manual jog only
- Screenshots require manual capture from the PyVista window
