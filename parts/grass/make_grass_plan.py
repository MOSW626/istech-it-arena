"""잔디 재단 계획 — 610mm 직각 코스 (track_610mm_build_2026-11-05.pdf).
usage (repo 루트에서): python parts/grass/make_grass_plan.py [롤 길이 m, 기본 23]

잔디 영역 = 벽(parts/wall_support/walls_610.csv)으로 둘러싸인 트랙 면 − 도로(본선 0.61 + 지름길 0.20).
각 벽 직선 구간을 따라 폭 0.20 m 띠로 나누고, 남는 모서리·P21 주변 조각은 따로 적는다.
재단은 '롤을 길이 방향으로 끊고 → 폭 1 m를 20 cm씩 5줄로 가르는' 블록 방식.
산출물: grass_pieces.csv, grass_blocks.csv, grass_layout.png, grass_cutting.png (이 폴더)"""
import csv, json, math, os, sys
from shapely.geometry import LineString, Polygon, box
from shapely.ops import polygonize, unary_union
from shapely import set_precision, affinity
GRID = 1e-4   # 0.1 mm 격자로 맞춰 부동소수 찌꺼기 조각을 없앤다

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ROLL_W, LANE = 1.0, 0.20
ROLL_LEN = float(sys.argv[1]) if len(sys.argv) > 1 else 23.0
LANES = round(ROLL_W / LANE)


def walls():
    with open(os.path.join(ROOT, "parts/wall_support/walls_610.csv")) as f:
        return [(r["wall"], r["material_piece"], (float(r["x0_m"]), float(r["y0_m"])), (float(r["x1_m"]), float(r["y1_m"])))
                for r in csv.DictReader(f)]


def road():
    d = json.load(open(os.path.join(ROOT, "track/design_final.json")))
    cl = d["centerline"] + [d["centerline"][0]]
    main = LineString(cl).buffer(d["track_width_m"] / 2, join_style="mitre", cap_style="flat")   # 고리 모양(가운데 구멍 유지)
    br = [LineString(b["centerline"]).buffer(b["width_m"] / 2, cap_style="flat", join_style="mitre") for b in d["branches"]]
    return unary_union([main] + br)


W = walls()
faces = list(polygonize(unary_union([LineString([a, b]) for _, _, a, b in W])))
R = road()
track_face = unary_union([f for f in faces if f.intersection(R).area > 1e-6])   # 도로가 지나는 면 = 트랙 면
islands = [f for f in faces if f.intersection(R).area <= 1e-6]
GRASS = track_face.difference(R)
GRASS = set_precision(unary_union([g for g in getattr(GRASS, "geoms", [GRASS]) if g.area > 1e-6]), GRID)


def runs():
    """같은 직선 위에서 끝점이 이어지는 벽끼리 합친다."""
    segs = [[a, b, [w]] for w, _, a, b in W]
    merged = True
    while merged:
        merged = False
        for i in range(len(segs)):
            for j in range(len(segs)):
                if i == j:
                    continue
                a1, b1, n1 = segs[i]
                a2, b2, n2 = segs[j]
                if math.dist(b1, a2) < 1e-6:
                    d1 = (b1[0] - a1[0], b1[1] - a1[1]); d2 = (b2[0] - a2[0], b2[1] - a2[1])
                    if abs(d1[0] * d2[1] - d1[1] * d2[0]) < 1e-9 and d1[0] * d2[0] + d1[1] * d2[1] > 0:
                        segs[i] = [a1, b2, n1 + n2]; del segs[j]; merged = True; break
            if merged:
                break
    return segs


def mrr(g):
    """최소 외접 직사각형 — 볼록 껍질의 각 변 방향으로 돌려 본다.
    (shapely minimum_rotated_rectangle이 일부 삼각형에서 넓이 0 사각형을 돌려줘서 직접 계산)"""
    hull = list(g.convex_hull.exterior.coords)
    best = None
    for (x0, y0), (x1, y1) in zip(hull, hull[1:]):
        th = math.atan2(y1 - y0, x1 - x0)
        r = affinity.rotate(g, -th, origin=(0, 0), use_radians=True)
        x_0, y_0, x_1, y_1 = r.bounds
        key = (round((x_1 - x_0) * (y_1 - y_0), 6), max(x_1 - x_0, y_1 - y_0))   # 넓이가 같으면 긴 변이 짧은 쪽
        if best is None or key < best[0]:
            best = (key, affinity.rotate(box(x_0, y_0, x_1, y_1), th, origin=(0, 0), use_radians=True))
    return best[1]


