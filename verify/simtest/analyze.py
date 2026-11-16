"""Judge a drive log against the track geometry (host side).
usage: python analyze.py <output_dir> <workdir>"""
import re, sys
import numpy as np
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
from shapely import affinity

out, wd = sys.argv[1], sys.argv[2]
d = np.loadtxt(f"{wd}/drive_log.csv", delimiter=",", skiprows=1)
t, x, y, z, roll, pitch, yaw = d[:, :7].T
sdf = open(f"{out}/world.sdf").read()


def boxes(link):
    body = re.search(rf'<link name="{link}">(.*?)</link>', sdf, re.S).group(1)
    polys = []
    for pose, size in re.findall(r"<collision[^>]*>\s*<pose>([^<]+)</pose>\s*<geometry><box><size>([^<]+)</size>", body):
        px, py, _, _, _, pyaw = map(float, pose.split()); sx, sy, _ = map(float, size.split())
        polys.append(affinity.translate(affinity.rotate(Polygon([(-sx/2, -sy/2), (sx/2, -sy/2), (sx/2, sy/2), (-sx/2, sy/2)]),
                                                        pyaw, use_radians=True, origin=(0, 0)), px, py))
    return unary_union(polys)


walls, road = boxes("walls"), boxes("track_surface")
fails = []
def gate(name, ok, detail):
    print("PASS" if ok else "FAIL", name, detail)
    if not ok: fails.append(name)

fp = [affinity.translate(affinity.rotate(Polygon([(-.1, -.075), (.1, -.075), (.1, .075), (-.1, .075)]), a, use_radians=True, origin=(0, 0)), px, py)
      for px, py, a in zip(x[::5], y[::5], yaw[::5])]
wd_min = min(walls.distance(f) for f in fp)
gate("no wall contact (footprint 0.20x0.15)", wd_min > 0.0, f"min wall distance {wd_min*100:.1f} cm")
off = np.array([f.difference(road).area / f.area for f in fp])
gate("footprint stays on road surface", off.max() < 0.5, f"max off-road share {off.max()*100:.1f}% , samples >0: {np.mean(off > 0.001)*100:.1f}%")
# settled ride height after spawn drop
m = t > t[0] + 2.0
dz = z[m].max() - z[m].min()
gate("no bumps at tile seams (chassis z range)", dz < 0.004, f"z range {dz*1000:.2f} mm")
gate("no tilt (roll/pitch)", max(abs(roll[m]).max(), abs(pitch[m]).max()) < np.radians(2),
     f"max roll {np.degrees(abs(roll[m]).max()):.2f} deg, pitch {np.degrees(abs(pitch[m]).max()):.2f} deg")
sp = np.hypot(np.diff(x), np.diff(y)) / np.maximum(np.diff(t), 1e-6)
win = int(1.0 / np.median(np.diff(t)))
moving = np.convolve(sp, np.ones(win) / win, mode="valid")
gate("never stuck (1 s mean speed > 0.1 m/s after start)", moving[win:].min() > 0.1, f"min 1s-mean speed {moving[win:].min():.2f} m/s")
lp = LineString(np.c_[x, y]).length
print(f"distance driven {lp:.1f} m in {t[-1]-t[0]:.1f} s sim")
print("\nRESULT:", "DRIVE_ALL_PASS" if not fails else f"FAIL {fails}")
sys.exit(1 if fails else 0)
