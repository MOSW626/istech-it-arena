"""벽 받침·이음 클립 — 610mm 직각 코스 (track_610mm_build_2026-11-05.pdf 18~22쪽).
usage (repo 루트에서): python parts/wall_support/make_wall_parts.py
필요: numpy shapely manifold3d trimesh matplotlib

벽은 walls_610.csv(PDF W01~W61). 좌표선 = 벽의 '도로 쪽 면', 판은 선 밖으로 두께만큼(회색 3T, EVA 10T).
부품 세 종류:
  받침(support)   — 벽 아래쪽을 잡는 삼각 받침. 벽 뒤(도로 반대쪽)에 서고, 도로 쪽은 2.4 mm 턱만 잔디 가장자리에 닿는다.
  이음 받침(joint) — 판과 판이 맞닿는 곳 아래. 두 판이 한 받침에 같이 꽂힌다(두께 다르면 홈이 계단).
  ㄷ자 클립(clip)  — 판 윗변에 위에서 끼우는 덮개. 일자 이음과 코너(90°·135°) 모두 같은 원리.
산출물(이 폴더): stl/*.stl, supports.csv(설치 좌표), parts_count.csv, wall_supports.png"""
import csv, json, math, os, collections
import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import polygonize, unary_union
from shapely import affinity, set_precision
import manifold3d as m3d
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
STL = os.path.join(HERE, "stl")

# ---- 치수 (mm). 첫 출력 후 실측해서 여기만 고치면 된다 ------------------------------------------
T = {"G": 3.0, "E": 10.0}       # 판 두께: 회색 포맥스 3T, EVA 10T
CLR = {"G": 0.5, "E": 0.5}      # 홈 여유 (EVA는 눌리므로 빡빡해도 됨)
H = 100.0        # 받침 높이 (11-07: 150 → 100, 출력 21분 → 8분)
D = 50.0         # 받침 바닥 길이 (벽 뒷면부터)
WID = 6.0        # 받침 두께(벽 따라). 이음 받침은 판마다 WID씩 = 12
PLATE = 2.5      # 뒤판·바닥판·빗대 두께 = 0.42 mm 선 6줄 (채움 없이 벽 선만으로 꽉 참)
LIP_T, LIP_H = 2.4, 40.0   # 도로 쪽 턱 (잔디 가장자리가 여기에 닿음)
BR = 2.4         # 벽이 올라앉는 바닥 다리 두께
CL_ARM = 30.0    # 클립 팔 길이 (이음·코너에서 각 판 쪽으로)
CL_LEG = 15.0    # 클립 다리 깊이 (판 윗변에서 아래로)
CL_WALL = 1.6    # 클립 살 두께 (선 4줄)
SPACING = 600.0  # 받침 최대 간격 (PDF 18쪽 '우선 600 mm 이하')
CORNER_OFF = 120.0   # 코너에서 첫 받침까지
MIN_PANEL = 300.0    # 이보다 짧은 판은 양 끝 이음 받침만
PLA_DENSITY = 1.24
FILL = {"support": 0.8, "joint": 0.8, "clip": 0.95}  # Bambu Studio 0.20 Standard 슬라이스 실측 필라멘트량 ÷ STL 부피 (11-07)


# ---- 벽·도로 ---------------------------------------------------------------------------------------
def load_walls():
    with open(os.path.join(HERE, "walls_610.csv")) as f:
        return [dict(id=r["wall"], piece=r["material_piece"], mat=r["material_piece"][0],
                     a=(float(r["x0_m"]), float(r["y0_m"])), b=(float(r["x1_m"]), float(r["y1_m"]))) for r in csv.DictReader(f)]


def load_road():
    d = json.load(open(os.path.join(ROOT, "track/design_final.json")))
    main = LineString(d["centerline"] + [d["centerline"][0]]).buffer(d["track_width_m"] / 2, join_style="mitre", cap_style="flat")
    return unary_union([main] + [LineString(b["centerline"]).buffer(b["width_m"] / 2, cap_style="flat", join_style="mitre")
                                 for b in d["branches"]])


WALLS = load_walls()
ROAD = load_road()
faces = list(polygonize(unary_union([LineString([w["a"], w["b"]]) for w in WALLS])))
TRACK = unary_union([f for f in faces if f.intersection(ROAD).area > 1e-6])     # 도로 + 잔디
HALL = box(0, 0, 11.0, 14.5)

