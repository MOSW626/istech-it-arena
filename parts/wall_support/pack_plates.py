"""P1S 판(256 mm)에 부품을 최대한 많이 넣어 판 수를 줄인다.

    python parts/wall_support/pack_plates.py 받침_EVA=80 받침_회색=22 클립=all

- 인자: `파일 이름 앞부분=개수`. `클립=all`은 3_ㄷ자클립 폴더 전부를 파일 이름의 개수만큼.
- 받침은 속이 빈 삼각형이라 서로 뒤집어 맞물리고, 빈 속에 작은 클립이 들어간다.
  받침은 뒤집어 놓아도(위아래) 같은 부품이라 거울 방향도 쓴다. 클립은 덮개면이 베드라 회전만.
- 1 mm 격자로 판을 칠해 두고 FFT로 '겹치지 않는 자리'를 한 번에 찾아 왼쪽 아래부터 채운다.
- 결과: plates/판NN_….3mf (부품마다 따로 된 물체, 판 위 자리 고정) + plates/plates.csv + plates/plates.png
"""
import collections, csv, glob, os, re, sys
import numpy as np, trimesh
from matplotlib.path import Path
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely import affinity

HERE = os.path.dirname(os.path.abspath(__file__))
STL, OUT = os.path.join(HERE, "stl"), os.path.join(HERE, "plates")
EXCL = (18.0, 28.0)   # P1S bed_exclude_area (왼쪽 앞 18 × 28 mm, Bambu 프로파일)
BED, MARGIN, GAP, RES = 256.0, 6.5, 1.5, 0.5   # mm. MARGIN = 판 가장자리 여백(브림 5 mm가 판 안에 들어오게), GAP = 부품 사이 최소 간격(브림끼리 붙어 한 장이 됨), RES = 배치 격자


def footprint(m):
    tris = [Polygon(t[:, :2]) for t in m.triangles]
    return unary_union([t for t in tris if t.area > 1e-6]).buffer(0).simplify(0.1)


def raster(poly, pad):
    """poly(+pad)를 RES 격자에 칠한 bool 배열과 그 원점(mm)."""
    g = poly.buffer(pad, join_style=2) if pad else poly
    x0, y0, x1, y1 = g.bounds
    nx, ny = int(np.ceil((x1 - x0) / RES)) + 1, int(np.ceil((y1 - y0) / RES)) + 1
    xs, ys = np.meshgrid(x0 + (np.arange(nx) + 0.5) * RES, y0 + (np.arange(ny) + 0.5) * RES)
    pts = np.c_[xs.ravel(), ys.ravel()]
    m = np.zeros(len(pts), bool)
    for p in getattr(g, "geoms", [g]):
        m |= Path(np.asarray(p.exterior.coords)).contains_points(pts)
        for h in p.interiors:
            m &= ~Path(np.asarray(h.coords)).contains_points(pts)
    return m.reshape(ny, nx), (x0, y0)


def orientations(mesh, flip):
    out = []
    for f in ([False, True] if flip else [False]):
        m0 = mesh.copy()
        if f:   # y축으로 180° 뒤집기 (받침은 같은 두께의 판이라 뒤집어도 같은 부품)
            m0.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [0, 1, 0]))
        for k in range(4):
            m = m0.copy()
            m.apply_transform(trimesh.transformations.rotation_matrix(k * np.pi / 2, [0, 0, 1]))
            m.apply_translation(-m.bounds[0])
            fp = footprint(m)
            out.append(dict(mesh=m, fp=fp, mask=raster(fp, GAP / 2 + 0.75 * RES)))
    return out


def parse_args(argv):
    want = []
    for a in argv:
        key, n = a.split("=")
        files = sorted(glob.glob(os.path.join(STL, "3_*", "*.stl"))) if key == "클립" else \
            [f for f in glob.glob(os.path.join(STL, "*", "*.stl")) if os.path.basename(f).startswith(key + "_")]
        assert files, f"'{key}'에 맞는 STL이 없음"
        for f in files:
            cnt = int(re.search(r"_(\d+)개\.stl$", f).group(1)) if n == "all" else int(n)
            want.append((f, cnt))
    return want


