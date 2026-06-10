import os

class Axis:
    def __init__(self):
        self.ActualPosition = 0
        self.Sollposition = 0
    
    def getActualPosition(self):
        return self.ActualPosition
    
    def getSetPosition(self):
        return self.Sollposition

    def cyclic(self):
        self.ActualPosition = self.Sollposition

if __name__ == "__main__":
    testaxis = Axis()
    print (testaxis.getActualPosition())