for w in WALLS:
    ax, ay = w["a"]; bx, by = w["b"]
    L = math.hypot(bx - ax, by - ay)
    w["L"] = L; w["u"] = ((bx - ax) / L, (by - ay) / L)
    n = (-w["u"][1], w["u"][0])
    mid = ((ax + bx) / 2, (ay + by) / 2)
    side = [TRACK.contains(Point(mid[0] + s * 0.05 * n[0], mid[1] + s * 0.05 * n[1])) for s in (1, -1)]
    assert side[0] != side[1], f"{w['id']}: 도로 쪽을 못 정함"
    w["n"] = (-n[0], -n[1]) if side[0] else n          # n = 도로 반대쪽(받침이 서는 쪽) 단위 법선
    w["t"], w["clr"] = T[w["mat"]], CLR[w["mat"]]


# ---- 이음점 분류 ------------------------------------------------------------------------------------
def key(p):
    return (round(p[0], 3), round(p[1], 3))


nodes = collections.defaultdict(list)
for w in WALLS:
    nodes[key(w["a"])].append((w, +1))     # +1: 이 점에서 벽이 u 방향으로 뻗음
    nodes[key(w["b"])].append((w, -1))
assert all(len(v) == 2 for v in nodes.values()), "벽이 닫힌 고리가 아님"

joints = []
for p, ((wa, sa), (wb, sb)) in nodes.items():
    ua = (wa["u"][0] * sa, wa["u"][1] * sa)            # 이음점에서 각 판 쪽으로 향하는 방향
    ub = (wb["u"][0] * sb, wb["u"][1] * sb)
    cos = ua[0] * ub[0] + ua[1] * ub[1]
    ang = math.degrees(math.acos(max(-1, min(1, cos))))  # 두 판 사이 각 (180 = 일자)
    inline = ang > 170
    if inline:                                         # P21 사선 W53|W54는 1° 꺾임 — 일자 클립으로 충분
        ub = (-ua[0], -ua[1])
    joints.append(dict(p=p, A=(wa, ua), B=(wb, ub), angle=ang, inline=inline))


# ---- 2D 도형 (mm, 이음점 원점) ----------------------------------------------------------------------
def strip(u, n, t, s0, s1):
    """판 하나가 차지하는 띠: 이음점에서 u 방향 s0..s1, 도로 쪽 면(0)부터 n 방향 t까지."""
    c = [(s * u[0] + q * n[0], s * u[1] + q * n[1]) for s, q in ((s0, 0), (s1, 0), (s1, t), (s0, t))]
    return Polygon(c)


def clip_shapes(j):
    (wa, ua), (wb, ub) = j["A"], j["B"]
    out = {}
    for name, (w, u), (w2, u2) in (("A", j["A"], j["B"]), ("B", j["B"], j["A"])):
        t = w["t"] + w["clr"]
        ext = 0.0
        n_w = w["n"]
        if j["inline"]:
            n_w = j["A"][0]["n"]                  # 일자 이음은 두 판의 도로 쪽 면이 같은 선
        if not j["inline"]:                       # 오목 코너면 상대 판 두께만큼 이음점 너머로 연장
            t2 = w2["t"] + w2["clr"]
            probe = (-u[0] * t2 / 2 + w["n"][0] * t / 2, -u[1] * t2 / 2 + w["n"][1] * t / 2)
            if probe[0] * w2["n"][0] + probe[1] * w2["n"][1] > 0:
                ext = t2
        out[name] = (strip(u, n_w, t, -ext, CL_ARM), strip(u, n_w, t, -ext, CL_ARM + 5))
        j["concave"] = j.get("concave", False) or ext > 0
    void = unary_union([out["A"][0], out["B"][0]])
    void_long = unary_union([out["A"][1], out["B"][1]])
    outer = void.buffer(CL_WALL, join_style="mitre", mitre_limit=2.0).simplify(0.05)   # 135° 코너의 뾰족한 꼭짓점 정리
    return set_precision(outer, 0.01), set_precision(void_long, 0.01)


def canon(poly_pair, j):
    """한 판이 +x로 가게 돌린 좌표로 모양 키를 만든다 (같은 모양 = 같은 STL). 두 판 모두 기준으로 해 보고 작은 키."""
    best = None
    for u in (j["A"][1], j["B"][1]):
        th = math.atan2(u[1], u[0])
        rot = [set_precision(affinity.rotate(g, -th, origin=(0, 0), use_radians=True), 0.01) for g in poly_pair]
        x0, y0 = rot[0].bounds[:2]
        rot = [affinity.translate(g, -x0, -y0) for g in rot]           # 위치 무관
        k = (tuple(sorted((round(x, 0), round(y, 0)) for x, y in rot[0].normalize().exterior.coords)), round(rot[0].area, 0), round(rot[1].area, 0))
        if best is None or k < best[0]:
            best = (k, rot)
    return best


