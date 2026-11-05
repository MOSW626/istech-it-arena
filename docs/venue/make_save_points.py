"""save_points.png — 610mm 직각 코스 세이브 포인트 (2026-11-06 확정, 운영진 표시 그림 기준).
usage: python docs/venue/make_save_points.py   (repo 루트에서)
세이브 포인트는 본선 중심선 위, s(출발선부터 진행 방향 거리, m)로 정한다."""
import csv, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

OUT = "track/output_final"
SAVE_S = [5.57, 14.61, 19.56, 24.50, 31.17, 38.54]

for f in ("Pretendard", "Apple SD Gothic Neo", "NanumGothic", "Noto Sans CJK KR"):
    if any(f in x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break


def load(name):
    with open(f"{OUT}/{name}") as fh:
        return [(float(r["x_m"]), float(r["y_m"]), float(r["s_m"])) for r in csv.DictReader(fh)]


cl, lb, rb = load("centerline.csv"), load("left_boundary.csv"), load("right_boundary.csv")


def at(s):
    i = min(range(len(cl)), key=lambda k: abs(cl[k][2] - s))
    j = min(i + 1, len(cl) - 1)
    return cl[i][0], cl[i][1], math.atan2(cl[j][1] - cl[i][1], cl[j][0] - cl[i][0])


fig, ax = plt.subplots(figsize=(7, 9))
ax.fill([p[0] for p in lb] + [p[0] for p in rb[::-1]], [p[1] for p in lb] + [p[1] for p in rb[::-1]],
        color="#d9d9d9", zorder=1)
for b in ("branch_0.csv", "branch_1.csv"):
    p = load(b)
    ax.plot([q[0] for q in p], [q[1] for q in p], color="#bbbbbb", lw=6, solid_capstyle="butt", zorder=1)
ax.plot([p[0] for p in cl], [p[1] for p in cl], color="#999", lw=0.6, ls="--", zorder=2)
ax.plot([9.495, 10.105], [6.5, 6.5], color="k", lw=2.5, zorder=3)
ax.annotate("출발/결승선", (10.1, 6.5), (10.4, 7.0), fontsize=9, arrowprops=dict(arrowstyle="-", lw=0.6))
rows = []
for n, s in enumerate(SAVE_S, 1):
    x, y, h = at(s)
    ax.annotate("", (x + 0.8 * math.cos(h), y + 0.8 * math.sin(h)), (x + 0.2 * math.cos(h), y + 0.2 * math.sin(h)),
                arrowprops=dict(arrowstyle="->", lw=1.6, color="#c00"), zorder=4)
    ax.plot(x, y, "o", ms=17, color="#d22", zorder=5)
    ax.text(x, y, str(n), color="w", ha="center", va="center", fontsize=10, weight="bold", zorder=6)
    rows.append((n, x, y, s))
ax.set_aspect("equal")
ax.set_xlim(1.5, 11.0)
ax.set_ylim(0.3, 14.0)
ax.set_xlabel("x [m]")
ax.set_ylabel("y [m]")
ax.grid(alpha=0.25)
ax.set_title("세이브 포인트 6곳 — 610mm 직각 코스 (2026-11-06)\n빨간 원 = 도로 가운데, 화살표 = 진행 방향", fontsize=11)
fig.tight_layout()
fig.savefig("docs/venue/save_points.png", dpi=110)
for r in rows:
    print("| %d | %.2f | (%.2f, %.2f) |" % (r[0], r[3], r[1], r[2]))
