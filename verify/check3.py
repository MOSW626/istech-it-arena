#!/usr/bin/env python3
"""독립 게이트 검증 — v2026.09.14 (ArUco 갠트리 설치 + 벽 0.40m).

track_gen.py의 자기 보고를 신뢰하지 않고 산출물을 직접 파싱한다.
양성 대조: 직전 릴리즈(v2026.09.02)가 같은 검사에서 실패해야 검사가 유효하다.

  usage: python3 check3.py <gate>      gate = g1..g8 | all
"""
import csv, hashlib, math, os, re, sys, json, xml.etree.ElementTree as ET

SP  = "/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/708a604c-8cbd-4b10-81eb-e32674559bcf/scratchpad"
NEW = os.path.join(SP, "new_out")                        # 이번 릴리즈 후보
OLD = os.path.join(SP, "rel0902", "x", "output_final")   # 양성 대조 (v2026.09.02)
GEN = "/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/istech-it-arena/track"
# colima는 $HOME 아래만 VM에 마운트한다. docker를 쓰는 G9은 scratchpad(/private/tmp)가 아니라
# 리포 안의 산출물을 본다 -- 설치 후라 new_out과 바이트 동일하고, G4/G6이 그걸 보증한다.
REPO_OUT  = os.path.join(GEN, "output_final")
GZ_BROKEN = "/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/.gzbroken"

WALL_H_EXPECT   = 0.40
MARKER_CENTER_H = 0.40
MARKER_SIZE     = 0.10
ROAD_W          = 0.45
CAR_W           = 0.15

# ---------- parsing helpers ----------

def sdf_links(path):
    """{link_name: [(pose6, boxsize3|None), ...]} — <link>/<pose> and every
    child geometry box with its own pose."""
    root = ET.parse(path).getroot()
    out = {}
    for link in root.iter("link"):
        name = link.get("name")
        lp = link.find("pose")
        lpose = [float(v) for v in lp.text.split()] if lp is not None else [0]*6
        items = []
        for child in list(link):
            if child.tag not in ("visual", "collision"):
                continue
            cp = child.find("pose")
            pose = [float(v) for v in cp.text.split()] if cp is not None else lpose
            box = child.find("./geometry/box/size")
            size = [float(v) for v in box.text.split()] if box is not None else None
            items.append((child.get("name"), pose, size))
        out[name] = (lpose, items)
    return out


def centerline(path):
    with open(path) as f:
        return [(float(r["x_m"]), float(r["y_m"]), float(r["s_m"])) for r in csv.DictReader(f)]


def nearest_on_centerline(cl, x, y):
    best = min(range(len(cl)), key=lambda i: (cl[i][0]-x)**2 + (cl[i][1]-y)**2)
    d = math.hypot(cl[best][0]-x, cl[best][1]-y)
    a, b = cl[(best-1) % len(cl)], cl[(best+1) % len(cl)]
    th = math.atan2(b[1]-a[1], b[0]-a[0])
    return d, th, cl[best][2]


def angdiff(a, b):
    return abs(math.atan2(math.sin(a-b), math.cos(a-b)))


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def aruco_links(path):
    return {k: v for k, v in sdf_links(path).items() if k.startswith("aruco_")}

# ---------- gates ----------

def g1():
    """벽 높이 = 0.40 m, 모든 벽 박스가 동일 높이이고 pose z = h/2 (바닥 밀착)."""
    links = sdf_links(os.path.join(NEW, "world.sdf"))
    assert "walls" in links, "walls 링크 없음"
    heights, zs = set(), set()
    n = 0
    for nm, pose, size in links["walls"][1]:
        if size is None:
            continue
        heights.add(round(size[2], 4)); zs.add(round(pose[2], 4)); n += 1
    assert heights == {WALL_H_EXPECT}, f"벽 높이 불일치: {sorted(heights)}"
    assert zs == {round(WALL_H_EXPECT/2, 4)}, f"벽 pose z 불일치: {sorted(zs)}"
    print(f"G1_OK walls={n} height={WALL_H_EXPECT} pose_z={WALL_H_EXPECT/2}")


