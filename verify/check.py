#!/usr/bin/env python3
"""Deep verification of issue #7-#11 fixes (v2026.09.01) against v2026.08.31 baseline.
Each gate prints G<N>_OK and exits 0 only if the claim holds AND (where applicable)
the baseline fails the same check (positive control)."""
import sys, json, math, subprocess, filecmp
import xml.etree.ElementTree as ET
from pathlib import Path

VDIR = Path(__file__).parent
REPO = Path("/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/istech-it-arena")
TRACK = REPO / "track"
NEW = TRACK / "output_final"
OLD = VDIR / "baseline" / "output_final"
RELNEW = VDIR / "release_new"
VENV = "/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3"

def die(msg):
    print("FAIL:", msg); sys.exit(1)

def sdf_links(p):
    return ET.parse(p).getroot().findall(".//link")

def pose6(el):
    t = el.findtext("pose")
    if t is None: return (0.0,)*6
    v = [float(x) for x in t.split()]
    return tuple(v + [0.0]*(6-len(v)))

def box_visuals_world(path):
    """(x,y,z,yaw,sx,sy,sz) for every box visual, link pose + element pose composed
    (one of the two is always zero in these files). Excludes grid slots & markers."""
    out = []
    for lk in sdf_links(path):
        name = lk.get("name", "")
        if name.startswith(("grid_slot", "aruco_", "ground_plane")): continue
        lp = pose6(lk)
        for vis in lk.findall("visual"):
            box = vis.find("geometry/box/size")
            if box is None: continue
            vp = pose6(vis)
            s = [float(x) for x in box.text.split()]
            out.append(tuple(round(lp[i]+vp[i], 4) for i in (0,1,2,5)) + tuple(round(x,4) for x in s))
    return sorted(out)

def counts(path):
    root = ET.parse(path).getroot()
    return dict(links=len(root.findall(".//link")),
                visuals=len(root.findall(".//visual")),
                collisions=len(root.findall(".//collision")),
                mu08=sum(1 for m in root.findall(".//mu") if m.text.strip() == "0.8"))

def marker_links(path):
    return {lk.get("name"): pose6(lk) for lk in sdf_links(path) if lk.get("name","").startswith("aruco_")}

