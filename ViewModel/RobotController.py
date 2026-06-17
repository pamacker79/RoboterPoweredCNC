"""
Modul: ViewModel.RobotController
==================================
Orchestrierungsschicht für einen einzelnen SCARA-Roboter.

Rolle im MVC-System
--------------------
Der RobotController verbindet HMI-Eingaben, kinematisches Modell und
3D-Visualisierung.  Er wird einmal pro SCARA-Roboter instanziert und
im 100-Hz-Hauptloop von ``main.py`` durch vier Methoden aufgerufen:

1. ``update_hmi()``       — Liest hmiControl, setzt Status und Sequenzanzeige,
                            ruft Handbetrieb oder Automatik auf.
2. ``update_kinematics()`` — Ruft ``Scara.forward()`` oder ``backward()``
                            auf, fängt Kinematik-Fehler ab.
3. ``cyclic()``           — Ruft ``Scara.cyclic(override)`` auf, damit
                            ActualPosition schrittweise zu Sollposition fährt.
4. ``update_view()``      — Übergibt ACS-Istwerte an die View.

Betriebsmodi
------------
**Handbetrieb** (OperationMode = 0):
    Jog-Befehle (X/Y/Z/R ± in Joint, Welt oder Werkzeugkoordinaten)
    werden direkt auf die Sollpositionen addiert.  Der "Saugen"-Taster
    löst ``_handle_saugen()`` aus.

**Automatikbetrieb** (OperationMode = 1):
    Zustandsmaschine mit 10 Zuständen (_A_IDLE bis _A_GO_HOME).
    Jeder Schritt wartet auf Ankunft (``_is_at_target()``) oder auf
    einen Dwell-Timer (_GRAB_TICKS) bevor der nächste Zustand beginnt.

Zustandsmaschine (Auto-Sequenz)
---------------------------------
_A_IDLE             (0) – Wartet auf Bauteil und freien Absetzplatz.
_A_MOVE_ABOVE_PICK  (1) – Fährt über die Aufnahmeposition (Z=0).
_A_LOWER_TO_PICK    (2) – Fährt auf Bauthöhe (Z = pick_wz).
_A_GRAB             (3) – Aktiviert Vakuum; Dwell 100 ms.
_A_LIFT_AFTER_PICK  (4) – Hebt Bauteil (Z=0).
_A_MOVE_ABOVE_PLACE (5) – Fährt über die Ablagestelle (Z=0).
_A_LOWER_TO_PLACE   (6) – Fährt auf Stapelkante (Z = place_wz).
_A_RELEASE          (7) – Deaktiviert Vakuum; Dwell 100 ms; Bauteil anlegen.
_A_LIFT_AFTER_PLACE (8) – Hebt Arm (Z=0).
_A_GO_HOME          (9) – Fährt in SCARA-Heimatposition (Gelenkkoordinaten).

Koordinatentransformation
--------------------------
Weltkoordinaten (wx, wy) und Roboter-lokale MCS-Koordinaten (lx, ly)
werden mit ``_world_to_local()`` und ``_local_to_world()`` ineinander
umgerechnet.  Dabei wird die Montagedrehung ``rotation_z`` der View
berücksichtigt, damit der Arm aus jeder Montagerichtung korrekt
arbeitet.

Sicherheitsmechanismen
-----------------------
* ``_AUTO_TIMEOUT`` — fault wenn ein Bewegungszustand nicht innerhalb
  von 6 s (600 Ticks) beendet wird.
* ``pickup_gate``   — callable, das True zurückgibt wenn die externe
  Vorbedingung erfüllt ist (z. B. H-Bot an Parkposition, anderer Roboter idle).
* ``place_is_sink`` — True bei Ablagestelle ohne Rückmeldecheck
  (Roboter 3 legt in einen Endstapel ab).

Abhängigkeiten
--------------
* ``Model.Scara``          — Kinematisches Modell
* ``Model.RobotConfig``    — SCARA_HOME-Position
* ``Model.WorkpieceManager`` — Bauteilregistrierung
* ``View.Scara``           — 3D-Visualisierung
* ``ViewModel.hmiControl`` — Eingaben vom Bediener
* ``ViewModel.hmiState``   — Istwert-Ausgabe ans HMI
"""

import math
from Model.RobotConfig import SCARA_HOME

# ── Auto-Sequenz-Zustände ────────────────────────────────────────────────────
_A_IDLE             = 0   # Wartet auf Bauteil
_A_MOVE_ABOVE_PICK  = 1   # Fährt über Aufnahme (Z=0)
_A_LOWER_TO_PICK    = 2   # Senkt auf Bauthöhe ab
_A_GRAB             = 3   # Aktiviert Vakuum (Dwell)
_A_LIFT_AFTER_PICK  = 4   # Hebt Bauteil an (Z=0)
_A_MOVE_ABOVE_PLACE = 5   # Fährt über Ablagestelle (Z=0)
_A_LOWER_TO_PLACE   = 6   # Senkt auf Stapelkante ab
_A_RELEASE          = 7   # Deaktiviert Vakuum (Dwell), legt Teil ab
_A_LIFT_AFTER_PLACE = 8   # Hebt Arm an (Z=0)
_A_GO_HOME          = 9   # Heimfahrt in SCARA_HOME

