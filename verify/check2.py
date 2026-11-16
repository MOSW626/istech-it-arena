#!/usr/bin/env python3
"""Round-2 verification (issue #13 fix) against v2026.09.01 baseline."""
import sys, json, math, subprocess, filecmp
import xml.etree.ElementTree as ET
from pathlib import Path

VDIR = Path(__file__).parent
REPO = Path("/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/istech-it-arena")
TRACK = REPO / "track"
NEW = TRACK / "output_final"
BASE = VDIR.parent / "verify-0901" / "release_new" / "output_final"   # v2026.09.01
VENV = str(VDIR.parent / "venv/bin/python3")

def die(m): print("FAIL:", m); sys.exit(1)

def links(p): return ET.parse(p).getroot().findall(".//link")
def pose6(el):
    t = el.findtext("pose")
    if t is None: return (0.0,)*6
    v = [float(x) for x in t.split()]
    return tuple(v + [0.0]*(6-len(v)))

def boxes_of(path, link_prefix, kind):
    """world-composed (x,y,yaw,sx,sy) 2D boxes of a given element kind under links with prefix."""
    out = []
    for lk in links(path):
        if not lk.get("name","").startswith(link_prefix): continue
        lp = pose6(lk)
        for el in lk.findall(kind):
            b = el.find("geometry/box/size")
            if b is None: continue
            ep = pose6(el)
            s = [float(x) for x in b.text.split()]
            out.append((lp[0]+ep[0], lp[1]+ep[1], lp[5]+ep[5], s[0], s[1]))
    return out

def poly_union(boxes2d):
    from shapely.geometry import Polygon
    from shapely.affinity import rotate, translate
    from shapely.ops import unary_union
    ps = []
    for x, y, yaw, sx, sy in boxes2d:
        p = Polygon([(-sx/2,-sy/2),(sx/2,-sy/2),(sx/2,sy/2),(-sx/2,sy/2)])
        ps.append(translate(rotate(p, math.degrees(yaw), origin=(0,0)), x, y))
    return unary_union(ps)

def design_geoms():
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    d = json.loads((TRACK/"design_final.json").read_text())
    pts = [(p[0],p[1]) for p in d["centerline"]]; pts.append(pts[0])
    main = LineString(pts)
    bl = [(LineString([(p[0],p[1]) for p in b["centerline"]]), b["width_m"]) for b in d["branches"]]
    drivable = unary_union([main.buffer(d["track_width_m"]/2)] + [l.buffer(w/2) for l,w in bl])
    corridor = unary_union([main.buffer(d["track_width_m"]/2 + 0.20)] + [l.buffer(w/2) for l,w in bl])
    return drivable, corridor

def surface_metrics(path):
    drv, _ = design_geoms()
    m = {}
    for kind in ("visual", "collision"):
        surf = poly_union(boxes_of(path, ("track_surface", "surface"), kind))
        miss = drv.difference(surf)
        m[kind] = dict(area=miss.area, ratio=miss.area/drv.area, deep=not miss.buffer(-0.005).is_empty)
    return m

def h1():
    t = (NEW/"world.sdf").read_text()
    if t.count("<script>") != 0: die("script blocks present")
    root = ET.parse(NEW/"world.sdf").getroot()
    maps = [m.text for m in root.findall(".//albedo_map")]
    if len(maps) != 4 or any(not m.startswith("aruco/") for m in maps): die(f"albedo paths {maps}")
    for m in maps:
        if not (NEW/m).exists(): die(f"missing {m}")
    n = sum(1 for lk in root.findall(".//link") if lk.get("name","").startswith("aruco_")
            and (lk.findtext("visual/material/diffuse") or "").split() == ["1","1","1","1"])
    if n != 4: die(f"diffuse on {n}/4 markers")
    if len(root.findall(".//link")) > 25: die("link merge regressed")
    print("H1_OK sdf sanity + merged links kept")

def h2():
    old = surface_metrics(BASE/"world.sdf")
    if old["visual"]["area"] < 0.25 or not old["visual"]["deep"]:
        die(f"positive control: baseline gap should be ~0.32 m^2, got {old['visual']['area']:.3f}")
    new = surface_metrics(NEW/"world.sdf")
    for kind, v in new.items():
        if v["ratio"] > 0.001: die(f"{kind} missing ratio {v['ratio']:.4%} > 0.1%")
        if v["deep"]: die(f"{kind} still has a gap deeper than 1 cm")
    print(f"H2_OK surface gaps: {old['visual']['area']:.3f} m^2 -> {new['visual']['area']:.4f} m^2 "
          f"({new['visual']['ratio']:.4%}), no gap >1cm, collision same")

