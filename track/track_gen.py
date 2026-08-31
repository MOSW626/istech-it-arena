#!/usr/bin/env python3
"""
track_gen.py -- Parametric track generator for the ISTech IT Arena
autonomous RC car competition: "후보1 통합 코스 (A+B)" (candidate 1, integrated
course).  Topology traced from the organizer's confirmed course-design image
and reproduced to scale inside the 11.0 x 14.5 m hall.

Single source of truth: running this script regenerates every deliverable
under output/ from the geometric design encoded below.

    python3 track_gen.py [--bump-height {low,mid,high}|meters]
                          [--resolution 0.01] [--scale 1.0] [--grid-cars 6]
                          [--outdir output]

Dependencies: numpy, matplotlib, opencv-python-headless (cv2.aruco), ezdxf,
pyyaml, shapely.

Course layout (see README.md for the full write-up):
  섹터 1 (start/finish straight -> speed bumps -> T1 헤어핀 -> gate①②)
  섹터 2 (협로 narrow section -> 노면변화 -> 직각 시케인 -> 에세스 -> gate②③)
  섹터 3 (시케인 hook -> 롱 스위퍼 -> starting grid -> start/finish)
  갈림길① : sector-3 shortcut bypassing the hook chicane
  갈림길② : shortcut connecting the sector1 start straight directly into the
            sector-2 narrow section, bypassing the T1 hairpin
"""
import argparse
import json
import math
import os
import sys

import numpy as np
import yaml

# ---------------------------------------------------------------------------
# Fixed competition constants (meters unless noted). All get multiplied by
# --scale so the whole venue package can be shrunk/grown consistently.
# ---------------------------------------------------------------------------
HALL_W = 11.0          # hall x-extent
HALL_H = 14.5          # hall y-extent
VEHICLE_L = 0.20                 # 대회 규정 차체 20cm(길이) x 15cm(폭)
VEHICLE_W = 0.15
TRACK_W = 0.35
NARROW_W = 0.12                 # 협로 width
NARROW_FLAT_LEN = 1.0            # length held at NARROW_W
NARROW_TAPER_LEN = 0.35          # linear taper in/out on each side
FRICTION_ZONE_LEN = 1.5          # 노면변화 patch length
GRASS_W = 0.20
WALL_T = 0.05
WALL_H = 0.30
MIN_RADIUS = 0.45
CHICANE_MIN_RADIUS = 0.30         # exception for the 직각 시케인 only
CLEARANCE_MIN = 0.35
BUMP_LEN = 0.05                 # along direction of travel
BUMP_SPACING = 0.6
BUMP_PRESETS = {"low": 0.005, "mid": 0.010, "high": 0.015}
ARUCO_DICT = "DICT_4X4_50"
ARUCO_SIZE = 0.10
ARUCO_MOUNT_H = 0.05             # bottom height of marker on wall
FORK_WIDTH = 0.35                 # alternate-route width

GRID_EXT = 2.0                    # extension of the pre-start straight (m)
GRID_SLOT_L = 0.25                # VEHICLE_L + 0.05
GRID_SLOT_W = 0.17                # VEHICLE_W + 0.02
GRID_STAGGER = 0.30               # longitudinal offset between the 2 columns
GRID_COL_OFFSET = 0.09            # lateral offset of each column from centerline
GRID_ROW_SPACING = 0.55           # longitudinal spacing between rows in a column
GRID_MARGIN_TO_START = 0.35       # gap left between last grid row and start line

REAL_IDS = {0: "start_finish", 10: "sector1_start", 20: "gate12", 30: "gate23", 45: "grid_entry"}
FAKE_IDS = [7, 23, 33]

# ---------------------------------------------------------------------------
# Course design -- traced from the organizer's reference image
# (후보1 통합 코스 A+B). Pixel coordinates below were digitized directly from
# that image (590x404 px, y-down) and are converted to design-meters (scale
# 1.0) via an affine fit that:
#   - rotates the (wide) image layout 90 deg so its long axis lines up with
#     the hall's long (14.5 m) axis,
#   - reserves GRID_EXT extra meters on the pre-start straight for the
#     starting grid (organizer's final change, not present in the image),
#   - centers the resulting bounding box in the hall with >=0.5 m margin
#     outside the track/grass/wall corridor on every side.
# ---------------------------------------------------------------------------
_PX_X0, _PX_X1 = 95.0, 580.0     # reference-image bbox (px) of the track ink
_PX_Y0, _PX_Y1 = 120.0, 347.0

_DESIGN_L = 11.3     # length-axis budget (m, design units) -> hall Y (14.5)
_DESIGN_W = 9.6      # width-axis budget (m, design units)  -> hall X (11.0)
_DESIGN_Y0 = 2.470206211419291
_DESIGN_X0 = 0.4602738590220885


def _fx(px):
    return (px - _PX_X0) / (_PX_X1 - _PX_X0)


def _fy(py):
    return (py - _PX_Y0) / (_PX_Y1 - _PX_Y0)


def _px2m(px, py, grid_shift=False):
    """Map a reference-image pixel coordinate to design-meters (scale 1.0),
    with the length axis (image-x) rotated onto world-Y and the width axis
    (image-y) rotated onto world-X. If grid_shift, subtracts GRID_EXT from
    the length coordinate (used only for the pre-start corner vertex, to
    open up room for the starting grid)."""
    length = _DESIGN_Y0 + _fx(px) * _DESIGN_L
    width = _DESIGN_X0 + _fy(py) * _DESIGN_W
    if grid_shift:
        length -= GRID_EXT
    return (width, length)


# Main-loop turn vertices, in travel order starting at the sector3->sector1
# corner (V_BL). Each tuple is (name, px, py, fillet_radius_m, is_chicane).
DESIGN_VERTICES_PX = [
    ("V_BL",     97, 335, 0.65, False),   # 롱 스위퍼 -> start straight corner
    ("V_HP_IN",  500, 332, 0.50, False),   # start of T1 헤어핀
    ("V_HP_TIP", 582, 297, 0.60, False),   # T1 헤어핀 apex (~180 deg)
    ("V_HP_OUT", 500, 265, 0.50, False),   # end of T1 헤어핀, into return lane
    ("V_N1",     197, 258, 0.45, False),   # 협로 exit corner (turn up)
    ("V_CHI_A",  172, 220, 0.30, True),    # 직각 시케인 corner 1
    ("V_CHI_B",  222, 208, 0.30, True),    # 직각 시케인 corner 2
    ("V_ESS2",   255, 160, 0.55, False),   # 에세스 bulge
    ("V_P1",     148, 142, 0.50, False),   # 섹터3 시케인(훅) upper bend
    ("V_P2",      98, 172, 0.55, False),   # 섹터3 시케인(훅) apex
    ("V_SWEEP",  108, 255, 1.30, False),   # 롱 스위퍼
]

GATE12_PX = (335, 280)             # gate①② : sector1 -> sector2
GATE23_PX = (200, 145)             # gate②③ : sector2 -> sector3
NARROW_CENTER_PX = (266, 269)      # 협로 midpoint
FRICTION_CENTER_PX = (200, 235)    # 노면변화 patch center
BUMP1_PX = (385, 347)              # speed-bump zone A: bottom straight
BUMP2_PX = (545, 322)              # speed-bump zone B: hairpin approach
STARTFINISH_PX = (97, 335)         # == original (pre-grid) V_BL location

FORK1_BRANCH_PX = (165, 138)       # 갈림길① branch (sector-3 hook entry)
FORK1_MERGE_PX = (100, 225)        # 갈림길① merge (before 롱 스위퍼)
FORK1_MID_PX = [(150, 200)]
FORK2_BRANCH_PX = (230, 335)       # 갈림길② branch (sector1 start straight)
FORK2_MERGE_PX = (230, 275)        # 갈림길② merge (섹터2 narrow-section area)
FORK2_MID_PX = [(255, 305)]


# ---------------------------------------------------------------------------
# Core geometry helpers (closed/open filleted polylines, offsets, sampling)
# ---------------------------------------------------------------------------
def build_rounded_polygon(vertices, radii, straight_step=0.03, arc_step=0.03):
    """Build a closed, exactly-continuous centerline from a polygon of
    vertices with per-vertex fillet radii. Returns (pts, vinfo, edge_len,
    warnings) where pts is a list of (x, y, theta, s)."""
    n = len(vertices)
    V = [np.array(v, dtype=float) for v in vertices]
    edge_dir, edge_len = [], []
    for i in range(n):
        a, b = V[i], V[(i + 1) % n]
        d = b - a
        L = float(np.hypot(*d))
        edge_dir.append(d / L)
        edge_len.append(L)

    vinfo = []
    for i in range(n):
        din = edge_dir[(i - 1) % n]
        dout = edge_dir[i]
        cross = din[0] * dout[1] - din[1] * dout[0]
        dot = float(np.clip(din[0] * dout[0] + din[1] * dout[1], -1, 1))
        turn = math.degrees(math.atan2(cross, dot))
        R = radii[i]
        t = R * math.tan(math.radians(abs(turn)) / 2.0) if abs(turn) > 1e-6 else 0.0
        fillet_start = V[i] - din * t
        fillet_end = V[i] + dout * t
        vinfo.append(dict(idx=i, turn=turn, R=R, t=t, fillet_start=fillet_start,
                           fillet_end=fillet_end, din=din, dout=dout, vertex=V[i]))

    warnings = []
    for i in range(n):
        t_prev = vinfo[i]["t"]
        t_next = vinfo[(i + 1) % n]["t"]
        avail = edge_len[i]
        if t_prev + t_next > avail - 1e-6:
            warnings.append(f"edge {i}->{(i+1)%n} too short: need "
                             f"{t_prev+t_next:.3f} m, have {avail:.3f} m")

    pts = []
    s = [0.0]

    def add_straight(p0, p1):
        L = float(np.hypot(*(p1 - p0)))
        if L < 1e-9:
            return
        n_s = max(1, int(L / straight_step))
        th = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        for k in range(1, n_s + 1):
            f = k / n_s
            p = p0 + (p1 - p0) * f
            pts.append((p[0], p[1], th, s[0] + L * f))
        s[0] += L

    def add_arc(info):
        R, turn = info["R"], info["turn"]
        if abs(turn) < 1e-6:
            return
        fs, fe, din = info["fillet_start"], info["fillet_end"], info["din"]
        left_normal = np.array([-din[1], din[0]])
        sign = 1.0 if turn > 0 else -1.0
        center = fs + left_normal * sign * R
        start_ang = math.atan2(fs[1] - center[1], fs[0] - center[0])
        ang_span = math.radians(turn)
        n_a = max(2, int(abs(ang_span) * R / arc_step))
        th0 = math.atan2(din[1], din[0])
        for k in range(1, n_a + 1):
            a = start_ang + ang_span * k / n_a
            p = center + R * np.array([math.cos(a), math.sin(a)])
            th = th0 + ang_span * k / n_a
            ds = R * abs(ang_span) * k / n_a
            pts.append((p[0], p[1], th, s[0] + ds))
        s[0] += R * abs(ang_span)

    start_pt = vinfo[0]["fillet_end"]
    pts.append((start_pt[0], start_pt[1],
                math.atan2(vinfo[0]["dout"][1], vinfo[0]["dout"][0]), 0.0))
    for i in range(n):
        nxt = (i + 1) % n
        add_straight(vinfo[i]["fillet_end"], vinfo[nxt]["fillet_start"])
        add_arc(vinfo[nxt])
    return pts, vinfo, edge_len, warnings


def wrap_heading(th):
    return (th + math.pi) % (2 * math.pi) - math.pi


def roll_to_start(pts, start_xy):
    """Re-index the closed centerline so that s=0 sits at the sample nearest
    the world point start_xy=(x,y)."""
    arr = np.array(pts)
    d = np.hypot(arr[:, 0] - start_xy[0], arr[:, 1] - start_xy[1])
    idx = int(np.argmin(d))
    L = arr[-1, 3]
    rolled = np.concatenate([arr[idx:], arr[:idx]], axis=0)
    s_offset = rolled[0, 3]
    new_s = (rolled[:, 3] - s_offset) % L
    new_s[0] = 0.0
    rolled[:, 3] = new_s
    return rolled, L


def offset_polyline(arr, offset):
    """Return points offset by `offset` meters (scalar or per-point array)
    along the local left normal (positive = left of travel direction)."""
    x, y, th = arr[:, 0], arr[:, 1], arr[:, 2]
    nx, ny = -np.sin(th), np.cos(th)
    off = offset if np.ndim(offset) else np.full_like(x, offset)
    return np.stack([x + nx * off, y + ny * off, th, arr[:, 3]], axis=1)


def sample_at_s(arr, s_query, Ltot):
    """Linear-interpolate (x,y,theta) at arc-length s_query (0..Ltot) on a
    closed, monotonically increasing-s polyline `arr`."""
    s = arr[:, 3]
    sq = s_query % Ltot
    if sq <= s[0] + 1e-12:
        return float(arr[0, 0]), float(arr[0, 1]), float(arr[0, 2])
    i = np.searchsorted(s, sq)
    i0 = (i - 1) % len(arr)
    i1 = i % len(arr)
    s0, s1 = s[i0], s[i1]
    if i1 == 0:
        s1 = Ltot
    f = 0.0 if s1 == s0 else (sq - s0) / (s1 - s0)
    x = arr[i0, 0] + f * (arr[i1, 0] - arr[i0, 0])
    y = arr[i0, 1] + f * (arr[i1, 1] - arr[i0, 1])
    th0, th1 = arr[i0, 2], arr[i1, 2]
    dth = wrap_heading(th1 - th0)
    th = th0 + f * dth
    return x, y, th


def nearest_s(arr, xy):
    d = np.hypot(arr[:, 0] - xy[0], arr[:, 1] - xy[1])
    i = int(np.argmin(d))
    return float(arr[i, 3]), float(d[i])


def circ_dist(s, s0, Ltot):
    d = abs((s - s0 + Ltot / 2.0) % Ltot - Ltot / 2.0)
    return d


def arc_span(s0, s1, Ltot):
    """Forward arc-length from s0 to s1 going in the direction of increasing s
    (wraps around the loop). Mirrors track_editor.html's arcSpan()."""
    return (s1 - s0) % Ltot