# ---- 3D ---------------------------------------------------------------------------------------------
def xs(poly):
    polys = getattr(poly, "geoms", [poly])
    rings = []
    for p in polys:
        rings.append(list(p.exterior.coords)[:-1])
        rings += [list(h.coords)[:-1] for h in p.interiors]
    return m3d.CrossSection(rings, fillrule=m3d.FillRule.EvenOdd)


def extrude(poly, h):
    return xs(poly).extrude(h)


def to_stl(man, path):
    mesh = man.to_mesh()
    tm = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts), process=True)
    assert tm.is_watertight and tm.is_volume, path
    tm.export(path)
    return tm


def support_profile(mat):
    """옆에서 본 받침 단면 (x = 도로 쪽 면에서 바깥쪽 거리, y = 높이)."""
    s = T[mat] + CLR[mat]
    back0 = s
    parts = [box(-LIP_T, 0, back0, BR),                          # 바닥 다리 (벽이 올라앉음)
             box(-LIP_T, 0, 0, LIP_H),                           # 도로 쪽 턱
             box(back0, 0, back0 + PLATE, H),                    # 뒤판
             box(back0, 0, back0 + D, PLATE),                    # 바닥판 (양면테이프 자리)
             LineString([(back0 + PLATE / 2, H - 8), (back0 + D - 4, PLATE / 2)]).buffer(PLATE / 2, cap_style="flat")]
    return unary_union(parts).intersection(box(-LIP_T, 0, back0 + D, H))


def support_solid(mats):
    """mats: 벽 따라 이어 붙일 판 재질 목록. ['G'] = 일반 받침, ['G','E'] = 이음 받침."""
    m = None
    for i, mat in enumerate(mats):
        piece = extrude(support_profile(mat), WID).translate([0, 0, i * WID])
        m = piece if m is None else m + piece
    return m                                    # 출력: 옆으로 눕혀서(단면이 베드에) — 서포트 불필요


def clip_solid(outer, void_long):
    legs = set_precision(outer.difference(void_long), 0.01)
    legs = unary_union([g for g in getattr(legs, "geoms", [legs]) if g.area > 1.0])   # 1 mm² 미만 찌꺼기 제거
    cap = extrude(outer, CL_WALL)
    return cap + extrude(legs, CL_WALL + CL_LEG)   # 출력: 덮개면이 베드에 (뒤집어서)


# ---- 받침 배치 -------------------------------------------------------------------------------------
def placements():
    rows = []
    jmap = {j["p"]: j for j in joints}
    for j in joints:
        if j["inline"]:
            rows.append(dict(kind="joint", mats="".join(sorted([j["A"][0]["mat"], j["B"][0]["mat"]])),
                             walls=f"{j['A'][0]['id']}|{j['B'][0]['id']}", x=j["p"][0], y=j["p"][1],
                             u=j["A"][1], n=j["A"][0]["n"], t=max(j["A"][0]["t"], j["B"][0]["t"])))
    for w in WALLS:
        L = w["L"] * 1000
        ends = []
        for p in (w["a"], w["b"]):
            ends.append(0.0 if jmap[key(p)]["inline"] else CORNER_OFF)   # 이음 받침이 있으면 끝 0, 코너면 120 mm 안쪽
        s0, s1 = ends[0], L - ends[1]
        if L < MIN_PANEL:
            pos = [] if all(jmap[key(p)]["inline"] for p in (w["a"], w["b"])) else [L / 2]
        else:
            pts = [round(s, 1) for s, e in ((s0, ends[0]), (s1, ends[1])) if e > 0]  # 코너 쪽 끝 받침
            lo, hi = s0, s1
            n_gap = max(1, math.ceil((hi - lo) / SPACING))
            pos = sorted(set([round(lo + (hi - lo) * k / n_gap, 1) for k in range(n_gap + 1)]) - {0.0, round(L, 1)})
            pos = [s for s in pos if (s > 1 and s < L - 1)]
            pos = sorted(set(pos) | set(pts))
        for s in pos:
            x = w["a"][0] + w["u"][0] * s / 1000; y = w["a"][1] + w["u"][1] * s / 1000
            rows.append(dict(kind="support", mats=w["mat"], walls=w["id"], x=x, y=y, u=w["u"], n=w["n"], t=w["t"], s_mm=s))
    return rows