def g2():
    """ArUco 4개: 도로 중앙 · 중심 높이 0.40 m · 10×10 cm · 접근 차량 정면."""
    cl = centerline(os.path.join(NEW, "centerline.csv"))
    marks = aruco_links(os.path.join(NEW, "world.sdf"))
    assert len(marks) == 4, f"마커 수 {len(marks)} (기대 4)"
    worst_off = worst_ang = 0.0
    for nm, (lpose, items) in sorted(marks.items()):
        x, y, z, _, _, yaw = lpose
        assert abs(z - MARKER_CENTER_H) < 1e-3, f"{nm} 중심 높이 {z}"
        size = items[0][2]
        assert abs(size[1]-MARKER_SIZE) < 1e-6 and abs(size[2]-MARKER_SIZE) < 1e-6, f"{nm} 크기 {size}"
        d, th, s = nearest_on_centerline(cl, x, y)
        worst_off = max(worst_off, d)
        assert d < 0.01, f"{nm} 센터라인에서 {d*100:.1f}cm 벗어남"
        ang = angdiff(yaw, th + math.pi)
        worst_ang = max(worst_ang, ang)
        assert ang < math.radians(2.0), f"{nm} 지향 오차 {math.degrees(ang):.2f}°"
    print(f"G2_OK markers=4 max_center_offset={worst_off*1000:.2f}mm "
          f"max_facing_err={math.degrees(worst_ang):.2f}deg size={MARKER_SIZE}")


def g3():
    """주행 간섭: 마커 하단 높이와 좌우 통과폭이 차량 규격을 허용하는가."""
    marks = aruco_links(os.path.join(NEW, "world.sdf"))
    bottoms = {round(l[0][2] - l[1][0][2][2]/2.0, 4) for l in marks.values()}
    assert len(bottoms) == 1, f"마커 하단 높이가 제각각: {bottoms}"
    bottom = bottoms.pop()
    side_gap = (ROAD_W - MARKER_SIZE) / 2.0
    margin = side_gap - CAR_W
    assert bottom >= 0.30, f"마커 하단 {bottom}m — 차량 상부와 간섭 위험"
    assert margin > 0.0, f"좌우 통과폭 부족 (측면 {side_gap}m vs 차폭 {CAR_W}m)"
    print(f"G3_OK bottom={bottom}m side_gap={side_gap:.3f}m car_margin={margin*100:.1f}cm/side")


def g4():
    """의도치 않은 부수 변경 없음 — 2D 산출물은 v2026.09.02와 바이트 동일."""
    same = ["centerline.csv", "left_boundary.csv", "right_boundary.csv",
            "branch_0.csv", "branch_1.csv", "map.png", "map.yaml",
            "map_with_grass.png", "map_with_grass.yaml", "traffic_light.py",
            "aruco/aruco_id0.png", "aruco/aruco_id20.png",
            "aruco/aruco_id30.png", "aruco/aruco_id45.png"]
    bad = [f for f in same if sha(os.path.join(NEW, f)) != sha(os.path.join(OLD, f))]
    assert not bad, f"2D 산출물이 바뀜: {bad}"
    # 바뀌어야 하는 것도 실제로 바뀌었는지 (검사가 무의미해지지 않게)
    changed = [f for f in ["world.sdf", "scene.json"]
               if sha(os.path.join(NEW, f)) != sha(os.path.join(OLD, f))]
    assert len(changed) == 2, f"높이 관련 파일이 안 바뀜: {changed}"
    print(f"G4_OK unchanged={len(same)} changed={changed}")