def corridor_and_drivable():
    """Independent recompute from design_final.json (not from track_gen code)."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    d = json.loads((TRACK/"design_final.json").read_text())
    pts = [(p[0], p[1]) for p in d["centerline"]]; pts.append(pts[0])
    main_line = LineString(pts)
    tw = d["track_width_m"]
    branch_lines = [LineString([(p[0],p[1]) for p in b["centerline"]]) for b in d["branches"]]
    bws = [b["width_m"] for b in d["branches"]]
    drivable = unary_union([main_line.buffer(tw/2)] + [l.buffer(w/2) for l,w in zip(branch_lines,bws)])
    corridor = unary_union([main_line.buffer(tw/2 + 0.20)] + [l.buffer(w/2) for l,w in zip(branch_lines,bws)])
    return corridor, drivable, branch_lines, bws

def scene(p): return json.loads((p/"scene.json").read_text())

def g1():
    old = (OLD/"world.sdf").read_text(); new = (NEW/"world.sdf").read_text()
    if old.count("<script>") == 0: die("positive control: baseline should contain <script>")
    if new.count("<script>") != 0: die(f"new world.sdf still has {new.count('<script>')} <script> blocks")
    print("G1_OK")

def g2():
    for p, prefix, ok in ((OLD, "../aruco/", False), (NEW, "aruco/", True)):
        root = ET.parse(p/"world.sdf").getroot()
        maps = [m.text for m in root.findall(".//albedo_map")]
        if len(maps) != 4: die(f"{p}: expected 4 albedo_map, got {len(maps)}")
        for m in maps:
            if not m.startswith(prefix): die(f"{p}: path {m} does not start with {prefix}")
            if ok and not (p/m).exists(): die(f"missing texture file {p/m}")
    print("G2_OK")

def g3():
    for p, want in ((OLD, False), (NEW, True)):
        root = ET.parse(p/"world.sdf").getroot()
        n = 0
        for lk in root.findall(".//link"):
            if lk.get("name","").startswith("aruco_"):
                d = lk.findtext("visual/material/diffuse")
                if d and d.split() == ["1","1","1","1"]: n += 1
        if want and n != 4: die(f"new: only {n}/4 markers have diffuse 1 1 1 1")
        if not want and n != 0: die("positive control: baseline should lack white diffuse")
    print("G3_OK")

def g4():
    co, cn = counts(OLD/"world.sdf"), counts(NEW/"world.sdf")
    if co["links"] != 1113: die(f"baseline links {co['links']} != 1113")
    if cn["links"] > 25: die(f"new links {cn['links']} > 25")
    for k in ("visuals","collisions","mu08"):
        if co[k] != cn[k]: die(f"{k}: old {co[k]} != new {cn[k]}")
    print(f"G4_OK links {co['links']}->{cn['links']} visuals={cn['visuals']} collisions={cn['collisions']} mu08={cn['mu08']}")

def g5():
    a, b = box_visuals_world(OLD/"world.sdf"), box_visuals_world(NEW/"world.sdf")
    if len(a) != len(b): die(f"box visual count differs {len(a)} vs {len(b)}")
    diff = [i for i,(x,y) in enumerate(zip(a,b)) if x != y]
    if diff: die(f"{len(diff)} box visuals moved, first: old={a[diff[0]]} new={b[diff[0]]}")
    print(f"G5_OK {len(a)} static box visuals identical between releases")

def g6():
    corridor, _, _, _ = corridor_and_drivable()
    boundary = corridor.boundary
    from shapely.geometry import Point
    worst = 0.0
    for m in scene(NEW)["aruco_markers"]["markers"]:
        d = boundary.distance(Point(m["pose"]["x"], m["pose"]["y"]))
        worst = max(worst, d)
        if d > 0.005: die(f"ID{m['id']} is {d:.4f} m from wall face")
    old_far = max(boundary.distance(Point(m["pose"]["x"], m["pose"]["y"]))
                  for m in scene(OLD)["aruco_markers"]["markers"])
    if old_far < 0.05: die(f"positive control: baseline markers should float (max {old_far:.4f})")
    print(f"G6_OK max wall distance {worst*1000:.2f} mm (baseline was {old_far*1000:.0f} mm)")

def g7():
    from shapely.geometry import Polygon
    from shapely.affinity import rotate, translate
    _, drivable, _, _ = corridor_and_drivable()
    def plate(m):
        sz = 0.10; th = 0.005
        p = Polygon([(-th/2,-sz/2),(th/2,-sz/2),(th/2,sz/2),(-th/2,sz/2)])
        p = rotate(p, math.degrees(m["pose"]["yaw_rad"]), origin=(0,0))
        return translate(p, m["pose"]["x"], m["pose"]["y"])
    for m in scene(NEW)["aruco_markers"]["markers"]:
        ov = plate(m).intersection(drivable).area
        if ov > 1e-9: die(f"ID{m['id']} overlaps drivable area by {ov:.6f} m^2")
    old30 = next(m for m in scene(OLD)["aruco_markers"]["markers"] if m["id"] == 30)
    if plate(old30).intersection(drivable).area < 1e-9:
        die("positive control: baseline ID30 should overlap the shortcut corridor")
    print("G7_OK no marker plate touches any drivable corridor")

def g8():
    sc = {m["id"]: m["pose"] for m in scene(NEW)["aruco_markers"]["markers"]}
    sdf = marker_links(NEW/"world.sdf")
    for mid, p in sc.items():
        lp = sdf[f"aruco_{mid}"]
        if abs(lp[0]-p["x"]) > 1e-3 or abs(lp[1]-p["y"]) > 1e-3 or abs(lp[5]-p["yaw_rad"]) > 1e-3:
            die(f"ID{mid} scene vs sdf pose mismatch: {p} vs {lp}")
    import ezdxf
    msp = ezdxf.readfile(NEW/"venue_layout.dxf").modelspace()
    pts = [e for e in msp if e.dxf.layer == "MARKERS"]
    if not pts: die("no MARKERS layer entities in DXF")
    def near(x, y):
        for e in pts:
            for v in getattr(e, "get_points", lambda: [])() or []:
                if math.hypot(v[0]-x, v[1]-y) < 0.25: return True
            ip = getattr(e.dxf, "insert", None)
            if ip is not None and math.hypot(ip[0]-x, ip[1]-y) < 0.25: return True
        return False
    for mid, p in sc.items():
        if not near(p["x"], p["y"]): die(f"ID{mid} has no DXF MARKERS entity within 0.25 m")
    print("G8_OK scene.json == world.sdf poses, DXF markers co-located")

def g9():
    for p, expect_match in ((OLD, False), (NEW, True)):
        g = scene(p)["starting_grid"]
        rows = {}
        for s in g["slots"]: rows.setdefault(s["row"], {})[s["col"]] = s["s_m"]
        deltas = {round(abs(v[0]-v[1]), 6) for v in rows.values() if len(v) == 2}
        if len(deltas) != 1: die(f"{p}: inconsistent stagger {deltas}")
        actual = deltas.pop()
        match = abs(g["longitudinal_stagger_m"] - actual) < 1e-9
        if match != expect_match:
            die(f"{p}: stagger meta {g['longitudinal_stagger_m']} vs actual {actual}, match={match}")
    print("G9_OK stagger metadata now equals applied 0.2 m (baseline mismatched, as reported)")

def g10():
    def grid_geo(p):
        out = {}
        for lk in sdf_links(p/"world.sdf"):
            n = lk.get("name","")
            if n.startswith("grid_slot"):
                z = pose6(lk)[2]; h = float(lk.findtext("visual/geometry/box/size").split()[2])
                out[n] = dict(pose=pose6(lk), top=z+h/2, size=lk.findtext("visual/geometry/box/size"),
                              ncol=len(lk.findall("collision")))
        return out
    o, n = grid_geo(OLD), grid_geo(NEW)
    if len(n) != 6: die(f"{len(n)} grid slots")
    for k in n:
        if n[k]["top"] <= 0.003: die(f"{k} top {n[k]['top']} still under road top 0.003")
        if o[k]["top"] > 0.003: die("positive control: baseline slot should be under road")
        po, pn = o[k]["pose"], n[k]["pose"]
        if (round(po[0],6), round(po[1],6), round(po[5],6)) != (round(pn[0],6), round(pn[1],6), round(pn[5],6)):
            die(f"{k} XY/yaw changed")
        if o[k]["size"] != n[k]["size"] or n[k]["ncol"] != 0: die(f"{k} size/collision changed")
    print(f"G10_OK slot top z={n['grid_slot_0']['top']:.4f} > 0.003, XY/size/no-collision preserved")

def g11():
    d = json.loads((TRACK/"design_final.json").read_text())
    if d["features"]["start_line"]["s"] != 0.0: die("design start_line.s != 0.0")
    sf = scene(NEW).get("start_finish")
    if not sf or sf["s_m"] != 0.0: die("scene.json start_finish missing or s != 0")
    with open(NEW/"centerline.csv") as f:
        f.readline(); x0, y0, *_ = [float(v) for v in f.readline().split(",")]
    if math.hypot(sf["pose"]["x"]-x0, sf["pose"]["y"]-y0) > 1e-3:
        die(f"start_finish pose {sf['pose']} != centerline s=0 ({x0},{y0})")
    if "start_finish" in scene(OLD): die("positive control: baseline should lack start_finish")
    print("G11_OK start line canonical at s=0, pose matches centerline origin")

def g12():
    out = VDIR/"regen"
    r = subprocess.run([VENV, "track_gen.py", "--design", "design_final.json", "--outdir", str(out)],
                       cwd=TRACK, capture_output=True, text=True, timeout=600)
    if r.returncode != 0: die("regen failed: " + r.stdout[-500:] + r.stderr[-500:])
    if "min_radius_general_ok: False" not in r.stdout: die("expected known min-radius exception missing")
    bad = [l for l in r.stdout.splitlines() if ": False" in l and "min_radius_general_ok" not in l]
    if bad: die("unexpected verification failures: " + "; ".join(bad))
    for f in ("scene.json", "world.sdf", "centerline.csv", "map.png", "map_with_grass.png"):
        if not filecmp.cmp(out/f, NEW/f, shallow=False): die(f"regenerated {f} differs from committed")
    print("G12_OK regeneration reproduces committed outputs byte-identically")

def g13():
    dc = filecmp.dircmp(RELNEW, TRACK, ignore=[".DS_Store"])
    def walk(d):
        errs = list(d.left_only) + list(d.right_only) + list(d.diff_files)
        for sub in d.subdirs.values(): errs += walk(sub)
        return errs
    errs = walk(dc)
    if errs: die("release asset differs from repo track/: " + ", ".join(errs[:10]))
    print("G13_OK v2026.09.01 release zip == committed track/")

def g14():
    out = VDIR/"builtin"
    r = subprocess.run([VENV, "track_gen.py", "--outdir", str(out)],
                       cwd=TRACK, capture_output=True, text=True, timeout=600)
    if r.returncode != 0: die("built-in course run failed: " + r.stdout[-300:] + r.stderr[-300:])
    if not (out/"world.sdf").exists(): die("built-in world.sdf missing")
    print("G14_OK built-in course path still runs")

if __name__ == "__main__":
    globals()[sys.argv[1]]()