def footprint(r):
    """받침이 바닥에서 차지하는 영역 (m)."""
    half = (WID if r["kind"] == "support" else WID * 2) / 2000
    s = (T[r["mats"][-1]] + CLR[r["mats"][-1]]) / 1000
    u, n = r["u"], r["n"]
    q0, q1 = -LIP_T / 1000, s + D / 1000
    c = [(r["x"] + a * u[0] + q * n[0], r["y"] + a * u[1] + q * n[1]) for a, q in ((-half, q0), (half, q0), (half, q1), (-half, q1))]
    return Polygon(c)


# ---- 실행 -------------------------------------------------------------------------------------------
os.makedirs(STL, exist_ok=True)
for f in os.listdir(STL):
    os.remove(os.path.join(STL, f))
made, counts, masses = {}, collections.Counter(), {}

name_of = {"G": "G3", "E": "E10"}
for mat in ("G", "E"):
    n = f"support_{name_of[mat]}"
    made[n] = to_stl(support_solid([mat]), os.path.join(STL, n + ".stl"))
for pair in (("G", "G"), ("G", "E"), ("E", "E")):
    n = f"joint_support_{name_of[pair[0]]}_{name_of[pair[1]]}"
    made[n] = to_stl(support_solid(list(pair)), os.path.join(STL, n + ".stl"))

clip_kinds = {}
for j in joints:
    outer, void_long = clip_shapes(j)
    k, (o_r, v_r) = canon((outer, void_long), j)
    (wa, _), (wb, _) = j["A"], j["B"]
    if k not in clip_kinds:
        if j["inline"]:
            label = f"clip_inline_{'_'.join(sorted([name_of[wa['mat']], name_of[wb['mat']]]))}"
        else:
            mats = "_".join(sorted([name_of[wa["mat"]], name_of[wb["mat"]]]))
            label = f"clip_corner{round(j['angle'])}_{'out' if j['concave'] else 'in'}_{mats}"
        base, i = label, 2
        while base in [v["name"] for v in clip_kinds.values()]:
            base = f"{label}_mirror" if i == 2 else f"{label}_v{i}"; i += 1
        clip_kinds[k] = dict(name=base, shape=(o_r, v_r), n=0, at=[])
    clip_kinds[k]["n"] += 1
    clip_kinds[k]["at"].append(j["p"])
    j["clip"] = clip_kinds[k]["name"]
for k, v in clip_kinds.items():
    made[v["name"]] = to_stl(clip_solid(*v["shape"]), os.path.join(STL, v["name"] + ".stl"))
    counts[v["name"]] = v["n"]

rows = placements()
for r in rows:
    if r["kind"] == "support":
        counts[f"support_{name_of[r['mats']]}"] += 1
    else:
        a, b = sorted(r["mats"]) if r["mats"] != "EG" else ("G", "E")
        counts[f"joint_support_{name_of[a]}_{name_of[b]}"] += 1

# ---- 검증 -------------------------------------------------------------------------------------------
fps = [footprint(r) for r in rows]
for r, fp in zip(rows, fps):
    back = Polygon(fp.exterior)          # 받침 전체
    assert HALL.contains(back), f"홀 밖으로 나감: {r['walls']}"
    # 도로(흰 포맥스) 위에 받침이 올라가면 안 된다 (PDF 18쪽). 도로 쪽 턱 2.4 mm만 잔디 가장자리에 닿는다.
    assert back.intersection(ROAD).area < 1e-9, f"받침이 도로 위: {r['walls']}"
    on_grass = back.intersection(TRACK).area
    assert on_grass <= (LIP_T / 1000) * (WID * 2 / 1000) + 1e-9, f"받침이 잔디를 {on_grass * 1e6:.0f} mm² 덮음: {r['walls']}"
for i in range(len(fps)):
    for k in range(i + 1, len(fps)):
        assert fps[i].intersection(fps[k]).area < 1e-9, f"받침끼리 겹침: {rows[i]['walls']} / {rows[k]['walls']}"