# ---------------------------------------------------------------------------
# --design mode geometry helpers -- these mirror the JS math in
# track_editor.html (crPoint / buildDenseCurve / resampleByArcLength /
# circumRadius / segIntersect) so that arc-length "s" coordinates recorded by
# the browser editor line up with the centerline rebuilt here in Python.
# ---------------------------------------------------------------------------
def cr_point(p0, p1, p2, p3, t):
    t2 = t * t
    t3 = t2 * t
    x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t +
               (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
               (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
    y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t +
               (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
               (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
    return (x, y)


def build_dense_curve(cps, closed, samples_per_seg=24):
    n = len(cps)
    if n < 2:
        return list(cps)
    seg_count = n if closed else n - 1

    def get(i):
        if closed:
            return cps[i % n]
        if i < 0:
            return cps[0]
        if i >= n:
            return cps[-1]
        return cps[i]

    pts = []
    for i in range(seg_count):
        p0, p1, p2, p3 = get(i - 1), get(i), get(i + 1), get(i + 2)
        start_k = 0 if i == 0 else 1
        for k in range(start_k, samples_per_seg + 1):
            pts.append(cr_point(p0, p1, p2, p3, k / samples_per_seg))
    return pts


def _locate_at(dense, cum, s, total, wrap_len, n):
    if s <= cum[-1]:
        lo, hi = 0, n - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if cum[mid] <= s:
                lo = mid
            else:
                hi = mid
        seg_len = cum[hi] - cum[lo]
        f = 0.0 if seg_len < 1e-12 else (s - cum[lo]) / seg_len
        return (dense[lo][0] + (dense[hi][0] - dense[lo][0]) * f,
                dense[lo][1] + (dense[hi][1] - dense[lo][1]) * f)
    else:
        f = 0.0 if wrap_len < 1e-12 else (s - cum[-1]) / wrap_len
        return (dense[-1][0] + (dense[0][0] - dense[-1][0]) * f,
                dense[-1][1] + (dense[0][1] - dense[-1][1]) * f)


def resample_by_arclength(dense, spacing, closed):
    n = len(dense)
    if n < 2:
        return list(dense)
    cum = [0.0]
    for i in range(1, n):
        cum.append(cum[-1] + math.hypot(dense[i][0] - dense[i - 1][0], dense[i][1] - dense[i - 1][1]))
    total = cum[-1]
    wrap_len = 0.0
    if closed:
        wrap_len = math.hypot(dense[-1][0] - dense[0][0], dense[-1][1] - dense[0][1])
        total += wrap_len
    count = max(4, round(total / spacing))
    out = []
    last_k = count if closed else count - 1
    for k in range(0, last_k + 1):
        if closed and k == count:
            break
        starget = (k / count) * total if closed else (k / (count - 1)) * total
        out.append(_locate_at(dense, cum, starget, total, wrap_len, n))
    return out


def _arr_from_resampled(rs, closed):
    """Shared tail end of both v2 (Catmull-Rom-rebuilt) and v3 (dense
    centerline-resampled) code paths: given a resampled list of (x,y) points,
    compute the [x,y,theta,s] array + total arc length."""
    n = len(rs)
    s = [0.0] * n
    for i in range(1, n):
        s[i] = s[i - 1] + math.hypot(rs[i][0] - rs[i - 1][0], rs[i][1] - rs[i - 1][1])
    total = s[-1]
    if closed:
        total += math.hypot(rs[-1][0] - rs[0][0], rs[-1][1] - rs[0][1])
    th = [0.0] * n
    for i in range(n):
        if closed:
            a, b = rs[(i - 1) % n], rs[(i + 1) % n]
        else:
            a, b = rs[max(0, i - 1)], rs[min(n - 1, i + 1)]
        th[i] = math.atan2(b[1] - a[1], b[0] - a[0])
    arr = np.array([[rs[i][0], rs[i][1], th[i], s[i]] for i in range(n)])
    return arr, float(total)


def build_arr_from_control_points(cps, closed, spacing=0.02):
    """Rebuild a (N,4) [x,y,theta,s] centerline array from design.json (v2)
    control_points, using the SAME Catmull-Rom + arc-length resample
    algorithm as track_editor.html so that feature "s" values line up.
    Only used for version < 3 designs -- see build_arr_from_centerline for
    version >= 3, which no longer curves everything through Catmull-Rom."""
    dense = build_dense_curve(cps, closed, 24)
    rs = resample_by_arclength(dense, spacing, closed)
    return _arr_from_resampled(rs, closed)


def build_arr_from_centerline(centerline_pts, closed, spacing=0.02):
    """Build a (N,4) [x,y,theta,s] centerline array directly from a v3
    design.json's dense "centerline" polyline (already containing straight
    fillet segments + arcs + Catmull-Rom spline runs, as drawn by
    track_editor.html's mixed corner/smooth point editor).

    Unlike build_arr_from_control_points, this does NOT rerun Catmull-Rom --
    that would smear the straight/fillet geometry the organizer drew back
    into curves. Instead we simply re-resample the already-dense polyline to
    a uniform arc-length grid (piecewise-linear interpolation between the
    existing ~5cm samples, which stays effectively exact on straight runs and
    introduces only a negligible chord error on arcs/splines)."""
    dense = [(float(p[0]), float(p[1])) for p in centerline_pts]
    if len(dense) < 2:
        raise ValueError("v3 design.json 'centerline' must have at least 2 points")
    rs = resample_by_arclength(dense, spacing, closed)
    return _arr_from_resampled(rs, closed)


def circum_radius(p1, p2, p3):
    a = math.hypot(p2[0] - p3[0], p2[1] - p3[1])
    b = math.hypot(p1[0] - p3[0], p1[1] - p3[1])
    c = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
    s = (a + b + c) / 2.0
    area_sq = max(0.0, s * (s - a) * (s - b) * (s - c))
    area = math.sqrt(area_sq)
    if area < 1e-9:
        return float("inf")
    return (a * b * c) / (4.0 * area)


def compute_min_radius(arr, closed, window_m=0.2, spacing=0.02):
    n = len(arr)
    off = max(1, round(window_m / spacing))
    min_r = float("inf")
    for i in range(n):
        if closed:
            a, c = arr[(i - off) % n], arr[(i + off) % n]
        else:
            i0, i1 = max(0, i - off), min(n - 1, i + off)
            if i0 == i or i1 == i:
                continue
            a, c = arr[i0], arr[i1]
        b = arr[i]
        R = circum_radius((a[0], a[1]), (b[0], b[1]), (c[0], c[1]))
        if R < min_r:
            min_r = R
    return min_r


def make_track_width_fn(base_w, narrow_zones, Ltot):
    """narrow_zones: list of dicts with s0, s1, width_m. Returns a
    track_width_at(s) callable that necks down to the narrowest applicable
    zone width with a NARROW_TAPER_LEN linear taper in/out."""
    def track_width_at(s):
        w = base_w
        for z in narrow_zones:
            span = arc_span(z["s0"], z["s1"], Ltot)
            mid = (z["s0"] + span / 2.0) % Ltot
            half_flat = span / 2.0
            d = circ_dist(s, mid, Ltot)
            taper = NARROW_TAPER_LEN
            if d <= half_flat:
                w = min(w, z["width_m"])
            elif d <= half_flat + taper:
                f = (d - half_flat) / taper
                w = min(w, z["width_m"] + f * (base_w - z["width_m"]))
        return w
    return track_width_at


def bumps_from_zone(arr, Ltot, s0, s1, bump_height, track_width_at):
    """One bump at the center of the zone (organizer decision 2026-07-27:
    single speed bump per zone)."""
    span = arc_span(s0, s1, Ltot)
    positions = [(s0 + span * 0.5) % Ltot]
    bumps = []
    for s in positions:
        x, y, th = sample_at_s(arr, s, Ltot)
        bumps.append(dict(x=float(x), y=float(y), yaw=float(th), s=float(s % Ltot),
                           length=BUMP_LEN, width=float(track_width_at(s % Ltot)),
                           height=bump_height))
    return bumps


def build_grid_zone_slots(arr, Ltot, s0, s1, cars):
    n_cols = 2
    n_rows = int(math.ceil(cars / n_cols))
    span = arc_span(s0, s1, Ltot)
    row_spacing = span / max(1, n_rows)
    col_offsets = [GRID_COL_OFFSET, -GRID_COL_OFFSET]
    col_stagger = [0.0, -min(GRID_STAGGER, row_spacing * 0.4)]
    slots = []
    car_idx = 0
    for col in range(n_cols):
        for row in range(n_rows):
            if car_idx >= cars:
                break
            s = (s0 + row_spacing * (row + 0.5) + col_stagger[col]) % Ltot
            x, y, th = sample_at_s(arr, s, Ltot)
            nx, ny = -math.sin(th), math.cos(th)
            gx, gy = x + nx * col_offsets[col], y + ny * col_offsets[col]
            slots.append(dict(index=car_idx, col=col, row=row, x=float(gx), y=float(gy),
                               yaw=float(th), s=float(s), length=GRID_SLOT_L, width=GRID_SLOT_W))
            car_idx += 1
    return slots


def markers_from_design(arr, Ltot, aruco_list, track_width_at, grass_half_at):
    markers = []
    for m in aruco_list:
        s = float(m["s"]) % Ltot
        side = 1.0 if m.get("side", "left") == "left" else -1.0
        x, y, th = sample_at_s(arr, s, Ltot)
        tw = track_width_at(s)
        gh = grass_half_at(s)
        off = side * (tw / 2.0 + gh * 0.4 + 0.05)
        mx = x - math.sin(th) * off
        my = y + math.cos(th) * off
        inward = (-side * (-math.sin(th)), -side * math.cos(th))
        yaw = math.atan2(inward[1], inward[0])
        mid = int(m["id"])
        fake = bool(m.get("fake", False))
        role = ("fake" if fake else REAL_IDS.get(mid, "custom"))
        markers.append(dict(id=mid, real=(not fake), role=role, x=float(mx), y=float(my),
                             z=ARUCO_MOUNT_H, yaw=float(yaw), s=float(s), note=m.get("note", "")))
    return markers


def traffic_light_from_design(arr, Ltot, tl, track_width_at):
    s = float(tl.get("s", 0.0)) % Ltot
    x, y, th = sample_at_s(arr, s, Ltot)
    tw = track_width_at(s)
    return dict(x=float(x), y=float(y), yaw=float(th), width=float(tw), gantry_height=1.2,
                lamps=["red", "yellow", "green"], side=tl.get("side", "left"), s=float(s))


def get_friction_zones(res):
    """Unify classic build_all()'s single 'friction_zone' dict and design
    mode's 'friction_zones' list into one list."""
    if "friction_zones" in res:
        return res["friction_zones"]
    if res.get("friction_zone"):
        return [res["friction_zone"]]
    return []


def get_narrow_targets(res):
    """Unify classic single narrow-section fields and design mode's
    meta['narrow_zones'] list into one list of dicts: s_center, width_m."""
    meta = res["meta"]
    if meta.get("narrow_zones"):
        return [dict(s_center=z["s_center"], width_m=z["width_m"]) for z in meta["narrow_zones"]]
    if meta.get("narrow_center_s") is not None:
        return [dict(s_center=meta["narrow_center_s"], width_m=meta["narrow_w"])]
    return []


def load_design(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def rounded_open_polyline(vertices, radii, straight_step=0.02, arc_step=0.02):
    """Fillet an OPEN polyline (used for the alternate-route forks)."""
    n = len(vertices)
    V = [np.array(v, dtype=float) for v in vertices]
    edge_dir, edge_len = [], []
    for i in range(n - 1):
        d = V[i + 1] - V[i]
        L = float(np.hypot(*d))
        edge_dir.append(d / L)
        edge_len.append(L)
    pts = []
    s = [0.0]
    pts_last = [None]

    def add_straight(p0, p1):
        L = float(np.hypot(*(p1 - p0)))
        if L < 1e-9:
            return
        n_s = max(1, int(L / straight_step))
        th = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        for k in range(0 if not pts else 1, n_s + 1):
            f = k / n_s
            p = p0 + (p1 - p0) * f
            pts.append((p[0], p[1], th, s[0] + L * f))
        s[0] += L

    if n == 2:
        add_straight(V[0], V[1])
        return pts

    for i in range(1, n - 1):
        din = edge_dir[i - 1]
        dout = edge_dir[i]
        cross = din[0] * dout[1] - din[1] * dout[0]
        dot = float(np.clip(din[0] * dout[0] + din[1] * dout[1], -1, 1))
        turn = math.degrees(math.atan2(cross, dot))
        R = radii[i - 1] if i - 1 < len(radii) else 0.0
        t = R * math.tan(math.radians(abs(turn)) / 2.0) if abs(turn) > 1e-6 and R > 0 else 0.0
        fs = V[i] - din * t
        fe = V[i] + dout * t
        add_straight(V[i - 1] if i == 1 else pts_last[0], fs)
        if abs(turn) > 1e-6 and R > 0:
            left_normal = np.array([-din[1], din[0]])
            sign = 1.0 if turn > 0 else -1.0
            center = fs + left_normal * sign * R
            start_ang = math.atan2(fs[1] - center[1], fs[0] - center[0])
            ang_span = math.radians(turn)
            n_a = max(2, int(abs(ang_span) * R / arc_step))
            th0 = math.atan2(din[1], din[0])
            for k in range(1, n_a + 1):
                a = start_ang + ang_span * k / n_a
                p = center + R * np.array([math.cos(a), math.sin(a)])
                th = th0 + ang_span * k / n_a
                ds = R * abs(ang_span) * k / n_a
                pts.append((p[0], p[1], th, s[0] + ds))
            s[0] += R * abs(ang_span)
        pts_last[0] = fe
    add_straight(pts_last[0], V[-1])
    return pts


def decimate_by_arclength(arr, step, closed=True):
    """Pick a subsequence of an (N,4) [x,y,th,s] array spaced ~step meters apart."""
    s = arr[:, 3]
    Ltot = s[-1]
    n_pick = max(4, int(round(Ltot / step)))
    s_targets = np.linspace(0, Ltot, n_pick, endpoint=not closed)
    idxs = np.searchsorted(s, s_targets)
    idxs = np.clip(idxs, 0, len(arr) - 1)
    idxs = sorted(set(idxs.tolist()))
    return arr[idxs]


def build_ribbon_boxes(points_xy_th, width, closed=True, overlap=1.15):
    """Turn a decimated polyline into a chain of oriented boxes (for SDF/rasterization)."""
    boxes = []
    n = len(points_xy_th)
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = points_xy_th[i]
        p1 = points_xy_th[(i + 1) % n]
        cx, cy = (p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if L < 1e-6:
            continue
        yaw = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        w = width[i] if np.ndim(width) else width
        boxes.append(dict(x=cx, y=cy, yaw=yaw, length=L * overlap, width=w))
    return boxes


def box_corners(b):
    hl, hw = b["length"] / 2.0, b["width"] / 2.0
    c, s = math.cos(b["yaw"]), math.sin(b["yaw"])
    pts = []
    for lx, ly in [(-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw)]:
        pts.append((b["x"] + lx * c - ly * s, b["y"] + lx * s + ly * c))
    return pts


# ---------------------------------------------------------------------------
# BRANCH ("갈림길"/지름길) mouth handling.
#
# A branch shares its two endpoints with the main centerline -- they are
# literally the same point in space (anchors). Its ribbon therefore overlaps
# the main ribbon in a small "mouth" region around each anchor. Approach:
#
#   1. DRIVABLE SURFACE (occupancy grid / SDF / preview fill): paint the main
#      surface and every branch surface as independent box chains. Since all
#      "surface_*" boxes are simply rasterized/rendered as free space without
#      erasing each other, the overlap at the mouth is automatically the
#      union drivable_union = main_ribbon UNION branch_ribbon -- no boolean
#      geometry library needed for this part.
#   2. WALLS / GRASS: for each branch and each of its two anchors, walk along
#      the branch outward from that anchor and find how far it stays within
#      "gap_margin" of the main centerline (gap_margin sized so it covers the
#      main track + grass corridor plus half the branch width, i.e. the
#      widest either ribbon could reach). That gives a short main-arc-length
#      window (on the side the branch departs on) where a wall/grass strip
#      would otherwise cut straight across the branch mouth -- we omit
#      wall/grass boxes there. Symmetrically, we omit the BRANCH's own
#      wall over the matching stretch of its own arc-length near that
#      anchor (its wall only starts once it has visibly separated from the
#      main ribbon). The two walls then line up into one continuous
#      boundary around the drivable union, open exactly at the two mouths.
# ---------------------------------------------------------------------------
def _reversed_with_relative_s(arr):
    """Reverse a (N,4) [x,y,th,s] array and re-zero its s column so index 0
    is the (former) last point with s=0 -- i.e. re-express arc length as
    "distance from the far end" instead of "distance from the near end"."""
    total = float(arr[-1, 3])
    rev = arr[::-1].copy()
    rev[:, 3] = total - rev[:, 3]
    return rev


def compute_branch_mouth_extent(main_arr, branch_pts_ordered, gap_margin):
    """Walk branch_pts_ordered (rows of a branch's (N,4) array, ordered
    OUTWARD starting from one anchor) and find how far the branch stays
    within gap_margin of the main centerline. Returns None if not even the
    anchor point itself is within gap_margin (shouldn't normally happen,
    since the anchor sits exactly ON the main line), otherwise a dict with:
      main_s_lo, main_s_hi : the affected MAIN arc-length window (wraps mod Ltot)
      side                 : 'left' or 'right' (which side of the main line)
      branch_s_reach       : how far (in the branch's own arc length, from
                              the anchor this ordering starts at) the overlap
                              extends -- i.e. the branch's own wall should
                              start only after this distance.
    """
    Ltot = float(main_arr[-1, 3])
    s_vals = []
    side_votes = {}
    branch_s_reach = 0.0
    for p in branch_pts_ordered:
        s_main, d = nearest_s(main_arr, (p[0], p[1]))
        if d >= gap_margin:
            break
        mx, my, mth = sample_at_s(main_arr, s_main, Ltot)
        nx, ny = -math.sin(mth), math.cos(mth)
        side = "left" if ((p[0] - mx) * nx + (p[1] - my) * ny) >= 0 else "right"
        s_vals.append(s_main)
        side_votes[side] = side_votes.get(side, 0) + 1
        branch_s_reach = float(p[3])
    if not s_vals:
        return None
    side = max(side_votes, key=side_votes.get)
    # unwrap the collected main-s values relative to the first one so a run
    # that happens to straddle the s=0/Ltot seam doesn't come out inverted
    unwrapped = [s_vals[0]]
    for s in s_vals[1:]:
        d = s - unwrapped[-1]
        d = (d + Ltot / 2.0) % Ltot - Ltot / 2.0
        unwrapped.append(unwrapped[-1] + d)
    lo, hi = min(unwrapped), max(unwrapped)
    pad = 0.05
    return dict(main_s_lo=(lo - pad) % Ltot, main_s_hi=(hi + pad) % Ltot,
                side=side, branch_s_reach=branch_s_reach + pad)


def build_ribbon_boxes_with_gaps(points_xy_th_s, width, gaps_s, closed=True, overlap=1.15):
    """Like build_ribbon_boxes, but splits the chain wherever a point's arc
    length s falls inside one of the gaps_s = [(s_lo, s_hi), ...] windows
    (each window may wrap through 0, i.e. s_lo > s_hi means "s >= s_lo OR
    s <= s_hi"), and does not bridge a box across a gap. This is what
    actually cuts an opening into the main track's wall/grass chain (or a
    branch's own wall chain) at a branch mouth."""
    n = len(points_xy_th_s)
    if n == 0:
        return []
    width_is_arr = bool(np.ndim(width))

    def in_gap(s):
        for lo, hi in gaps_s:
            if lo <= hi:
                if lo <= s <= hi:
                    return True
            else:
                if s >= lo or s <= hi:
                    return True
        return False

    keep = [not in_gap(float(points_xy_th_s[i][3])) for i in range(n)]
    idxs = list(range(n)) + ([0] if closed else [])

    boxes = []
    cur_pts, cur_w = [], []

    def flush():
        if len(cur_pts) >= 2:
            w = np.array(cur_w) if width_is_arr else width
            boxes.extend(build_ribbon_boxes(np.array(cur_pts), w, closed=False, overlap=overlap))

    for idx in idxs:
        j = idx % n
        if keep[j]:
            cur_pts.append(points_xy_th_s[j])
            if width_is_arr:
                cur_w.append(width[j])
        else:
            flush()
            cur_pts, cur_w = [], []
    flush()
    return boxes


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def build_all(scale=1.0, resolution=0.01, bump_height=0.010, grid_cars=6, outdir="output"):
    sc = scale
    names = [v[0] for v in DESIGN_VERTICES_PX]
    is_chicane = {v[0]: v[4] for v in DESIGN_VERTICES_PX}
    pts_xy = []
    radii = []
    for name, px, py, r, _chi in DESIGN_VERTICES_PX:
        x, y = _px2m(px, py, grid_shift=(name == "V_BL"))
        pts_xy.append((x * sc, y * sc))
        radii.append(r * sc)

    raw_pts, vinfo, edge_len, warn = build_rounded_polygon(pts_xy, radii)
    sf_xy = _px2m(*STARTFINISH_PX)
    arr, Ltot = roll_to_start(raw_pts, (sf_xy[0] * sc, sf_xy[1] * sc))

    track_w0 = TRACK_W * sc
    narrow_w0 = NARROW_W * sc
    grass_w0 = GRASS_W * sc
    wall_t = WALL_T * sc
    wall_h = WALL_H * sc
    taper_len = NARROW_TAPER_LEN * sc
    flat_len = NARROW_FLAT_LEN * sc
    fric_len = FRICTION_ZONE_LEN * sc

    narrow_xy = (_px2m(*NARROW_CENTER_PX)[0] * sc, _px2m(*NARROW_CENTER_PX)[1] * sc)
    narrow_center_s, _ = nearest_s(arr, narrow_xy)

    def track_width_at(s):
        d = circ_dist(s, narrow_center_s, Ltot)
        half_flat = flat_len / 2.0
        if d <= half_flat:
            return narrow_w0
        elif d <= half_flat + taper_len:
            f = (d - half_flat) / taper_len
            return narrow_w0 + f * (track_w0 - narrow_w0)
        return track_w0

    def grass_half_at(s):
        tw = track_width_at(s)
        return max(0.03 * sc, grass_w0 * (tw / track_w0))

    tw_arr = np.array([track_width_at(s) for s in arr[:, 3]])
    gh_arr = np.array([grass_half_at(s) for s in arr[:, 3]])

    left_b = offset_polyline(arr, tw_arr / 2.0)
    right_b = offset_polyline(arr, -tw_arr / 2.0)
    left_grass_out = offset_polyline(arr, tw_arr / 2.0 + gh_arr)
    right_grass_out = offset_polyline(arr, -(tw_arr / 2.0 + gh_arr))
    left_wall_c = offset_polyline(arr, tw_arr / 2.0 + gh_arr + wall_t / 2.0)
    right_wall_c = offset_polyline(arr, -(tw_arr / 2.0 + gh_arr + wall_t / 2.0))

    # ---- gates ----
    gate12_xy = (_px2m(*GATE12_PX)[0] * sc, _px2m(*GATE12_PX)[1] * sc)
    gate23_xy = (_px2m(*GATE23_PX)[0] * sc, _px2m(*GATE23_PX)[1] * sc)
    gate12_s, _ = nearest_s(arr, gate12_xy)
    gate23_s, _ = nearest_s(arr, gate23_xy)

    sectors = [
        dict(name="sector1", s_start=0.0, s_end=gate12_s),
        dict(name="sector2", s_start=gate12_s, s_end=gate23_s),
        dict(name="sector3", s_start=gate23_s, s_end=Ltot),
    ]

    # ---- friction zone (노면변화) ----
    fric_xy = (_px2m(*FRICTION_CENTER_PX)[0] * sc, _px2m(*FRICTION_CENTER_PX)[1] * sc)
    fric_s, _ = nearest_s(arr, fric_xy)
    friction_zone = dict(s_center=fric_s, s_start=(fric_s - fric_len / 2.0) % Ltot,
                          s_end=(fric_s + fric_len / 2.0) % Ltot, length=fric_len,
                          note="노면변화: 마찰계수 변경 구간 (아스팔트->저마찰 표면)")

    # ---- alternate routes (forks) ----
    def build_fork(branch_px, merge_px, mid_px_list, radius=0.5):
        b_xy = (_px2m(*branch_px)[0] * sc, _px2m(*branch_px)[1] * sc)
        m_xy = (_px2m(*merge_px)[0] * sc, _px2m(*merge_px)[1] * sc)
        branch_s, _ = nearest_s(arr, b_xy)
        merge_s, _ = nearest_s(arr, m_xy)
        p0 = np.array(sample_at_s(arr, branch_s, Ltot)[:2])
        p1 = np.array(sample_at_s(arr, merge_s, Ltot)[:2])
        mids = [np.array((_px2m(*p)[0] * sc, _px2m(*p)[1] * sc)) for p in mid_px_list]
        verts = [p0] + mids + [p1]
        rads = [radius * sc] * len(mids)
        pts = rounded_open_polyline(verts, rads, straight_step=0.02, arc_step=0.02)
        farr = np.array(pts)
        return dict(arr=farr, branch_s=branch_s, merge_s=merge_s, length=float(farr[-1, 3]))

    fork1 = build_fork(FORK1_BRANCH_PX, FORK1_MERGE_PX, FORK1_MID_PX, radius=0.5)
    fork2 = build_fork(FORK2_BRANCH_PX, FORK2_MERGE_PX, FORK2_MID_PX, radius=0.5)
    fork_w = FORK_WIDTH * sc
    fork1_left = offset_polyline(fork1["arr"], fork_w / 2.0)
    fork1_right = offset_polyline(fork1["arr"], -fork_w / 2.0)
    fork2_left = offset_polyline(fork2["arr"], fork_w / 2.0)
    fork2_right = offset_polyline(fork2["arr"], -fork_w / 2.0)

    def bypassed_len(branch_s, merge_s):
        return (merge_s - branch_s) % Ltot

    fork1_bypass = bypassed_len(fork1["branch_s"], fork1["merge_s"])
    fork2_bypass = bypassed_len(fork2["branch_s"], fork2["merge_s"])
    lap_via_fork1 = Ltot - fork1_bypass + fork1["length"]
    lap_via_fork2 = Ltot - fork2_bypass + fork2["length"]

    # ---- speed bumps: two hazard-striped zones, 3 bumps @ 0.6 m each ----
    def bump_zone(center_px):
        c_xy = (_px2m(*center_px)[0] * sc, _px2m(*center_px)[1] * sc)
        s0, _ = nearest_s(arr, c_xy)
        offs = [-BUMP_SPACING * sc, 0.0, BUMP_SPACING * sc]
        zone = []
        for o in offs:
            s = s0 + o
            x, y, th = sample_at_s(arr, s, Ltot)
            zone.append(dict(x=float(x), y=float(y), yaw=float(th), s=float(s % Ltot),
                              length=BUMP_LEN * sc, width=track_width_at(s % Ltot),
                              height=bump_height * sc))
        return zone

    bumps = bump_zone(BUMP1_PX) + bump_zone(BUMP2_PX)

    # ---- traffic light gantry at start/finish ----
    tlx, tly, tlth = sample_at_s(arr, 0.0, Ltot)
    traffic_light = dict(x=float(tlx), y=float(tly), yaw=float(tlth), width=track_w0,
                          gantry_height=1.2 * sc, lamps=["red", "yellow", "green"])

    # ---- starting grid: grid_cars in 2 staggered columns, before s=0 ----
    n_cols = 2
    n_rows = int(math.ceil(grid_cars / n_cols))
    grid_slots = []
    # row 0 (closest to start line) sits GRID_MARGIN_TO_START before s=0
    row0_s = -(GRID_MARGIN_TO_START * sc) - GRID_SLOT_L * sc / 2.0
    col_offsets = [GRID_COL_OFFSET * sc, -GRID_COL_OFFSET * sc]
    col_stagger = [0.0, -GRID_STAGGER * sc]
    car_idx = 0
    for col in range(n_cols):
        for row in range(n_rows):
            if car_idx >= grid_cars:
                break
            s = row0_s - row * GRID_ROW_SPACING * sc + col_stagger[col]
            x, y, th = sample_at_s(arr, s % Ltot, Ltot)
            nx, ny = -math.sin(th), math.cos(th)
            gx = x + nx * col_offsets[col]
            gy = y + ny * col_offsets[col]
            grid_slots.append(dict(index=car_idx, col=col, row=row, x=float(gx), y=float(gy),
                                    yaw=float(th), s=float(s % Ltot),
                                    length=GRID_SLOT_L * sc, width=GRID_SLOT_W * sc))
            car_idx += 1
    grid_start_s = (row0_s - (n_rows - 1) * GRID_ROW_SPACING * sc - GRID_SLOT_L * sc) % Ltot

    # ---- ArUco markers ----
    centroid = np.mean(pts_xy, axis=0) * sc

    def outer_side_offset(x, y, th):
        nxl, nyl = -math.sin(th), math.cos(th)
        vx, vy = x - centroid[0], y - centroid[1]
        return 1.0 if (vx * nxl + vy * nyl) > 0 else -1.0

    def marker_pose(s_query, note=""):
        x, y, th = sample_at_s(arr, s_query, Ltot)
        tw = track_width_at(s_query % Ltot)
        gh = grass_half_at(s_query % Ltot)
        side = outer_side_offset(x, y, th)
        off = side * (tw / 2.0 + gh * 0.4 + 0.05 * sc)
        mx = x - math.sin(th) * off
        my = y + math.cos(th) * off
        inward = (-side * (-math.sin(th)), -side * math.cos(th))
        yaw = math.atan2(inward[1], inward[0])
        return dict(x=float(mx), y=float(my), z=ARUCO_MOUNT_H * sc, yaw=float(yaw),
                    s=float(s_query % Ltot), note=note)

    markers = []
    markers.append(dict(id=0, real=True, role="start_finish", **marker_pose(0.0, "출발/결승선")))
    markers.append(dict(id=10, real=True, role="sector1_start", **marker_pose(0.6 * sc, "섹터1 시작 (출발선 직후)")))
    markers.append(dict(id=20, real=True, role="gate12", **marker_pose(gate12_s, "게이트①② (섹터2 시작)")))
    markers.append(dict(id=30, real=True, role="gate23", **marker_pose(gate23_s, "게이트②③ (섹터3 시작)")))
    markers.append(dict(id=45, real=True, role="grid_entry", **marker_pose(grid_start_s, "그리드 진입 (섹터3 출구)")))

    fake_defs = [
        (7, gate12_s + 1.2 * sc, "허위 마커: 섹터2 협로 부근 (반대편 벽)"),
        (23, gate23_s - 0.8 * sc, "허위 마커: 섹터3 진입 직전 (잘못된 벽)"),
        (33, Ltot - 1.0 * sc, "허위 마커: 그리드 진입 부근 (반대편 벽)"),
    ]
    for fid, sfake, note in fake_defs:
        x, y, th = sample_at_s(arr, sfake % Ltot, Ltot)
        tw = track_width_at(sfake % Ltot)
        gh = grass_half_at(sfake % Ltot)
        side = -outer_side_offset(x, y, th)
        off = side * (tw / 2.0 + gh * 0.4 + 0.05 * sc)
        mx = x - math.sin(th) * off
        my = y + math.cos(th) * off
        inward = (-side * (-math.sin(th)), -side * math.cos(th))
        yaw = math.atan2(inward[1], inward[0])
        markers.append(dict(id=fid, real=False, role="fake", x=float(mx), y=float(my),
                             z=ARUCO_MOUNT_H * sc, yaw=float(yaw), s=float(sfake % Ltot), note=note))

    min_r_general = min(r for n, r in zip(names, radii) if not is_chicane[n])
    min_r_chicane = min([r for n, r in zip(names, radii) if is_chicane[n]], default=None)

    meta = dict(
        scale=sc, resolution=resolution, bump_height=bump_height, grid_cars=grid_cars,
        Ltot=float(Ltot), track_w=track_w0, narrow_w=narrow_w0, grass_w=grass_w0,
        wall_t=wall_t, wall_h=wall_h, sectors=sectors, warnings=warn, vinfo_names=names,
        radii=radii, is_chicane=is_chicane, min_r_general=float(min_r_general),
        min_r_chicane=(float(min_r_chicane) if min_r_chicane is not None else None),
        centroid=centroid.tolist(), startfinish_s=0.0, gate12_s=float(gate12_s),
        gate23_s=float(gate23_s), narrow_center_s=float(narrow_center_s),
        narrow_s_range=((narrow_center_s - flat_len / 2.0) % Ltot,
                         (narrow_center_s + flat_len / 2.0) % Ltot),
        grid_start_s=float(grid_start_s), grid_ext=GRID_EXT * sc,
        fork1_bypass_len=float(fork1_bypass), fork2_bypass_len=float(fork2_bypass),
        lap_via_fork1=float(lap_via_fork1), lap_via_fork2=float(lap_via_fork2),
    )

    return dict(arr=arr, left_b=left_b, right_b=right_b, left_grass_out=left_grass_out,
                right_grass_out=right_grass_out, left_wall_c=left_wall_c, right_wall_c=right_wall_c,
                tw_arr=tw_arr, gh_arr=gh_arr,
                fork1=fork1, fork2=fork2, fork1_left=fork1_left, fork1_right=fork1_right,
                fork2_left=fork2_left, fork2_right=fork2_right,
                markers=markers, bumps=bumps, traffic_light=traffic_light,
                friction_zone=friction_zone, grid_slots=grid_slots, meta=meta,
                vinfo=vinfo, names=names, edge_len=edge_len,
                track_width_at=track_width_at, grass_half_at=grass_half_at)


def build_all_from_design(design, resolution=0.01, bump_height=0.010, grid_cars_override=None, outdir="output"):
    """Build the same `res` dict shape as build_all(), but sourced entirely
    from a track_editor.html design.json (organizer-drawn centerline)
    instead of the built-in 후보1 통합 코스 layout. No gates/sectors -- those
    are a built-in-course-only concept. v4 designs MAY include "branches"
    (갈림길/지름길): separate narrow lanes that fork off the main centerline
    and rejoin it later, both routes drivable -- see build_geometry_boxes()
    for how their walls/grass are cut to leave open mouths where they meet
    the main track."""
    version = design.get("version", 2)
    if version not in (2, 3, 4):
        print(f"[track_gen] WARNING: design.json version={version!r}, expected 2, 3 or 4 -- continuing anyway")

    track_w0 = float(design.get("track_width_m", TRACK_W))
    closed = bool(design.get("closed", True))

    if version >= 3:
        # v3: control_points may mix 'corner' (straight + fillet) and
        # 'smooth' (Catmull-Rom) points. DO NOT rebuild the centerline from
        # control_points here -- that would re-run global Catmull-Rom and
        # curve every straight segment the organizer drew. Use the dense
        # "centerline" polyline the editor already resampled instead.
        centerline_in = design.get("centerline")
        if not centerline_in or len(centerline_in) < 2:
            raise ValueError("v3 design.json is missing a dense 'centerline' array "
                              "(track_editor.html should always export one)")
        arr, Ltot = build_arr_from_centerline(centerline_in, closed, spacing=0.02)
    else:
        # v2 (or unversioned legacy): control_points are plain [x,y] pairs and
        # the whole centerline is one global Catmull-Rom curve through them.
        cps = [(float(p[0]), float(p[1])) for p in design["control_points"]]
        if len(cps) < 3:
            raise ValueError("design.json control_points must have at least 3 points")
        arr, Ltot = build_arr_from_control_points(cps, closed, spacing=0.02)

    # v4: "branches" (갈림길/지름길) -- each one is its own OPEN dense
    # centerline (already includes its two anchor points, which coincide
    # exactly with points on the MAIN centerline at s0/s1) exported by
    # track_editor.html. Just like the main v3+ centerline, we re-resample
    # the already-dense polyline rather than rebuilding it from
    # control_points, so the organizer's straight/fillet/spline geometry is
    # preserved exactly.
    branches = []
    for bi, b in enumerate(design.get("branches") or []):
        centerline_b = b.get("centerline")
        if not centerline_b or len(centerline_b) < 2:
            print(f"[track_gen] WARNING: branch #{bi} ({b.get('name','?')}) has no dense "
                  f"centerline -- skipping")
            continue
        barr, blen = build_arr_from_centerline(centerline_b, closed=False, spacing=0.02)
        branches.append(dict(
            name=b.get("name", f"갈림길{bi + 1}"),
            width_m=float(b.get("width_m", NARROW_W)),
            s0=float(b.get("s0", 0.0)) % Ltot,
            s1=float(b.get("s1", 0.0)) % Ltot,
            arr=barr, length=float(blen),
        ))

    feats = design.get("features", {}) or {}
    narrow_zones_in = feats.get("narrow_zones") or []
    narrow_zones = [dict(s0=float(z["s0"]) % Ltot, s1=float(z["s1"]) % Ltot,
                          width_m=float(z.get("width_m", NARROW_W))) for z in narrow_zones_in]

    track_width_at = make_track_width_fn(track_w0, narrow_zones, Ltot)
    grass_w0 = GRASS_W

    def grass_half_at(s):
        tw = track_width_at(s)
        return max(0.03, grass_w0 * (tw / track_w0))

    tw_arr = np.array([track_width_at(s) for s in arr[:, 3]])
    gh_arr = np.array([grass_half_at(s) for s in arr[:, 3]])

    wall_t, wall_h = WALL_T, WALL_H
    left_b = offset_polyline(arr, tw_arr / 2.0)
    right_b = offset_polyline(arr, -tw_arr / 2.0)
    left_grass_out = offset_polyline(arr, tw_arr / 2.0 + gh_arr)
    right_grass_out = offset_polyline(arr, -(tw_arr / 2.0 + gh_arr))
    left_wall_c = offset_polyline(arr, tw_arr / 2.0 + gh_arr + wall_t / 2.0)
    right_wall_c = offset_polyline(arr, -(tw_arr / 2.0 + gh_arr + wall_t / 2.0))

    bumps = []
    for z in feats.get("bump_zones") or []:
        bumps += bumps_from_zone(arr, Ltot, float(z["s0"]) % Ltot, float(z["s1"]) % Ltot,
                                  bump_height, track_width_at)

    friction_zones = []
    for z in feats.get("friction_zones") or []:
        s0, s1 = float(z["s0"]) % Ltot, float(z["s1"]) % Ltot
        span = arc_span(s0, s1, Ltot)
        s_center = (s0 + span / 2.0) % Ltot
        friction_zones.append(dict(s_center=s_center, s_start=s0, s_end=s1, length=span,
                                    note="노면변화: 마찰계수 변경 구간 (아스팔트->저마찰 표면)"))

    grid_slots = []
    grid_cars = 0
    gz = feats.get("grid_zone")
    if gz:
        grid_cars = int(grid_cars_override if grid_cars_override is not None else gz.get("cars", 6))
        grid_slots = build_grid_zone_slots(arr, Ltot, float(gz["s0"]) % Ltot, float(gz["s1"]) % Ltot, grid_cars)

    tl_in = feats.get("traffic_light") or {"s": 0.0, "side": "left"}
    traffic_light = traffic_light_from_design(arr, Ltot, tl_in, track_width_at)

    markers = markers_from_design(arr, Ltot, feats.get("aruco") or [], track_width_at, grass_half_at)

    min_r_general = compute_min_radius(arr, closed)

    startfinish_s = 0.0
    sl = feats.get("start_line")
    if sl:
        startfinish_s = float(sl["s"]) % Ltot

    centroid = arr[:, :2].mean(axis=0)

    meta_narrow_zones = []
    for z in narrow_zones:
        span = arc_span(z["s0"], z["s1"], Ltot)
        meta_narrow_zones.append(dict(s_center=(z["s0"] + span / 2.0) % Ltot,
                                       width_m=z["width_m"], s0=z["s0"], s1=z["s1"]))

    meta = dict(
        scale=1.0, resolution=resolution, bump_height=bump_height, grid_cars=grid_cars,
        Ltot=float(Ltot), track_w=track_w0,
        narrow_w=(narrow_zones[0]["width_m"] if narrow_zones else track_w0),
        grass_w=grass_w0, wall_t=wall_t, wall_h=wall_h, sectors=[], warnings=[],
        vinfo_names=[], radii=[], is_chicane={}, min_r_general=float(min_r_general), min_r_chicane=None,
        centroid=centroid.tolist(), startfinish_s=startfinish_s,
        narrow_zones=meta_narrow_zones,
        grid_start_s=(float(gz["s0"]) % Ltot if gz else 0.0), grid_ext=0.0,
        design_mode=True,
    )

    return dict(arr=arr, left_b=left_b, right_b=right_b, left_grass_out=left_grass_out,
                right_grass_out=right_grass_out, left_wall_c=left_wall_c, right_wall_c=right_wall_c,
                tw_arr=tw_arr, gh_arr=gh_arr, branches=branches,
                markers=markers, bumps=bumps, traffic_light=traffic_light,
                friction_zones=friction_zones, grid_slots=grid_slots, meta=meta,
                vinfo=[], names=[], edge_len=[],
                track_width_at=track_width_at, grass_half_at=grass_half_at)


# ---------------------------------------------------------------------------
# Verification checks
# ---------------------------------------------------------------------------
def run_checks(res):
    arr = res["arr"]
    meta = res["meta"]
    track_w = meta["track_w"]
    grass_w = meta["grass_w"]
    wall_t = meta["wall_t"]
    Ltot = meta["Ltot"]
    sc = meta["scale"]
    results = {}

    # 1. min radius: general vertices >= MIN_RADIUS, chicane vertices >= CHICANE_MIN_RADIUS
    results["min_centerline_radius_general_m"] = round(meta["min_r_general"], 4)
    results["min_radius_general_ok"] = meta["min_r_general"] >= MIN_RADIUS * sc - 1e-9
    results["min_centerline_radius_chicane_m"] = (round(meta["min_r_chicane"], 4)
                                                    if meta["min_r_chicane"] is not None else None)
    results["min_radius_chicane_ok"] = (meta["min_r_chicane"] is None or
                                         meta["min_r_chicane"] >= CHICANE_MIN_RADIUS * sc - 1e-9)

    # 2. bounding box incl. outer wall footprint fits hall with margin
    has_forks = res.get("fork1") is not None
    branches = res.get("branches") or []
    half_corridor = track_w / 2.0 + grass_w + wall_t
    if has_forks:
        xs = np.concatenate([arr[:, 0], res["fork1"]["arr"][:, 0], res["fork2"]["arr"][:, 0]])
        ys = np.concatenate([arr[:, 1], res["fork1"]["arr"][:, 1], res["fork2"]["arr"][:, 1]])
    elif branches:
        xs = np.concatenate([arr[:, 0]] + [b["arr"][:, 0] for b in branches])
        ys = np.concatenate([arr[:, 1]] + [b["arr"][:, 1] for b in branches])
    else:
        xs, ys = arr[:, 0], arr[:, 1]
    bbox = (xs.min() - half_corridor, xs.max() + half_corridor,
            ys.min() - half_corridor, ys.max() + half_corridor)
    bbox_w = bbox[1] - bbox[0]
    bbox_h = bbox[3] - bbox[2]
    hall_w, hall_h = HALL_W * sc, HALL_H * sc
    margin_w = (hall_w - bbox_w) / 2.0
    margin_h = (hall_h - bbox_h) / 2.0
    results["outer_bbox_m"] = (round(bbox_w, 3), round(bbox_h, 3))
    results["hall_m"] = (hall_w, hall_h)
    results["margin_each_side_m"] = (round(margin_w, 3), round(margin_h, 3))
    results["fits_hall_ok"] = bool(bbox[0] >= -1e-6 and bbox[2] >= -1e-6 and
                                    bbox[1] <= hall_w + 1e-6 and bbox[3] <= hall_h + 1e-6)
    results["margin_ge_0.5_ok"] = bool(margin_w >= 0.5 * sc - 1e-6 and margin_h >= 0.5 * sc - 1e-6)

    # 3. self-intersection: main loop + both boundaries + both forks + no fillet warnings
    results["fillet_warnings"] = meta["warnings"]
    try:
        from shapely.geometry import LinearRing, LineString, Polygon
        centerline_simple = LinearRing(arr[:, :2]).is_simple
        left_simple = LinearRing(res["left_b"][:, :2]).is_simple
        right_simple = LinearRing(res["right_b"][:, :2]).is_simple
        ribbon = Polygon(np.concatenate([res["left_b"][:, :2], res["right_b"][::-1, :2]], axis=0))
        check = dict(centerline_simple=bool(centerline_simple), left_boundary_simple=bool(left_simple),
                     right_boundary_simple=bool(right_simple), track_ribbon_polygon_valid=bool(ribbon.is_valid))
        ok = centerline_simple and left_simple and right_simple and ribbon.is_valid and not meta["warnings"]
        if has_forks:
            f1_simple = LineString(res["fork1"]["arr"][:, :2]).is_simple
            f2_simple = LineString(res["fork2"]["arr"][:, :2]).is_simple
            check["fork1_simple"] = bool(f1_simple)
            check["fork2_simple"] = bool(f2_simple)
            ok = ok and f1_simple and f2_simple
        results["self_intersection_check"] = check
        results["no_self_intersection_ok"] = bool(ok)
    except Exception as e:
        results["self_intersection_check"] = f"shapely check skipped: {e}"
        results["no_self_intersection_ok"] = not meta["warnings"]

    # 4. adjacent-section clearance >= 0.35 m (track edge to track edge), main loop only
    idx = np.arange(0, len(arr), 3)
    Ps = arr[idx]
    S = Ps[:, 3]
    XY = Ps[:, :2]
    best = 1e9
    for i in range(len(Ps)):
        ds = np.abs(S - S[i])
        ds = np.minimum(ds, Ltot - ds)
        far = ds > 1.2 * sc
        if not far.any():
            continue
        d = np.hypot(XY[far, 0] - XY[i, 0], XY[far, 1] - XY[i, 1])
        m = d.min()
        if m < best:
            best = m
    clearance = best - track_w
    results["min_adjacent_clearance_m"] = round(float(clearance), 4)
    results["clearance_ok"] = bool(clearance >= CLEARANCE_MIN * sc - 1e-6)

    # 4b. fork-vs-main clearance away from the fork's own branch/merge junction.
    # A fork is only allowed to run close to the main loop within a short taper
    # zone approaching its branch/merge point (like a highway on/off-ramp);
    # anywhere else it must keep the same >=0.35 m clearance as the main loop.
    if has_forks:
        taper = 1.0 * sc
        fork_clear = {}
        for key in ("fork1", "fork2"):
            f = res[key]
            farr = f["arr"]
            fs = farr[:, 3]
            bS, mS = f["branch_s"], f["merge_s"]
            main_keep = np.array([min(circ_dist(s, bS, Ltot), circ_dist(s, mS, Ltot)) > taper for s in arr[:, 3]])
            fork_keep = (fs > 0.3 * sc) & (fs < fs[-1] - 0.3 * sc)
            FXY = farr[fork_keep, :2]
            MXY = arr[main_keep, :2]
            if len(FXY) and len(MXY):
                d = np.hypot(MXY[:, None, 0] - FXY[None, :, 0], MXY[:, None, 1] - FXY[None, :, 1])
                m = float(d.min()) - track_w / 2.0 - (FORK_WIDTH * sc) / 2.0
            else:
                m = float("inf")
            fork_clear[key] = round(m, 4)
        results["fork_vs_main_clearance_m"] = fork_clear
        results["fork_clearance_ok"] = bool(all(v >= CLEARANCE_MIN * sc - 1e-6 for v in fork_clear.values()))
    else:
        results["fork_vs_main_clearance_m"] = {}
        results["fork_clearance_ok"] = True

    # 5. lap length in [35,55] (scaled), main route only (advisory for --design mode)
    results["lap_length_m"] = round(Ltot, 3)
    lo, hi = 35.0 * sc, 55.0 * sc
    results["lap_length_ok"] = bool(lo <= Ltot <= hi)
    if has_forks:
        results["lap_length_via_fork1_m"] = round(meta["lap_via_fork1"], 3)
        results["lap_length_via_fork2_m"] = round(meta["lap_via_fork2"], 3)

    # 6. narrow section width exactly at target at its flattest (WARN not fail below MIN_RADIUS
    #    is handled by min_radius_*_ok above; this is a separate exact-width check)
    narrow_targets = get_narrow_targets(res)
    if len(narrow_targets) == 1:
        t = narrow_targets[0]
        w_at_center = res["track_width_at"](t["s_center"])
        results["narrow_section_width_m"] = round(w_at_center, 5)
        results["narrow_section_width_ok"] = bool(abs(w_at_center - t["width_m"]) < 1e-3)
    elif len(narrow_targets) > 1:
        lst = []
        all_ok = True
        for t in narrow_targets:
            w_at_center = res["track_width_at"](t["s_center"])
            ok = abs(w_at_center - t["width_m"]) < 1e-3
            all_ok = all_ok and ok
            lst.append(dict(s_center=round(t["s_center"], 3), width_m=round(w_at_center, 5),
                             target_width_m=t["width_m"], ok=ok))
        results["narrow_section_widths"] = lst
        results["narrow_section_width_ok"] = bool(all_ok)
    else:
        results["narrow_section_width_m"] = None
        results["narrow_section_width_ok"] = True

    # 7. grid slots do not overlap track walls (or the track surface itself)
    try:
        from shapely.geometry import Polygon as SPoly
        from shapely.geometry import box as sbox
        track_poly = SPoly(np.concatenate([res["left_b"][:, :2], res["right_b"][::-1, :2]], axis=0)).buffer(0)
        overlaps = []
        for g in res["grid_slots"]:
            c, s_ = math.cos(g["yaw"]), math.sin(g["yaw"])
            hl, hw = g["length"] / 2.0, g["width"] / 2.0
            corners = [(g["x"] + lx * c - ly * s_, g["y"] + lx * s_ + ly * c)
                       for lx, ly in [(-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw)]]
            gp = SPoly(corners)
            if gp.intersects(track_poly.boundary.buffer(1e-4)) and not track_poly.contains(gp):
                overlaps.append(g["index"])
        results["grid_slots_overlap_wall"] = overlaps
        results["grid_slots_ok"] = len(overlaps) == 0
    except Exception as e:
        results["grid_slots_ok"] = f"check skipped: {e}"

    # 8. branches (갈림길/지름길): each one checked for its own min radius and
    # self-intersection, independent of the main-loop checks above.
    if branches:
        try:
            from shapely.geometry import LineString as _BranchLS
            have_shapely = True
        except Exception:
            have_shapely = False
        branch_results = []
        all_branch_ok = True
        for b in branches:
            min_r = compute_min_radius(b["arr"], closed=False)
            simple = True
            if have_shapely:
                try:
                    simple = bool(_BranchLS(b["arr"][:, :2]).is_simple)
                except Exception:
                    simple = True
            radius_ok = min_r >= MIN_RADIUS * sc - 1e-9
            ok = bool(radius_ok and simple)
            all_branch_ok = all_branch_ok and ok
            branch_results.append(dict(
                name=b["name"], width_m=b["width_m"], length_m=round(b["length"], 3),
                s0_m=round(b["s0"], 3), s1_m=round(b["s1"], 3),
                min_radius_m=(round(min_r, 4) if math.isfinite(min_r) else None),
                min_radius_ok=bool(radius_ok), self_intersection_simple=simple, ok=ok,
            ))
        results["branches"] = branch_results
        results["branches_ok"] = bool(all_branch_ok)
    else:
        results["branches"] = []
        results["branches_ok"] = True

    return results


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------
def write_csvs(res, outdir):
    arr = res["arr"]
    tw_arr = res["tw_arr"]
    with open(os.path.join(outdir, "centerline.csv"), "w") as f:
        f.write("x_m,y_m,s_m,track_width_m\n")
        for row, tw in zip(arr, tw_arr):
            f.write(f"{row[0]:.5f},{row[1]:.5f},{row[3]:.5f},{tw:.4f}\n")
    with open(os.path.join(outdir, "left_boundary.csv"), "w") as f:
        f.write("x_m,y_m,s_m\n")
        for row in res["left_b"]:
            f.write(f"{row[0]:.5f},{row[1]:.5f},{row[3]:.5f}\n")
    with open(os.path.join(outdir, "right_boundary.csv"), "w") as f:
        f.write("x_m,y_m,s_m\n")
        for row in res["right_b"]:
            f.write(f"{row[0]:.5f},{row[1]:.5f},{row[3]:.5f}\n")
    if res.get("fork1") is not None:
        for i, key in [(1, "fork1"), (2, "fork2")]:
            with open(os.path.join(outdir, f"alt_route_{i}.csv"), "w") as f:
                f.write("x_m,y_m,s_m,track_width_m\n")
                for row in res[key]["arr"]:
                    f.write(f"{row[0]:.5f},{row[1]:.5f},{row[3]:.5f},{FORK_WIDTH*res['meta']['scale']:.4f}\n")
    for i, b in enumerate(res.get("branches") or []):
        with open(os.path.join(outdir, f"branch_{i}.csv"), "w", encoding="utf-8") as f:
            f.write("x_m,y_m,s_m,width_m\n")
            for row in b["arr"]:
                f.write(f"{row[0]:.5f},{row[1]:.5f},{row[3]:.5f},{b['width_m']:.4f}\n")


def build_union_wall_boxes(res, wall_step):
    """Design-mode walls: buffer/union the whole drivable corridor (main ribbon
    + grass + branch ribbons) with shapely, then box up its boundary rings.
    Replaces the per-ribbon gap-cutting for walls, which left floating wall
    stubs wherever a branch ran close alongside the main track. Inner islands
    (between a branch and the main road) only get a wall if a wall physically
    fits inside them; sliver islands are dropped."""
    from shapely.geometry import LineString, Polygon as ShPolygon
    from shapely.ops import unary_union
    meta = res["meta"]
    wt = meta["wall_t"]
    pts = res["arr"][:, :2].tolist()
    pts.append(pts[0])
    parts = [LineString(pts).buffer(float(np.max(res["tw_arr"])) / 2.0 + GRASS_W * meta["scale"])]
    for br in (res.get("branches") or []):
        parts.append(LineString(br["arr"][:, :2]).buffer(br["width_m"] / 2.0))
    corridor = unary_union(parts).buffer(0)
    if corridor.geom_type == "MultiPolygon":
        corridor = max(corridor.geoms, key=lambda g: g.area)
    rings = [corridor.buffer(wt / 2.0).exterior]
    for hole in corridor.interiors:
        inner = ShPolygon(hole).buffer(-wt / 2.0)
        geoms = list(inner.geoms) if inner.geom_type == "MultiPolygon" else ([] if inner.is_empty else [inner])
        for g in geoms:
            # ponytail: islands shorter than 0.6m of wall are dropped (grass-only separation)
            if g.exterior.length >= 0.6:
                rings.append(g.exterior)
    boxes = []
    for ring in rings:
        rs = resample_by_arclength([(p[0], p[1]) for p in ring.coords], wall_step, closed=True)
        rarr, _ = _arr_from_resampled(rs, closed=True)
        boxes += build_ribbon_boxes(rarr, wt, closed=True)
    return boxes


def build_geometry_boxes(res, wall_step=0.14, surface_step=0.35):
    """Precompute wall / track-surface / grass / fork box chains shared by
    SDF, DXF and map raster."""
    meta = res["meta"]
    wt = meta["wall_t"]
    arr = res["arr"]

    out = {}
    tw_dec_idx = np.searchsorted(arr[:, 3], decimate_by_arclength(arr, wall_step)[:, 3])
    tw_dec_idx = np.clip(tw_dec_idx, 0, len(arr) - 1)

    def dec_with_width(a, w_full, step, closed=True):
        s = a[:, 3]
        Ltot = s[-1]
        n_pick = max(4, int(round(Ltot / step)))
        s_targets = np.linspace(0, Ltot, n_pick, endpoint=not closed)
        idxs = np.clip(np.searchsorted(s, s_targets), 0, len(a) - 1)
        idxs = sorted(set(idxs.tolist()))
        return a[idxs], w_full[idxs]

    lw = offset_polyline(arr, res["tw_arr"] / 2 + res["gh_arr"] + wt / 2)
    rw = offset_polyline(arr, -(res["tw_arr"] / 2 + res["gh_arr"] + wt / 2))
    lw_dec, _ = dec_with_width(lw, res["tw_arr"], wall_step)
    rw_dec, _ = dec_with_width(rw, res["tw_arr"], wall_step)

    dec, tw_d = dec_with_width(arr, res["tw_arr"], surface_step)
    out["surface_main"] = build_ribbon_boxes(dec, tw_d, closed=True)

    lg = offset_polyline(arr, res["tw_arr"] / 2 + res["gh_arr"] / 2)
    rg = offset_polyline(arr, -(res["tw_arr"] / 2 + res["gh_arr"] / 2))
    lg_dec, gh_d_l = dec_with_width(lg, res["gh_arr"], surface_step)
    rg_dec, gh_d_r = dec_with_width(rg, res["gh_arr"], surface_step)

    branches = res.get("branches") or []
    if branches:
        # find, per branch and per anchor, the main-arc-length window (and
        # side) that must be left open in the main wall/grass, and the
        # matching branch-local window where the branch's OWN wall must stay
        # open (see the big comment above compute_branch_mouth_extent).
        gaps_left, gaps_right = [], []
        for br in branches:
            gap_margin = meta["track_w"] / 2.0 + GRASS_W + br["width_m"] / 2.0 + 0.03
            start_info = compute_branch_mouth_extent(arr, br["arr"], gap_margin)
            end_info = compute_branch_mouth_extent(arr, _reversed_with_relative_s(br["arr"]), gap_margin)
            if start_info:
                (gaps_left if start_info["side"] == "left" else gaps_right).append(
                    (start_info["main_s_lo"], start_info["main_s_hi"]))
            if end_info:
                (gaps_left if end_info["side"] == "left" else gaps_right).append(
                    (end_info["main_s_lo"], end_info["main_s_hi"]))

        out["walls_main_left"] = build_union_wall_boxes(res, wall_step)
        out["walls_main_right"] = []
        out["grass_main_left"] = build_ribbon_boxes_with_gaps(lg_dec, gh_d_l, gaps_left, closed=True)
        out["grass_main_right"] = build_ribbon_boxes_with_gaps(rg_dec, gh_d_r, gaps_right, closed=True)

        for i, br in enumerate(branches):
            key = f"branch{i}"
            barr = br["arr"]
            bw = br["width_m"]
            out[f"walls_{key}_left"] = []
            out[f"walls_{key}_right"] = []
            out[f"surface_{key}"] = build_ribbon_boxes(
                decimate_by_arclength(barr, surface_step, closed=False), bw, closed=False)
            # A branch's own grass buffer is intentionally skipped: it is a
            # single-car-width shortcut running right alongside the main
            # route, and adding a second layer of grass gap-cutting on top
            # of the wall gap-cutting above would meaningfully complicate the
            # mouth geometry for a purely cosmetic strip. The main track's
            # grass still gets cut at the mouths (right above).
    else:
        out["walls_main_left"] = build_ribbon_boxes(lw_dec, wt, closed=False)
        out["walls_main_right"] = build_ribbon_boxes(rw_dec, wt, closed=False)
        out["grass_main_left"] = build_ribbon_boxes(lg_dec, gh_d_l, closed=True)
        out["grass_main_right"] = build_ribbon_boxes(rg_dec, gh_d_r, closed=True)

    fork_w = FORK_WIDTH * meta["scale"]
    for i, key in ([(1, "fork1"), (2, "fork2")] if res.get("fork1") is not None else []):
        farr = res[key]["arr"]
        flw = offset_polyline(farr, fork_w / 2 + GRASS_W * meta["scale"] * 0.3 + wt / 2)
        frw = offset_polyline(farr, -(fork_w / 2 + GRASS_W * meta["scale"] * 0.3 + wt / 2))
        out[f"walls_{key}_left"] = build_ribbon_boxes(decimate_by_arclength(flw, wall_step, closed=False),
                                                        wt, closed=False)
        out[f"walls_{key}_right"] = build_ribbon_boxes(decimate_by_arclength(frw, wall_step, closed=False),
                                                         wt, closed=False)
        out[f"surface_{key}"] = build_ribbon_boxes(decimate_by_arclength(farr, surface_step, closed=False),
                                                      fork_w, closed=False)
        fg_l = offset_polyline(farr, fork_w / 2 + GRASS_W * meta["scale"] * 0.15)
        fg_r = offset_polyline(farr, -(fork_w / 2 + GRASS_W * meta["scale"] * 0.15))
        out[f"grass_{key}_left"] = build_ribbon_boxes(decimate_by_arclength(fg_l, surface_step, closed=False),
                                                         GRASS_W * meta["scale"] * 0.3, closed=False)
        out[f"grass_{key}_right"] = build_ribbon_boxes(decimate_by_arclength(fg_r, surface_step, closed=False),
                                                          GRASS_W * meta["scale"] * 0.3, closed=False)
    return out


def write_map(res, boxes, outdir, resolution):
    import cv2
    meta = res["meta"]
    arr = res["arr"]
    branches = res.get("branches") or []
    pad = 0.8 * meta["scale"]
    if res.get("fork1") is not None:
        xs = np.concatenate([arr[:, 0], res["fork1"]["arr"][:, 0], res["fork2"]["arr"][:, 0]])
        ys = np.concatenate([arr[:, 1], res["fork1"]["arr"][:, 1], res["fork2"]["arr"][:, 1]])
    elif branches:
        xs = np.concatenate([arr[:, 0]] + [b["arr"][:, 0] for b in branches])
        ys = np.concatenate([arr[:, 1]] + [b["arr"][:, 1] for b in branches])
    else:
        xs, ys = arr[:, 0], arr[:, 1]
    x0, x1 = xs.min() - pad, xs.max() + pad
    y0, y1 = ys.min() - pad, ys.max() + pad
    W = int(math.ceil((x1 - x0) / resolution))
    H = int(math.ceil((y1 - y0) / resolution))

    def w2p(x, y):
        return (int(round((x - x0) / resolution)), int(round((y1 - y) / resolution)))

    def make_canvas():
        return np.full((H, W), 205, dtype=np.uint8)

    def fill_boxes(canvas, box_list, value):
        for b in box_list:
            poly = np.array([w2p(*c) for c in box_corners(b)], dtype=np.int32)
            cv2.fillPoly(canvas, [poly], int(value))

    canvas_plain = make_canvas()
    canvas_grass = make_canvas()

    branch_surface_keys = tuple(f"surface_branch{i}" for i in range(len(branches)))
    branch_wall_keys = tuple(f"walls_branch{i}_{side}" for i in range(len(branches)) for side in ("left", "right"))

    # NOTE: surface boxes are simply OR'd together (later fillPoly calls don't
    # erase earlier ones) -- this is exactly how the main route and every
    # branch route end up as one drivable_union of free space, with no
    # polygon-boolean step needed: whichever ribbon(s) cover a pixel, it's free.
    surface_keys = ("surface_main", "surface_fork1", "surface_fork2") + branch_surface_keys
    for key in surface_keys:
        fill_boxes(canvas_plain, boxes.get(key, []), 254)
        fill_boxes(canvas_grass, boxes.get(key, []), 254)

    grass_keys = ("grass_main_left", "grass_main_right", "grass_fork1_left", "grass_fork1_right",
                  "grass_fork2_left", "grass_fork2_right")
    for key in grass_keys:
        fill_boxes(canvas_plain, boxes.get(key, []), 254)
        fill_boxes(canvas_grass, boxes.get(key, []), 150)

    wall_keys = ("walls_main_left", "walls_main_right", "walls_fork1_left", "walls_fork1_right",
                 "walls_fork2_left", "walls_fork2_right") + branch_wall_keys
    for key in wall_keys:
        fill_boxes(canvas_plain, boxes.get(key, []), 0)
        fill_boxes(canvas_grass, boxes.get(key, []), 0)

    cv2.imwrite(os.path.join(outdir, "map.png"), canvas_plain)
    cv2.imwrite(os.path.join(outdir, "map_with_grass.png"), canvas_grass)

    yaml_dict = {
        "image": "map.png", "resolution": float(resolution), "origin": [float(x0), float(y0), 0.0],
        "negate": 0, "occupied_thresh": 0.65, "free_thresh": 0.196,
    }
    with open(os.path.join(outdir, "map.yaml"), "w") as f:
        yaml.safe_dump(yaml_dict, f, default_flow_style=None, sort_keys=False)

    yaml_dict2 = dict(yaml_dict)
    yaml_dict2["image"] = "map_with_grass.png"
    with open(os.path.join(outdir, "map_with_grass.yaml"), "w") as f:
        yaml.safe_dump(yaml_dict2, f, default_flow_style=None, sort_keys=False)

    return dict(origin=(x0, y0), size=(W, H))


def _sdf_box_link(name, x, y, z, yaw, sx, sy, sz, rgba, static_friction=None):
    fric = ""
    if static_friction is not None:
        fric = f"""
        <surface><friction><ode><mu>{static_friction}</mu><mu2>{static_friction}</mu2></ode></friction></surface>"""
    return f"""
    <link name="{name}">
      <pose>{x:.4f} {y:.4f} {z:.4f} 0 0 {yaw:.5f}</pose>
      <collision name="{name}_col">
        <geometry><box><size>{sx:.4f} {sy:.4f} {sz:.4f}</size></box></geometry>{fric}
      </collision>
      <visual name="{name}_vis">
        <geometry><box><size>{sx:.4f} {sy:.4f} {sz:.4f}</size></box></geometry>
        <material>
          <ambient>{rgba}</ambient><diffuse>{rgba}</diffuse>
        </material>
      </visual>
    </link>"""


def write_sdf(res, boxes, outdir):
    meta = res["meta"]
    wall_h, wall_t = meta["wall_h"], meta["wall_t"]
    branches = res.get("branches") or []
    branch_surface_keys = tuple(f"surface_branch{i}" for i in range(len(branches)))
    branch_wall_keys = tuple(f"walls_branch{i}_{side}" for i in range(len(branches)) for side in ("left", "right"))
    links = []

    ground = """
    <link name="ground_plane_link">
      <collision name="ground_collision">
        <geometry><plane><normal>0 0 1</normal><size>30 30</size></plane></geometry>
      </collision>
      <visual name="ground_visual">
        <geometry><plane><normal>0 0 1</normal><size>30 30</size></plane></geometry>
        <material><ambient>0.55 0.55 0.55 1</ambient><diffuse>0.55 0.55 0.55 1</diffuse></material>
      </visual>
    </link>"""
    links.append(ground)

    for key in ("surface_main", "surface_fork1", "surface_fork2") + branch_surface_keys:
        for i, b in enumerate(boxes.get(key, [])):
            links.append(_sdf_box_link(f"{key}_{i}", b["x"], b["y"], 0.0015, b["yaw"],
                                        b["length"], b["width"], 0.003, "0.12 0.12 0.13 1"))

    for key in ("grass_main_left", "grass_main_right", "grass_fork1_left", "grass_fork1_right",
                "grass_fork2_left", "grass_fork2_right"):
        for i, b in enumerate(boxes.get(key, [])):
            links.append(_sdf_box_link(f"{key}_{i}", b["x"], b["y"], 0.001, b["yaw"],
                                        b["length"], b["width"], 0.002, "0.13 0.55 0.13 1"))

    for key in ("walls_main_left", "walls_main_right", "walls_fork1_left", "walls_fork1_right",
                "walls_fork2_left", "walls_fork2_right") + branch_wall_keys:
        for i, b in enumerate(boxes.get(key, [])):
            links.append(_sdf_box_link(f"{key}_{i}", b["x"], b["y"], wall_h / 2.0, b["yaw"],
                                        b["length"], wall_t, wall_h, "0.85 0.85 0.85 1",
                                        static_friction=0.8))

    # 노면변화 friction-change patch(es): distinct color + lower friction coefficient
    for j, fz in enumerate(get_friction_zones(res)):
        fx_, fy_, fth = sample_at_s(res["arr"], fz["s_center"], meta["Ltot"])
        tw_here = res["track_width_at"](fz["s_center"])
        links.append(_sdf_box_link(f"friction_zone_patch_{j}", fx_, fy_, 0.002, fth,
                                    fz["length"], tw_here, 0.004, "0.55 0.35 0.75 1",
                                    static_friction=0.35))

    for i, bmp in enumerate(res["bumps"]):
        links.append(_sdf_box_link(f"bump_{i}", bmp["x"], bmp["y"], bmp["height"] / 2.0, bmp["yaw"],
                                    bmp["width"], bmp["length"], bmp["height"], "0.9 0.6 0.1 1"))

    # starting-grid painted-line boxes (flat, non-colliding visuals only)
    for g in res["grid_slots"]:
        name = f"grid_slot_{g['index']}"
        links.append(f"""
    <link name="{name}">
      <pose>{g['x']:.4f} {g['y']:.4f} 0.0012 0 0 {g['yaw']:.5f}</pose>
      <visual name="{name}_vis">
        <geometry><box><size>{g['length']:.4f} {g['width']:.4f} 0.001</size></box></geometry>
        <material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material>
      </visual>
    </link>""")

    tl = res["traffic_light"]
    gh = tl["gantry_height"]
    beam_len = tl["width"] + 0.3 * meta["scale"]
    post_h = gh
    yaw = tl["yaw"]
    perp = yaw + math.pi / 2.0
    tl_sign = 1.0 if tl.get("side", "left") == "left" else -1.0
    px = tl["x"] + tl_sign * math.cos(perp) * (tl["width"] / 2.0 + 0.05 * meta["scale"])
    py = tl["y"] + tl_sign * math.sin(perp) * (tl["width"] / 2.0 + 0.05 * meta["scale"])
    links.append(_sdf_box_link("tl_post", px, py, post_h / 2.0, yaw,
                                0.06 * meta["scale"], 0.06 * meta["scale"], post_h, "0.2 0.2 0.2 1"))
    links.append(_sdf_box_link("tl_beam", tl["x"], tl["y"], gh, yaw,
                                beam_len, 0.06 * meta["scale"], 0.06 * meta["scale"], "0.2 0.2 0.2 1"))
    lamp_r = 0.045 * meta["scale"]
    lamp_colors = {"lamp_red": "1 0 0 1", "lamp_yellow": "1 1 0 1", "lamp_green": "0 1 0 1"}
    lamp_offsets = [-0.15, 0.0, 0.15]
    for (name, rgba), doff in zip(lamp_colors.items(), lamp_offsets):
        lx = tl["x"] + math.cos(yaw) * doff * meta["scale"]
        ly = tl["y"] + math.sin(yaw) * doff * meta["scale"]
        links.append(f"""
    <link name="{name}">
      <pose>{lx:.4f} {ly:.4f} {gh - 0.12*meta['scale']:.4f} 0 0 0</pose>
      <visual name="{name}_vis">
        <geometry><sphere><radius>{lamp_r:.4f}</radius></sphere></geometry>
        <material>
          <ambient>{rgba}</ambient><diffuse>{rgba}</diffuse>
          <emissive>{rgba}</emissive>
        </material>
      </visual>
      <collision name="{name}_col">
        <geometry><sphere><radius>{lamp_r:.4f}</radius></sphere></geometry>
      </collision>
    </link>""")

    for m in res["markers"]:
        size = ARUCO_SIZE * meta["scale"]
        thick = 0.005 * meta["scale"]
        name = f"aruco_{m['id']}"
        yaw = m["yaw"]
        img = f"../aruco/aruco_id{m['id']}.png"
        links.append(f"""
    <link name="{name}">
      <pose>{m['x']:.4f} {m['y']:.4f} {m['z']+size/2:.4f} 0 0 {yaw:.5f}</pose>
      <visual name="{name}_vis">
        <geometry><box><size>{thick:.4f} {size:.4f} {size:.4f}</size></box></geometry>
        <material>
          <pbr><metal><albedo_map>{img}</albedo_map></metal></pbr>
          <script><uri>{img}</uri></script>
        </material>
      </visual>
      <collision name="{name}_col">
        <geometry><box><size>{thick:.4f} {size:.4f} {size:.4f}</size></box></geometry>
      </collision>
    </link>""")

    links_xml = "\n".join(links)
    sdf = f"""<?xml version="1.0" ?>
<sdf version="1.8">
  <world name="it_arena_track">
    <physics name="default_physics" type="ode">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>
    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.9 0.9 0.9 1</diffuse>
      <direction>-0.4 0.2 -0.9</direction>
    </light>
    <model name="it_arena_track_static">
      <static>true</static>
      {links_xml}
    </model>
  </world>
</sdf>
"""
    with open(os.path.join(outdir, "world.sdf"), "w") as f:
        f.write(sdf)
    return sdf


def write_dxf(res, boxes, outdir):
    import ezdxf
    meta = res["meta"]
    doc = ezdxf.new("R2010", setup=True)
    msp = doc.modelspace()
    for name, color in [("HALL", 5), ("TRACK", 7), ("WALLS", 8), ("GRASS", 3),
                         ("MARKERS", 1), ("FEATURES", 2), ("GRID", 6), ("FORKS", 4)]:
        if name not in doc.layers:
            doc.layers.add(name=name, color=color)

    hall_w, hall_h = HALL_W * meta["scale"], HALL_H * meta["scale"]
    msp.add_lwpolyline([(0, 0), (hall_w, 0), (hall_w, hall_h), (0, hall_h), (0, 0)],
                        dxfattribs={"layer": "HALL"})

    def poly(arr2d, layer, closed=False):
        pts = [(float(p[0]), float(p[1])) for p in arr2d]
        msp.add_lwpolyline(pts, close=closed, dxfattribs={"layer": layer})

    poly(res["left_b"], "TRACK", closed=True)
    poly(res["right_b"], "TRACK", closed=True)
    poly(res["left_grass_out"], "GRASS", closed=True)
    poly(res["right_grass_out"], "GRASS", closed=True)
    if res.get("fork1") is not None:
        poly(res["fork1_left"], "FORKS")
        poly(res["fork1_right"], "FORKS")
        poly(res["fork2_left"], "FORKS")
        poly(res["fork2_right"], "FORKS")

    branches = res.get("branches") or []
    for i, br in enumerate(branches):
        poly(offset_polyline(br["arr"], br["width_m"] / 2.0), "FORKS")
        poly(offset_polyline(br["arr"], -br["width_m"] / 2.0), "FORKS")
        mid = br["arr"][len(br["arr"]) // 2]
        msp.add_text(f"{br['name']} {br['width_m']:.2f}m", height=0.10 * meta["scale"],
                      dxfattribs={"layer": "FORKS"}).set_placement((mid[0] - 0.3, mid[1] + 0.3))

    branch_wall_keys = tuple(f"walls_branch{i}_{side}" for i in range(len(branches)) for side in ("left", "right"))
    for key in ("walls_main_left", "walls_main_right", "walls_fork1_left", "walls_fork1_right",
                "walls_fork2_left", "walls_fork2_right") + branch_wall_keys:
        for b in boxes.get(key, []):
            corners = box_corners(b) + [box_corners(b)[0]]
            msp.add_lwpolyline(corners, dxfattribs={"layer": "WALLS"})

    for bmp in res["bumps"]:
        b = dict(x=bmp["x"], y=bmp["y"], yaw=bmp["yaw"], length=bmp["length"], width=bmp["width"])
        corners = box_corners(b) + [box_corners(b)[0]]
        msp.add_lwpolyline(corners, dxfattribs={"layer": "FEATURES"})
        msp.add_text("BUMP", height=0.08 * meta["scale"],
                      dxfattribs={"layer": "FEATURES"}).set_placement((bmp["x"], bmp["y"] + 0.15))

    for g in res["grid_slots"]:
        b = dict(x=g["x"], y=g["y"], yaw=g["yaw"], length=g["length"], width=g["width"])
        corners = box_corners(b) + [box_corners(b)[0]]
        msp.add_lwpolyline(corners, dxfattribs={"layer": "GRID"})
        msp.add_text(f"G{g['index']}", height=0.06 * meta["scale"],
                      dxfattribs={"layer": "GRID"}).set_placement((g["x"], g["y"]))

    for fz in get_friction_zones(res):
        fxp, fyp, fthp = sample_at_s(res["arr"], fz["s_center"], meta["Ltot"])
        msp.add_text("노면변화", height=0.10 * meta["scale"],
                      dxfattribs={"layer": "FEATURES"}).set_placement((fxp - 0.3, fyp + 0.3))

    for nz in get_narrow_targets(res):
        nxp, nyp, _ = sample_at_s(res["arr"], nz["s_center"], meta["Ltot"])
        msp.add_text(f"협로 {nz['width_m']:.2f}m", height=0.10 * meta["scale"],
                      dxfattribs={"layer": "FEATURES"}).set_placement((nxp - 0.3, nyp + 0.3))

    for m in res["markers"]:
        s = ARUCO_SIZE * meta["scale"]
        msp.add_circle((m["x"], m["y"]), radius=s / 2, dxfattribs={"layer": "MARKERS"})
        label = f"ID{m['id']}" + ("" if m["real"] else "(FAKE)")
        msp.add_text(label, height=0.10 * meta["scale"],
                      dxfattribs={"layer": "MARKERS"}).set_placement((m["x"] + 0.1, m["y"] + 0.1))

    tl = res["traffic_light"]
    perp = tl["yaw"] + math.pi / 2
    sf_a = (tl["x"] - math.cos(perp) * (meta["track_w"] / 2 + meta["grass_w"]),
            tl["y"] - math.sin(perp) * (meta["track_w"] / 2 + meta["grass_w"]))
    sf_b = (tl["x"] + math.cos(perp) * (meta["track_w"] / 2 + meta["grass_w"]),
            tl["y"] + math.sin(perp) * (meta["track_w"] / 2 + meta["grass_w"]))
    msp.add_line(sf_a, sf_b, dxfattribs={"layer": "FEATURES"})
    msp.add_text("START/FINISH + TRAFFIC LIGHT", height=0.12 * meta["scale"],
                  dxfattribs={"layer": "FEATURES"}).set_placement((tl["x"] - 0.6, tl["y"] + 0.3))

    doc.saveas(os.path.join(outdir, "venue_layout.dxf"))


def write_aruco(res, outdir):
    import cv2
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    aruco_dir = os.path.join(outdir, "aruco")
    os.makedirs(aruco_dir, exist_ok=True)
    adict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    all_ids = sorted([m["id"] for m in res["markers"]])
    id_role = {m["id"]: (m["real"], m.get("role", "fake")) for m in res["markers"]}

    core_px = 700
    pad = (1000 - core_px) // 2
    png_paths = {}
    for mid in all_ids:
        core = cv2.aruco.generateImageMarker(adict, mid, core_px)
        canvas = np.full((1000, 1000), 255, dtype=np.uint8)
        canvas[pad:pad + core_px, pad:pad + core_px] = core
        path = os.path.join(aruco_dir, f"aruco_id{mid}.png")
        cv2.imwrite(path, canvas)
        png_paths[mid] = path

    A4_W, A4_H = 8.27, 11.69
    side_in = ARUCO_SIZE / 0.0254
    x0 = (A4_W - side_in) / 2.0
    y0 = (A4_H - side_in) / 2.0 + 0.6
    pdf_path = os.path.join(outdir, "aruco_print_sheet.pdf")
    with PdfPages(pdf_path) as pdf:
        for mid in all_ids:
            real, role = id_role[mid]
            fig = plt.figure(figsize=(A4_W, A4_H))
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_xlim(0, A4_W)
            ax.set_ylim(0, A4_H)
            ax.axis("off")
            img = plt.imread(png_paths[mid])
            ax.imshow(img, extent=(x0, x0 + side_in, y0, y0 + side_in), cmap="gray")
            ax.add_patch(plt.Rectangle((x0, y0), side_in, side_in, fill=False, lw=0.5, edgecolor="gray"))
            tag = "REAL" if real else "FAKE (decoy)"
            ax.text(A4_W / 2, y0 + side_in + 0.5, f"ArUco ID {mid}  --  {tag}  --  {role}",
                     ha="center", fontsize=16, weight="bold")
            ax.text(A4_W / 2, y0 - 0.4, "DICT_4X4_50   size = 0.10 m x 0.10 m   print at 100% scale",
                     ha="center", fontsize=10)
            pdf.savefig(fig)
            plt.close(fig)
    return png_paths, pdf_path


def write_scene_json(res, outdir, checks):
    meta = res["meta"]
    arr = res["arr"]
    Ltot = meta["Ltot"]
    has_forks = res.get("fork1") is not None
    is_design = bool(meta.get("design_mode"))

    def poly_list(a, step=8):
        return [[round(float(p[0]), 4), round(float(p[1]), 4)] for p in a[::step]]

    track_dict = {
        "width_m": meta["track_w"],
        "lap_length_m": round(Ltot, 4),
        "min_centerline_radius_general_m": meta["min_r_general"],
        "min_centerline_radius_chicane_m": meta["min_r_chicane"],
        "centerline_polyline": poly_list(arr),
        "left_boundary_polyline": poly_list(res["left_b"]),
        "right_boundary_polyline": poly_list(res["right_b"]),
        "sectors": [dict(name=s["name"], s_start_m=round(s["s_start"], 3),
                          s_end_m=round(s["s_end"], 3)) for s in meta["sectors"]],
    }
    if has_forks:
        track_dict["lap_length_via_fork1_m"] = round(meta["lap_via_fork1"], 4)
        track_dict["lap_length_via_fork2_m"] = round(meta["lap_via_fork2"], 4)
    if meta.get("gate12_s") is not None and meta.get("gate23_s") is not None:
        track_dict["gates"] = {
            "gate12": {"s_m": round(meta["gate12_s"], 3), "note": "섹터1->섹터2 경계 (헤어핀 출구)"},
            "gate23": {"s_m": round(meta["gate23_s"], 3), "note": "섹터2->섹터3 경계 (에세스 상단)"},
        }

    narrow_targets = get_narrow_targets(res)
    if len(narrow_targets) == 1 and not is_design:
        # classic single-zone path: preserve exact original schema/fields
        t = narrow_targets[0]
        track_dict["narrow_section"] = {
            "width_m": t["width_m"], "s_center_m": round(meta["narrow_center_s"], 3),
            "s_start_m": round(meta["narrow_s_range"][0], 3),
            "s_end_m": round(meta["narrow_s_range"][1], 3),
            "flat_length_m": NARROW_FLAT_LEN * meta["scale"],
            "taper_length_m": NARROW_TAPER_LEN * meta["scale"],
            "note": "협로: 1대만 통과 가능, 벽이 넥(neck)을 따라감",
        }
    elif len(narrow_targets) == 1:
        t = narrow_targets[0]
        track_dict["narrow_section"] = {
            "width_m": t["width_m"], "s_center_m": round(t["s_center"], 3),
            "taper_length_m": NARROW_TAPER_LEN,
            "note": "협로: 1대만 통과 가능, 벽이 넥(neck)을 따라감",
        }
    elif len(narrow_targets) > 1:
        track_dict["narrow_sections"] = [
            dict(width_m=t["width_m"], s_center_m=round(t["s_center"], 3), taper_length_m=NARROW_TAPER_LEN)
            for t in narrow_targets
        ]
    fz_list = get_friction_zones(res)
    if len(fz_list) == 1:
        track_dict["friction_zone"] = fz_list[0]
    elif len(fz_list) > 1:
        track_dict["friction_zones"] = fz_list
    else:
        track_dict["friction_zone"] = None

    scene = {
        "course_name": ("후보1 통합 코스 (A+B)" if not is_design else "사용자 설계 코스 (track_editor.html)"),
        "hall": {"width_m": HALL_W * meta["scale"], "height_m": HALL_H * meta["scale"],
                 "operational_margin_target_m": 0.5 * meta["scale"]},
        "scale": meta["scale"],
        "resolution_m_per_px": meta["resolution"],
        "vehicle": {"length_m": VEHICLE_L * meta["scale"], "width_m": VEHICLE_W * meta["scale"]},
        "track": track_dict,
        "alt_routes": ({
            "fork1": {
                "name": "갈림길①", "location": "섹터3 시케인(훅) 우회",
                "branch_s_m": round(res["fork1"]["branch_s"], 3),
                "merge_s_m": round(res["fork1"]["merge_s"], 3),
                "length_m": round(res["fork1"]["length"], 3),
                "width_m": FORK_WIDTH * meta["scale"],
                "centerline_polyline": poly_list(res["fork1"]["arr"], step=2),
                "csv": "alt_route_1.csv",
            },
            "fork2": {
                "name": "갈림길②", "location": "섹터1/섹터2 접속부 (헤어핀 우회)",
                "branch_s_m": round(res["fork2"]["branch_s"], 3),
                "merge_s_m": round(res["fork2"]["merge_s"], 3),
                "length_m": round(res["fork2"]["length"], 3),
                "width_m": FORK_WIDTH * meta["scale"],
                "centerline_polyline": poly_list(res["fork2"]["arr"], step=2),
                "csv": "alt_route_2.csv",
            },
        } if has_forks else {}),
        "branches": [
            {
                "name": b["name"], "width_m": b["width_m"],
                "s0_m": round(b["s0"], 3), "s1_m": round(b["s1"], 3),
                "length_m": round(b["length"], 3),
                "note": "갈림길: 메인 트랙과 나란히 갈라졌다가 다시 합류하는 별도의 좁은 지름길 (양쪽 모두 주행 가능)",
                "centerline_polyline": poly_list(b["arr"], step=2),
            }
            for b in (res.get("branches") or [])
        ],
        "starting_grid": {
            "car_count": meta["grid_cars"], "columns": 2,
            "slot_length_m": GRID_SLOT_L * meta["scale"], "slot_width_m": GRID_SLOT_W * meta["scale"],
            "longitudinal_stagger_m": GRID_STAGGER * meta["scale"],
            "extension_added_m": meta["grid_ext"],
            "grid_start_s_m": round(meta["grid_start_s"], 3),
            "slots": [dict(index=g["index"], col=g["col"], row=g["row"],
                            x=round(g["x"], 4), y=round(g["y"], 4), yaw_rad=round(g["yaw"], 4),
                            s_m=round(g["s"], 3)) for g in res["grid_slots"]],
        },
        "grass": {"width_each_side_m": meta["grass_w"],
                   "note": "협로/갈림길 구간에서는 폭이 트랙 폭에 비례해 줄어듦"},
        "walls": {"height_m": meta["wall_h"], "thickness_m": meta["wall_t"],
                   "note": "외곽 벽은 트랙/잔디 바깥 경계를 따르고, 협로에서는 벽이 넥을 따라감. 피트 레인 없음(그리드로 대체)."},
        "speed_bumps": {
            "bump_length_m": BUMP_LEN * meta["scale"], "bump_height_m": meta["bump_height"],
            "spacing_m": BUMP_SPACING * meta["scale"], "count": len(res["bumps"]),
            "bumps": [dict(x=round(b["x"], 4), y=round(b["y"], 4), yaw_rad=round(b["yaw"], 4),
                            s_m=round(b["s"], 3)) for b in res["bumps"]],
        },
        "traffic_light": {
            "pose": {"x": round(res["traffic_light"]["x"], 4), "y": round(res["traffic_light"]["y"], 4),
                      "yaw_rad": round(res["traffic_light"]["yaw"], 4)},
            "gantry_height_m": res["traffic_light"]["gantry_height"],
            "lamps": res["traffic_light"]["lamps"], "udp_port": 47810,
        },
        "aruco_markers": {
            "dictionary": ARUCO_DICT, "marker_size_m": ARUCO_SIZE * meta["scale"],
            "mount_bottom_height_m": ARUCO_MOUNT_H * meta["scale"],
            "markers": [
                {"id": m["id"], "real": m["real"], "role": m.get("role", "fake"),
                 "pose": {"x": round(m["x"], 4), "y": round(m["y"], 4), "z": round(m["z"], 4),
                           "yaw_rad": round(m["yaw"], 4)},
                 "normal_note": "yaw points along the marker's outward-facing normal, toward the track",
                 "s_m": (round(m["s"], 3) if m["s"] is not None else None),
                 "note": m.get("note", "")}
                for m in res["markers"]
            ],
        },
        "verification": checks,
    }
    with open(os.path.join(outdir, "scene.json"), "w") as f:
        json.dump(scene, f, indent=2)
    return scene


def write_traffic_light_controller(outdir):
    content = '''#!/usr/bin/env python3
"""
traffic_light.py -- simulator-agnostic race-start traffic light controller
for the ISTech IT Arena track.

Broadcasts the light state as JSON over UDP broadcast on port 47810, so any
team's stack (F1TENTH gym, ROS 2 node, a bare Python client, Gazebo bridge,
...) can subscribe without depending on a specific simulator's message type.

Sequence (matches a standard F1-style start):
    RED          3.0 s
    RED + YELLOW 1.0 s
    GREEN        (race on, held until stopped / re-armed)

Wire format (UDP, JSON, one packet per state change and one heartbeat/0.2s):
    {"t": <unix_time_s>, "state": "red"|"red_yellow"|"green",
     "red": bool, "yellow": bool, "green": bool, "seq": <int>}

--- Hooking this into Gazebo (Gazebo Sim / gz) ---
This script does NOT talk to Gazebo directly (kept simulator-neutral). If you
want the lamp_red / lamp_yellow / lamp_green links in world.sdf to actually
light up, run a small bridge that listens on this UDP socket and toggles the
material's <emissive> via the transport service, e.g.:

    gz service -s /world/it_arena_track/state ...  # or
    gz topic -t /world/it_arena_track/visual_config -m gz.msgs.Visual -p '...'

or, in ROS 2 + ros_gz, remap the state to a `std_msgs/ColorRGBA` topic and use
an `ignition::gazebo::systems::UserCommands` / material-switch plugin. Because
exact topic names depend on your Gazebo version, wire this up on the
integration side; this script only guarantees the UDP JSON contract above.
"""
import argparse
import json
import socket
import time

UDP_PORT = 47810


def broadcast_loop(port=UDP_PORT, host="255.255.255.255", loop=True):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    seq = 0

    def send(state, red, yellow, green):
        nonlocal seq
        seq += 1
        payload = json.dumps({"t": time.time(), "state": state, "red": red,
                               "yellow": yellow, "green": green, "seq": seq}).encode()
        sock.sendto(payload, (host, port))

    def hold(state, red, yellow, green, duration):
        t_end = time.time() + duration
        while time.time() < t_end:
            send(state, red, yellow, green)
            time.sleep(0.2)

    print(f"[traffic_light] broadcasting UDP JSON on port {port} ...")
    while True:
        print("[traffic_light] RED")
        hold("red", True, False, False, 3.0)
        print("[traffic_light] RED+YELLOW")
        hold("red_yellow", True, True, False, 1.0)
        print("[traffic_light] GREEN - go!")
        t_end = time.time() + 3600 if loop else time.time() + 5
        while time.time() < t_end:
            send("green", False, False, True)
            time.sleep(0.2)
        if not loop:
            break


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=UDP_PORT)
    ap.add_argument("--host", default="255.255.255.255", help="UDP target (broadcast by default)")
    ap.add_argument("--once", action="store_true", help="run one red->green sequence and exit")
    args = ap.parse_args()
    broadcast_loop(port=args.port, host=args.host, loop=not args.once)
'''
    with open(os.path.join(outdir, "traffic_light.py"), "w") as f:
        f.write(content)


def render_preview(res, boxes, outdir, checks):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    from matplotlib.patches import Polygon, Rectangle

    kr_font = None
    candidate_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for fam in ["NanumGothic", "Noto Sans CJK KR", "AppleGothic", "Malgun Gothic"]:
        matches = [f.fname for f in fm.fontManager.ttflist if fam.lower() in f.name.lower()]
        if matches:
            kr_font = fm.FontProperties(fname=matches[0])
            break
    if kr_font is None:
        for p in candidate_paths:
            if os.path.exists(p):
                fm.fontManager.addfont(p)
                kr_font = fm.FontProperties(fname=p)
                break
    if kr_font is None:
        kr_font = fm.FontProperties()
    matplotlib.rcParams["axes.unicode_minus"] = False

    meta = res["meta"]
    arr = res["arr"]
    has_forks = res.get("fork1") is not None
    branches = res.get("branches") or []
    branch_colors = ["#00c2ff", "#ff8fa3", "#c77dff", "#ffd54d", "#7CFFB2", "#ff9d4d"]
    is_design = bool(meta.get("design_mode"))

    fig, ax = plt.subplots(figsize=(10, 13))

    hall_w, hall_h = HALL_W * meta["scale"], HALL_H * meta["scale"]
    ax.add_patch(Rectangle((0, 0), hall_w, hall_h, fill=False, edgecolor="purple", lw=2, zorder=1))

    def ribbon_poly(left, right, color, alpha, z):
        pts = np.concatenate([left[:, :2], right[::-1, :2]], axis=0)
        ax.add_patch(Polygon(pts, closed=True, facecolor=color, edgecolor="none", alpha=alpha, zorder=z))

    ribbon_poly(res["left_grass_out"], res["left_b"], "#7CCB6E", 1.0, 2)
    ribbon_poly(res["right_b"], res["right_grass_out"], "#7CCB6E", 1.0, 2)
    ribbon_poly(res["left_b"], res["right_b"], "#555555", 1.0, 3)
    if has_forks:
        ribbon_poly(res["fork1_left"], res["fork1_right"], "#C77DFF", 0.9, 3)
        ribbon_poly(res["fork2_left"], res["fork2_right"], "#FF8FA3", 0.9, 3)
    for i, br in enumerate(branches):
        bl = offset_polyline(br["arr"], br["width_m"] / 2.0)
        brr = offset_polyline(br["arr"], -br["width_m"] / 2.0)
        ribbon_poly(bl, brr, branch_colors[i % len(branch_colors)], 0.9, 3.2)

    branch_wall_keys = tuple(f"walls_branch{i}_{side}" for i in range(len(branches)) for side in ("left", "right"))
    for key in ("walls_main_left", "walls_main_right", "walls_fork1_left", "walls_fork1_right",
                "walls_fork2_left", "walls_fork2_right") + branch_wall_keys:
        for b in boxes.get(key, []):
            ax.add_patch(Polygon(box_corners(b), closed=True, facecolor="black", zorder=4))

    ax.plot(arr[:, 0], arr[:, 1], "--", color="white", lw=0.6, zorder=5)

    # 노면변화 patch(es)
    for fi, fz in enumerate(get_friction_zones(res)):
        fxp, fyp, fthp = sample_at_s(arr, fz["s_center"], meta["Ltot"])
        tw_here = res["track_width_at"](fz["s_center"])
        b = dict(x=fxp, y=fyp, yaw=fthp, length=fz["length"], width=tw_here)
        ax.add_patch(Polygon(box_corners(b), closed=True, facecolor="#9B59B6", alpha=0.6, zorder=6))
        ax.annotate("노면변화", (fxp, fyp), xytext=(fxp + 1.0, fyp + 1.1 + fi * 0.4), fontsize=9,
                    fontproperties=kr_font, arrowprops=dict(arrowstyle="->", lw=0.8), zorder=10)

    # 협로 label(s)
    for ni, nz in enumerate(get_narrow_targets(res)):
        nxp, nyp, _ = sample_at_s(arr, nz["s_center"], meta["Ltot"])
        ax.annotate(f"협로 {nz['width_m']:.2f}m (1대)", (nxp, nyp), xytext=(nxp - 2.4, nyp - 0.6 - ni * 0.4),
                    fontsize=9, fontproperties=kr_font, arrowprops=dict(arrowstyle="->", lw=0.8), zorder=10)

    for bmp in res["bumps"]:
        b = dict(x=bmp["x"], y=bmp["y"], yaw=bmp["yaw"], length=bmp["length"] * 6, width=bmp["width"])
        ax.add_patch(Polygon(box_corners(b), closed=True, facecolor="#B8860B", zorder=6))
    if res["bumps"]:
        mid = res["bumps"][len(res["bumps"]) // 2]
        bx, by = mid["x"], mid["y"]
        ax.annotate(f"과속방지턱 x{len(res['bumps'])}", (bx, by), xytext=(bx + 1.3, by + 1.0),
                    fontsize=9, ha="left", fontproperties=kr_font,
                    arrowprops=dict(arrowstyle="->", lw=0.8), zorder=10)

    # grid slots
    for g in res["grid_slots"]:
        b = dict(x=g["x"], y=g["y"], yaw=g["yaw"], length=g["length"], width=g["width"])
        ax.add_patch(Polygon(box_corners(b), closed=True, fill=False, edgecolor="white", lw=1.2, zorder=8))
    if res["grid_slots"]:
        gx = np.mean([g["x"] for g in res["grid_slots"]])
        gy = np.mean([g["y"] for g in res["grid_slots"]])
        ax.annotate(f"출발 그리드 ({meta['grid_cars']}대, 2열 지그재그)", (gx, gy),
                    xytext=(gx - 3.2, gy - 1.6), fontsize=9, fontproperties=kr_font,
                    arrowprops=dict(arrowstyle="->", lw=0.8), zorder=10)

    tl = res["traffic_light"]
    perp = tl["yaw"] + math.pi / 2
    half = meta["track_w"] / 2 + meta["grass_w"]
    sf_a = (tl["x"] - math.cos(perp) * half, tl["y"] - math.sin(perp) * half)
    sf_b = (tl["x"] + math.cos(perp) * half, tl["y"] + math.sin(perp) * half)
    ax.plot([sf_a[0], sf_b[0]], [sf_a[1], sf_b[1]], color="white", lw=2.5, zorder=7, solid_capstyle="butt")
    ax.plot([sf_a[0], sf_b[0]], [sf_a[1], sf_b[1]], color="black", lw=2.5, zorder=6.5, ls=(0, (3, 3)))
    ax.plot(tl["x"], tl["y"] + half + 0.15 * meta["scale"], marker="^", color="black", ms=14, zorder=8)
    for i, c in enumerate(["red", "gold", "green"]):
        ax.plot(tl["x"] + (i - 1) * 0.08 * meta["scale"], tl["y"] + half + 0.15 * meta["scale"],
                 marker="o", color=c, ms=6, zorder=9)
    ax.annotate("출발/결승선 + 신호등", (tl["x"], tl["y"] + half + 0.15 * meta["scale"]),
                xytext=(tl["x"] + 2.6, tl["y"] + 0.3), fontproperties=kr_font,
                fontsize=9, arrowprops=dict(arrowstyle="->", lw=0.8), zorder=10)

    # gates (built-in-course only; --design mode has no gates/forks concept)
    if meta.get("gate12_s") is not None and meta.get("gate23_s") is not None:
        gate_offsets = {"게이트①②": (0.9, 1.0), "게이트②③": (-1.0, 1.5)}
        for s_val, label in [(meta["gate12_s"], "게이트①②"), (meta["gate23_s"], "게이트②③")]:
            gx_, gy_, gth = sample_at_s(arr, s_val, meta["Ltot"])
            perp2 = gth + math.pi / 2
            halfw = meta["track_w"] / 2 + meta["grass_w"] * 0.5
            ga = (gx_ - math.cos(perp2) * halfw, gy_ - math.sin(perp2) * halfw)
            gb = (gx_ + math.cos(perp2) * halfw, gy_ + math.sin(perp2) * halfw)
            ax.plot([ga[0], gb[0]], [ga[1], gb[1]], color="orange", lw=2.0, zorder=7)
            dx, dy = gate_offsets[label]
            ax.annotate(label, (gx_, gy_), xytext=(gx_ + dx, gy_ + dy), fontsize=9,
                        fontproperties=kr_font, arrowprops=dict(arrowstyle="->", lw=0.8), zorder=10)

    # forks (built-in-course only)
    if has_forks:
        f1x, f1y = res["fork1"]["arr"][len(res["fork1"]["arr"]) // 2, :2]
        ax.annotate("갈림길① (시케인 우회)", (f1x, f1y), xytext=(f1x - 3.0, f1y + 0.6), fontsize=9,
                    fontproperties=kr_font, color="#7B2FBE", arrowprops=dict(arrowstyle="->", lw=0.8), zorder=10)
        f2x, f2y = res["fork2"]["arr"][len(res["fork2"]["arr"]) // 2, :2]
        ax.annotate("갈림길② (헤어핀 우회)", (f2x, f2y), xytext=(f2x + 1.5, f2y + 1.7), fontsize=9,
                    fontproperties=kr_font, color="#C2185B", arrowprops=dict(arrowstyle="->", lw=0.8), zorder=10)

    # branches (v4 design-mode 갈림길/지름길)
    for i, br in enumerate(branches):
        mx_, my_ = br["arr"][len(br["arr"]) // 2, :2]
        col = branch_colors[i % len(branch_colors)]
        ax.annotate(f"{br['name']} ({br['width_m']:.2f}m)", (mx_, my_),
                    xytext=(mx_ + 1.2, my_ + 0.8 + (i % 3) * 0.4), fontsize=9,
                    fontproperties=kr_font, color=col, arrowprops=dict(arrowstyle="->", lw=0.8), zorder=10)

    # sector labels
    sector_colors = {"sector1": "#1E8E6B", "sector2": "#D08A20", "sector3": "#6C63C7"}
    sector_labels = {"sector1": "섹터 1", "sector2": "섹터 2", "sector3": "섹터 3"}
    for sec in meta["sectors"]:
        s_mid = (sec["s_start"] + sec["s_end"]) / 2.0 % meta["Ltot"]
        mx, my, _ = sample_at_s(arr, s_mid, meta["Ltot"])
        ax.text(mx, my, sector_labels[sec["name"]], fontsize=11, weight="bold",
                fontproperties=kr_font, color=sector_colors[sec["name"]],
                ha="center", va="center", zorder=11,
                bbox=dict(boxstyle="round", facecolor="white", edgecolor=sector_colors[sec["name"]], alpha=0.85))

    for m in res["markers"]:
        if m["real"]:
            ax.plot(m["x"], m["y"], "o", color="dodgerblue", ms=7, mec="black", zorder=9)
            ax.annotate(f"ID{m['id']}", (m["x"], m["y"]), fontsize=8, color="navy",
                        xytext=(4, 4), textcoords="offset points", zorder=10)
        else:
            ax.plot(m["x"], m["y"], "x", color="red", ms=10, mew=2.2, zorder=9)
            ax.annotate(f"ID{m['id']}(fake)", (m["x"], m["y"]), fontsize=8, color="red",
                        xytext=(6, -13), textcoords="offset points", zorder=10)

    half_corridor = meta["track_w"] / 2 + meta["grass_w"] + meta["wall_t"]
    if has_forks:
        xs = np.concatenate([arr[:, 0], res["fork1"]["arr"][:, 0], res["fork2"]["arr"][:, 0]])
        ys = np.concatenate([arr[:, 1], res["fork1"]["arr"][:, 1], res["fork2"]["arr"][:, 1]])
    elif branches:
        xs = np.concatenate([arr[:, 0]] + [b["arr"][:, 0] for b in branches])
        ys = np.concatenate([arr[:, 1]] + [b["arr"][:, 1] for b in branches])
    else:
        xs, ys = arr[:, 0], arr[:, 1]
    bx0, bx1 = xs.min() - half_corridor, xs.max() + half_corridor
    by0, by1 = ys.min() - half_corridor, ys.max() + half_corridor
    ax.annotate("", xy=(bx0, -0.6), xytext=(bx1, -0.6), arrowprops=dict(arrowstyle="<->", color="dimgray"))
    ax.text((bx0 + bx1) / 2, -0.9, f"{bx1-bx0:.2f} m", ha="center", fontsize=9, color="dimgray")
    ax.annotate("", xy=(hall_w + 0.6, by0), xytext=(hall_w + 0.6, by1),
                arrowprops=dict(arrowstyle="<->", color="dimgray"))
    ax.text(hall_w + 0.9, (by0 + by1) / 2, f"{by1-by0:.2f} m", va="center", rotation=90,
            fontsize=9, color="dimgray")

    ax.set_xlim(-1.5, hall_w + 2.0)
    ax.set_ylim(-1.8, hall_h + 1.0)
    ax.set_aspect("equal")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    course_title = "후보1 통합 코스 (A+B)" if not is_design else "사용자 설계 코스 (track_editor.html)"
    ax.set_title(f"IT Arena 트랙 평면도 - {course_title}  (전장 {meta['Ltot']:.1f} m, 홀 {hall_w:.1f}x{hall_h:.1f} m)",
                 fontproperties=kr_font, fontsize=12)

    narrow_targets_for_legend = get_narrow_targets(res)
    if narrow_targets_for_legend:
        narrow_txt = ", ".join(f"{t['width_m']:.2f}m" for t in narrow_targets_for_legend)
        surface_legend = f"주행 노면 (기본 {meta['track_w']:.2f}m, 협로 {narrow_txt})"
    else:
        surface_legend = f"주행 노면 (기본 {meta['track_w']:.2f}m)"

    legend_items = [(plt.Line2D([0], [0], color="#555555", lw=8), surface_legend)]
    if has_forks:
        legend_items += [
            (plt.Line2D([0], [0], color="#C77DFF", lw=8), "갈림길① 대체 경로"),
            (plt.Line2D([0], [0], color="#FF8FA3", lw=8), "갈림길② 대체 경로"),
        ]
    for i, br in enumerate(branches):
        legend_items.append((plt.Line2D([0], [0], color=branch_colors[i % len(branch_colors)], lw=8),
                              f"{br['name']} (지름길, {br['width_m']:.2f}m)"))
    legend_items += [
        (plt.Line2D([0], [0], color="#7CCB6E", lw=8), "잔디 완충구간"),
        (plt.Line2D([0], [0], color="black", lw=6), f"벽 (높이 {WALL_H}m, 두께 0.05m)"),
        (plt.Line2D([0], [0], color="#B8860B", lw=6), "과속방지턱 구간"),
        (plt.Line2D([0], [0], color="#9B59B6", lw=6), "노면변화 구간"),
        (plt.Line2D([0], [0], color="white", lw=1.5, marker="s", mec="black"), "출발 그리드 슬롯"),
        (plt.Line2D([0], [0], marker="o", color="dodgerblue", lw=0, mec="black"), "실제 ArUco 마커"),
        (plt.Line2D([0], [0], marker="x", color="red", lw=0, mew=2), "가짜(FAKE) ArUco 마커"),
        (plt.Line2D([0], [0], marker="^", color="black", lw=0), "출발 신호등"),
        (plt.Line2D([0], [0], color="purple", lw=2), f"홀 외곽선 ({HALL_W:.1f} x {HALL_H:.1f} m)"),
    ]
    kr_font_small = kr_font.copy()
    kr_font_small.set_size(8)
    ax.legend([h for h, _ in legend_items], [l for _, l in legend_items],
              loc="upper left", framealpha=0.9, prop=kr_font_small)

    ok = all(v for k, v in checks.items() if k.endswith("_ok") and isinstance(v, bool))
    status = "PASS" if ok else "CHECK"
    ax.text(0.99, 0.01, f"lap={checks['lap_length_m']}m  minR_gen={checks['min_centerline_radius_general_m']}m  "
                          f"minR_chi={checks['min_centerline_radius_chicane_m']}m  "
                          f"clearance={checks['min_adjacent_clearance_m']}m  [{status}]",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color="dimgray")

    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "preview.png"), dpi=130)
    plt.close(fig)


def parse_bump_height(s):
    if s in BUMP_PRESETS:
        return BUMP_PRESETS[s]
    try:
        return float(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"--bump-height must be one of {list(BUMP_PRESETS)} or a number in meters")


def main():
    ap = argparse.ArgumentParser(description="ISTech IT Arena track generator -- 후보1 통합 코스 (A+B)")
    ap.add_argument("--bump-height", type=parse_bump_height, default=BUMP_PRESETS["mid"],
                     help="low|mid|high preset or a value in meters (default: mid = 0.010 m)")
    ap.add_argument("--resolution", type=float, default=0.01, help="map raster resolution, m/px (default 0.01)")
    ap.add_argument("--scale", type=float, default=1.0, help="global scale factor applied to every dimension "
                                                              "(ignored in --design mode)")
    ap.add_argument("--grid-cars", type=int, default=6, help="number of starting-grid car slots (default 6, "
                                                              "overrides design.json's grid_zone.cars if given)")
    ap.add_argument("--outdir", default="output", help="output directory (default: output)")
    ap.add_argument("--design", default=None, metavar="design.json",
                     help="load a track_editor.html design.json and build the track from it instead of the "
                          "built-in 후보1 통합 코스 layout (skips the hardcoded layout entirely)")
    args = ap.parse_args()

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(os.path.join(outdir, "aruco"), exist_ok=True)

    grid_cars_explicit = args.grid_cars if any(a.startswith("--grid-cars") for a in sys.argv[1:]) else None

    if args.design:
        print(f"[track_gen] --design given: loading {args.design} (skipping built-in layout) ...")
        design = load_design(args.design)
        res = build_all_from_design(design, resolution=args.resolution, bump_height=args.bump_height,
                                     grid_cars_override=grid_cars_explicit, outdir=outdir)
        print(f"[track_gen] design centerline: {len(design.get('control_points', []))} control points, "
              f"lap length {res['meta']['Ltot']:.2f} m, track width {res['meta']['track_w']:.2f} m")
    else:
        print(f"[track_gen] building geometry  scale={args.scale}  bump_height={args.bump_height} m "
              f"resolution={args.resolution} m/px  grid_cars={args.grid_cars} ...")
        res = build_all(scale=args.scale, resolution=args.resolution, bump_height=args.bump_height,
                         grid_cars=args.grid_cars, outdir=outdir)
    boxes = build_geometry_boxes(res)

    print("[track_gen] writing centerline / boundary / alt-route CSVs ...")
    write_csvs(res, outdir)

    print("[track_gen] writing occupancy-grid map.png / map_with_grass.png / *.yaml ...")
    write_map(res, boxes, outdir, args.resolution)

    print("[track_gen] writing Gazebo world.sdf ...")
    write_sdf(res, boxes, outdir)

    print("[track_gen] writing venue_layout.dxf ...")
    write_dxf(res, boxes, outdir)

    print("[track_gen] generating ArUco markers + print sheet ...")
    write_aruco(res, outdir)

    print("[track_gen] writing traffic_light.py controller ...")
    write_traffic_light_controller(outdir)

    print("[track_gen] running verification checks ...")
    checks = run_checks(res)

    print("[track_gen] writing scene.json ...")
    write_scene_json(res, outdir, checks)

    print("[track_gen] rendering preview.png ...")
    render_preview(res, boxes, outdir, checks)

    print("\n=== VERIFICATION RESULTS ===")
    for k, v in checks.items():
        print(f"  {k}: {v}")
    print("============================\n")
    print(f"[track_gen] done. All files written under: {os.path.abspath(outdir)}")
    return res, checks


if __name__ == "__main__":
    main()
