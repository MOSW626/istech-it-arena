"""Release gates for the 610mm right-angle course (2026-11-06).
usage: <venv python> check7.py g1..g8|all     (g3,g4,g5 need colima + gzcheck:jazzy)"""
import hashlib, json, math, os, re, shutil, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..", "istech-it-arena")
GEN = os.path.join(REPO, "track")
NEW = os.path.join(GEN, "output_final")
ST = os.path.join(HERE, "simtest")                  # under $HOME: colima mounts only there
PY = sys.executable
PDFTXT = os.path.join(ST, "pdf_text.txt")
OLD_REV = "2b27ab2"                                 # v2026.11.01 tree (curved course) = positive control


def sh(*a, **k):
    return subprocess.run(a, capture_output=True, text=True, **k)


def old_out():
    d = os.path.join(ST, "oldout")
    os.makedirs(d, exist_ok=True)
    for f in ("world.sdf", "scene.json", "map_with_grass.png", "map_with_grass.yaml"):
        open(os.path.join(d, f), "wb").write(subprocess.run(["git", "show", f"{OLD_REV}:track/output_final/{f}"],
                                                            cwd=REPO, capture_output=True, check=True).stdout)
    return d


def g1():
    """시뮬 기하 == PDF 도면 (P01~P22 바닥, W01~W61 벽) — check6 17항목, 구 코스는 탈락."""
    if not os.path.exists(PDFTXT):
        r = sh("pdftotext", "-layout", os.path.join(GEN, "track_610mm_build_2026-11-05.pdf"), PDFTXT)
        assert r.returncode == 0, r.stderr
    r = sh(PY, os.path.join(HERE, "check6.py"), PDFTXT, NEW)
    assert r.returncode == 0 and "ALL PASS" in r.stdout, r.stdout[-600:]
    n = r.stdout.count("\nPASS") + r.stdout.startswith("PASS")
    print(f"G1_OK pdf_gates={n}")


def raster(sdf_path, link, yaml_path, shape):
    """Rasterize a world.sdf link's collision boxes onto the map grid."""
    import cv2
    y = open(yaml_path).read()
    res = float(re.search(r"resolution: ([\d.]+)", y).group(1))
    ox, oy = map(float, re.search(r"origin: \[([-\d.e]+), ([-\d.e]+)", y).groups())
    body = re.search(rf'<link name="{link}">(.*?)</link>', open(sdf_path).read(), re.S).group(1)
    m = np.zeros(shape, np.uint8)
    for pose, size in re.findall(r"<collision[^>]*>\s*<pose>([^<]+)</pose>\s*<geometry><box><size>([^<]+)</size>", body):
        px, py, _, _, _, a = map(float, pose.split()); sx, sy, _ = map(float, size.split())
        c, s = math.cos(a), math.sin(a)
        pts = [(px + u * c - v * s, py + u * s + v * c) for u, v in ((-sx/2, -sy/2), (sx/2, -sy/2), (sx/2, sy/2), (-sx/2, sy/2))]
        pix = np.array([[(x - ox) / res, shape[0] - (yy - oy) / res] for x, yy in pts]) - 0.5
        cv2.fillPoly(m, [np.round(pix * 16).astype(np.int32)], 1, shift=4)
    return m.astype(bool)


def map_iou(out):
    import cv2
    a = cv2.imread(os.path.join(out, "map_with_grass.png"), 0)
    yml = os.path.join(out, "map_with_grass.yaml")
    road = raster(os.path.join(NEW, "world.sdf"), "track_surface", yml, a.shape)
    wall = raster(os.path.join(NEW, "world.sdf"), "walls", yml, a.shape)
    k = np.ones((3, 3), np.uint8)                        # 1 px tolerance: 5 cm walls at 1 cm/px have rasterization edges
    dil = lambda m: cv2.dilate(m.astype(np.uint8), k).astype(bool)
    match = lambda p, q: min((p & dil(q)).sum() / max(p.sum(), 1), (q & dil(p)).sum() / max(q.sum(), 1))
    return match(a == 254, road), match(a == 0, wall)