_GRAB_TICKS      = 10    # Ticks für Vakuum-Dwell (~100 ms bei 100 Hz)
_AUTO_TIMEOUT    = 600   # Ticks vor Störungsauslösung (~6 s)
_ARRIVED_TOL_DEG = 1.5   # Ankunftstoleranz Winkelachsen [Grad]
_ARRIVED_TOL_MM  = 1.5   # Ankunftstoleranz Linearachsen [mm]
_SUCTION_RADIUS  = 60.0  # Max. XY-Abstand für manuelle Saugnapfprüfung [mm]
_SUCTION_RADIUS_Z = 30.0 # Max. Z-Abstand für manuelle Saugnapfprüfung [mm]
_WPM_PART_TOP    = 25.0  # Standard-Bauteiloberkante im WPM (Teile liegen auf Z=0, Höhe=25 mm)


class RobotController:
    """
    Orchestrierungsschicht für einen SCARA-Roboter.

    Verbindet HMI-Eingaben (hmiControl), kinematisches Modell (Scara)
    und 3D-Visualisierung (View.Scara).

    Parameter
    ---------
    robot_trafo : Model.Scara
        Kinematisches Modell des Roboters.
    robot_view : View.Scara
        3D-Visualisierung des Roboters.
    hmi : Hmi
        HMI-Panel des Roboters.
    hmi_state : hmiState
        Istwert-DTO für die HMI-Anzeige.
    workpiece_manager : WorkpieceManager oder None
        Globales Bauteilregister.
    magazin_view : MagazinViewPV oder None
        Magazin-View (nur für Roboter 1, der das Magazin bedient).
    pickup_world : tuple(float, float) oder None
        Weltkoordinaten der Aufnahmestelle (Auto-Modus).
    place_world : tuple(float, float) oder None
        Weltkoordinaten der Ablagestelle (Auto-Modus).
    pickup_gate : callable oder None
        Funktion, die True zurückgibt wenn der Start erlaubt ist
        (z. B. anderer Roboter in Heimatposition).
    place_is_sink : bool
        True wenn die Ablagestelle ein Endlager ist (kein Belegtheits-Check).
    """

    def __init__(self, robot_trafo, robot_view, hmi, hmi_state,
                 workpiece_manager=None, magazin_view=None,
                 pickup_world=None, place_world=None,
                 pickup_gate=None, place_is_sink=False):
        """Initialisiert den Controller mit allen Abhängigkeiten."""
        self.robot_trafo   = robot_trafo
        self.robot_view    = robot_view
        self.hmi           = hmi
        self.hmi_state     = hmi_state
        self.wpm           = workpiece_manager
        self.magazin_view  = magazin_view
        self.pickup_world  = pickup_world
        self.place_world   = place_world
        self.pickup_gate   = pickup_gate
        self.place_is_sink = place_is_sink

        self._gripper_closed  = False
        self._joint_mode      = True   # True = Gelenkkoordinaten, False = kartesisch
        self._manual_mode     = True
        self._fault           = False

        self._carried_part_id = None   # ID des manuell getragenen Teils

        # Auto-Sequenz-Zustand
        self._auto_state   = _A_IDLE
        self._auto_tick    = 0
        self._pick_wx      = 0.0   # Roboter-lokale Aufnahmekoordinaten
        self._pick_wy      = 0.0
        self._pick_wz      = 0.0
        self._place_wx     = 0.0   # Roboter-lokale Ablagekoordinaten
        self._place_wy     = 0.0
        self._place_wz     = 0.0
        self._pending_wpm_part = None  # WPM-Teile-Dict das für den Griff reserviert ist

        if hasattr(self.robot_view, "set_gripper"):
            self.robot_view.set_gripper(closed=False)

    # =========================================================================
    # Öffentliche API — vom Hauptloop aufgerufen
    # =========================================================================

    @property
    def is_idle(self) -> bool:
        """
        True wenn die Auto-Sequenz abgeschlossen ist und der Arm in SCARA_HOME steht.

        Wird von anderen Controllern als Handshake-Guard genutzt
        (z. B. H-Bot wartet auf Roboter 1).
        """
        return self._auto_state == _A_IDLE

    def update_hmi(self):
        """
        Verarbeitet HMI-Eingaben, aktualisiert den Statusstreifen und
        delegiert an Handbetrieb oder Automatik.

        Ablauf:
        1. Reset-Impuls prüfen (Fehler löschen, Arm in Home).
        2. Saugen-Taste sperren/freigeben.
        3. Status-Label setzen (Priorität: Fault > kein Modus > Automatik > Limit > Bereit).
        4. Falls Modus noch nicht gewählt: Istwerte anzeigen und früh zurückkehren.
        5. Handbetrieb oder Automatik aufrufen.
        6. Istwerte und Sequenzanzeige aktualisieren.
        """
        hmi_ctrl = self.hmi.getHmiControl()
        is_auto  = (hmi_ctrl.OperationMode == 1)

        # ── Reset-Impuls ──────────────────────────────────────────────────────
        if getattr(hmi_ctrl, "Reset", False):
            self._fault      = False
            self._auto_state = _A_IDLE
            self._cancel_vacuum()
            self.robot_trafo.acsAxis1.Sollposition = SCARA_HOME["acsAxis1"]
            self.robot_trafo.acsAxis2.Sollposition = SCARA_HOME["acsAxis2"]
            self.robot_trafo.acsAxis3.Sollposition = SCARA_HOME["acsAxis3"]
            self.robot_trafo.acsAxis4.Sollposition = SCARA_HOME["acsAxis4"]
            hmi_ctrl.Reset = False

        mode_ok = hmi_ctrl.mode_selected

        # ── Saugen-Taste: nur aktiv wenn Modus gewählt und Handbetrieb ────────
        if hasattr(self.hmi, "set_saugen_enabled"):
            self.hmi.set_saugen_enabled(mode_ok and not is_auto)

        # ── Status-Anzeige (Prioritätsreihenfolge) ────────────────────────────
        if self._fault:
            self.hmi.setStatus("STÖRUNG — Reset drücken", "red")
        elif not mode_ok:
            self.hmi.setStatus("Betriebsmodus wählen!", "orange")
        elif is_auto and self._auto_state != _A_IDLE:
            self.hmi.setStatus(f"Automatik — Schritt {self._auto_state}/9", "lightyellow")
        elif is_auto:
            self.hmi.setStatus("Automatik — wartet auf Teil", "lightcyan")
        elif self._any_at_limit():
            self.hmi.setStatus("Achse an Grenzwert", "orange")
        else:
            self.hmi.setStatus("Bereit", "lightgreen")

        # Fault: nur Istwerte anzeigen, keine Steuerbefehle ausführen
        if self._fault:
            self._update_hmi_state()
            self.hmi.setHmiState(self.hmi_state)
            return

        # Kein Modus gewählt: Istwerte anzeigen, keine Bewegung
        if not mode_ok:
            self._update_hmi_state()
            self.hmi.setHmiState(self.hmi_state)
            if hasattr(self.hmi, "setSequenceState"):
                self.hmi.setSequenceState(self._auto_state)
            return

        # ── Betriebsart-Dispatch ──────────────────────────────────────────────
        if is_auto:
            self._manual_mode = False
            self._run_auto(hmi_ctrl)
        else:
            # Umschalten auf Handbetrieb: Sequenz abbrechen und Vakuum lösen
            if not self._manual_mode:
                self._auto_state  = _A_IDLE
                self._auto_tick   = 0
                self._cancel_vacuum()
                self._pending_wpm_part = None
            self._manual_mode = True
            self._run_manual(hmi_ctrl)

        self._update_hmi_state()
        self.hmi.setHmiState(self.hmi_state)
        if hasattr(self.hmi, "setSequenceState"):
            self.hmi.setSequenceState(self._auto_state)

    def update_kinematics(self):
        """
        Aktualisiert das kinematische Modell (Vorwärts- oder Rückwärtskinematik).

        Im Gelenkkoordinaten-Modus (``_joint_mode=True``) wird nur
        ``forward()`` aufgerufen.  Im kartesischen Modus wird zuerst
        ``backward()`` (IK) und danach ``forward()`` (FK) aufgerufen,
        um ACS- und MCS-Werte konsistent zu halten.

        Kinematik-Fehler (Arbeitsraum-Verletzung) werden abgefangen und
        lösen eine Störung aus — die Sollpositionen werden auf die
        Istwerte zurückgesetzt, damit kein weiterer Fehler entsteht.
        """
        try:
            if self._joint_mode:
                self.robot_trafo.forward()
            else:
                self.robot_trafo.backward()
                self.robot_trafo.forward()
        except ValueError as e:
            print(f"Kinematik Fehler: {e}")
            for axis in [
                self.robot_trafo.acsAxis1, self.robot_trafo.acsAxis2,
                self.robot_trafo.acsAxis3, self.robot_trafo.acsAxis4,
                self.robot_trafo.mcsAxisX, self.robot_trafo.mcsAxisY,
                self.robot_trafo.mcsAxisZ, self.robot_trafo.mcsAxisR,
            ]:
                axis.Sollposition = axis.ActualPosition
            self._fault = True

    def cyclic(self):
        """
        Führt alle ACS-Achsen schrittweise an ihre Sollpositionen heran.

        Im Handbetrieb wird immer mit Override=100 % gefahren (volle Geschwindigkeit).
        Im Automatikbetrieb wird der Override-Wert des HMI-Schiebereglers verwendet.
        """
        if self._manual_mode:
            self.robot_trafo.cyclic(override=1.0)
        else:
            pct = getattr(self.hmi.getHmiControl(), "OverridePercent", 100)
            self.robot_trafo.cyclic(override=pct / 100.0)

    def update_view(self):
        """
        Übergibt die aktuellen ACS-Istwerte an die 3D-View.

        Verwendet immer ``ActualPosition`` (wo der Roboter physisch steht),
        nie ``Sollposition`` (wo er hinfahren soll).  Das stellt sicher,
        dass die 3D-Animation die Bewegungsrampe widerspiegelt.

        Der +180°-Offset auf acsAxis1 korrigiert die STL-Nullstellung:
        der Arm zeigt im STL in -X, die Kinematik nimmt +X als Referenz.
        """
        self.robot_view.update_joints(
            self.robot_trafo.acsAxis1.ActualPosition + 180.0,
            self.robot_trafo.acsAxis2.ActualPosition,
            self.robot_trafo.acsAxis4.ActualPosition,
            z_height=self.robot_trafo.acsAxis3.ActualPosition
        )

    # =========================================================================
    # Handbetrieb
    # =========================================================================

    def _run_manual(self, hmi_ctrl):
        """
        Verarbeitet Jog-Eingaben und Saugen-Impuls im Handbetrieb.

        Koordinatensystem-Prüfung: wenn noch kein KS gewählt ist,
        wird der Status auf "Koordinatensystem wählen!" gesetzt und
        die Jog-Verarbeitung übersprungen.
        """
        coord_system = getattr(hmi_ctrl, "CoordSystem", "wählen")
        coord_ok     = coord_system in ["Joint", "Welt", "Werkzeug"]

        if not coord_ok:
            self.hmi.setStatus("Koordinatensystem wählen!", "orange")
        else:
            self._joint_mode = self._handle_manual_control(hmi_ctrl)

        # Saugen-Einmal-Impuls verarbeiten
        if getattr(hmi_ctrl, "Saugen", False):
            hmi_ctrl.Saugen = False
            self._handle_saugen()

    def _handle_saugen(self):
        """
        Schaltet Vakuum ein oder aus, abhängig vom aktuellen Trägezustand.

        Wenn der Sauger bereits geschlossen ist, wird das Bauteil abgelegt.
        Ansonsten wird versucht, das nächste Bauteil aufzunehmen.
        """
        if self._gripper_closed:
            self._release_part()
        else:
            self._attempt_pickup()

    def _attempt_pickup(self):
        """
        Versucht, ein Bauteil mit dem Sauger aufzunehmen.

        Suchpriorität:
        1. Oberstes Teil im Magazin (nur wenn ``magazin_view`` gesetzt).
        2. Nächstes freies Teil im WorkpieceManager.

        Ein Aufnehmen ist nur möglich wenn der TCP innerhalb des
        Suchradius (XY und Z) am Bauteil ist.
        """
        tcp_wx, tcp_wy, tcp_wz = self._tcp_world_pos()

        # ① Magazin-Rohteil prüfen
        if self.magazin_view is not None:
            mag_coords = self.magazin_view.get_pickup_coordinates()
            if mag_coords is not None:
                mx, my, mz = mag_coords
                dist_xy = math.sqrt((tcp_wx - mx) ** 2 + (tcp_wy - my) ** 2)
                dist_z  = abs(tcp_wz - mz)
                if dist_xy <= _SUCTION_RADIUS:
                    if dist_z <= _SUCTION_RADIUS_Z:
                        self.magazin_view.pick_top_part()
                        self._activate_vacuum()
                        self._carried_part_id = "magazine"
                        self.hmi.setStatus("Teil aus Magazin angesaugt", "lightgreen")
                    else:
                        self.hmi.setStatus(
                            f"Kein Rohteil in der Nähe des Saugers — Höhendifferenz: {dist_z:.0f} mm",
                            "orange"
                        )
                    return

        # ② Freie Teile im WorkpieceManager prüfen
        if self.wpm is not None:
            part = self.wpm.pick_nearest(tcp_wx, tcp_wy, _SUCTION_RADIUS)
            if part is not None:
                dist_z = abs(tcp_wz - part["top_z"])
                if dist_z <= _SUCTION_RADIUS_Z:
                    self.wpm.remove_part(part["id"])
                    self._activate_vacuum()
                    self._carried_part_id = part["id"]
                    self.hmi.setStatus("Rohteil angesaugt", "lightgreen")
                else:
                    self.hmi.setStatus(
                        f"Kein Rohteil in der Nähe des Saugers — Höhendifferenz: {dist_z:.0f} mm",
                        "orange"
                    )
                return

        # ③ Kein Teil in Reichweite
        self.hmi.setStatus("Kein Rohteil in der Nähe des Saugers", "orange")

    def _release_part(self):
        """
        Legt das getragene Bauteil an der aktuellen TCP-Position ab (Z=0).

        Die Ablageposition ist immer auf dem Boden (Z=0); die aktuelle
        TCP-Weltrotation wird auf das Teil übertragen, damit es in der
        richtigen Ausrichtung liegt.
        """
        if self.wpm is not None:
            tcp_wx, tcp_wy, _ = self._tcp_world_pos()
            self.wpm.add_part(
                self.robot_view.pl,
                tcp_wx,
                tcp_wy,
                rotation_z=self._tcp_rotation(),
            )
        self._cancel_vacuum()
        self._carried_part_id = None
        self.hmi.setStatus("Teil abgelegt (Z=0)", "lightgreen")

    # =========================================================================
    # Automatikbetrieb
    # =========================================================================

    def _run_auto(self, hmi_ctrl):
        """
        Führt die automatische Pick-and-Place-Sequenz aus (10 Zustände).

        Wird jeden 100-Hz-Tick aufgerufen.  Jeder Bewegungszustand setzt
        ein MCS-Ziel und wartet auf Ankunft.  Dwell-Zustände (_A_GRAB,
        _A_RELEASE) zählen Ticks bis zum Ablauf.
        """
        self._auto_tick += 1

        if self._auto_state == _A_IDLE:
            self._auto_try_start()
            self._auto_tick = 0   # Tick-Zähler in Ruhe nicht ansteigen lassen

        elif self._auto_state == _A_MOVE_ABOVE_PICK:
            self._set_mcs_target(self._pick_wx, self._pick_wy, 0.0)
            if self._is_at_target():
                self._next_auto_state()
            elif self._auto_tick >= _AUTO_TIMEOUT:
                self._trigger_auto_fault("Timeout: Anfahrt Pickup-Position")

        elif self._auto_state == _A_LOWER_TO_PICK:
            self._set_mcs_target(self._pick_wx, self._pick_wy, self._pick_wz)
            if self._is_at_target():
                self._next_auto_state()
            elif self._auto_tick >= _AUTO_TIMEOUT:
                self._trigger_auto_fault("Timeout: Absenken zum Bauteil")

        elif self._auto_state == _A_GRAB:
            if self._auto_tick == 1:
                self._activate_vacuum()
                if self._pending_wpm_part is not None:
                    self.wpm.remove_part(self._pending_wpm_part["id"])
                    self._pending_wpm_part = None
                elif self.magazin_view is not None:
                    self.magazin_view.pick_top_part()
            if self._auto_tick >= _GRAB_TICKS:
                self._next_auto_state()

        elif self._auto_state == _A_LIFT_AFTER_PICK:
            self._set_mcs_target(self._pick_wx, self._pick_wy, 0.0)
            if self._is_at_target():
                self._next_auto_state()
            elif self._auto_tick >= _AUTO_TIMEOUT:
                self._trigger_auto_fault("Timeout: Anheben nach Pickup")

        elif self._auto_state == _A_MOVE_ABOVE_PLACE:
            self._set_mcs_target(self._place_wx, self._place_wy, 0.0)
            if self._is_at_target():
                self._next_auto_state()
            elif self._auto_tick >= _AUTO_TIMEOUT:
                self._trigger_auto_fault("Timeout: Anfahrt Ablageposition")

        elif self._auto_state == _A_LOWER_TO_PLACE:
            self._set_mcs_target(self._place_wx, self._place_wy, self._place_wz)
            if self._is_at_target():
                self._next_auto_state()
            elif self._auto_tick >= _AUTO_TIMEOUT:
                self._trigger_auto_fault("Timeout: Absenken zur Ablage")

        elif self._auto_state == _A_RELEASE:
            if self._auto_tick == 1:
                self._cancel_vacuum()
                if self.wpm is not None:
                    place_wx, place_wy = self._local_to_world(self._place_wx, self._place_wy)
                    self.wpm.add_part(
                        self.robot_view.pl,
                        place_wx,
                        place_wy,
                        rotation_z=self._tcp_rotation(),
                    )
            if self._auto_tick >= _GRAB_TICKS:
                self._next_auto_state()

        elif self._auto_state == _A_LIFT_AFTER_PLACE:
            self._set_mcs_target(self._place_wx, self._place_wy, 0.0)
            if self._is_at_target():
                self._next_auto_state()   # → _A_GO_HOME
            elif self._auto_tick >= _AUTO_TIMEOUT:
                self._trigger_auto_fault("Timeout: Anheben nach Ablage")

        elif self._auto_state == _A_GO_HOME:
            # Heimfahrt in Gelenkkoordinaten (sicher, keine IK-Singularität)
            self._joint_mode = True
            self.robot_trafo.acsAxis1.Sollposition = SCARA_HOME["acsAxis1"]
            self.robot_trafo.acsAxis2.Sollposition = SCARA_HOME["acsAxis2"]
            self.robot_trafo.acsAxis3.Sollposition = SCARA_HOME["acsAxis3"]
            self.robot_trafo.acsAxis4.Sollposition = SCARA_HOME["acsAxis4"]
            if self._is_at_target():
                self._auto_state = _A_IDLE
                self._auto_tick  = 0
            elif self._auto_tick >= _AUTO_TIMEOUT:
                self._trigger_auto_fault("Timeout: Heimfahrt")

    def _auto_try_start(self):
        """
        Prüft alle Startbedingungen und startet die Sequenz wenn erfüllt.

        Bedingungen (in Reihenfolge):
        1. Absetzplatz frei (ausser bei place_is_sink=True).
        2. Bauteil an Aufnahmeposition vorhanden (Magazin oder WPM).
        3. Externer Gate-Check (pickup_gate) liefert True.

        Wenn alle Bedingungen erfüllt sind, werden Aufnahme- und
        Ablagepositionen in lokale MCS-Koordinaten umgerechnet und der
        Zustand auf _A_MOVE_ABOVE_PICK gesetzt.
        """
        if self.pickup_world is None or self.place_world is None:
            return

        pw_x, pw_y = self.pickup_world
        pl_x, pl_y = self.place_world

        # Bedingung 1: Absetzplatz prüfen
        if not self.place_is_sink:
            if self.wpm is not None and self.wpm.has_part_at(pl_x, pl_y, _SUCTION_RADIUS):
                self.hmi.setStatus("Automatik — Absetzplatz belegt, warte...", "lightsalmon")
                return

        # Bedingung 2: Bauteil an Aufnahmestelle vorhanden?
        pick_z  = None
        pending = None

        if self.magazin_view is not None:
            coords = self.magazin_view.get_pickup_coordinates()
            if coords is not None:
                pick_z = self._world_z_to_mcs(coords[2])

        if pick_z is None and self.wpm is not None:
            part = self.wpm.pick_nearest(pw_x, pw_y, _SUCTION_RADIUS)
            if part is not None:
                pick_z  = self._world_z_to_mcs(part["top_z"])
                pending = part

        if pick_z is None:
            return   # Kein Bauteil vorhanden

        # Bedingung 3: Externer Gate-Check
        if self.pickup_gate is not None and not self.pickup_gate():
            return

        # Positionen in lokale MCS-Koordinaten umrechnen und auf Reichweite klemmen
        self._pick_wx,  self._pick_wy  = self._clamp_local_to_reach(
            *self._world_to_local(pw_x, pw_y))
        self._pick_wz   = pick_z
        self._place_wx, self._place_wy = self._clamp_local_to_reach(
            *self._world_to_local(pl_x, pl_y))

        # Stapelhöhe an der tatsächlichen (geklemmten) Weltposition abfragen
        actual_pl_wx, actual_pl_wy = self._local_to_world(self._place_wx, self._place_wy)
        place_z_world  = self.wpm.get_place_z(actual_pl_wx, actual_pl_wy) if self.wpm else _WPM_PART_TOP
        self._place_wz = self._world_z_to_mcs(place_z_world)
        self._pending_wpm_part = pending

        self._auto_state = _A_MOVE_ABOVE_PICK
        self._auto_tick  = 0
        self._joint_mode = False

    # =========================================================================
    # Hilfsmethoden
    # =========================================================================

    def _next_auto_state(self):
        """Wechselt in den nächsten Automatik-Zustand und setzt den Tick-Zähler zurück."""
        self._auto_state += 1
        self._auto_tick   = 0

    def _is_at_target(self) -> bool:
        """
        Gibt True zurück wenn alle ACS-Achsen ihre Sollpositionen
        innerhalb der konfigurierten Toleranzen erreicht haben.
        """
        angular = [self.robot_trafo.acsAxis1,
                   self.robot_trafo.acsAxis2,
                   self.robot_trafo.acsAxis4]
        linear  = [self.robot_trafo.acsAxis3]
        return (
            all(abs(a.ActualPosition - a.Sollposition) <= _ARRIVED_TOL_DEG for a in angular)
            and
            all(abs(a.ActualPosition - a.Sollposition) <= _ARRIVED_TOL_MM  for a in linear)
        )

    def _trigger_auto_fault(self, reason: str):
        """
        Löst eine Automatik-Störung aus und setzt den Zustand zurück.

        Parameter
        ---------
        reason : str
            Beschreibung des Störungsgrunds (wird auf der Konsole ausgegeben).
        """
        self._fault      = True
        self._auto_state = _A_IDLE
        self._auto_tick  = 0
        self._cancel_vacuum()
        print(f"Auto-Fault: {reason}")

    def _set_mcs_target(self, local_x: float, local_y: float, local_z: float):
        """
        Setzt das kartesische Sollziel im Roboter-lokalen MCS.

        Schaltet auf kartesischen Modus (IK) und propagiert Z direkt
        auf acsAxis3, damit ``_is_at_target()`` sofort reagiert.
        """
        self._joint_mode = False
        self.robot_trafo.mcsAxisX.Sollposition = local_x
        self.robot_trafo.mcsAxisY.Sollposition = local_y
        self.robot_trafo.mcsAxisZ.Sollposition = local_z
        # Z direkt propagieren: mcsAxisZ = L3 + acsAxis3, L3 ist immer 0
        self.robot_trafo.acsAxis3.Sollposition = local_z

    def _activate_vacuum(self):
        """Aktiviert Vakuum: setzt internen Flag und färbt Saugnapf grün."""
        self._gripper_closed = True
        if hasattr(self.robot_view, "set_gripper"):
            self.robot_view.set_gripper(closed=True)
        if hasattr(self.robot_view, "attach_part"):
            self.robot_view.attach_part(True)

    def _cancel_vacuum(self):
        """Deaktiviert Vakuum: setzt internen Flag und färbt Saugnapf rot."""
        self._gripper_closed = False
        if hasattr(self.robot_view, "set_gripper"):
            self.robot_view.set_gripper(closed=False)
        if hasattr(self.robot_view, "attach_part"):
            self.robot_view.attach_part(False)

    def _tcp_rotation(self) -> float:
        """
        Gibt die TCP-Weltrotation in Grad zurück.

        Summe aus ACS-Gelenken plus Montagedrehung der View.
        Wird für die korrekte Ausrichtung abgelegter Bauteile verwendet.
        """
        joint_sum = (self.robot_trafo.acsAxis1.ActualPosition +
                     self.robot_trafo.acsAxis2.ActualPosition +
                     self.robot_trafo.acsAxis4.ActualPosition)
        return joint_sum + getattr(self.robot_view, 'rotation_z', 0.0)

    def _world_to_local(self, wx: float, wy: float):
        """
        Rechnet Weltkoordinaten in Roboter-lokale MCS-Koordinaten um.

        Berücksichtigt die Montagedrehung ``rotation_z`` der View sowie
        den Weltversatz ``position`` der Roboterbasis.

        Parameter
        ---------
        wx, wy : float
            Weltkoordinaten [mm].

        Rückgabe
        --------
        tuple(float, float)
            Lokale MCS-Koordinaten (lx, ly) [mm].
        """
        vp = self.robot_view.position
        dx = wx - vp[0]
        dy = wy - vp[1]
        rot = getattr(self.robot_view, 'rotation_z', 0.0)
        if abs(rot) < 0.01:
            return dx, dy
        r = -math.radians(rot)   # Inverse der Montagedrehung
        return (
            dx * math.cos(r) - dy * math.sin(r),
            dx * math.sin(r) + dy * math.cos(r),
        )

    def _local_to_world(self, lx: float, ly: float):
        """
        Rechnet Roboter-lokale MCS-Koordinaten in Weltkoordinaten um.

        Inverse zu ``_world_to_local()``.

        Parameter
        ---------
        lx, ly : float
            Lokale MCS-Koordinaten [mm].

        Rückgabe
        --------
        tuple(float, float)
            Weltkoordinaten (wx, wy) [mm].
        """
        vp  = self.robot_view.position
        rot = getattr(self.robot_view, 'rotation_z', 0.0)
        if abs(rot) < 0.01:
            return vp[0] + lx, vp[1] + ly
        r  = math.radians(rot)
        dx = lx * math.cos(r) - ly * math.sin(r)
        dy = lx * math.sin(r) + ly * math.cos(r)
        return vp[0] + dx, vp[1] + dy

    def _tcp_world_pos(self):
        """
        Berechnet die Weltposition der Saugnapf-Spitze aus den ACS-Istwerten.

        Rückgabe
        --------
        tuple(float, float, float)
            (wx, wy, wz) der TCP-Spitze in Weltkoordinaten [mm].
        """
        a1  = math.radians(self.robot_trafo.acsAxis1.ActualPosition)
        a2  = math.radians(self.robot_trafo.acsAxis2.ActualPosition)
        L1  = self.robot_trafo.L1
        L2  = self.robot_trafo.L2
        lx  = L1 * math.cos(a1) + L2 * math.cos(a1 + a2)
        ly  = L1 * math.sin(a1) + L2 * math.sin(a1 + a2)
        wx, wy = self._local_to_world(lx, ly)
        ref = getattr(self.robot_view, "tcp_z_ref", self.robot_view.position[2])
        return wx, wy, ref + self.robot_trafo.acsAxis3.ActualPosition

    def _world_z_to_mcs(self, world_z: float) -> float:
        """
        Rechnet eine absolute Welt-Z-Koordinate in den benötigten mcsAxisZ-Wert um.

        Da mcsAxisZ = tcp_z_ref + acsAxis3 (mit L3=0), gilt:
            mcsAxisZ = world_z - tcp_z_ref

        Parameter
        ---------
        world_z : float
            Absoluter Z-Wert in der 3D-Szene [mm].

        Rückgabe
        --------
        float
            Benötigter mcsAxisZ-Sollwert [mm].
        """
        ref = getattr(self.robot_view, "tcp_z_ref", self.robot_view.position[2])
        return world_z - ref

    def _clamp_local_to_reach(self, lx: float, ly: float):
        """
        Klemmt ein lokales MCS-Ziel auf den erreichbaren Ring des Arbeitsraums.

        Wenn das Ziel ausserhalb des Rings liegt, wird es in der gleichen
        Richtung auf die nächste erreichbare Position verschoben.  Der
        60-mm-Saugnapfradius überbrückt die verbleibende Lücke.

        Parameter
        ---------
        lx, ly : float
            Gewünschte lokale MCS-Koordinaten [mm].

        Rückgabe
        --------
        tuple(float, float)
            Geklemmte lokale Koordinaten innerhalb des Arbeitsraums [mm].
        """
        L_max = self.robot_trafo.L1 + self.robot_trafo.L2
        L_min = abs(self.robot_trafo.L1 - self.robot_trafo.L2)
        d = math.sqrt(lx ** 2 + ly ** 2)
        if d == 0.0:
            return lx, ly
        if d > L_max:
            f = L_max / d
            return lx * f, ly * f
        if d < L_min:
            f = L_min / d
            return lx * f, ly * f
        return lx, ly

    def _any_at_limit(self) -> bool:
        """Gibt True zurück wenn eine ACS-Achse an ihrer Softwarebegrenzung anliegt."""
        return any(a.is_at_limit() for a in [
            self.robot_trafo.acsAxis1, self.robot_trafo.acsAxis2,
            self.robot_trafo.acsAxis3, self.robot_trafo.acsAxis4,
        ])

    def _handle_manual_control(self, hmi_ctrl,
                                step_joint: float = 1.0,
                                step_world: float = 2.0) -> bool:
        """
        Übersetzt HMI-Jogtasten in Sollpositions-Inkremente.

        Parameter
        ---------
        hmi_ctrl : hmiControl
            Aktueller HMI-Steuerbefehl.
        step_joint : float
            Schrittweite im Gelenkkoordinatensystem [Grad].
        step_world : float
            Schrittweite im kartesischen System [mm].

        Rückgabe
        --------
        bool
            True = Gelenkkoordinaten (jog_joint), False = kartesisch.
        """
        coord_system = getattr(hmi_ctrl, "CoordSystem", "Joint")
        if coord_system not in ["Joint", "Welt", "Werkzeug"]:
            coord_system = "Joint"
        if coord_system == "Joint":
            da1, da2, da3, da4 = self._jog_delta(hmi_ctrl, step_joint)
            self.robot_trafo.jog_joint(da1, da2, da3, da4)
            return True
        dx, dy, dz, dr = self._jog_delta(hmi_ctrl, step_world)
        # Welt-Jog: Inkrement in Roboter-lokales KS drehen (Montagedrehung berücksichtigen)
        rot = getattr(self.robot_view, 'rotation_z', 0.0)
        if abs(rot) > 0.01:
            r  = -math.radians(rot)
            dx, dy = (dx * math.cos(r) - dy * math.sin(r),
                      dx * math.sin(r) + dy * math.cos(r))
        if coord_system == "Welt":
            self.robot_trafo.jog_world(dx, dy, dz, dr)
        else:
            self.robot_trafo.jog_tool(dx, dy, dz, dr)
        return False

    def _jog_delta(self, hmi_ctrl, step: float):
        """
        Berechnet das Jog-Inkrement aus den gedrückten HMI-Tasten.

        Parameter
        ---------
        hmi_ctrl : hmiControl
            Aktueller HMI-Steuerbefehl.
        step : float
            Schrittweite pro Tick (positiver Wert).

        Rückgabe
        --------
        tuple(float, float, float, float)
            (dx, dy, dz, dr) — Inkremente für alle vier Freiheitsgrade.
        """
        dx = (step if hmi_ctrl.MoveXPlus else 0.0) - (step if hmi_ctrl.MoveXNeg else 0.0)
        dy = (step if hmi_ctrl.MoveYPlus else 0.0) - (step if hmi_ctrl.MoveYNeg else 0.0)
        dz = (step if hmi_ctrl.MoveZPlus else 0.0) - (step if hmi_ctrl.MoveZNeg else 0.0)
        dr = (step if hmi_ctrl.MoveRPlus else 0.0) - (step if hmi_ctrl.MoveRNeg else 0.0)
        return dx, dy, dz, dr

    def _update_hmi_state(self):
        """
        Schreibt die aktuellen ACS-Istwerte und die berechnete TCP-Weltposition
        in das hmiState-DTO für die HMI-Anzeige.
        """
        a1_act = self.robot_trafo.acsAxis1.ActualPosition
        a2_act = self.robot_trafo.acsAxis2.ActualPosition
        a3_act = self.robot_trafo.acsAxis3.ActualPosition
        a4_act = self.robot_trafo.acsAxis4.ActualPosition
        self.hmi_state.axisJ1Position = a1_act
        self.hmi_state.axisJ2Position = a2_act
        self.hmi_state.axisJ3Position = a3_act
        self.hmi_state.axisJ4Position = a4_act

        # TCP-Weltposition aus ACS-Istwerten via FK + Koordinatentransformation
        r1 = math.radians(a1_act)
        r2 = math.radians(a2_act)
        L1 = self.robot_trafo.L1
        L2 = self.robot_trafo.L2
        lx = L1 * math.cos(r1) + L2 * math.cos(r1 + r2)
        ly = L1 * math.sin(r1) + L2 * math.sin(r1 + r2)
        wx, wy = self._local_to_world(lx, ly)
        self.hmi_state.axisXPosition = wx
        self.hmi_state.axisYPosition = wy
        self.hmi_state.axisZPosition = a3_act
        self.hmi_state.axisRPosition = a1_act + a2_act + a4_act
