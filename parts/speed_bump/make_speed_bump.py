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
SEG_W = 225.0       # 기본 조각 폭 = 450 / 2 (Bambu P1S 256mm 베드에 2개가 한 판)
STEPS = 96          # 곡선 분할 수

# 이음새 — 전높이 턱/홈. 차가 때리는 힘(x)에 대한 전단을 받아낸다.
TONGUE_X = 20.0     # 주행 방향 길이
TONGUE_Y = 6.0      # 폭 방향 돌출/깊이
CLEARANCE = 0.2     # 공차 (홈을 한 쪽당 이만큼 키운다). FDM/PLA 기준
CHAMFER = 0.4       # 이음새 모따기 — 조립 길잡이 겸 메시 T-정션 방지


def profile(x, length, height):
    """주행 방향 위치 x(0..length)에서의 높이."""
    return height * (1.0 - math.cos(2.0 * math.pi * x / length)) / 2.0


def _ramp(x, lo, hi, ch, peak):
    """[lo,hi] 구간에서 양 끝 ch 만큼 경사지게 올라갔다 내려오는 사다리꼴.

    수직 단차 대신 모따기를 두는 이유는 두 가지다.
    ① 조립할 때 **들어가는 길잡이(lead-in)** 가 된다.
    ② 수직 단차는 메시에서 **T-정션**을 만들어 솔리드가 닫히지 않는다.
    """
    if x <= lo or x >= hi:
        return 0.0
    if x < lo + ch:
        return peak * (x - lo) / ch
    if x > hi - ch:
        return peak * (hi - x) / ch
    return peak


def y_bounds(x, width, length, tongue, groove, clear, t_x, t_y, ch=CHAMFER):
    """위치 x에서 부품이 차지하는 폭 방향 구간 [y_lo, y_hi].

    이음새는 **전높이 턱(tongue) + 홈(groove)** 이다.
    차가 방지턱을 때리는 힘은 **주행 방향(x)** 이고 조각은 **폭 방향(y)** 으로 나뉘므로,
    이음새가 실제로 받는 하중은 조각끼리의 **x 전단**이다. 전높이 턱·홈의 옆면
    (x = 일정 평면)이 그 힘을 그대로 받아낸다.
    """
    x0, x1 = (length - t_x) / 2.0, (length + t_x) / 2.0
    y_lo, y_hi = 0.0, width
    if groove:                                  # 홈: 사방으로 공차만큼 크게
        y_lo = _ramp(x, x0 - clear, x1 + clear, ch, t_y + clear)
    if tongue:                                  # 턱: 설계 치수 그대로
        y_hi = width + _ramp(x, x0, x1, ch, t_y)
    return y_lo, y_hi


def build_mesh(width=SEG_W, length=TRAVEL_L, height=HEIGHT, steps=STEPS,
               tongue=False, groove=False, clear=CLEARANCE,
               t_x=TONGUE_X, t_y=TONGUE_Y, ch=CHAMFER):
    """(삼각형 목록). 윗면 + 바닥 + 양 옆면으로 닫힌 솔리드.

    x = 주행 방향(0..length), y = 폭 방향, z = 높이.
    양 끝에서 h=0이라 앞뒤 마구리면은 존재하지 않는다.
    """
    x0, x1 = (length - t_x) / 2.0, (length + t_x) / 2.0
    xs = [length * i / steps for i in range(steps + 1)]
    if tongue:
        xs += [x0, x0 + ch, x1 - ch, x1]
    if groove:
        g0, g1 = x0 - clear, x1 + clear
        xs += [g0, g0 + ch, g1 - ch, g1]
    xs = sorted(set(round(v, 9) for v in xs))

    pts = [(x, *y_bounds(x, width, length, tongue, groove, clear, t_x, t_y, ch),
            profile(x, length, height)) for x in xs]

    tris = []

    def quad(a, b, c, d, want):
        ux, uy, uz = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        vx, vy, vz = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        if sum(p * q for p, q in zip(n, want)) < 0:
            a, b, c, d = a, d, c, b
        tris.append((a, b, c))
        tris.append((a, c, d))

    for i in range(len(pts) - 1):
        xa, la, ha_, za = pts[i]
        xb, lb, hb_, zb = pts[i + 1]
        quad((xa, la, za), (xa, ha_, za), (xb, hb_, zb), (xb, lb, zb), (0, 0, 1))
        quad((xa, la, 0.0), (xa, ha_, 0.0), (xb, hb_, 0.0), (xb, lb, 0.0), (0, 0, -1))
        quad((xa, la, 0.0), (xb, lb, 0.0), (xb, lb, zb), (xa, la, za), (0, -1, 0))
        quad((xa, ha_, 0.0), (xb, hb_, 0.0), (xb, hb_, zb), (xa, ha_, za), (0, 1, 0))

    return [t for t in tris if _area(t) > 1e-12]


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