def pack(want):
    W = int(BED / RES)
    lo, hi = int(MARGIN / RES), int((BED - MARGIN) / RES)
    kinds = {}
    for f, cnt in want:
        m = trimesh.load(f)
        name = os.path.basename(f).rsplit("_", 1)[0]
        kinds[name] = dict(orient=orientations(m, flip=name.startswith(("받침", "이음받침"))), n=cnt)
    # 큰 것부터 (받침 → 큰 클립 → 작은 클립): 작은 것이 큰 것의 빈 속과 틈을 채운다
    queue = [n for n in sorted(kinds, key=lambda n: -kinds[n]["orient"][0]["fp"].convex_hull.area) for _ in range(kinds[n]["n"])]
    plates = []
    for name in queue:
        for pl in plates + [None]:
            if pl is None:
                pl = dict(occ=np.zeros((W, W), bool), items=[]); plates.append(pl)
                pl["occ"][:int((EXCL[1] + GAP) / RES), :int((EXCL[0] + GAP) / RES)] = True   # P1S 왼쪽 앞 금지 구역
            best = None
            F = np.fft.rfft2(pl["occ"].astype(float))
            for oi, o in enumerate(kinds[name]["orient"]):
                mk, (ox, oy) = o["mask"]
                h, w = mk.shape
                # 겹침 수 = occ ⊛ mask (상관). FFT로 모든 자리를 한 번에
                K = np.zeros((W, W)); K[:h, :w] = mk[::-1, ::-1]
                ov = np.fft.irfft2(F * np.fft.rfft2(K), s=(W, W))[h - 1:, w - 1:]  # ov[j,i] = 자리 (i,j)에서 겹침
                ok = ov < 0.5
                j0, i0 = lo + int(np.ceil(-oy / RES)), lo + int(np.ceil(-ox / RES))   # 부품 바닥 경계가 판 여백 안
                jmax, imax = hi - h + 1, hi - w + 1
                ok[:max(j0, 0)] = False; ok[:, :max(i0, 0)] = False
                ok[max(jmax, 0):] = False; ok[:, max(imax, 0):] = False
                # Bambu는 금지 구역을 부품의 감싼 사각형으로 판정한다 → 사각형이 구역에 걸리는 자리는 뺀다
                ex_j = int(np.ceil((EXCL[1] + MARGIN + oy) / RES)); ex_i = int(np.ceil((EXCL[0] + MARGIN + ox) / RES))
                ok[:max(ex_j, 0), :max(ex_i, 0)] = False
                js, is_ = np.nonzero(ok)
                if len(js) == 0:
                    continue
                k = np.argmin(js * W + is_)   # 아래(앞)부터, 그다음 왼쪽부터
                cand = (js[k], is_[k], oi)
                if best is None or cand[0] * W + cand[1] < best[0] * W + best[1]:
                    best = cand
            if best:
                j, i, oi = best
                o = kinds[name]["orient"][oi]
                mk, (ox, oy) = o["mask"]
                pl["occ"][j:j + mk.shape[0], i:i + mk.shape[1]] |= mk
                pl["items"].append(dict(name=name, o=o, dx=i * RES - ox, dy=j * RES - oy))
                break
    return plates


def check(plates):
    for p, pl in enumerate(plates, 1):
        polys = [affinity.translate(it["o"]["fp"], it["dx"], it["dy"]) for it in pl["items"]]
        for q in polys:
            x0, y0, x1, y1 = q.bounds
            assert not (x0 < EXCL[0] and y0 < EXCL[1]), f"판{p} 금지 구역에 걸림"
            assert x0 >= MARGIN - 1e-6 and y0 >= MARGIN - 1e-6 and x1 <= BED - MARGIN + 1e-6 and y1 <= BED - MARGIN + 1e-6, f"판{p} 여백 밖"
        for a in range(len(polys)):
            for b in range(a + 1, len(polys)):
                d = polys[a].distance(polys[b])
                assert d >= GAP / 2, f"판{p}: 부품 간격 {d:.2f} mm"