def g5():
    """양성 대조 — 구버전(v2026.09.02)은 G1·G2에서 실패해야 한다."""
    old_links = sdf_links(os.path.join(OLD, "world.sdf"))
    oh = {round(sz[2], 4) for _, _, sz in old_links["walls"][1] if sz}
    assert oh == {0.30}, f"구버전 벽 높이 기대 0.30, 실제 {sorted(oh)}"
    cl = centerline(os.path.join(OLD, "centerline.csv"))
    offs, zs = [], []
    for nm, (lp, items) in aruco_links(os.path.join(OLD, "world.sdf")).items():
        d, th, _ = nearest_on_centerline(cl, lp[0], lp[1])
        offs.append(d); zs.append(round(lp[2], 4))
    assert min(offs) > 0.15, f"구버전 마커가 이미 도로 중앙? min_off={min(offs)}"
    assert all(abs(z - MARKER_CENTER_H) > 0.2 for z in zs), f"구버전 마커 높이 {zs}"
    print(f"G5_OK old_wall_h=0.30 old_marker_min_offset={min(offs):.3f}m old_marker_z={sorted(set(zs))}")


def g6():
    """재생성 재현성 — 타임스탬프를 품는 포맷(dxf/pdf/preview) 외 바이트 동일."""
    import subprocess
    rerun = os.path.join(SP, "rerun_out")
    r = subprocess.run([os.path.join(SP, "venv/bin/python3"), "track_gen.py",
                        "--design", "design_final.json", "--outdir", rerun],
                       cwd=GEN, capture_output=True, text=True)
    assert r.returncode == 0, f"재생성 실패:\n{r.stderr[-800:]}"
    volatile = {"venue_layout.dxf", "aruco_print_sheet.pdf", "preview.png"}
    diffs = []
    for root, _, files in os.walk(NEW):
        for fn in files:
            rel = os.path.relpath(os.path.join(root, fn), NEW)
            if rel in volatile:
                continue
            if sha(os.path.join(NEW, rel)) != sha(os.path.join(rerun, rel)):
                diffs.append(rel)
    assert not diffs, f"재생성 불일치: {diffs}"
    print(f"G6_OK deterministic (volatile-excluded), volatile={sorted(volatile)}")


def g7():
    """SDF 위생 — XML 정상, aruco 텍스처 경로 실재, script 태그 0."""
    p = os.path.join(NEW, "world.sdf")
    ET.parse(p)                                   # well-formed
    txt = open(p).read()
    assert "<script>" not in txt, "script 태그 존재 (Gazebo 호환 회귀)"
    imgs = set(re.findall(r"<albedo_map>([^<]+)</albedo_map>", txt))
    assert len(imgs) == 4, f"albedo_map {len(imgs)}개"
    missing = [i for i in imgs if not os.path.exists(os.path.join(NEW, i))]
    assert not missing, f"텍스처 파일 없음: {missing}"
    print(f"G7_OK xml_ok script=0 textures={len(imgs)}")


def g8():
    """scene.json ↔ world.sdf 일치 (마커 pose·높이, 벽 높이)."""
    sc = json.load(open(os.path.join(NEW, "scene.json")))
    links = sdf_links(os.path.join(NEW, "world.sdf"))
    wh = {round(sz[2], 4) for _, _, sz in links["walls"][1] if sz}.pop()
    assert abs(sc["walls"]["height_m"] - wh) < 1e-9, \
        f"scene.json 벽 {sc['walls']['height_m']} vs sdf {wh}"
    am = sc["aruco_markers"]
    assert abs(am["mount_center_height_m"] - MARKER_CENTER_H) < 1e-6, am["mount_center_height_m"]
    assert "갠트리" in am["mounting"], am["mounting"]
    for m in am["markers"]:
        lp = links[f"aruco_{m['id']}"][0]
        assert abs(lp[0]-m["pose"]["x"]) < 1e-3 and abs(lp[1]-m["pose"]["y"]) < 1e-3, f"id{m['id']} xy 불일치"
        assert abs(lp[2] - (m["pose"]["z"] + MARKER_SIZE/2)) < 1e-6, f"id{m['id']} z 불일치"
    print(f"G8_OK wall_h={wh} center_h={am['mount_center_height_m']} markers={len(am['markers'])}")


