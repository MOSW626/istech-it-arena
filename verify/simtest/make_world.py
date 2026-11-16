"""Build drive-test inputs from a track output dir (host side, stdlib + numpy).
usage: python make_world.py <output_dir> <workdir>
Writes <workdir>/world_car.sdf (track world + 15x20 cm test car at front grid slot)
and <workdir>/route.csv (lap 1 main loop, lap 2 through both shortcuts)."""
import json, sys
import numpy as np

out, wd = sys.argv[1], sys.argv[2]
scene = json.load(open(f"{out}/scene.json"))
slot = max(scene["starting_grid"]["slots"], key=lambda g: g["s_m"])      # front slot
x0, y0, yaw0 = slot["x"], slot["y"], slot["yaw_rad"]

# test car: 0.20 x 0.15 footprint, rear-wheel diff drive, front frictionless casters
CAR = f"""
<model name="car">
  <pose>{x0} {y0} 0.04 0 0 {yaw0}</pose>
  <link name="chassis">
    <pose>0 0 0.035 0 0 0</pose>
    <inertial><mass>1.5</mass><inertia><ixx>0.004</ixx><iyy>0.006</iyy><izz>0.008</izz><ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia></inertial>
    <collision name="c"><geometry><box><size>0.20 0.10 0.05</size></box></geometry></collision>
    <visual name="v"><geometry><box><size>0.20 0.10 0.05</size></box></geometry></visual>
  </link>
  {''.join(f'''
  <link name="{n}">
    <pose>-0.065 {sy*0.0625} 0.0 -1.5708 0 0</pose>
    <inertial><mass>0.1</mass><inertia><ixx>3e-5</ixx><iyy>3e-5</iyy><izz>6e-5</izz><ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia></inertial>
    <collision name="c"><geometry><cylinder><radius>0.033</radius><length>0.025</length></cylinder></geometry>
      <surface><friction><ode><mu>1.0</mu><mu2>1.0</mu2></ode></friction></surface></collision>
    <visual name="v"><geometry><cylinder><radius>0.033</radius><length>0.025</length></cylinder></geometry></visual>
  </link>
  <joint name="{n}_j" type="revolute"><parent>chassis</parent><child>{n}</child><axis><xyz>0 0 1</xyz></axis></joint>'''
  for n, sy in (("wl", 1), ("wr", -1)))}
  {''.join(f'''
  <link name="{n}">
    <pose>0.065 {sy*0.0625} -0.008 0 0 0</pose>
    <inertial><mass>0.05</mass><inertia><ixx>1e-5</ixx><iyy>1e-5</iyy><izz>1e-5</izz><ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia></inertial>
    <collision name="c"><geometry><sphere><radius>0.025</radius></sphere></geometry>
      <surface><friction><ode><mu>0</mu><mu2>0</mu2></ode></friction></surface></collision>
  </link>
  <joint name="{n}_j" type="ball"><parent>chassis</parent><child>{n}</child></joint>'''
  for n, sy in (("cl", 1), ("cr", -1)))}
  <plugin filename="gz-sim-diff-drive-system" name="gz::sim::systems::DiffDrive">
    <left_joint>wl_j</left_joint><right_joint>wr_j</right_joint>
    <wheel_separation>0.125</wheel_separation><wheel_radius>0.033</wheel_radius>
    <topic>/car/cmd_vel</topic>
  </plugin>
  <plugin filename="gz-sim-pose-publisher-system" name="gz::sim::systems::PosePublisher">
    <publish_link_pose>false</publish_link_pose><publish_model_pose>true</publish_model_pose>
    <use_pose_vector_msg>false</use_pose_vector_msg><update_frequency>100</update_frequency>
  </plugin>
</model>
"""
w = open(f"{out}/world.sdf").read()
i = w.rindex("</world>")
open(f"{wd}/world_car.sdf", "w").write(w[:i] + CAR + w[i:])

# route
cl = np.loadtxt(f"{out}/centerline.csv", delimiter=",", skiprows=1)
s = cl[:, 2]
L = s[-1] + np.hypot(*(cl[-1, :2] - cl[0, :2]))
br = [(b, np.loadtxt(f"{out}/branch_{i}.csv", delimiter=",", skiprows=1))
      for i, b in enumerate(scene["branches"])]
s_front = slot["s_m"]
main1 = np.vstack([cl[s >= s_front, :2], cl[s < s_front, :2]])  # one full lap from the grid
lap2 = [cl[s < br[0][0]["s0_m"], :2], br[0][1][:, :2],
        cl[(s > br[0][0]["s1_m"]) & (s < br[1][0]["s0_m"]), :2], br[1][1][:, :2],
        cl[s > br[1][0]["s1_m"], :2], cl[s < s_front + 1.5, :2]]
route = np.vstack([main1] + lap2)
np.savetxt(f"{wd}/route.csv", route, delimiter=",", fmt="%.5f")
print(f"MAKE_OK slot=({x0},{y0}) L={L:.3f} route_pts={len(route)}")