def analytic_volume(width, length, height, tongue, groove, clear, t_x, t_y, n=200000):
    """해석적 부피: integral of h(x) * (y_hi - y_lo) dx."""
    tot = 0.0
    for i in range(n):
        x = length * (i + 0.5) / n
        lo, hi = y_bounds(x, width, length, tongue, groove, clear, t_x, t_y)
        tot += profile(x, length, height) * (hi - lo)
    return tot * length / n


def selftest():
    variants = [(False, False), (True, False), (False, True), (True, True)]
    for tongue, groove in variants:
        for w in (150.0, 225.0):
            tris = build_mesh(width=w, tongue=tongue, groove=groove)
            ok, bad = is_watertight(tris)
            assert ok, "메시가 닫혀 있지 않음 (턱=%s 홈=%s): 모서리 %d개" % (tongue, groove, bad)
            v = volume(tris)
            assert v > 0, "부피가 음수 — 법선 방향 오류: %.3f" % v
            want = analytic_volume(w, TRAVEL_L, HEIGHT, tongue, groove,
                                   CLEARANCE, TONGUE_X, TONGUE_Y)
            assert abs(v - want) / want < 0.003, (tongue, groove, v, want)

            zs = [p[2] for t in tris for p in t]
            assert abs(max(zs) - HEIGHT) < 1e-6 and abs(min(zs)) < 1e-9

    # --- 공차: 평탄부에서 홈이 턱보다 한 쪽당 CLEARANCE 만큼 크다 ---
    x0, x1 = (TRAVEL_L - TONGUE_X) / 2, (TRAVEL_L + TONGUE_X) / 2
    mid = TRAVEL_L / 2
    yb = lambda x, t, g: y_bounds(x, SEG_W, TRAVEL_L, t, g, CLEARANCE, TONGUE_X, TONGUE_Y)
    assert yb(mid, True, False)[1] == SEG_W + TONGUE_Y, "턱 높이가 설계값과 다름"
    assert yb(mid, False, True)[0] == TONGUE_Y + CLEARANCE, "홈 깊이에 공차가 안 들어감"
    # 턱은 [x0,x1] 밖에서 0, 홈은 [x0-c, x1+c] 밖에서 0
    assert yb(x0 - 1e-9, True, False)[1] == SEG_W
    assert yb(x1 + 1e-9, True, False)[1] == SEG_W
    assert yb(x0 - CLEARANCE - 1e-9, False, True)[0] == 0.0
    assert yb(x1 + CLEARANCE + 1e-9, False, True)[0] == 0.0
    # 홈이 턱보다 x 방향으로 한 쪽당 CLEARANCE 만큼 길다
    assert abs(((x1 + CLEARANCE) - (x0 - CLEARANCE)) - (TONGUE_X + 2 * CLEARANCE)) < 1e-12

    # --- 가상 조립: 턱 부품 + 홈 부품을 붙여 간섭과 틈을 본다 ---
    W = SEG_W
    gap_joint, gap_flat, contact = 1e9, 1e9, 0
    for i in range(20001):
        x = TRAVEL_L * i / 20000
        a_lo, a_hi = yb(x, True, False)
        b_lo, b_hi = yb(x, False, True)
        b_lo += W                                # 조립 좌표로 평행이동
        assert a_hi <= b_lo + 1e-12, "간섭! x=%.4f  A끝 %.4f  B시작 %.4f" % (x, a_hi, b_lo)
        if a_hi > W + 1e-12:                     # 턱이 나와 있는 구간
            gap_joint = min(gap_joint, b_lo - a_hi)
        else:                                    # 민짜 구간 — 면끼리 맞닿아야 한다
            gap_flat = min(gap_flat, b_lo - a_hi)
            contact += 1
    assert abs(gap_joint - CLEARANCE) < 1e-9, "이음새 틈이 공차와 다름: %.4f" % gap_joint
    assert abs(gap_flat) < 1e-12, "민짜 구간이 떠 있음: %.4f" % gap_flat
    frac = contact / 20001.0
    want = (TRAVEL_L - TONGUE_X) / TRAVEL_L      # 턱 밖 = 맞닿는 구간
    assert abs(frac - want) < 0.01, "맞닿는 구간 비율이 예상과 다름: %.3f vs %.3f" % (frac, want)

    # 조립 전체 폭이 정확히 450 (턱은 홈 안에 들어가므로 폭을 늘리지 않는다)
    assert abs(W * 2 - ROAD_W) < 1e-9
    assert abs(SEG_W * 2 - ROAD_W) < 1e-9

    # --- 턱이 단면 안에 들어가는가 (높이 여유) ---
    h_at_joint = min(profile(x0, TRAVEL_L, HEIGHT), profile(x1, TRAVEL_L, HEIGHT))
    assert h_at_joint > 3.0, "이음새 위치가 너무 얇음: %.2f mm" % h_at_joint

    # --- 턱 없음 ---
    assert abs(profile(0, TRAVEL_L, HEIGHT)) < 1e-12
    assert abs(profile(TRAVEL_L, TRAVEL_L, HEIGHT)) < 1e-12
    assert abs(profile(TRAVEL_L / 2, TRAVEL_L, HEIGHT) - HEIGHT) < 1e-12

    slope = math.degrees(math.atan(HEIGHT * math.pi / TRAVEL_L))
    print("selftest OK")
    print("  닫힌 메시 4종(민짜/턱/홈/턱+홈) x 2폭, 부피 오차 0.3% 이내")
    print("  이음새 전높이 턱 %gx%g mm, 이음새 지점 단면 높이 %.1f mm"
          % (TONGUE_X, TONGUE_Y, h_at_joint))
    print("  공차 %.2f mm — 가상 조립 간섭 없음, 이음새 틈 %.2f mm, 민짜 구간은 맞닿음"
          % (CLEARANCE, gap_joint))
    print("  턱 없음(양 끝 기울기 0), 최대 경사 %.1f도" % slope)