def g2():
    """ROS 점유격자 맵이 Gazebo world와 같은 자리 — 도로(254)·벽(0)이 world 박스와 겹침, 구 맵은 탈락."""
    r, w = map_iou(NEW)
    assert r > 0.99 and w > 0.99, (r, w)
    ro, wo = map_iou(old_out())
    assert ro < 0.5 and wo < 0.5, f"구 맵이 통과 — 검사 무효 ({ro:.2f},{wo:.2f})"
    print(f"G2_OK road_match={r:.4f} wall_match={w:.4f} old=({ro:.2f},{wo:.2f})")


def g3():
    """Gazebo 실주행 — 15x20 cm 차가 그리드 맨 앞칸에서 출발해 본선 1랩 + 지름길 2개 랩을 벽 접촉·멈춤 없이 완주."""
    wd = os.path.join(ST, "run_gate")
    shutil.rmtree(wd, ignore_errors=True); os.makedirs(wd)
    shutil.copy(os.path.join(ST, "drive.py"), wd)
    r = sh(PY, os.path.join(ST, "make_world.py"), NEW, wd); assert "MAKE_OK" in r.stdout, r.stdout + r.stderr
    r = sh(os.path.join(ST, "run_drive.sh"), wd)
    assert "done=True" in r.stdout and "GZ_ERR=0 GZ_WRN=0" in r.stdout, r.stdout[-500:]
    a = sh(PY, os.path.join(ST, "analyze.py"), NEW, wd)
    assert a.returncode == 0 and "DRIVE_ALL_PASS" in a.stdout, a.stdout
    neg = sh(PY, os.path.join(ST, "analyze.py"), old_out(), wd)
    assert neg.returncode != 0 and "FAIL no wall contact" in neg.stdout, "구 코스 기하로도 통과 — 검사 무효"
    rtf = re.search(r"sim_s=([\d.]+) wall_s=([\d.]+)", r.stdout)
    print("G3_OK", re.search(r"DRIVE_END.*", r.stdout).group(0).split(" samples")[0],
          f"rtf={float(rtf.group(1))/float(rtf.group(2)):.2f}", "|", " ".join(l for l in a.stdout.splitlines() if "min wall" in l))


def cam_poses(scene, mid, ds):
    cl = np.loadtxt(os.path.join(NEW, "centerline.csv"), delimiter=",", skiprows=1)
    L = cl[-1, 2] + np.hypot(*(cl[-1, :2] - cl[0, :2]))
    m = next(k for k in scene["aruco_markers"]["markers"] if k["id"] == mid)
    out = []
    for d in ds:
        s = (m["s_m"] - d - 0.10) % L                   # camera sits 0.10 m ahead of car center
        i = int(np.argmin(np.abs(cl[:, 2] - s)))
        j = (i + 5) % len(cl)
        out.append((d, cl[i, 0], cl[i, 1], math.atan2(cl[j, 1] - cl[i, 1], cl[j, 0] - cl[i, 0])))
    return out