pieces, left = [], GRASS
for a, b, names in sorted(runs(), key=lambda s: -math.dist(s[0], s[1])):
    line = LineString([a, b])
    strip = unary_union([line.buffer(LANE, single_sided=True, cap_style="flat", join_style="mitre"),
                         line.buffer(-LANE, single_sided=True, cap_style="flat", join_style="mitre")])
    got = set_precision(strip.intersection(left), GRID)
    for g in getattr(got, "geoms", [got]):
        if g.geom_type == "Polygon" and g.area > 1e-5:
            pieces.append(("/".join(names), g)); left = set_precision(left.difference(g), GRID)
def is_strip(g):
    r = mrr(g)
    c = list(r.exterior.coords)
    return abs(r.area - g.area) < 1e-5 and abs(min(math.dist(c[0], c[1]), math.dist(c[1], c[2])) - LANE) < 1e-4


for g in getattr(left, "geoms", [left]):
    if g.geom_type != "Polygon" or g.area <= 1e-4 or g.buffer(-0.002).is_empty:   # 2 mm보다 얇은 찌꺼기 제외
        continue
    for k, (src, p) in sorted(enumerate(pieces), key=lambda e: e[1][1].length):   # 짧은 띠부터 붙여 본다
        u = set_precision(unary_union([p, g]), GRID)
        if u.geom_type == "Polygon" and is_strip(u):
            pieces[k] = (src, u); break
    else:
        pieces.append(("모서리·지름길", g))

rows = []
for k, (src, g) in enumerate(pieces, 1):
    r = mrr(g)
    c = list(r.exterior.coords)
    e1, e2 = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    L, Wd = max(e1, e2), min(e1, e2)
    rect = abs(r.area - g.area) < 1e-5
    kind = "띠" if rect and abs(Wd - LANE) < 1e-4 else ("직사각형" if rect else "모양 조각")
    rows.append(dict(id=f"S{k:02d}", kind=kind, length_mm=round(L * 1000), width_mm=round(Wd * 1000),
                     area_m2=round(g.area, 4), along=src, geom=g, cx=g.centroid.x, cy=g.centroid.y))

# 블록 재단: 롤을 길이 B로 끊고 20 cm씩 5줄로 가른다. B보다 긴 띠는 같은 길이로 나눈다(맞댐 이음).
def split(r, n):
    g = r["geom"]; c = list(mrr(g).exterior.coords)
    a, b = (c[0], c[1]) if math.dist(c[0], c[1]) >= math.dist(c[1], c[2]) else (c[1], c[2])
    q = c[2] if (a, b) == (c[0], c[1]) else c[3]
    out = []
    for i in range(n):
        f0, f1 = i / n, (i + 1) / n
        p = lambda f, o: (a[0] + (b[0] - a[0]) * f + (o[0] - b[0]), a[1] + (b[1] - a[1]) * f + (o[1] - b[1]))
        cell = Polygon([(a[0] + (b[0] - a[0]) * f0, a[1] + (b[1] - a[1]) * f0), (a[0] + (b[0] - a[0]) * f1, a[1] + (b[1] - a[1]) * f1),
                        p(f1, q), p(f0, q)])
        part = set_precision(g.intersection(cell.buffer(1e-9)), GRID)
        out.append(dict(r, id=f"{r['id']}-{i + 1}", length_mm=round(r["length_mm"] / n), area_m2=round(part.area, 4),
                        geom=part, cx=part.centroid.x, cy=part.centroid.y))
    return out


