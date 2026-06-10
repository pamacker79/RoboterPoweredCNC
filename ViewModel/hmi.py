
import sys
sys.path.append('../ViewModel')

import tkinter as tk
from tkinter import ttk
from hmiControl import hmiControl
from hmiState import hmiState
from tkinter import ttk, messagebox

class Hmi:
    def __init__(self, parent, nameofHmi):
        self.root = tk.Frame(
    parent,
    bg="lightblue",
    width=400,
    height=400,
    relief="ridge",
    borderwidth=2
)

        self.root.pack(side="left", padx=5)
        self.root.pack_propagate(False)

        # Instanz der Steuerung
        self.hmiControl = hmiControl()
        self.hmiState = hmiState()
        self.step = 1

        # Layout
        links = 10
        rechts = 250
        unten = 350


        # ---------------- EVENTS ----------------

        def on_coord_changed(event):
            selected = combo_axis.get()
            self.hmiControl.CoordSystem = selected
            print(f"Koordinatensystem geändert auf: {selected}")

        def on_mode_changed(event):
            selected = combo_mode.get()

            if selected == "Hand":
                self.hmiControl.OperationMode = 0
            elif selected == "Automatisch":
                self.hmiControl.OperationMode = 1

            print(f"Betriebsmodus geändert auf: {selected}")

        def on_start_click():
            self.hmiControl.Start = True
            self.hmiControl.Stop = False
            print("Start")

        def on_stop_click():
            self.hmiControl.Start = False
            self.hmiControl.Stop = True
            print("Stop")


        # ---------------- UI ----------------

        titel = tk.Label(
            self.root,
            text=nameofHmi,
            bg="lightblue",
            font=("Arial", 12, "bold")
        )
        titel.pack(pady=5)

        button_start = tk.Button(
            self.root,
            text="Start",
            width=15,
            command=on_start_click
        )
        button_start.place(x=links, y=unten)

        button_stop = tk.Button(
            self.root,
            text="Stop",
            width=15,
            command=on_stop_click
        )
        button_stop.place(x=rechts, y=unten)

        # Koordinatensystem
        combo_axis = ttk.Combobox(
            self.root,
            values=["Welt", "Joint", "Werkzeug"],
            state="readonly"
        )
        combo_axis.set("wählen")
        combo_axis.bind("<<ComboboxSelected>>", on_coord_changed)
        combo_axis.place(x=links, y=40)

        # Betriebsart
        combo_mode = ttk.Combobox(
            self.root,
            values=["Hand", "Automatisch"],
            state="readonly"
        )
        combo_mode.set("wählen")
        combo_mode.bind("<<ComboboxSelected>>", on_mode_changed)
        combo_mode.place(x=rechts, y=40)

        # Beschriftungen
        self.LabelPos1 = tk.Label(self.root, text="X :", bg="lightblue")
        self.LabelPos1.place(x=10, y=100)

        self.LabelPos2 = tk.Label(self.root, text="Y :", bg="lightblue")
        self.LabelPos2.place(x=10, y=130)

        self.LabelPos3 = tk.Label(self.root, text="Z :", bg="lightblue")
        self.LabelPos3.place(x=10, y=160)

        self.LabelPos4 = tk.Label(self.root, text="R :", bg="lightblue")
        self.LabelPos4.place(x=10, y=190)

        # X
        self.x_label = tk.Label(self.root, text="0", bg="lightblue")
        self.x_label.place(x=200, y=100)

        self.ButtonXPlus = tk.Button(self.root, text="+", width=3)
        self.ButtonXPlus.place(x=80, y=95)
        self.ButtonXPlus.bind("<Button-1>", lambda event: self.x_plus(True))
        self.ButtonXPlus.bind("<ButtonRelease-1>", lambda event: self.x_plus(False))

        self.ButtonXNeg = tk.Button(self.root, text="-", width=3)
        self.ButtonXNeg.place(x=120, y=95)
        self.ButtonXNeg.bind("<Button-1>", lambda event: self.x_minus(True))
        self.ButtonXNeg.bind("<ButtonRelease-1>", lambda event: self.x_minus(False))

        # Y
        self.y_label = tk.Label(self.root, text="0", bg="lightblue")
        self.y_label.place(x=200, y=130)

        self.ButtonYPlus = tk.Button(self.root, text="+", width=3)
        self.ButtonYPlus.place(x=80, y=125)
        self.ButtonYPlus.bind("<Button-1>", lambda event: self.y_plus(True))
        self.ButtonYPlus.bind("<ButtonRelease-1>", lambda event: self.y_plus(False))

        self.ButtonYNeg = tk.Button(self.root, text="-", width=3)
        self.ButtonYNeg.place(x=120, y=125)
        self.ButtonYNeg.bind("<Button-1>", lambda event: self.y_minus(True))
        self.ButtonYNeg.bind("<ButtonRelease-1>", lambda event: self.y_minus(False))

        # Z
        self.z_label = tk.Label(self.root, text="0", bg="lightblue")
        self.z_label.place(x=200, y=160)

        self.ButtonZPlus = tk.Button(self.root, text="+", width=3)
        self.ButtonZPlus.place(x=80, y=155)
        self.ButtonZPlus.bind("<Button-1>", lambda event: self.z_plus(True))
        self.ButtonZPlus.bind("<ButtonRelease-1>", lambda event: self.z_plus(False))

        self.ButtonZNeg = tk.Button(self.root, text="-", width=3)
        self.ButtonZNeg.place(x=120, y=155)
        self.ButtonZNeg.bind("<Button-1>", lambda event: self.z_minus(True))
        self.ButtonZNeg.bind("<ButtonRelease-1>", lambda event: self.z_minus(False))

        # R
        self.r_label = tk.Label(self.root, text="0", bg="lightblue")
        self.r_label.place(x=200, y=190)

        self.ButtonRPlus = tk.Button(self.root, text="+", width=3)
        self.ButtonRPlus.place(x=80, y=185)
        self.ButtonRPlus.bind("<Button-1>", lambda event: self.r_plus(True))
        self.ButtonRPlus.bind("<ButtonRelease-1>", lambda event: self.r_plus(False))

        self.ButtonRNeg = tk.Button(self.root, text="-", width=3)
        self.ButtonRNeg.place(x=120, y=185)
        self.ButtonRNeg.bind("<Button-1>", lambda event: self.r_minus(True))
        self.ButtonRNeg.bind("<ButtonRelease-1>", lambda event: self.r_minus(False))

    def is_hand_mode(self):
        return self.hmiControl.OperationMode == 0
    
    def x_plus(self,value):
        self.hmiControl.MoveXPlus = value
        if value and self.is_hand_mode():
            self.hmiState.axisXPosition += 1
            self.x_label["text"] = self.hmiState.axisXPosition   
        print("xplus")

    def x_minus(self,value):
        self.hmiControl.MoveXNeg = value
        if value and self.is_hand_mode():
            self.hmiState.axisXPosition -= 1
            self.x_label["text"] = self.hmiState.axisXPosition
        print("xminus")

    def y_plus(self,value):
        self.hmiControl.MoveYPlus = value
        if value and self.is_hand_mode():
            self.hmiState.axisYPosition += 1
            self.y_label["text"] = self.hmiState.axisYPosition
        print("yplus")        

    def y_minus(self,value):    
        self.hmiControl.MoveYNeg = value
        if value and self.is_hand_mode():
            self.hmiState.axisYPosition -= 1
            self.y_label["text"] = self.hmiState.axisYPosition
        print("yminus")

    def z_plus(self,value):

        self.hmiControl.MoveZPlus = value
        if value and self.is_hand_mode():
            self.hmiState.axisZPosition += 1
            self.z_label["text"] = self.hmiState.axisZPosition
        print("zplus")    

    def z_minus(self,value):
        self.hmiControl.MoveZNeg = value
        if value and self.is_hand_mode():
            self.hmiState.axisZPosition -= 1
            self.z_label["text"] = self.hmiState.axisZPosition
        print("zminus")    

    def r_plus(self,value):
        self.hmiControl.MoveRPlus = value
        if value and self.is_hand_mode():
            self.hmiState.axisRPosition += 1
            self.r_label["text"] = self.hmiState.axisRPosition
        print("rplus")    

    def r_minus(self,value):
        self.hmiControl.MoveRNeg = value
        if value and self.is_hand_mode():
            self.hmiState.axisRPosition -= 1
            self.r_label["text"] = self.hmiState.axisRPosition
        print("rminus")    

    def getHmiControl(self):
        return self.hmiControl
    
    def setHmiState(self,hmiState):
        self.hmiState = hmiState
        self.x_label["text"] = self.hmiState.axisXPosition
        self.y_label["text"] = self.hmiState.axisYPosition
        self.z_label["text"] = self.hmiState.axisZPosition
        self.r_label["text"]= self.hmiState.axisRPosition

if __name__ == "__main__":

    root = tk.Tk()
    root.title("3 Roboter")
    root.geometry("1200x450")

    frame1 = tk.Frame(root)
    frame1.pack(side="left", padx=5)

    frame2 = tk.Frame(root)
    frame2.pack(side="left", padx=5)

    frame3 = tk.Frame(root)
    frame3.pack(side="left", padx=5)

    hmi1 = Hmi(frame1, "Roboter Scara")
    hmi2 = Hmi(frame2, "Roboter Hbot")
    hmi3 = Hmi(frame3, "Roboter 3")



    root.mainloop()