def g4():
    """카메라(높이 7.8 cm, VFOV 42.5°)가 각 코스 마커를 '도로를 따라 1.0~1.8 m 앞'에서 최소 2곳 검출 (minMarkerDistanceRate 0.02)."""
    import cv2
    scene = json.load(open(os.path.join(NEW, "scene.json")))
    cd = os.path.join(ST, "cam_gate"); shutil.rmtree(cd, ignore_errors=True); os.makedirs(cd)
    shutil.copytree(os.path.join(NEW, "aruco"), os.path.join(cd, "aruco")); shutil.copy(os.path.join(ST, "grab.py"), cd)
    jobs = []
    for mid in (0, 20, 30, 45):
        for d, x, y, a in cam_poses(scene, mid, (1.0, 1.4, 1.8)):
            n = f"id{mid}_d{d}"
            sh(PY, os.path.join(ST, "make_cam.py"), NEW, os.path.join(cd, n + ".sdf"), str(x), str(y), str(a), "/w/x")
            jobs.append((mid, d, n))
    open(os.path.join(cd, "jobs.txt"), "w").write("\n".join(n for _, _, n in jobs) + "\n")
    r = sh("docker", "run", "--rm", "-v", f"{cd}:/w", "gzcheck:jazzy", "bash", "-c",
           "source /opt/ros/jazzy/setup.bash; while read n; do gz sim -s -r --headless-rendering /w/$n.sdf >/w/$n.log 2>&1 & "
           "python3 /w/grab.py /w/$n.npy; kill %1 2>/dev/null; wait 2>/dev/null; done < /w/jobs.txt")
    p = cv2.aruco.DetectorParameters(); p.minMarkerDistanceRate = 0.02
    det = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), p)
    seen = {}
    for mid, d, n in jobs:
        f = os.path.join(cd, n + ".npy")
        assert os.path.exists(f), f"frame missing {n}: {r.stdout[-300:]}"
        ids = det.detectMarkers(cv2.cvtColor(np.load(f), cv2.COLOR_RGB2GRAY))[1]
        if ids is not None and mid in ids.ravel():
            seen.setdefault(mid, []).append(d)
    summary = " ".join(f"id{m}@{seen.get(m, [])}" for m in (0, 20, 30, 45))
    assert seen.get(30) and len(seen[30]) >= 2, "ID30(양성 대조)도 안 보임 — 렌더/검출 경로 고장: " + summary
    bad = [m for m in (0, 20, 30, 45) if len(seen.get(m, [])) < 2]
    assert not bad, f"마커 {bad} 접근 1.0~1.8 m에서 2곳 미만 검출: {summary}"
    print("G4_OK", summary)


def g5():
    """Gazebo 로드 — gz sdf -k Valid, Err/Wrn 0, 깨진 world 음성 대조가 걸림."""
    def probe(world, mount):
        cmd = (f'. /opt/ros/jazzy/setup.sh; cd /world; gz sdf -k {world} >/dev/null 2>&1; echo SPEC_EXIT=$?; '
               f'gz sim -s -r --iterations 200 -v 3 {world} 2>&1 ' r'| sed "s/\x1b\[[0-9;]*m//g" | grep -cE "^\[(Err|Wrn)"')
        out = sh("docker", "run", "--rm", "-v", f"{mount}:/world:ro", "gzcheck:jazzy", "bash", "-lc", cmd).stdout
        return int(re.search(r"SPEC_EXIT=(\d+)", out).group(1)), int([l for l in out.splitlines() if l.strip().isdigit()][-1])
    spec, noise = probe("world.sdf", NEW)
    assert spec == 0 and noise == 0, (spec, noise)
    b = os.path.join(ST, "gz_broken"); shutil.rmtree(b, ignore_errors=True); shutil.copytree(NEW, b)
    open(os.path.join(b, "bad.sdf"), "w").write(open(os.path.join(NEW, "world.sdf")).read().replace("</sdf>", ""))
    bs, bn = probe("bad.sdf", b)
    assert bs != 0 and bn > 0, f"깨진 world 통과 — 검사 무효 ({bs},{bn})"
    print(f"G5_OK spec=valid err_wrn=0 neg=({bs},{bn})")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def g6():
    """재현성 — make_design_610.py → design_final.json 동일, track_gen 재실행 → output_final 동일(PDF·DXF는 타임스탬프 제외)."""
    import ezdxf
    t = os.path.join(ST, "regen"); shutil.rmtree(t, ignore_errors=True); os.makedirs(t)
    r = sh(PY, "make_design_610.py", os.path.join(t, "design.json"), cwd=GEN); assert r.returncode == 0, r.stderr
    assert sha(os.path.join(t, "design.json")) == sha(os.path.join(GEN, "design_final.json")), "design_final.json 불일치"
    r = sh(PY, "track_gen.py", "--design", "design_final.json", "--outdir", os.path.join(t, "o"), cwd=GEN)
    assert r.returncode == 0, r.stderr[-500:]
    files = sorted(os.path.relpath(os.path.join(dp, f), NEW) for dp, _, fs in os.walk(NEW) for f in fs)
    vol = {"venue_layout.dxf", "aruco_print_sheet.pdf"}
    bad = [f for f in files if f not in vol and sha(os.path.join(NEW, f)) != sha(os.path.join(t, "o", f))]
    assert not bad, bad
    strip = lambda d: re.sub(rb"/(CreationDate|ModDate) \(D:[^)]*\)", b"", d)
    assert strip(open(os.path.join(NEW, "aruco_print_sheet.pdf"), "rb").read()) == strip(open(os.path.join(t, "o", "aruco_print_sheet.pdf"), "rb").read())
    e = lambda p: sorted(f"{x.dxftype()}|{x.dxf.layer}" for x in ezdxf.readfile(p).modelspace())
    assert e(os.path.join(NEW, "venue_layout.dxf")) == e(os.path.join(t, "o", "venue_layout.dxf"))
    print(f"G6_OK files={len(files)} deterministic")


