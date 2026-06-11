"""
Module: Axis
Purpose: Single motion axis with software limit enforcement.
Responsibilities: Clamp Sollposition to [min_pos, max_pos], expose at-limit flag, cyclic update.
Inputs:  Sollposition writes (from HMI jog, CNC waypoints, or kinematics results).
Outputs: ActualPosition (updated by cyclic()), is_at_limit() flag.
Dependencies: none
"""


class Axis:
    def __init__(self, min_pos=None, max_pos=None):
        self._sollposition = 0.0
        self.ActualPosition = 0.0
        self.min_pos = min_pos
        self.max_pos = max_pos
        self._at_limit = False

    @property
    def Sollposition(self):
        return self._sollposition

    @Sollposition.setter
    def Sollposition(self, value):
        if self.min_pos is not None and value < self.min_pos:
            value = self.min_pos
            self._at_limit = True
        elif self.max_pos is not None and value > self.max_pos:
            value = self.max_pos
            self._at_limit = True
        else:
            self._at_limit = False
        self._sollposition = value

    def is_at_limit(self):
        return self._at_limit

    def set_limits(self, min_pos, max_pos):
        self.min_pos = min_pos
        self.max_pos = max_pos

    def getActualPosition(self):
        return self.ActualPosition

    def getSetPosition(self):
        return self._sollposition

    def cyclic(self):
        self.ActualPosition = self._sollposition


if __name__ == "__main__":
    # Unit tests
    a = Axis(-10.0, 10.0)
    a.Sollposition = 15.0
    assert a.Sollposition == 10.0 and a.is_at_limit(), "upper clamp failed"

    a.Sollposition = -20.0
    assert a.Sollposition == -10.0 and a.is_at_limit(), "lower clamp failed"

    a.Sollposition = 5.0
    assert a.Sollposition == 5.0 and not a.is_at_limit(), "in-range failed"

    b = Axis()
    b.Sollposition = 999.0
    assert b.Sollposition == 999.0, "unbounded axis should not clamp"

    b.Sollposition = 5.0
    b.cyclic()
    assert b.ActualPosition == 5.0, "cyclic failed"

    print("Alle Axis-Tests bestanden.")
