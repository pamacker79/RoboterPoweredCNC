"""
Modul: ViewModel.hmiControl
============================
Datentransferobjekt (DTO) für eingehende HMI-Steuerbefehle.

Datenfluss
----------
``Hmi`` schreibt in dieses Objekt (Tastendruck, Schieberegler).
``RobotController.update_hmi()`` liest daraus und reagiert darauf.
Das Objekt wird von ``Hmi.getHmiControl()`` zurückgegeben.

Felder
------
MoveXPlus / MoveXNeg … MoveRPlus / MoveRNeg : bool
    Jog-Flags — True solange die entsprechende Taste gedrückt ist.
    Werden in ``_axis_row()`` über ``<Button-1>`` / ``<ButtonRelease-1>``
    gesetzt und zurückgesetzt.
Saugen : bool
    Vakuum-Einschalt-Anforderung — Einmal-Impuls (wird nach Verarbeitung
    im Controller auf False zurückgesetzt).
Reset : bool
    Störungs-Reset-Anforderung — Einmal-Impuls.
OperationMode : int
    Betriebsart: 0 = Handbetrieb, 1 = Automatikbetrieb.
mode_selected : bool
    True sobald der Bediener eine Betriebsart aus dem Dropdown gewählt hat.
    Verhindert, dass der Roboter sofort losfährt bevor eine Auswahl
    getroffen wurde (OperationMode=0 ist vor UND nach Auswahl von "Hand"
    identisch — dieser Flag unterscheidet beide Zustände).
CoordSystem : str
    Aktives Koordinatensystem: "Joint", "Welt" oder "Werkzeug".
OverridePercent : int
    Geschwindigkeitsskalierung vom HMI-Schieberegler [0 … 100 %].
"""
import sys
sys.path.append('../ViewModel')


class hmiControl:
    """
    Datencontainer für HMI-Eingaben — vom Bediener zum Regler.

    Alle Felder werden von der Hmi-Klasse beschrieben und vom
    RobotController gelesen.  Kein interner Zustand, keine Logik.
    """

    def __init__(self):
        """Initialisiert alle Felder auf sichere Standardwerte (Stillstand)."""
        # Jog-Tasten: True = Taste gedrückt
        self.MoveXPlus = False
        self.MoveXNeg  = False
        self.MoveYPlus = False
        self.MoveYNeg  = False
        self.MoveZPlus = False
        self.MoveZNeg  = False
        self.MoveRPlus = False
        self.MoveRNeg  = False

        # Einzel-Impulse (werden nach Verarbeitung vom Controller zurückgesetzt)
        self.Saugen = False
        self.Reset  = False

        # Betriebsartwahl
        self.OperationMode  = 0        # 0 = Handbetrieb, 1 = Automatikbetrieb
        self.mode_selected  = False    # True sobald der Bediener eine Betriebsart gewählt hat

        # Koordinatensystem und Geschwindigkeit
        self.CoordSystem     = "wählen"  # "Joint", "Welt" oder "Werkzeug"
        self.OverridePercent = 100       # 0–100 %
