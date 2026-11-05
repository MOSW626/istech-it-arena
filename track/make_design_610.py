"""design_final.json for the 610mm right-angle course.
Source: track/track_610mm_build_2026-11-05.pdf pp.46-47 (P piece rectangles).
Centerline = middle of each 0.61 m strip."""
import json, sys
from shapely.geometry import LineString, Point

# P-piece strip centers (m): x of vertical strips, y of horizontal strips
X_R, X_M1, X_M2, X_M3, X_L = 9.800, 7.970, 6.140, 4.310, 2.480   # P01, P07, P11, P13, P15
Y_B, Y_T, Y_6, Y_3 = 1.200, 13.200, 6.000, 3.000                  # P17, P06, P10/P14, P12
START = (X_R, 6.5)   # start/finish line on the right straight (2026-11-06 확정)

loop = [START, (X_R, Y_T), (X_M1, Y_T), (X_M1, Y_6), (X_M2, Y_6), (X_M2, Y_3),
        (X_M3, Y_3), (X_M3, Y_6), (X_L, Y_6), (X_L, Y_B), (X_R, Y_B)]
main = LineString(loop + [START])
L = main.length


def s_of(p):
    return main.project(Point(p))


# P22: center y 4.5 (pdf y=4.4~4.6), P11 -> P13.  P21: line through (2.785,2.600)-(3.880,1.505)
# extended to the P15 / P17 strip centers.
P22 = [(X_M2, 4.5), (X_M3, 4.5)]
P21 = [(X_L, 2.600 + (2.785 - X_L)), (3.880 + (1.505 - Y_B), Y_B)]

branches = [dict(name="지름길 P22", width_m=0.2, s0=s_of(P22[0]), s1=s_of(P22[1]), label_offset=[1.7, 0.25],
                 control_points=[], centerline=[list(p) for p in P22]),
            dict(name="지름길 P21", width_m=0.2, s0=s_of(P21[0]), s1=s_of(P21[1]), label_offset=[1.7, -0.05],
                 control_points=[], centerline=[list(p) for p in P21])]

d = dict(
    version=4, hall=dict(w=11, h=14.5), track_width_m=0.61, closed=True,
    corner_join="mitre", course_name="610mm 직각 코스 (2026-11-05 도면)",
    source="track_610mm_build_2026-11-05.pdf pp.46-47",
    control_points=[], centerline=[list(p) for p in loop],
    features=dict(
        start_line=dict(s=0.0),
        # 신호등은 맨 앞 그리드칸 앞선에서 1.3 m (2026-11-06 확정). 앞칸 카메라(7.8 cm) 렌더에서 0.9 m 이하는 마커가 화면 위로 잘리고 1.1 m부터 검출.
        traffic_light=dict(s=0.0, side="left", ahead_of_grid=1.3),
        bump_zones=[], friction_zones=[],
        grid_zone=dict(s0=L - 3.03, s1=L - 1.53, cars=6),   # 신호등 s는 11-01 배치(44.285) 그대로, 그리드만 1.0 m 뒤로
        aruco=[dict(id=0, fake=False, s=0.0, side="right", mount="traffic_light"),
               # ID20: P22 직전 코너 (X_M2, Y_6) 위, 다가오는 y=6 직선을 향함 (2026-11-06 확정, 렌더 검출 1.0·1.4 m).
               # 분기 0.6 m 전(코너 출구 0.9 m)은 근거리 사각이라 안 보였다. 코너 점의 heading은 이등분선이라 1.5 cm 앞 s를 쓴다(진행 방향 = -x).
               dict(id=20, fake=False, s=s_of((X_M2, Y_6)) - 0.015, side="left"),
               dict(id=45, fake=False, s=0.0, side="left", mount="traffic_light"),
               dict(id=30, fake=False, s=branches[1]["s0"] - 0.6, side="left")]),   # ID30: P21 분기 0.6 m 전 (11-06 확정, 1.0~1.8 m 검출)
    branches=branches,
)
assert abs(L - 44.64) < 0.005, L
json.dump(d, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
print(f"L={L:.3f}", [(b["name"], round(b["s0"], 3), round(b["s1"], 3)) for b in branches])
