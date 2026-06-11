"""
Module: CncInterpreter
Purpose: G-Code parser and path interpolator for CNC program execution.
Responsibilities: Parse G0/G1/G2/G3, G90/G91, F, X/Y/Z/I/J/K; interpolate moves into
                  small waypoints; export robot-ready motion command dicts.
Inputs:  G-Code file path or string via load_from_path() / load_from_string().
Outputs: List of waypoint dicts {X, Y, Z} from interpolate_path(step_size).
Dependencies: pathlib, re
"""
from pathlib import Path
import re


class CncInterpreter:
    def __init__(self):
        self.position = {
            "X": 0.0,
            "Y": 0.0,
            "Z": 0.0
        }

        self.feedrate = None
        self.absolute_mode = True
        self.moves = []

    def load_from_string(self, gcode: str):
        lines = gcode.splitlines()
        self._parse_lines(lines)

    def load_from_path(self, path: str | Path):
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Datei nicht gefunden: {path}")

        with path.open("r", encoding="utf-8") as file:
            lines = file.readlines()

        self._parse_lines(lines)

    def _parse_lines(self, lines):
        for line_number, line in enumerate(lines, start=1):
            line = self._clean_line(line)

            if not line:
                continue

            self._parse_line(line, line_number)

    def _clean_line(self, line: str) -> str:
        # Kommentare mit ; entfernen
        line = line.split(";")[0]

        # Kommentare in Klammern entfernen
        line = re.sub(r"\(.*?\)", "", line)

        return line.strip().upper()

    def _parse_line(self, line: str, line_number: int):
        tokens = re.findall(r"([A-Z])([-+]?\d*\.?\d+)", line)

        command = None
        values = {}

        for letter, value in tokens:
            if letter == "G":
                command = f"G{int(float(value))}"
            else:
                values[letter] = float(value)

        if command == "G90":
            self.absolute_mode = True
            return

        if command == "G91":
            self.absolute_mode = False
            return

        if "F" in values:
            self.feedrate = values["F"]

        if command in ["G0", "G1"]:
            self._linear_move(command, values, line_number)

        elif command in ["G2", "G3"]:
            self._arc_move(command, values, line_number)

        elif command is not None:
            print(f"Warnung Zeile {line_number}: Befehl {command} wird noch nicht unterstützt")

    def _linear_move(self, command, values, line_number):
        start = self.position.copy()
        end = self.position.copy()

        for axis in ["X", "Y", "Z"]:
            if axis in values:
                if self.absolute_mode:
                    end[axis] = values[axis]
                else:
                    end[axis] += values[axis]

        self.position = end.copy()

        self.moves.append({
            "line": line_number,
            "type": "rapid" if command == "G0" else "linear",
            "start": start,
            "end": end,
            "feedrate": self.feedrate
        })

    def _arc_move(self, command, values, line_number):
        start = self.position.copy()
        end = self.position.copy()

        for axis in ["X", "Y", "Z"]:
            if axis in values:
                if self.absolute_mode:
                    end[axis] = values[axis]
                else:
                    end[axis] += values[axis]

        center_offset = {
            "I": values.get("I", 0.0),
            "J": values.get("J", 0.0),
            "K": values.get("K", 0.0)
        }

        self.position = end.copy()

        self.moves.append({
            "line": line_number,
            "type": "arc_cw" if command == "G2" else "arc_ccw",
            "start": start,
            "end": end,
            "center_offset": center_offset,
            "feedrate": self.feedrate
        })

    def get_moves(self):
        return self.moves

    def interpolate_path(self, step_size = 10.0): # Pfad in kleine Schritte unterteilen
        interpolated_moves = []

        for move in self.moves:
            start = move ["start"]
            end = move ["end"]

            dx = end["X"] - start["X"]
            dy = end["Y"] - start["Y"]
            dz = end["Z"] - start["Z"]

            distance = (dx**2 + dy**2 + dz**2) ** 0.5

            if distance == 0:
                continue

            steps = max(1, int(distance / step_size)) 

            for step in range(steps + 1):
                t = step / steps

                point = {
                    "X": start["X"] + t * dx,
                    "Y": start["Y"] + t * dy,
                    "Z": start["Z"] + t * dz,
                    "move_type": move["type"],
                    "feedrate": move["feedrate"]
                }
    
                interpolated_moves.append(point)

        return interpolated_moves
            
    def export_robot_path(
        self,
        default_rapid_speed=3000,
        default_linear_speed=1000,
        default_blend=2.0
    ):
        robot_path = []

        for index, move in enumerate(self.moves, start=1):
            end = move["end"]

            # Geschwindigkeit bestimmen
            if move["feedrate"] is not None:
                speed = move["feedrate"]
            elif move["type"] == "rapid":
                speed = default_rapid_speed
            else:
                speed = default_linear_speed

            robot_point = {
                "point_number": index,
                "x": end["X"],
                "y": end["Y"],
                "z": end["Z"],
                "speed": speed,
                "blend": default_blend,
                "move_type": move["type"]
            }

            robot_path.append(robot_point)

        return robot_path

if __name__ == "__main__":
    # -------------------------
    # HAUPTPROGRAMM
    # -------------------------

    print("CNC Interpreter gestartet")
    print("------------------------")

    cnc = CncInterpreter()

    # programm.nc muss im gleichen Ordner liegen wie diese Python-Datei
    datei_pfad = Path(__file__).parent / "programm.nc"

    print("Ich lese diese Datei:")
    print(datei_pfad)

    print("\nInhalt der Datei:")
    print(datei_pfad.read_text(encoding="utf-8"))

    cnc.load_from_path(datei_pfad)

    print ("\nInterpolierter Pfad:")

    interpolated_path = cnc.interpolate_path(step_size=10.0)

    for point in interpolated_path:
        print(f"X{point['X']} Y{point['Y']} Z{point['Z']}")

    # -------------------------
    # BEWEGUNGEN AUSGEBEN
    # -------------------------

    print("\nBewegungen aus Datei:")

    for move in cnc.get_moves():
        start = move["start"]
        end = move["end"]

        print(
            f"Zeile {move['line']}: "
            f"{move['type']} von "
            f"X{start['X']} Y{start['Y']} Z{start['Z']} nach "
            f"X{end['X']} Y{end['Y']} Z{end['Z']} "
            f"mit F{move['feedrate']}"
        )


    # -------------------------
    # ROBOTER-PFAD EXPORTIEREN
    # -------------------------

    print("\nRoboter-Pfad 3D mit Geschwindigkeit und Verschleifpunkt:")

    robot_path = cnc.export_robot_path(
        default_rapid_speed=3000,
        default_linear_speed=1000,
        default_blend=2.0
    )

    for point in robot_path:
        print(
            f"P{point['point_number']}: "
            f"X={point['x']}, "
            f"Y={point['y']}, "
            f"Z={point['z']}, "
            f"Speed={point['speed']}, "
            f"Blend={point['blend']}, "
            f"Typ={point['move_type']}"
        )


    # -------------------------
    # ROBOTER-BEFEHLE AUSGEBEN
    # -------------------------

    print("\nRoboter-Befehle:")

    for point in robot_path:
        print(
            f"move_to("
            f"{point['x']}, "
            f"{point['y']}, "
            f"{point['z']}, "
            f"speed={point['speed']}, "
            f"blend={point['blend']}"
            f")"
        )