for w in WALLS:                                     # 판마다 받침 간격 ≤ SPACING (판 끝 = 이음 받침 또는 코너 지지)
    ss = sorted([0.0, w["L"] * 1000] + [r["s_mm"] for r in rows if r["kind"] == "support" and r["walls"] == w["id"]])
    gaps = [b - a for a, b in zip(ss, ss[1:])]
    assert max(gaps) <= SPACING + 1 or w["L"] * 1000 < MIN_PANEL, (w["id"], gaps)
assert sum(counts[k] for k in counts if k.startswith("clip")) == len(joints)
for n, tm in made.items():
    masses[n] = tm.volume / 1000 * PLA_DENSITY * FILL["clip" if n.startswith("clip") else "support"]
    b = tm.bounds[1] - tm.bounds[0]
    assert max(b[0], b[1]) < 250, f"{n}: P1S 베드(256 mm)보다 큼 {b}"

# ---- 출력 -------------------------------------------------------------------------------------------
with open(os.path.join(HERE, "supports.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["번호", "종류", "벽", "벽 시작점에서_mm", "x_m", "y_m", "받침이 서는 방향(nx,ny)"])
    for i, r in enumerate(sorted(rows, key=lambda r: (r["walls"].split("|")[-1], r.get("s_mm", 0))), 1):
        nm = f"support_{name_of[r['mats']]}" if r["kind"] == "support" else \
            "joint_support_" + "_".join(name_of[m] for m in (("G", "E") if r["mats"] == "EG" else tuple(r["mats"])))
        wr.writerow([i, nm, r["walls"], f"{r['s_mm']:.0f}" if "s_mm" in r else "이음점", f"{r['x']:.3f}", f"{r['y']:.3f}", f"{r['n'][0]:+.0f},{r['n'][1]:+.0f}" if abs(r['n'][0]) in (0, 1) else f"{r['n'][0]:+.3f},{r['n'][1]:+.3f}"])
total_g = 0
with open(os.path.join(HERE, "parts_count.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["부품", "필요 수량", "예비 포함(+10%)", "개당 PLA_g(추정)", "합계_g(예비 포함)", "STL"])
    for n in sorted(made):
        need = counts[n]; spare = math.ceil(need * 1.1)
        total_g += spare * masses[n]
        wr.writerow([n, need, spare, f"{masses[n]:.1f}", f"{spare * masses[n]:.0f}", f"stl/{n}.stl"])
    wr.writerow(["합계", sum(counts.values()), "", "", f"{total_g:.0f}", ""])

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
for fn in ("Pretendard", "Apple SD Gothic Neo", "NanumGothic", "Noto Sans CJK KR"):
    if any(fn in x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = fn; break
from matplotlib.path import Path
from matplotlib.patches import PathPatch


def fill(ax, geom, **kw):
    for g in getattr(geom, "geoms", [geom]):
        rings = [g.exterior] + list(g.interiors)
        verts = [c for r in rings for c in r.coords]
        codes = [c for r in rings for c in [Path.MOVETO] + [Path.LINETO] * (len(r.coords) - 2) + [Path.CLOSEPOLY]]
        ax.add_patch(PathPatch(Path(verts, codes), **kw))


fig, ax = plt.subplots(figsize=(10, 14))
fill(ax, ROAD, color="#e6e6e6", lw=0, zorder=1)
fill(ax, TRACK.difference(ROAD), color="#bfe3b8", lw=0, zorder=1)
for w in WALLS:
    ax.plot([w["a"][0], w["b"][0]], [w["a"][1], w["b"][1]], color="#333" if w["mat"] == "G" else "#d07020", lw=1.5, zorder=3)
for r, fp in zip(rows, fps):
    ax.fill(*fp.exterior.xy, color="#1f5fbf" if r["kind"] == "support" else "#c0218a", zorder=4)
for j in joints:
    ax.plot(*j["p"], marker="s" if j["inline"] else "^", ms=3.5, color="k", zorder=5)
ax.set_aspect("equal"); ax.grid(alpha=0.2); ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]")
ax.set_title(f"벽 받침 배치 — 받침 {sum(1 for r in rows if r['kind'] == 'support')}개(파랑) · 이음 받침 {sum(1 for r in rows if r['kind'] == 'joint')}개(자주) · "
             f"ㄷ자 클립 {len(joints)}개(■ 일자 ▲ 코너)\n선: 검정 = 회색 포맥스 3T, 주황 = EVA 10T · 받침은 벽 뒤(도로 반대쪽)", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "wall_supports.png"), dpi=130); plt.close(fig)

# 단면도
fig, axs = plt.subplots(1, 3, figsize=(13, 5.2))
for ax, mat in zip(axs[:2], ("G", "E")):
    pr = support_profile(mat)
    fill(ax, pr, color="#8aa", ec="k", lw=0.8)
    s = T[mat]
    ax.add_patch(plt.Rectangle((0, BR), s, 400 - BR, color="#bbb" if mat == "G" else "#f0b070", alpha=0.6))
    ax.add_patch(plt.Rectangle((-200, 0), 200 - LIP_T, 6, color="#7cc576"))
    ax.annotate("잔디 6 mm", (-120, 6), (-190, 40), fontsize=8, arrowprops=dict(arrowstyle="-"))
    ax.text(s / 2, 300, "벽 " + ("회색 3T" if mat == "G" else "EVA 10T"), rotation=90, ha="center", fontsize=9)
    ax.annotate(f"높이 {H:.0f}", (s + PLATE + 2, H), (s + 30, H + 25), fontsize=8, arrowprops=dict(arrowstyle="-"))
    ax.annotate(f"바닥 {D:.0f} (양면테이프)", (s + D, 2), (s + 25, -30), fontsize=8, arrowprops=dict(arrowstyle="-"))
    ax.annotate(f"도로 쪽 턱 {LIP_T}×{LIP_H:.0f}", (-LIP_T, LIP_H), (-170, LIP_H + 40), fontsize=8, arrowprops=dict(arrowstyle="-"))
    ax.set_xlim(-200, 110); ax.set_ylim(-50, 420); ax.set_aspect("equal")
    ax.set_title(f"받침 단면 ({'회색 3T' if mat == 'G' else 'EVA 10T'}) · 홈 {T[mat] + CLR[mat]:.1f} mm · 두께 {WID:.0f} mm", fontsize=9)
    ax.axvline(0, color="r", lw=0.6, ls="--"); ax.text(2, 410, "← 도로 쪽 | 도면 W좌표선", fontsize=7, color="r")
ax = axs[2]
o, v = clip_kinds[next(k for k in clip_kinds if clip_kinds[k]["name"].startswith("clip_inline_G3_G3"))]["shape"]
ax.fill(*o.exterior.xy, color="#8aa", ec="k")
for g in getattr(v, "geoms", [v]):
    ax.fill(*g.exterior.xy, color="white", ec="#555", ls="--")
ax.set_aspect("equal"); ax.set_title(f"ㄷ자 클립 (위에서 본 모양, 일자 회색-회색)\n점선 = 판이 들어가는 홈 · 덮개 {CL_WALL:g} mm + 다리 {CL_LEG:g} mm", fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "wall_parts_section.png"), dpi=130); plt.close(fig)

from mpl_toolkits.mplot3d.art3d import Poly3DCollection
show = ["support_G3", "joint_support_G3_E10", "clip_inline_G3_G3", "clip_corner90_out_E10_E10", "clip_corner90_in_E10_G3", "clip_corner135_in_E10_E10"]
fig = plt.figure(figsize=(15, 9))
for i, n in enumerate(show, 1):
    tm = made[n]
    ax = fig.add_subplot(2, 3, i, projection="3d")
    v = tm.vertices.copy()
    if n.startswith("clip"):
        v[:, 2] = v[:, 2].max() - v[:, 2]          # 설치 방향(덮개가 위)으로 보여 줌
    else:
        v = v[:, [0, 2, 1]]                        # 받침: 단면이 세로로 서게
    ax.add_collection3d(Poly3DCollection(v[tm.faces], facecolor="#8fb3c7", edgecolor="#335", linewidths=0.05))
    lo, hi = v.min(0), v.max(0); c = (lo + hi) / 2; r = (hi - lo).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(25, -60); ax.set_axis_off()
    ax.set_title(f"{n}\n{counts[n]}개 · 약 {masses[n]:.0f} g", fontsize=9)
fig.suptitle("부품 모양 (설치 방향). 출력은 받침 = 옆으로 눕혀서, 클립 = 덮개면이 베드로", fontsize=11)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "wall_parts_3d.png"), dpi=110); plt.close(fig)

print("WALL_PARTS_OK", dict(counts), f"PLA≈{total_g / 1000:.2f}kg(예비 포함, 추정)")
for n in sorted(made):
    b = made[n].bounds[1] - made[n].bounds[0]
    print(f"  {n}: {b[0]:.0f}×{b[1]:.0f}×{b[2]:.0f} mm, {masses[n]:.1f} g")
