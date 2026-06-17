"""
Modul: Model.Axis
=================
Stellt eine einzelne Bewegungsachse mit Softwarebegrenzungen und
geschwindigkeitsgeregeltem Rampen-Antrieb bereit.

Verwendung im Projekt
---------------------
Jede physikalische oder kartesische Achse (Gelenkwinkel, Hub, X/Y/Z) wird
durch genau eine Axis-Instanz repräsentiert.  Der Regler schreibt den
Sollwert (``Sollposition``) und liest den Istwert (``ActualPosition``).
In jedem 100-Hz-Tick ruft der Hauptloop ``cyclic()`` auf – diese Methode
bewegt ActualPosition schrittweise auf Sollposition zu, begrenzt durch die
konfigurierte Maximalgeschwindigkeit.

Warum eine eigene Klasse statt eines einfachen float?
------------------------------------------------------
* Softwarebegrenzungen (min/max) werden beim Setzen des Sollwerts direkt
  geprüft und eingehalten – kein zusätzlicher Code im Aufrufer notwendig.
* Die velocity-Property entkoppelt die Bewegungsgeschwindigkeit vom
  Steuer-Takt und ermöglicht Override-Skalierung.
* Unverzügliche (velocity=None) und geramte Achsen verhalten sich identisch
  nach aussen.
"""


class Axis:
    """
    Einzelne Bewegungsachse mit Begrenzung und Geschwindigkeitsrampe.

    Parameter
    ---------
    min_pos : float oder None
        Untere Softwarebegrenzung.  Bei None keine untere Begrenzung.
    max_pos : float oder None
        Obere Softwarebegrenzung.  Bei None keine obere Begrenzung.
    velocity : float oder None
        Maximalgeschwindigkeit in Einheiten pro ``cyclic()``-Aufruf
        (100 Hz → 1 Tick = 10 ms).  ``None`` bedeutet unverzügliche
        Übernahme (ActualPosition = Sollposition sofort).

    Attribute
    ---------
    ActualPosition : float
        Istwert der Achse – wird von ``cyclic()`` schrittweise nachgeführt.
    """

    def __init__(self, min_pos=None, max_pos=None, velocity=None):
        self._sollposition  = 0.0
        self.ActualPosition = 0.0
        self.min_pos        = min_pos
        self.max_pos        = max_pos
        self._at_limit      = False
        self.velocity       = velocity   # max Änderung pro cyclic()-Aufruf; None = sofort

    # ------------------------------------------------------------------
    # Sollposition-Property mit Begrenzungsprüfung
    # ------------------------------------------------------------------

    @property
    def Sollposition(self):
        """Gibt den aktuell gesetzten Sollwert zurück."""
        return self._sollposition

    @Sollposition.setter
    def Sollposition(self, value):
        """
        Setzt den Sollwert und klemmt ihn auf [min_pos, max_pos].

        Wenn der Wert eine Grenze überschreitet, wird er auf die Grenze
        gesetzt und ``_at_limit`` auf True gestellt.  Liegt er innerhalb,
        wird ``_at_limit`` auf False zurückgesetzt.
        """
        if self.min_pos is not None and value < self.min_pos:
            value          = self.min_pos
            self._at_limit = True
        elif self.max_pos is not None and value > self.max_pos:
            value          = self.max_pos
            self._at_limit = True
        else:
            self._at_limit = False
        self._sollposition = value

    # ------------------------------------------------------------------
    # Hilfs-Getter (Legacy-Kompatibilität)
    # ------------------------------------------------------------------

    def is_at_limit(self) -> bool:
        """Gibt True zurück, wenn der letzte Sollwert an eine Begrenzung geklemmt wurde."""
        return self._at_limit

    def set_limits(self, min_pos: float, max_pos: float):
        """Setzt neue Softwarebegrenzungen zur Laufzeit."""
        self.min_pos = min_pos
        self.max_pos = max_pos

    def getActualPosition(self) -> float:
        """Gibt den Istwert zurück (Legacy-API)."""
        return self.ActualPosition

    def getSetPosition(self) -> float:
        """Gibt den Sollwert zurück (Legacy-API)."""
        return self._sollposition

    # ------------------------------------------------------------------
    # Zyklische Aktualisierung (100 Hz)
    # ------------------------------------------------------------------

    def cyclic(self, override: float = 1.0):
        """
        Führt ActualPosition schrittweise an Sollposition heran (Bewegungsrampe).

        Wird einmal pro Steuer-Tick (100 Hz) aufgerufen.

        Parameter
        ---------
        override : float
            Geschwindigkeitsskalierung im Bereich [0.0 … 1.0].
            0.0 → Achse steht still; 1.0 → volle konfigurierte Geschwindigkeit.
            Wird auf [0, 1] begrenzt.

        Verhalten
        ---------
        * Ist ``velocity`` None, wird ActualPosition sofort auf Sollposition gesetzt.
        * Liegt die Restdistanz innerhalb der effektiven Schrittweite, rastet die
          Achse exakt auf den Sollwert ein (kein Überschwingen).
        * Bei override = 0 bewegt sich die Achse nicht (kein Drift).
        """
        if self.velocity is None:
            # Unverzögerte Achse (z. B. MCS-Achsen, die aus Kinematik abgeleitet werden)
            self.ActualPosition = self._sollposition
        else:
            effective_vel = self.velocity * max(0.0, min(1.0, override))
            if effective_vel == 0.0:
                return  # Achse eingefroren (Override = 0)
            diff = self._sollposition - self.ActualPosition
            if abs(diff) <= effective_vel:
                # Einrasten: Restdistanz kleiner als ein Schritt → direkt auf Ziel
                self.ActualPosition = self._sollposition
            else:
                self.ActualPosition += effective_vel if diff > 0 else -effective_vel


# ------------------------------------------------------------------
# Selbsttest (python Model/Axis.py)
# ------------------------------------------------------------------
if __name__ == "__main__":
    # Begrenzungstest
    a = Axis(-10.0, 10.0)
    a.Sollposition = 15.0
    assert a.Sollposition == 10.0 and a.is_at_limit(), "Obere Begrenzung fehlgeschlagen"

    a.Sollposition = -20.0
    assert a.Sollposition == -10.0 and a.is_at_limit(), "Untere Begrenzung fehlgeschlagen"

    a.Sollposition = 5.0
    assert a.Sollposition == 5.0 and not a.is_at_limit(), "Freier Bereich fehlgeschlagen"

    # Unverzögerte Achse
    b = Axis()
    b.Sollposition = 999.0
    assert b.Sollposition == 999.0, "Unbegrenzte Achse sollte nicht klemmen"

    b.Sollposition = 5.0
    b.cyclic()
    assert b.ActualPosition == 5.0, "cyclic() bei velocity=None fehlgeschlagen"

    # Geschwindigkeitsrampe
    c = Axis(velocity=2.0)
    c.Sollposition = 10.0
    c.cyclic(override=1.0)
    assert c.ActualPosition == 2.0, "Rampe: erster Schritt fehlgeschlagen"
    for _ in range(10):
        c.cyclic(override=1.0)
    assert c.ActualPosition == 10.0, "Rampe: Ziel nicht erreicht"

    print("Alle Axis-Tests bestanden.")
