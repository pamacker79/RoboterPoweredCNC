import time
from viewModel_Tiago import RobotViewer

def main():
    print("Initialisiere den Roboter...")
    

    robot = RobotViewer()
    

    robot.show()
    
    print("Starte externe Steuerung...")
    
    # 3. Externe Animationsschleife
    for step in range(5000):
        robot.update_joints(inner_angle=-step, outer_angle=step, spindle_angle=0)
        
        print(f"Schritt: {step} | Äusserer Arm Winkel: {step} | Innerer Arm Winkel: {-step}")
        
        time.sleep(0.2)
        
    print("Animation beendet.")
    robot.close()

# Startpunkt des Skripts
if __name__ == "__main__":
    main()