def pack(B):
    items = []
    for r in rows:
        if r["kind"] == "띠" and r["length_mm"] > B:
            items += split(r, math.ceil(r["length_mm"] / B))
        else:
            items.append(r)
    one = sorted([i for i in items if i["width_mm"] <= LANE * 1000], key=lambda r: -r["length_mm"])
    wide = [i for i in items if i["width_mm"] > LANE * 1000]
    lanes = []                                            # first-fit decreasing, 줄 용량 B
    for it in one:
        for l in lanes:
            if sum(p["length_mm"] for p in l) + it["length_mm"] <= B:
                l.append(it); break
        else:
            lanes.append([it])
    blocks = [dict(length_mm=max(sum(p["length_mm"] for p in l) for l in lanes[i:i + LANES]), lanes=lanes[i:i + LANES])
              for i in range(0, len(lanes), LANES)]
    for w in wide:                                        # 폭 넓은 조각(P21 삼각형)은 따로 한 블록
        blocks.append(dict(length_mm=w["length_mm"], lanes=[[w]] * math.ceil(w["width_mm"] / (LANE * 1000))))
    return items, blocks


SPARE = 1.0   # 재단 실수·보수용으로 남길 롤 길이 (m)
best = None
for B in range(1500, 6001, 50):        # 롤 안에 (여유 SPARE 남기고) 들어가는 배치 중 조각 수(=이음) 최소
    items, blocks = pack(B)
    tot = sum(b["length_mm"] for b in blocks) / 1000
    if tot <= ROLL_LEN - SPARE and (best is None or (len(items), tot) < (len(best[2]), best[0])):
        best = (tot, B, items, blocks)
assert best, f"롤 {ROLL_LEN} m 안에 배치 불가"
_, BLOCK, items, blocks = best
strips = [i for i in items if i["kind"] == "띠"]
others = [i for i in items if i["kind"] != "띠"]
for o in others:
    o["_done"] = True
rows = items
used = sum(b["length_mm"] for b in blocks) / 1000

# --- 검증 -----------------------------------------------------------------------------------
cover = unary_union([r["geom"] for r in rows])
gap = cover.symmetric_difference(GRASS).area
assert gap < 5e-4, f"조각 합 != 잔디 영역 (차이 {gap:.5f} m²)"   # 5 cm² 이하 = 좌표 반올림 찌꺼기
import itertools; ov=[(x["id"],y["id"],round(x["geom"].intersection(y["geom"]).area,5)) for x,y in itertools.combinations(rows,2) if x["geom"].intersection(y["geom"]).area>1e-4]; assert not ov, ("조각끼리 겹침", ov)   # 1e-4 m² = 20 cm 폭에서 0.5 mm
assert not cover.intersection(R).area > 1e-6, "잔디가 도로를 덮음"
assert abs(GRASS.area - 18.38) < 0.05, f"잔디 면적 {GRASS.area:.3f} ≠ PDF 26쪽 약 18.38 m²"
for _, _, a, b in W:                                                # 모든 벽 면이 잔디(또는 섬) 경계 위
    assert LineString([a, b]).distance(GRASS.boundary) < 1e-6
assert used <= ROLL_LEN, f"롤 {ROLL_LEN} m 부족: {used:.2f} m 필요"
assert all(o.get("_done") for o in others)

