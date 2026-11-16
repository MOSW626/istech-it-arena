"""Inside container: wait for one camera frame and save it as raw RGB .npy. usage: python3 grab.py <out.npy>"""
import sys, time, numpy as np
from gz.transport13 import Node
from gz.msgs10.image_pb2 import Image
got = {}
def cb(m):
    if "img" not in got and m.width:
        got["img"] = np.frombuffer(m.data, np.uint8).reshape(m.height, m.width, -1).copy()
n = Node(); n.subscribe(Image, "/world/it_arena_track/model/camcar/link/body/sensor/cam/image", cb)
t = time.time()
while "img" not in got and time.time() - t < 150:
    time.sleep(0.2)
time.sleep(1.0); got.pop("img", None); t2 = time.time()      # skip first frame (textures may still load)
while "img" not in got and time.time() - t2 < 30:
    time.sleep(0.2)
if "img" in got:
    np.save(sys.argv[1], got["img"]); print("GRAB_OK", got["img"].shape, f"{time.time()-t:.1f}s")
else:
    print("GRAB_NONE")
