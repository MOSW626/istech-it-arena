"""Runs inside gzcheck:jazzy next to `gz sim -s -r world_car.sdf`.
Pure pursuit along route.csv with a car-like turn-radius limit; logs ground-truth pose.
usage: python3 drive.py <workdir>"""
import math, sys, time, threading
import numpy as np
from gz.transport13 import Node
from gz.msgs10.twist_pb2 import Twist
from gz.msgs10.pose_pb2 import Pose

wd = sys.argv[1]
route = np.loadtxt(f"{wd}/route.csv", delimiter=",")
LOOK, V, RMIN = 0.35, 1.0, 0.40        # lookahead m, cruise m/s, min turn radius m (Ackermann-like)
node = Node()
pub = node.advertise("/car/cmd_vel", Twist)
log, state = [], dict(i=0, done=False, last=time.time())
lock = threading.Lock()


def on_pose(msg):
    with lock:
        if state["done"]:
            return
        state["last"] = time.time()
        t = msg.header.stamp.sec + msg.header.stamp.nsec * 1e-9
        p, q = msg.position, msg.orientation
        roll = math.atan2(2 * (q.w * q.x + q.y * q.z), 1 - 2 * (q.x ** 2 + q.y ** 2))
        pitch = math.asin(max(-1, min(1, 2 * (q.w * q.y - q.z * q.x))))
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y ** 2 + q.z ** 2))
        log.append((t, p.x, p.y, p.z, roll, pitch, yaw, state["i"]))
        i0 = state["i"]
        seg = route[i0:i0 + 80]                          # search only just ahead: lap 2 overlaps lap 1
        state["i"] = i = i0 + int(np.argmin(np.hypot(seg[:, 0] - p.x, seg[:, 1] - p.y)))
        j = i
        while j < len(route) - 1 and math.hypot(route[j, 0] - p.x, route[j, 1] - p.y) < LOOK:
            j += 1
        cmd = Twist()
        if i >= len(route) - 3:
            state["done"] = True
        else:
            a = math.atan2(route[j, 1] - p.y, route[j, 0] - p.x) - yaw
            a = math.atan2(math.sin(a), math.cos(a))
            k = max(-1 / RMIN, min(1 / RMIN, 2 * math.sin(a) / LOOK))
            v = V / (1 + 0.4 * abs(k))
            cmd.linear.x, cmd.angular.z = v, v * k
        pub.publish(cmd)


node.subscribe(Pose, "/model/car/pose", on_pose)
t_wall = time.time()
while True:
    time.sleep(0.5)
    with lock:
        if state["done"] or time.time() - state["last"] > 20 or time.time() - t_wall > 900:
            break
pub.publish(Twist())
with lock:
    np.savetxt(f"{wd}/drive_log.csv", np.array(log), delimiter=",", fmt="%.5f",
               header="t,x,y,z,roll,pitch,yaw,route_i", comments="")
    t_sim = log[-1][0] - log[0][0] if log else 0
    print(f"DRIVE_END done={state['done']} route_i={state['i']}/{len(route)} sim_s={t_sim:.1f} "
          f"wall_s={time.time() - t_wall:.1f} samples={len(log)}")