def g9():
    """Gazebo 실기동 — 헤드리스 서버로 실제 로드되고 [Err]/[Wrn]이 0인가.

    로컬 macOS에는 gz가 없어 colima + docker로 돌린다. 준비는 한 번만:
        brew install colima docker && colima start --cpu 4 --memory 6
        cd verify && docker build -t gzcheck:jazzy -f Dockerfile.gz .

    ⚠️ **`gz sim`은 world 파싱에 실패해도 exit 0을 반환한다.** 종료 코드는 판정에
    쓸 수 없고, 로그의 [Err]/[Wrn] 건수와 `gz sdf -k`(이쪽은 정직하게 255를 낸다)로
    판정한다. 이 사실 자체를 아래 음성 대조가 매번 재확인한다.

    헤드리스 서버(-s)라 렌더링 경로는 타지 않는다 — 텍스처가 실제로 화면에 보이는지는
    이 게이트가 보증하지 않는다 (GATES 문서의 '미충족' 참고).
    """
    import subprocess, shutil

    def run(sh, mount):
        return subprocess.run(["docker", "run", "--rm", "-v", f"{mount}:/world:ro",
                               "gzcheck:jazzy", "bash", "-lc", sh],
                              capture_output=True, text=True)

    assert subprocess.run(["docker", "image", "inspect", "gzcheck:jazzy"],
                          capture_output=True).returncode == 0, \
        "gzcheck:jazzy 이미지 없음 — docstring의 준비 절차 참고"

    def probe(world, mount):
        sh = (f'. /opt/ros/jazzy/setup.sh; cd /world; '
              f'gz sdf -k {world} >/dev/null 2>&1; echo SPEC_EXIT=$?; '
              f'gz sim -s -r --iterations 200 -v 3 {world} 2>&1 '
              r'| sed "s/\x1b\[[0-9;]*m//g" | grep -cE "^\[(Err|Wrn)"')
        out = run(sh, mount).stdout
        spec = int(re.search(r"SPEC_EXIT=(\d+)", out).group(1))
        noise = int([l for l in out.splitlines() if l.strip().isdigit()][-1])
        return spec, noise

    spec, noise = probe("world.sdf", REPO_OUT)
    assert spec == 0, f"gz sdf -k 실패 (exit {spec})"
    assert noise == 0, f"gz sim 로그에 Err/Wrn {noise}건"

    # 음성 대조 — 깨진 world는 반드시 잡혀야 한다 (이게 통과하면 검사가 무의미)
    if not os.path.isdir(GZ_BROKEN):
        shutil.copytree(REPO_OUT, GZ_BROKEN)
    open(os.path.join(GZ_BROKEN, "world_badxml.sdf"), "w").write(
        open(os.path.join(REPO_OUT, "world.sdf")).read().replace("</sdf>", ""))
    bspec, bnoise = probe("world_badxml.sdf", GZ_BROKEN)
    assert bspec != 0 and bnoise > 0, \
        f"깨진 world가 통과함 — 검사 무효 (spec_exit={bspec}, err_wrn={bnoise})"

    links = run('. /opt/ros/jazzy/setup.sh; cd /world; gz sdf -p world.sdf 2>/dev/null '
                '| grep -c "<link name=.aruco_"', REPO_OUT).stdout.strip()
    assert links == "4", f"파싱된 ArUco 링크 {links}개 (기대 4)"
    print(f"G9_OK spec=valid err_wrn=0 aruco_links=4 "
          f"neg_control(spec_exit={bspec}, err_wrn={bnoise})")


GATES = dict(g1=g1, g2=g2, g3=g3, g4=g4, g5=g5, g6=g6, g7=g7, g8=g8, g9=g9)

if __name__ == "__main__":
    which = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    for k in (sorted(GATES) if which == "all" else [which]):
        GATES[k]()