# --- 출력 -----------------------------------------------------------------------------------
with open(os.path.join(HERE, "grass_pieces.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["조각", "종류", "길이_mm", "폭_mm", "면적_m2", "중심_x_m", "중심_y_m", "붙는 벽"])
    for r in rows:
        w.writerow([r["id"], r["kind"], r["length_mm"], r["width_mm"], r["area_m2"], f"{r['cx']:.3f}", f"{r['cy']:.3f}", r["along"]])
with open(os.path.join(HERE, "grass_blocks.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["블록", "롤에서 끊을 길이_mm"] + [f"{i + 1}줄" for i in range(LANES)])
    for i, b in enumerate(blocks, 1):
        w.writerow([f"B{i}", b["length_mm"]] + [" + ".join(p["id"] for p in l) for l in b["lanes"]] + [""] * (LANES - len(b["lanes"])))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
for fn in ("Pretendard", "Apple SD Gothic Neo", "NanumGothic", "Noto Sans CJK KR"):
    if any(fn in x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = fn; break


def fill(ax, g, **kw):
    for p in getattr(g, "geoms", [g]):
        ax.fill(*p.exterior.xy, **kw)
        for h in p.interiors:
            ax.fill(*h.xy, color="white")


fig, ax = plt.subplots(figsize=(10, 14))
fill(ax, R, color="#e8e8e8", zorder=1)
for isl in islands:
    fill(ax, isl, color="#f7f7f7", zorder=1)
cols = {"띠": "#7cc576", "직사각형": "#4f9a49", "모양 조각": "#e0a030"}
for r in rows:
    fill(ax, r["geom"], color=cols[r["kind"]], ec="#225522", lw=0.4, zorder=2)
    ax.text(r["cx"], r["cy"], r["id"], fontsize=5.5, ha="center", va="center", zorder=3,
            rotation=0 if r["geom"].bounds[2] - r["geom"].bounds[0] >= r["geom"].bounds[3] - r["geom"].bounds[1] else 90)
for _, m, a, b in W:
    ax.plot([a[0], b[0]], [a[1], b[1]], color="#333" if m[0] == "G" else "#d07020", lw=1.6, zorder=4)
ax.set_aspect("equal"); ax.grid(alpha=0.2)
ax.set_title(f"잔디 조각 배치 — 폭 200 mm, {len(rows)}조각 (띠 {len(strips)} · 기타 {len(others)})\n"
             f"초록 = 20 cm 띠, 진초록 = 직사각형, 주황 = 모양 조각(재단 전 현장 대고 그림) · 선 = 벽(검정 회색판 / 주황 EVA)", fontsize=10)
ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]")
fig.tight_layout(); fig.savefig(os.path.join(HERE, "grass_layout.png"), dpi=130); plt.close(fig)

Lmax = max(b["length_mm"] for b in blocks) / 1000
fig, axs = plt.subplots(len(blocks), 1, figsize=(12, 1.9 * len(blocks)))
for i, (ax, b) in enumerate(zip(axs, blocks), 1):
    L = b["length_mm"] / 1000
    ax.add_patch(plt.Rectangle((0, 0), L, ROLL_W, fill=False, ec="k", lw=1.2))
    for li, lane in enumerate(b["lanes"]):
        xx = 0
        for p in lane:
            pl = p["length_mm"] / 1000
            if p["width_mm"] > LANE * 1000:                     # 넓은 조각은 블록 전체에 한 번만
                if li == 0:
                    ax.add_patch(plt.Polygon([(0, 0), (pl, 0), (0, p["width_mm"] / 1000)], color=cols[p["kind"]], ec="#225522"))
                    ax.text(pl / 3, 0.3, f"{p['id']} 삼각형\n{p['length_mm']}×{p['width_mm']} (대각선 컷)", fontsize=8)
                continue
            ax.add_patch(plt.Rectangle((xx, li * LANE), pl, LANE, color=cols[p["kind"]], ec="#225522", lw=0.5))
            ax.text(xx + pl / 2, li * LANE + LANE / 2, f"{p['id']}  {p['length_mm']}", fontsize=7, ha="center", va="center")
            xx += pl
    ax.set_xlim(-0.05, Lmax + 0.05); ax.set_ylim(-0.05, ROLL_W + 0.05); ax.set_aspect("equal")
    ax.set_yticks([k * LANE for k in range(LANES + 1)]); ax.tick_params(labelsize=7)
    ax.set_ylabel(f"B{i}", rotation=0, labelpad=18, fontsize=11, weight="bold")
    wide_blk = any(p["width_mm"] > LANE * 1000 for l in b["lanes"] for p in l)
    ax.set_title(f"B{i}: 롤에서 {b['length_mm']} mm 끊기 → " + ("가르지 않고 대각선으로 잘라 삼각형 (나머지 반은 보수용)" if wide_blk else f"20 cm × {LANES}줄"), fontsize=9, loc="left")
fig.suptitle(f"잔디 롤 재단도 — 1 m 폭 롤 사용 {used:.2f} m / {ROLL_LEN:g} m (남는 {ROLL_LEN - used:.2f} m는 보수용) · 숫자 = 조각 길이 mm", fontsize=11)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "grass_cutting.png"), dpi=150); plt.close(fig)

print(f"block={BLOCK}mm"); print(f"GRASS_OK area={GRASS.area:.3f}m2 pieces={len(rows)} strips={len(strips)} others={len(others)} "
      f"strip_total={sum(r['length_mm'] for r in strips) / 1000:.2f}m blocks={len(blocks)} roll_used={used:.2f}m")
for r in others:
    print(" ", r["id"], r["kind"], r["length_mm"], "x", r["width_mm"], r["along"])