def g7():
    """신호등 스크립트 selftest 통과, ArUco PNG 4장이 DICT_4X4_50의 0·20·30·45로 해독."""
    import cv2
    r = sh(PY, os.path.join(NEW, "traffic_light.py"), "--selftest")
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]
    det = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), cv2.aruco.DetectorParameters())
    got = {}
    for f in sorted(os.listdir(os.path.join(NEW, "aruco"))):
        ids = det.detectMarkers(cv2.imread(os.path.join(NEW, "aruco", f), 0))[1]
        got[f] = None if ids is None else ids.ravel().tolist()
    assert sorted(v[0] for v in got.values() if v) == [0, 20, 30, 45] and all(f"id{v[0]}" in f for f, v in got.items()), got
    print("G7_OK selftest aruco=", sorted(v[0] for v in got.values()))


def g8():
    """문서 숫자 == scene.json (랩·폭·지름길 s·마커 s·신호등 s), '다시 바뀔 수' 문구 없음, 공개 repo에 주소·번호 없음."""
    sc = json.load(open(os.path.join(NEW, "scene.json")))
    tr = open(os.path.join(GEN, "README.md")).read()
    lap = sc["track"]["lap_length_m"] if "lap_length_m" in sc["track"] else sc["track"]["length_m"]
    want = [lap, 0.61] + [b["s0_m"] for b in sc["branches"]]
    want += [m["s_m"] for m in sc["aruco_markers"]["markers"] if m["id"] in (20, 30)] + [sc["traffic_light"]["s_m"]]
    nums = np.array([float(v) for v in re.findall(r"\d+\.\d+", tr)])
    miss = [w for w in want if not (np.abs(nums - w) < 0.0051).any()]
    assert not miss, f"track/README에 없는 값: {miss}"
    for f in ("README.md", "MANUAL.md", "track/README.md"):
        assert "다시 바뀔 수" not in open(os.path.join(REPO, f)).read(), f
    pii = r"010-[0-9]{3,4}-[0-9]{4}|지혜관|대학로 291" + os.environ.get("PII_EXTRA", "")   # 비공개 키워드는 로컬 환경변수로 (예: "|이름|회사")
    added = "\n".join(l for l in sh("git", "diff", "origin/main", "--", ".", cwd=REPO).stdout.splitlines()
                       if l.startswith("+") and not l.startswith("+++"))
    assert added, "diff 비어 있음 — 검사 대상 없음"
    leak = re.findall(pii, added)
    assert not leak, leak
    pdf = sh("pdftotext", os.path.join(GEN, "track_610mm_build_2026-11-05.pdf"), "-").stdout
    assert len(pdf) > 10000 and not re.findall(pii + r"|@[a-z0-9.-]+\.(com|kr)", pdf), "PDF에 연락처/후원 정보"
    assert re.findall(pii, "연락 010-1234-5678"), "PII 정규식이 양성 샘플을 못 잡음"
    print(f"G8_OK values={len(want)} no_pii")


