#!/usr/bin/env python3
"""과속방지턱 STL 생성기 — ISTech IT Arena.

시뮬레이터(`track/output_final/world.sdf`)의 `bump_0`은 **450 x 50 x 10 mm** 박스입니다.
여기서 만드는 실물은 그 외형 안에 들어가므로 시공 위치와 DXF를 그대로 쓸 수 있습니다.

윗면은 반코사인 곡선입니다.

    h(x) = H * (1 - cos(2*pi*x/L)) / 2

양 끝에서 높이와 기울기가 모두 0이라 **턱(립)이 생기지 않습니다.** 박스로 만들면
진입면이 수직벽이 되어 작은 바퀴가 걸립니다.

프린터 베드를 고려해 기본은 **150 mm 조각**이고, 3개를 이어 붙여 450 mm를 만듭니다.
서포트가 필요 없고 바닥이 평면이라 어느 프린터에서나 그대로 출력됩니다.

    python3 make_speed_bump.py                 # 150 mm 조각, 높이 10 mm
    python3 make_speed_bump.py --height 5      # low
    python3 make_speed_bump.py --width 450     # 큰 베드용 통짜
    python3 make_speed_bump.py --selftest
"""
import argparse
import math
import struct
import sys

ROAD_W = 450.0      # 도로 폭 (world.sdf bump_0)
TRAVEL_L = 50.0     # 주행 방향 길이
HEIGHT = 10.0       # 시뮬 기본값 (--bump-height mid)
SEG_W = 150.0       # 기본 조각 폭 = 450 / 3
STEPS = 96          # 곡선 분할 수


def profile(x, length, height):
    """주행 방향 위치 x(0..length)에서의 높이."""
    return height * (1.0 - math.cos(2.0 * math.pi * x / length)) / 2.0


def build_mesh(width=SEG_W, length=TRAVEL_L, height=HEIGHT, steps=STEPS):
    """(vertices, triangles). 윗면 + 바닥 + 양 옆면으로 닫힌 솔리드.

    x = 주행 방향(0..length), y = 도로 폭 방향(0..width), z = 높이.
    양 끝에서 h=0이라 앞뒤 마구리면은 존재하지 않는다.
    """
    xs = [length * i / steps for i in range(steps + 1)]
    top = [[(x, 0.0, profile(x, length, height)),
            (x, width, profile(x, length, height))] for x in xs]
    tris = []

    def quad(a, b, c, d, want):
        """사각형을 삼각형 2개로. 법선이 want 방향을 보도록 감는 순서를 맞춘다.
        윗면은 오르막/내리막에서 부호가 뒤집히므로 강제로 맞춰야 한다."""
        ux, uy, uz = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        vx, vy, vz = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        if sum(p * q for p, q in zip(n, want)) < 0:
            a, b, c, d = a, d, c, b
        tris.append((a, b, c))
        tris.append((a, c, d))

    for i in range(steps):                                  # 윗면 (위를 본다)
        quad(top[i][0], top[i][1], top[i + 1][1], top[i + 1][0], (0, 0, 1))
    for i in range(steps):                                  # 바닥 (아래를 본다)
        quad((xs[i], 0.0, 0.0), (xs[i], width, 0.0),
             (xs[i + 1], width, 0.0), (xs[i + 1], 0.0, 0.0), (0, 0, -1))
    for i in range(steps):                                  # 옆면 y=0
        quad((xs[i], 0.0, 0.0), (xs[i + 1], 0.0, 0.0),
             top[i + 1][0], top[i][0], (0, -1, 0))
    for i in range(steps):                                  # 옆면 y=width
        quad(top[i][1], top[i + 1][1],
             (xs[i + 1], width, 0.0), (xs[i], width, 0.0), (0, 1, 0))

    tris = [t for t in tris if _area(t) > 1e-12]            # 퇴화 삼각형 제거
    return tris


def _area(t):
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)


def volume(tris):
    """부호 있는 부피 (mm^3). 닫힌 메시면 양수."""
    v = 0.0
    for (ax, ay, az), (bx, by, bz), (cx, cy, cz) in tris:
        v += (ax * (by * cz - bz * cy)
              - ay * (bx * cz - bz * cx)
              + az * (bx * cy - by * cx)) / 6.0
    return v


def is_watertight(tris):
    """모든 모서리가 정확히 두 삼각형에 공유되는가."""
    edges = {}
    for t in tris:
        for i in range(3):
            a, b = t[i], t[(i + 1) % 3]
            key = tuple(sorted((tuple(round(c, 6) for c in a),
                                tuple(round(c, 6) for c in b))))
            edges[key] = edges.get(key, 0) + 1
    bad = [k for k, n in edges.items() if n != 2]
    return (not bad), len(bad)