def h3():
    drv, cor = design_geoms()
    G = cor.difference(drv)
    def grass_union(p): return poly_union(boxes_of(p, "grass", "visual"))
    gold = grass_union(BASE/"world.sdf")
    if G.difference(gold).area / G.area < 0.02:
        die(f"positive control: baseline grass should have branch-area holes ({G.difference(gold).area/G.area:.2%})")
    gnew = grass_union(NEW/"world.sdf")
    miss = G.difference(gnew).area / G.area
    enc = gnew.intersection(drv).area / drv.area
    if miss > 0.01: die(f"grass missing {miss:.2%} > 1%")
    if enc > 0.005: die(f"grass encroaches drivable {enc:.2%} > 0.5%")
    print(f"H3_OK grass: missing {G.difference(gold).area/G.area:.2%} -> {miss:.3%}, encroach {enc:.3%}")

def h4():
    a = sorted(round(v,4) for b in boxes_of(BASE/"world.sdf", "walls", "visual") for v in b)
    b = sorted(round(v,4) for b_ in boxes_of(NEW/"world.sdf", "walls", "visual") for v in b_)
    if a != b: die("wall geometry changed (should be untouched)")
    for pref in ("aruco_", "grid_slot", "tl_", "lamp_", "bump_"):
        pa = sorted(pose6(l) for l in links(BASE/"world.sdf") if l.get("name","").startswith(pref))
        pb = sorted(pose6(l) for l in links(NEW/"world.sdf") if l.get("name","").startswith(pref))
        if pa != pb: die(f"{pref} poses changed")
    print("H4_OK walls/markers/grid/lights/bump untouched")

def h5():
    out = VDIR/"regen"
    r = subprocess.run([VENV, "track_gen.py", "--design", "design_final.json", "--outdir", str(out)],
                       cwd=TRACK, capture_output=True, text=True, timeout=900)
    if r.returncode != 0: die("regen failed: " + r.stdout[-400:] + r.stderr[-400:])
    bad = [l for l in r.stdout.splitlines() if ": False" in l and "min_radius_general_ok" not in l]
    if bad: die("verification failures: " + ";".join(bad))
    if "min_radius_general_ok: False" not in r.stdout: die("known exception line missing")
    for f in ("scene.json", "world.sdf", "centerline.csv", "map.png", "map_with_grass.png"):
        if not filecmp.cmp(out/f, NEW/f, shallow=False): die(f"regen {f} differs from working tree")
    print("H5_OK deterministic regen, only known verification exception")

def h6():
    out = VDIR/"builtin"
    r = subprocess.run([VENV, "track_gen.py", "--outdir", str(out)],
                       cwd=TRACK, capture_output=True, text=True, timeout=900)
    if r.returncode != 0: die("builtin failed")
    print("H6_OK builtin course path runs")

def h7():
    import cv2, numpy as np, yaml
    y = yaml.safe_load((NEW/"map_with_grass.yaml").read_text())
    img = cv2.imread(str(NEW/"map_with_grass.png"), cv2.IMREAD_GRAYSCALE)
    res, (ox, oy) = y["resolution"], y["origin"][:2]
    H = img.shape[0]
    def px(x, y_): return img[int(round(H - (y_-oy)/res)), int(round((x-ox)/res))]
    if px(9.768, 1.244) != 254: die(f"hairpin gap pixel still {px(9.768,1.244)}")
    drv, cor = design_geoms()
    from shapely.geometry import Point
    import random
    random.seed(1)
    minx, miny, maxx, maxy = cor.bounds
    bad = 0; n = 0
    G = cor.difference(drv)
    while n < 300:
        p = Point(random.uniform(minx,maxx), random.uniform(miny,maxy))
        if G.buffer(0).contains(p) and G.boundary.distance(p) > 0.02:
            n += 1
            if px(p.x, p.y) not in (150,): bad += 1
    if bad/n > 0.02: die(f"{bad}/{n} interior grass sample pixels not grass-colored")
    print(f"H7_OK raster: hairpin gap filled, grass samples {n-bad}/{n} correct")

if __name__ == "__main__":
    globals()[sys.argv[1]]()