def g10():
    """그리드 맨 앞칸(양 열) 카메라가 신호등 마커 0·45를 검출. 음성 대조: 11-01 간격(앞선에서 0.30 m) 자리에서는 검출 안 됨."""
    import cv2
    scene = json.load(open(os.path.join(NEW, "scene.json")))
    tl = scene["traffic_light"]
    slots = scene["starting_grid"]["slots"]
    front = [g for g in slots if g["row"] == max(s["row"] for s in slots)]
    lead_edge = max(g["s_m"] for g in slots) + 0.125
    gap = tl["s_m"] - lead_edge
    assert 0.5 <= gap, f"신호등-그리드 간격 {gap:.3f} < 0.5 m"
    cd = os.path.join(ST, "cam_g10"); shutil.rmtree(cd, ignore_errors=True); os.makedirs(cd)
    shutil.copytree(os.path.join(NEW, "aruco"), os.path.join(cd, "aruco")); shutil.copy(os.path.join(ST, "grab.py"), cd)
    jobs = [(f"slot{g['index']}", g["x"], g["y"], g["yaw_rad"], True) for g in front]
    jobs += [(f"old{g['index']}", g["x"], tl["pose"]["y"] - 0.30 - 0.125, g["yaw_rad"], False) for g in front]
    for n, x, y, a, _ in jobs:
        sh(PY, os.path.join(ST, "make_cam.py"), NEW, os.path.join(cd, n + ".sdf"), str(x), str(y), str(a), "/w/x")
    open(os.path.join(cd, "jobs.txt"), "w").write("\n".join(j[0] for j in jobs) + "\n")
    sh("docker", "run", "--rm", "-v", f"{cd}:/w", "gzcheck:jazzy", "bash", "-c",
       "source /opt/ros/jazzy/setup.bash; while read n; do timeout -s KILL 200 gz sim -s -r --headless-rendering /w/$n.sdf >/w/$n.log 2>&1 & "
       "timeout -s KILL 200 python3 /w/grab.py /w/$n.npy; pkill -9 -f 'gz sim'; pkill -9 -f ruby; sleep 2; wait 2>/dev/null; done < /w/jobs.txt")
    p = cv2.aruco.DetectorParameters(); p.minMarkerDistanceRate = 0.02
    det = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), p)
    res = {}
    for n, *_ in jobs:
        f = os.path.join(cd, n + ".npy")
        assert os.path.exists(f), f"frame missing {n}"
        ids = det.detectMarkers(cv2.cvtColor(np.load(f), cv2.COLOR_RGB2GRAY))[1]
        res[n] = set() if ids is None else set(ids.ravel().tolist())
    for n, *_, want in jobs:
        if want:
            assert {0, 45} <= res[n], f"{n}: 0·45 미검출 {res[n]}"
        else:
            assert not ({0, 45} & res[n]), f"음성 대조 {n}가 검출됨 — 검사가 못 떨어짐 {res[n]}"
    print(f"G10_OK gap={gap:.3f}", {k: sorted(v) for k, v in res.items()})


GATES = {f"g{i}": globals()[f"g{i}"] for i in (*range(1, 9), 10)}
if __name__ == "__main__":
    w = sys.argv[1] if len(sys.argv) > 1 else "all"
    for k in (list(GATES) if w == "all" else [w]):
        GATES[k]()
