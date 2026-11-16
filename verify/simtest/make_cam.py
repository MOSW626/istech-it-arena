"""World with a static camera car (camera 7.8 cm high, VFOV 42.5 deg, 640x480) at one pose.
usage: python make_cam.py <output_dir> <out.sdf> <x> <y> <yaw_rad> <frames_dir>"""
import sys
out, dst, x, y, yaw, frames = sys.argv[1], sys.argv[2], *map(float, sys.argv[3:6]), sys.argv[6]
PLUG = """
<plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
<plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
<plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors"><render_engine>ogre2</render_engine></plugin>
"""
CAM = f"""
<model name="camcar"><static>true</static><pose>{x} {y} 0 0 0 {yaw}</pose>
 <link name="body">
  <visual name="v"><pose>0 0 0.03 0 0 0</pose><geometry><box><size>0.20 0.15 0.06</size></box></geometry></visual>
  <sensor name="cam" type="camera"><pose>0.10 0 0.078 0 0 0</pose>
   <camera><horizontal_fov>0.958</horizontal_fov><image><width>640</width><height>480</height></image>
    <clip><near>0.02</near><far>20</far></clip><save enabled="true"><path>{frames}</path></save></camera>
   <always_on>1</always_on><update_rate>5</update_rate></sensor>
 </link></model>
"""
w = open(f"{out}/world.sdf").read()
i = w.index(">", w.index("<world")) + 1
w = w[:i] + PLUG + w[i:]
j = w.rindex("</world>")
open(dst, "w").write(w[:j] + CAM + w[j:])
print("CAM_WORLD_OK")