def emit_set(segments, height, steps, clear, prefix):
    """조각 N개 한 벌. 바깥쪽 면은 민짜, 안쪽 면끼리 턱/홈으로 물린다."""
    w = ROAD_W / segments
    made = []
    for i in range(segments):
        tongue = i < segments - 1          # 마지막 조각 빼고 +y 쪽에 턱
        groove = i > 0                     # 첫 조각 빼고 -y 쪽에 홈
        tris = build_mesh(w, TRAVEL_L, height, steps, tongue, groove, clear)
        ok, bad = is_watertight(tris)
        if not ok:
            sys.exit("[거부] %d번 조각 메시가 닫혀 있지 않습니다 (모서리 %d개)" % (i + 1, bad))
        role = ("턱" if tongue else "") + ("홈" if groove else "")
        name = "%s_%gmm_h%g_%d_of_%d.stl" % (prefix, w, height, i + 1, segments)
        write_stl(name, tris)
        made.append((name, role or "민짜", volume(tris) / 1000))
    return w, made


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="과속방지턱 STL 생성 (이음새 턱/홈 + 공차)")
    p.add_argument("--segments", type=int, default=2,
                   help="조각 수 (기본 2 — 450/2 = 225 mm, Bambu P1S 한 판)")
    p.add_argument("--height", type=float, default=HEIGHT, help="높이 mm (low/mid/high = 5/10/15)")
    p.add_argument("--clearance", type=float, default=CLEARANCE, help="이음새 공차 mm (기본 0.2)")
    p.add_argument("--steps", type=int, default=STEPS, help="곡선 분할 수")
    p.add_argument("--prefix", default="speed_bump", help="파일 이름 접두어")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        selftest()
        sys.exit(0)
    if a.segments < 1:
        sys.exit("[거부] --segments 는 1 이상이어야 합니다")

    w, made = emit_set(a.segments, a.height, a.steps, a.clearance, a.prefix)
    for name, role, vol_cm3 in made:
        print("  %-40s %-6s %6.1f cm3" % (name, role, vol_cm3))
    print("\n  조각 %d개 x %g mm = %g mm (도로 폭)" % (a.segments, w, a.segments * w))
    print("  단면 %g x %g mm, 최대 경사 %.1f도 (양 끝 기울기 0 — 턱 없음)"
          % (TRAVEL_L, a.height, math.degrees(math.atan(a.height * math.pi / TRAVEL_L))))
    print("  이음새 전높이 턱 %g x %g mm, 공차 %.2f mm" % (TONGUE_X, TONGUE_Y, a.clearance))
    BED = 246.0
    if w > BED:
        print("  ⚠ 조각 폭 %g mm — Bambu P1S(가용 %g mm)에 들어가지 않습니다" % (w, BED))
    else:
        rows = int((BED + 5) // 55)
        print("  P1S 256x256 판: 한 판에 최대 %d개 (%g x %d mm)"
              % (min(rows, a.segments), w, a.segments * 50 + (a.segments - 1) * 5))