def write_stl(path, tris, name="speed_bump"):
    with open(path, "wb") as f:
        f.write(name.encode()[:80].ljust(80, b"\0"))
        f.write(struct.pack("<I", len(tris)))
        for (ax, ay, az), (bx, by, bz), (cx, cy, cz) in tris:
            ux, uy, uz = bx - ax, by - ay, bz - az
            vx, vy, vz = cx - ax, cy - ay, cz - az
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            m = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            f.write(struct.pack("<12fH", nx / m, ny / m, nz / m,
                                ax, ay, az, bx, by, bz, cx, cy, cz, 0))


def selftest():
    for h in (5.0, 10.0, 15.0):
        for w in (150.0, 450.0):
            tris = build_mesh(width=w, height=h)
            ok, bad = is_watertight(tris)
            assert ok, "메시가 닫혀 있지 않음: 모서리 %d개" % bad
            vol = volume(tris)
            assert vol > 0, "부피가 음수 (법선 방향 오류): %.3f" % vol

            # 반코사인 단면의 면적은 H*L/2, 부피는 그 x 폭
            expect = h * TRAVEL_L / 2.0 * w
            assert abs(vol - expect) / expect < 0.002, (vol, expect)

            xs = [v[0] for t in tris for v in t]
            ys = [v[1] for t in tris for v in t]
            zs = [v[2] for t in tris for v in t]
            assert abs(min(xs)) < 1e-9 and abs(max(xs) - TRAVEL_L) < 1e-9
            assert abs(min(ys)) < 1e-9 and abs(max(ys) - w) < 1e-9
            assert abs(min(zs)) < 1e-9 and abs(max(zs) - h) < 1e-6

    # 양 끝 기울기 0 (턱 없음), 중앙이 최고점
    assert abs(profile(0, TRAVEL_L, HEIGHT)) < 1e-12
    assert abs(profile(TRAVEL_L, TRAVEL_L, HEIGHT)) < 1e-12
    assert abs(profile(TRAVEL_L / 2, TRAVEL_L, HEIGHT) - HEIGHT) < 1e-12
    eps = 1e-6
    assert abs(profile(eps, TRAVEL_L, HEIGHT)) < 1e-9, "진입부에 턱이 있음"

    # 조각 3개가 도로 폭과 맞는가
    assert abs(SEG_W * 3 - ROAD_W) < 1e-9

    slope = math.degrees(math.atan(HEIGHT * math.pi / TRAVEL_L))
    print("selftest OK -- 닫힌 메시, 부피 오차 0.2%% 이내, 턱 없음, 최대 경사 %.1f도" % slope)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="과속방지턱 STL 생성")
    p.add_argument("--width", type=float, default=SEG_W, help="조각 폭 mm (기본 150, 3개로 450)")
    p.add_argument("--length", type=float, default=TRAVEL_L, help="주행 방향 길이 mm (기본 50)")
    p.add_argument("--height", type=float, default=HEIGHT, help="높이 mm (low/mid/high = 5/10/15)")
    p.add_argument("--steps", type=int, default=STEPS, help="곡선 분할 수")
    p.add_argument("--out", help="출력 파일 (기본 speed_bump_<폭>x<높이>.stl)")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        selftest()
        sys.exit(0)

    tris = build_mesh(a.width, a.length, a.height, a.steps)
    ok, bad = is_watertight(tris)
    if not ok:
        sys.exit("[거부] 메시가 닫혀 있지 않습니다 (모서리 %d개)" % bad)
    out = a.out or "speed_bump_%gx%g.stl" % (a.width, a.height)
    write_stl(out, tris)
    n = ROAD_W / a.width
    print("  %s  (삼각형 %d개)" % (out, len(tris)))
    print("  %g x %g x %g mm, 부피 %.1f cm3" % (a.width, a.length, a.height, volume(tris) / 1000))
    print("  최대 경사 %.1f도 (양 끝 기울기 0 — 턱 없음)"
          % math.degrees(math.atan(a.height * math.pi / a.length)))
    if abs(n - round(n)) < 1e-9:
        print("  도로 폭 450 mm = 이 조각 %d개" % round(n))
    else:
        print("  ⚠ 450 mm가 이 폭으로 나누어떨어지지 않습니다 (%.2f개분)" % n)
