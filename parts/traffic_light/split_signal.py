"""signal_610_old_style.stl -> P1S(256 mm)용 분할 STL + 이음 슬리브.

    ~/miniforge3/bin/python parts/traffic_light/split_signal.py

자르는 곳 (도로 중심 기준): 가로대 x=±120, ±320 / 기둥 높이 40, 232.
기둥을 세워 뽑으면 232 mm 막대가 흔들려 떨어지기 쉬워서, 발판만 짧게 세우고 나머지는 전부 눕힌다.
자른 면은 전부 15 x 14.6 mm 사각 봉이라, 슬리브(사각 관)를 씌우고 순간접착제로 붙인다.
"""
import os
import numpy as np
import trimesh
import manifold3d as mf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "print")
CUT_X = (120.0, 320.0)       # 가로대 자르는 곳 (|x|)
CUT_H = 232.0                # 기둥 자르는 높이 (모서리 조각 아래)
CUT_FOOT = 40.0              # 발판 조각 높이
CLR, WALL, SLEEVE_L = 0.2, 3.0, 40.0
BIG = 2000.0


def to_m(t):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices, np.float32),
                               tri_verts=np.asarray(t.faces, np.uint32)))


def to_t(m):
    g = m.to_mesh()
    return trimesh.Trimesh(g.vert_properties[:, :3], g.tri_verts)


def box(x0, x1, y0, y1, z0=-BIG, z1=BIG):
    return mf.Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def main():
    src = trimesh.load(os.path.join(HERE, "signal_610_old_style.stl"))
    lo, hi = src.bounds
    src.apply_translation([-(lo[0] + hi[0]) / 2, -lo[1], 0])   # x: 도로 중심 0, y: 높이(바닥 0)
    full = to_m(src)
    a, b = CUT_X
    pieces = {   # 이름: (잘라낼 영역, 눕히는 방식)
        "1_가운데_가로대+신호모듈": (box(-a, a, -BIG, BIG), "flat"),
        "2_가로대_왼쪽": (box(-b, -a, -BIG, BIG), "flat"),
        "2_가로대_오른쪽": (box(a, b, -BIG, BIG), "flat"),
        "3_모서리_왼쪽": (box(-BIG, -b, CUT_H, BIG), "flat"),
        "3_모서리_오른쪽": (box(b, BIG, CUT_H, BIG), "flat"),
        "4_기둥_왼쪽": (box(-BIG, -b, CUT_FOOT, CUT_H), "flat"),
        "4_기둥_오른쪽": (box(b, BIG, CUT_FOOT, CUT_H), "flat"),
        "5_발판_왼쪽": (box(-BIG, -b, -BIG, CUT_FOOT), "up"),
        "5_발판_오른쪽": (box(b, BIG, -BIG, CUT_FOOT), "up"),
    }
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".stl"):
            os.remove(os.path.join(OUT, f))
    vol = 0.0
    for name, (region, how) in pieces.items():
        p = to_t(full ^ region)
        vol += p.volume
        if how == "up":                       # 발판을 바닥에: 높이(y) -> z
            p.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
        p.apply_translation(-p.bounds[0])
        e = p.extents
        assert max(e[0], e[1]) <= 245 and e[2] <= 250, (name, e)
        p.export(os.path.join(OUT, f"{name}_1개.stl"))
        print(f"{name}: {e[0]:.0f} x {e[1]:.0f} x {e[2]:.0f} mm")
    assert abs(vol - src.volume) < 1e-3 * src.volume, (vol, src.volume)   # 빠진 조각 없음

    # 슬리브: 봉 단면(가로대 h 450~465, z -20.8~-6.2)을 재서 안쪽 치수 결정
    bar = to_t(full ^ box(150, 300, -BIG, BIG))
    w, d = bar.extents[1], bar.extents[2]
    iw, idp = w + 2 * CLR, d + 2 * CLR
    tube = (mf.Manifold.cube([iw + 2 * WALL, idp + 2 * WALL, SLEEVE_L])
            - mf.Manifold.cube([iw, idp, SLEEVE_L + 2]).translate([WALL, WALL, -1]))
    to_t(tube).export(os.path.join(OUT, "6_이음슬리브_8개.stl"))
    print(f"슬리브: 봉 {w:.1f} x {d:.1f} -> 안쪽 {iw:.1f} x {idp:.1f}, 길이 {SLEEVE_L:.0f}")


if __name__ == "__main__":
    main()
