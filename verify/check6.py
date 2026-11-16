"""Gate for the 610mm right-angle course (2026-11-05).
Checks the generated output against the build PDF's own tables, not against
the design json it was generated from.
usage: python check6.py <pdf_text.txt> <output_dir>"""
import re, sys
import numpy as np
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

txt, out = open(sys.argv[1]).read(), sys.argv[2]
fails = []


def gate(name, ok, detail=""):
    print(("PASS" if ok else "FAIL"), name, detail)
    if not ok:
        fails.append(name)


# --- PDF tables ------------------------------------------------------------
P = {m[0]: tuple(map(float, m[1:])) for m in re.findall(
    r"(P\d\d)\s+([\d.]+) / ([\d.]+)\s+([\d.]+) × ([\d.]+)", txt)}
W = {m[0]: tuple(map(float, m[1:])) for m in re.findall(
    r"(W\d\d) [GE]\d\d \d+\s+\(([\d.]+), ([\d.]+)\) → \(([\d.]+), ([\d.]+)\)", txt)}
gate("pdf parsed P01..P22", sorted(P) == [f"P{i:02d}" for i in range(1, 23)], f"{len(P)}")
gate("pdf parsed W01..W61", sorted(W) == [f"W{i:02d}" for i in range(1, 62)], f"{len(W)}")

p21 = Polygon([(2.785, 2.458579), (2.785, 2.741421), (4.021421, 1.505), (3.738579, 1.505)])
pieces = [box(x, y, x + w / 1000, y + h / 1000) for k, (x, y, w, h) in P.items() if k != "P21"]
road_pdf = unary_union(pieces + [p21])

# --- generated drivable area = what scene / map says is road -----------------
cl = np.loadtxt(f"{out}/centerline.csv", delimiter=",", skiprows=1)
lb = np.loadtxt(f"{out}/left_boundary.csv", delimiter=",", skiprows=1)
rb = np.loadtxt(f"{out}/right_boundary.csv", delimiter=",", skiprows=1)
ring = Polygon(lb[:, :2]).symmetric_difference(Polygon(rb[:, :2]))   # annulus between the two edges
main_pdf = unary_union([box(x, y, x + w / 1000, y + h / 1000) for k, (x, y, w, h) in P.items()
                        if k not in ("P21", "P22")])
d = ring.symmetric_difference(main_pdf).area
gate("main road (boundary CSVs) == P01..P20", d < 1e-4, f"symdiff {d * 1e4:.2f} cm2")

L = float(cl[-1, 2]) + float(np.hypot(*(cl[-1, :2] - cl[0, :2])))
gate("lap length 44.64 m", abs(L - 44.64) < 0.005, f"{L:.4f}")
gate("track width 0.61", np.allclose(cl[:, 3], 0.61))

br = [np.loadtxt(f"{out}/branch_{i}.csv", delimiter=",", skiprows=1) for i in (0, 1)]
for i, b in enumerate(br):
    gate(f"branch_{i} width 0.20", np.allclose(b[:, 3], 0.20))
drv = unary_union([ring] + [LineString(b[:, :2]).buffer(0.1) for b in br])
d = drv.symmetric_difference(road_pdf).area
gate("drivable (main + branches) == P01..P22", d < 5e-3, f"symdiff {d * 1e4:.1f} cm2 (branch caps lie on road)")
# P21/P22 footprint exactly: branch strip clipped off the main road must equal the PDF piece
for name, b, piece in (("P22", br[0], box(4.615, 4.4, 5.835, 4.6)), ("P21", br[1], p21)):
    strip = LineString(b[:, :2]).buffer(0.1, cap_style="flat").difference(main_pdf)
    d = strip.symmetric_difference(piece).area
    gate(f"{name} strip off main road == pdf piece", d < 1e-4, f"symdiff {d * 1e4:.2f} cm2")

# --- walls: world.sdf wall boxes vs W01..W61 inner faces ---------------------
sdf = open(f"{out}/world.sdf").read()
link = sdf[sdf.index('<link name="walls">'):]
link = link[:link.index("</link>")]
walls, heights = [], set()
for pose, size in re.findall(r"<collision[^>]*>\s*<pose>([^<]+)</pose>\s*<geometry><box><size>([^<]+)</size>", link):
    x, y, z, _, _, yaw = map(float, pose.split())
    sx, sy, sz = map(float, size.split())
    heights.add(sz)
    c, s = np.cos(yaw), np.sin(yaw)
    walls.append(Polygon([(x + a * c - b_ * s, y + a * s + b_ * c)
                          for a, b_ in ((-sx / 2, -sy / 2), (sx / 2, -sy / 2), (sx / 2, sy / 2), (-sx / 2, sy / 2))]))
wall_u = unary_union(walls)
gate("wall height 0.40", heights == {0.4}, f"{heights}")
# every W segment (pdf: the wall's road-side face) must be covered by a wall box
bad, tot = [], 0.0
for k, (x0, y0, x1, y1) in sorted(W.items()):
    seg = LineString([(x0, y0), (x1, y1)])
    tot += seg.length
    covered = seg.buffer(0.001, cap_style="flat").difference(wall_u.buffer(0.002)).area
    if covered > 1e-7:
        bad.append(k)
gate("W01..W61 all lie on a wall face", not bad, f"missing: {bad}")
extra = wall_u.difference(unary_union([LineString([(x0, y0), (x1, y1)]).buffer(0.06, cap_style="square")
                                        for x0, y0, x1, y1 in W.values()])).area
gate("no wall where the pdf has none", extra < 1e-6, f"{extra * 1e4:.3f} cm2")
gate("W total 89.06 m", abs(tot - 89.06) < 0.02, f"{tot:.3f}")
gate("no wall on road", wall_u.intersection(road_pdf).area < 1e-6, f"{wall_u.intersection(road_pdf).area * 1e4:.3f} cm2")
# the small triangle beside P21 has no wall (pdf p.4)
tri = Polygon([(2.985, 1.705), (2.985, 2.10), (3.38, 1.705)])
gate("P21 triangle island: no wall", wall_u.intersection(tri).area < 1e-6)
gate("P22 island walled (W57..W61)", all(k not in bad for k in ("W57", "W58", "W59", "W60", "W61")))

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAIL {fails}")
sys.exit(1 if fails else 0)