def write_3mf(path, meshes, names):
    """부품마다 따로 된 물체로 담은 3MF. 한 덩어리 STL은 Bambu가 볼록 껍질로 보고 왼쪽 앞 금지 구역에 걸린다고 거부한다."""
    import zipfile
    objs, items = [], []
    for k, (m, nm) in enumerate(zip(meshes, names), 1):
        v = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>' for a, b, c in m.vertices)
        t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in m.faces)
        objs.append(f'<object id="{k}" name="{nm}" type="model"><mesh><vertices>{v}</vertices><triangles>{t}</triangles></mesh></object>')
        items.append(f'<item objectid="{k}"/>')
    model = ('<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             f'<resources>{"".join(objs)}</resources><build>{"".join(items)}</build></model>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr("3D/3dmodel.model", model)


def write(plates):
    os.makedirs(OUT, exist_ok=True)
    for f in glob.glob(os.path.join(OUT, "판*.3mf")): os.remove(f)   # 쌓기_*.3mf(make_stack.py)는 남긴다
    rows = []
    for p, pl in enumerate(plates, 1):
        c = collections.Counter(it["name"] for it in pl["items"])
        label = "+".join(f"{n}{k}" for n, k in sorted(c.items(), key=lambda x: -x[1]))
        parts = []
        for it in pl["items"]:
            m = it["o"]["mesh"].copy(); m.apply_translation([it["dx"], it["dy"], 0]); parts.append(m)
        fn = f"판{p:02d}_{len(pl['items'])}개.3mf"
        write_3mf(os.path.join(OUT, fn), parts, [it["name"] for it in pl["items"]])
        rows.append([fn, len(pl["items"]), label])
    with open(os.path.join(OUT, "plates.csv"), "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["파일", "개수", "들어간 부품"]); wr.writerows(rows)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["AppleGothic", "DejaVu Sans"]
    n = len(plates); cols = min(n, 4); rws = (n + cols - 1) // cols
    fig, axs = plt.subplots(rws, cols, figsize=(4 * cols, 4.3 * rws), squeeze=False)
    colors = {}
    for ax, (p, pl) in zip(axs.ravel(), enumerate(plates, 1)):
        ax.add_patch(plt.Rectangle((0, 0), BED, BED, fill=False, lw=1))
        for it in pl["items"]:
            q = affinity.translate(it["o"]["fp"], it["dx"], it["dy"])
            col = colors.setdefault(it["name"], plt.cm.tab20(len(colors) % 20))
            for g in getattr(q, "geoms", [q]):
                ax.fill(*g.exterior.xy, color=col, alpha=.8, lw=0)
                for h in g.interiors: ax.fill(*h.xy, color="white", lw=0)
        ax.set_title(f"판 {p} · {len(pl['items'])}개", fontsize=10)
        ax.set_xlim(-2, BED + 2); ax.set_ylim(-2, BED + 2); ax.set_aspect("equal"); ax.axis("off")
    for ax in axs.ravel()[n:]: ax.axis("off")
    fig.legend([plt.Rectangle((0, 0), 1, 1, color=c) for c in colors.values()], list(colors), loc="lower center", ncol=3, fontsize=8)
    fig.tight_layout(rect=(0, 0.2, 1, 1)); fig.savefig(os.path.join(OUT, "plates.png"), dpi=110)
    return rows


if __name__ == "__main__":
    want = parse_args(sys.argv[1:] or ["받침_EVA=80", "받침_회색=22", "클립=all"])
    plates = pack(want)
    check(plates)
    assert sum(len(p["items"]) for p in plates) == sum(c for _, c in want)
    for r in write(plates):
        print(*r)
    print(f"총 {len(plates)}판 · {sum(c for _, c in want)}개 → {OUT}")
