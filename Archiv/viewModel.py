import pyvista as pv
import os

cwd = os.getcwd()
filename = cwd+"\\View\\data\\Base.stl"
reader = pv.get_reader(filename)
BaseMesh = reader.read()

filename = cwd+"\\View\\data\\InnerArm.stl"
reader = pv.get_reader(filename)
InnerArmMesh = reader.read()

pl = pv.Plotter()
base = pl.add_mesh(BaseMesh)
actor = pl.add_mesh(InnerArmMesh)


def callback(step):
    base.position = [step, step, 0]
    print(actor.position)


pl.add_timer_event(max_steps=5000, duration=200, callback=callback)

cpos = pv.CameraPosition(
    position=(0.0, -1500.0, 850.0), focal_point=(0.0, 0.0, 0.0), viewup=(0.0, 1.0, 0.0)
)
pl.show(cpos=cpos)