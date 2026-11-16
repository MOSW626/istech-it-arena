#!/usr/bin/env python3
"""독립 게이트 검증 — v2026.11.01 (3차 회의 반영).

변경: ① 과속방지턱 제거 ② 그리드 칸 검정(테이프) ③ 신호등을 실물 위치·형상으로
(선두 그리드 앞 0.30 m, 발광부 중심 0.419 m, 바닥 대비 60°, 도로를 가로질러 R R R R G)
④ ArUco 0·45를 신호등 좌우로 이동. 트랙 기하·지도·CSV는 한 바이트도 바뀌면 안 된다.

track_gen.py의 자기 보고를 믿지 않고 산출물을 직접 파싱한다.
양성 대조: 직전 릴리즈(v2026.10.24)가 같은 검사에서 실패해야 검사가 유효하다.

  usage: python3 check5.py <gate>      gate = g1..g10 | all
"""
import hashlib, json, math, os, re, shutil, subprocess, sys, xml.etree.ElementTree as ET

SP   = "/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad"
OLD  = os.path.join(SP, "rel1024", "x", "output_final")    # 양성 대조 (v2026.10.24)
GEN  = "/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/istech-it-arena/track"
REPO = os.path.dirname(GEN)
NEW  = os.path.join(GEN, "output_final")
GZ_BROKEN = "/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/.gzbroken"
PY   = os.path.join(SP, "v/bin/python")

CHANGED = {"world.sdf", "scene.json", "preview.png", "venue_layout.dxf", "aruco_print_sheet.pdf"}
TOUCHED_LINK = re.compile(r"^(bump_\d+|grid_slot_\d+|tl_.*|lamp_.*|aruco_0|aruco_45)$")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def files(root):
    return sorted(os.path.relpath(os.path.join(r, f), root) for r, _, fs in os.walk(root) for f in fs)


def links(out):
    return {l.get("name"): l for l in ET.parse(os.path.join(out, "world.sdf")).getroot().iter("link")}


def pose(link):
    p = link.find("pose")
    if p is None:
        p = link.find(".//pose")
    return [float(v) for v in p.text.split()]


def scene(out):
    return json.load(open(os.path.join(out, "scene.json")))


def light_frame(out):
    """도로 방향(fwd)과 운전자 왼쪽(left)을 신호등 위치의 centerline에서 직접 구한다."""
    import csv
    sc = scene(out)
    rows = [tuple(map(float, r[:3])) for r in list(csv.reader(open(os.path.join(out, "centerline.csv"))))[1:]]
    s_tl = sc["traffic_light"]["s_m"]
    i = min(range(len(rows) - 1), key=lambda k: abs(rows[k][2] - s_tl))
    dx, dy = rows[i + 1][0] - rows[i][0], rows[i + 1][1] - rows[i][1]
    n = math.hypot(dx, dy)
    return sc, (dx / n, dy / n), (-dy / n, dx / n)


# ---------- checks shared by gate and positive control ----------

def bump_gone(out):
    L = links(out)
    assert not [n for n in L if n.startswith("bump")], "bump 링크가 남음"
    assert scene(out)["speed_bumps"]["count"] == 0, "scene.json 방지턱 수 != 0"
    import ezdxf
    txt = [e.dxf.text for e in ezdxf.readfile(os.path.join(out, "venue_layout.dxf")).modelspace()
           if e.dxftype() == "TEXT"]
    assert "BUMP" not in txt, "DXF에 BUMP 표기가 남음"
    return len(L)


def grid_black(out):
    L = links(out)
    g = [n for n in L if n.startswith("grid_slot_")]
    cols = {L[n].find(".//diffuse").text.strip() for n in g}
    assert len(g) == 6 and cols == {"0.05 0.05 0.05 1"}, (len(g), cols)
    return len(g)


def light_ok(out):
    sc, fwd, left = light_frame(out)
    tl = sc["traffic_light"]
    lead = max(g["s_m"] for g in sc["starting_grid"]["slots"])
    want_s = lead + sc["starting_grid"]["slot_length_m"] / 2 + 0.30
    assert abs(tl["s_m"] - want_s) < 0.002, f"신호등 s {tl['s_m']} != 선두칸 앞선+0.30 {want_s:.3f}"
    L = links(out)
    lamps = sorted((n for n in L if n.startswith("lamp_")))
    assert len(lamps) == 10, f"광원 {len(lamps)}개 (실물 2x5=10)"
    P = {n: pose(L[n])[:3] for n in lamps}
    cz = sum(p[2] for p in P.values()) / 10
    assert abs(cz - 0.419) < 0.002, f"발광부 중심 높이 {cz:.4f}"
    tx, ty = tl["pose"]["x"], tl["pose"]["y"]
    lat = {n: (p[0] - tx) * left[0] + (p[1] - ty) * left[1] for n, p in P.items()}
    along = [(p[0] - tx) * fwd[0] + (p[1] - ty) * fwd[1] for p in P.values()]
    # 운전자 기준 왼쪽 -> 오른쪽 = lat 큰 쪽 -> 작은 쪽
    order = [n.rsplit("_", 1)[0] for n in sorted(lamps, key=lambda n: -lat[n])][::2]
    assert order == ["lamp_red_1", "lamp_red_2", "lamp_red_3", "lamp_red_4", "lamp_green"], order
    span = max(lat.values()) - min(lat.values())
    assert span > 0.10 and max(along) - min(along) < 0.02, f"도로를 가로지르지 않음 span={span:.3f}"
    for n in lamps:
        rgba = L[n].find(".//diffuse").text.split()
        assert (rgba[:3] == ["0", "1", "0"]) == ("green" in n), (n, rgba)
    # 패널: 바닥 대비 60°, 하단 약 0.397
    px, py, pz, _, pitch, yaw = pose(L["tl_panel"])
    t, w, h = map(float, L["tl_panel"].find(".//size").text.split())
    tilt = 90 - math.degrees(pitch)
    assert abs(tilt - 60) < 0.5, f"기울기 {tilt}"
    nx, ny = math.cos(yaw), math.sin(yaw)
    assert nx * fwd[0] + ny * fwd[1] < -0.99, "패널이 접근 차량을 보지 않음"
    bottom = pz - h / 2 * math.cos(pitch) - t / 2 * math.sin(pitch)
    assert abs(bottom - 0.397) < 0.004, f"모듈 하단 {bottom:.4f}"
    return tl["s_m"], cz, tilt, bottom


def markers_ok(out, old_out):
    sc, fwd, left = light_frame(out)
    tl = sc["traffic_light"]
    M = {m["id"]: m for m in sc["aruco_markers"]["markers"]}
    assert sorted(M) == [0, 20, 30, 45], sorted(M)
    lat = {}
    for mid in (0, 45):
        m = M[mid]
        assert abs(m["s_m"] - tl["s_m"]) < 1e-3, f"ID{mid} s {m['s_m']} != 신호등 {tl['s_m']}"
        p = m["pose"]
        lat[mid] = (p["x"] - tl["pose"]["x"]) * left[0] + (p["y"] - tl["pose"]["y"]) * left[1]
        assert math.cos(p["yaw_rad"]) * fwd[0] + math.sin(p["yaw_rad"]) * fwd[1] < -0.99, f"ID{mid} 방향"
        assert abs(p["z"] + 0.05 - 0.40) < 1e-6, f"ID{mid} 중심 높이"
    assert lat[0] < 0 < lat[45], f"좌우 배치 {lat}"           # 0 = 운전자 오른쪽, 45 = 왼쪽
    for mid in (0, 45):
        assert 0.085 + 0.05 <= abs(lat[mid]) and abs(lat[mid]) + 0.05 <= 0.225, f"ID{mid} lat {lat[mid]}"
    O = {m["id"]: m for m in scene(old_out)["aruco_markers"]["markers"]}
    for mid in (20, 30):
        assert M[mid] == O[mid], f"ID{mid}가 바뀜"
    return lat


# ---------- gates ----------

def g1():
    """방지턱 제거 — world·scene·DXF 어디에도 없다."""
    n = bump_gone(NEW)
    d = json.load(open(os.path.join(GEN, "design_final.json")))["features"]
    assert d["bump_zones"] == [], d["bump_zones"]
    print(f"G1_OK bump=0 links={n} design_bump_zones=[]")


def g2():
    """그리드 칸 6개 전부 검정."""
    print(f"G2_OK grid_slots={grid_black(NEW)} color=0.05")


def g3():
    """신호등 — 선두 그리드 앞 0.30 m, 중심 0.419, 60°, 하단 ~0.397, 운전자 기준 R R R R G가 도로를 가로지름."""
    s, cz, tilt, bottom = light_ok(NEW)
    print(f"G3_OK s={s:.3f} lamp_center_z={cz:.4f} tilt={tilt:.1f} bottom={bottom:.4f} order=RRRRG")


def g4():
    """ArUco 0·45 — 신호등과 같은 s, 0은 오른쪽·45는 왼쪽, 패널과 겹치지 않고 도로 안, 20·30 불변."""
    lat = markers_ok(NEW, OLD)
    print(f"G4_OK id0_lat={lat[0]:+.3f} id45_lat={lat[45]:+.3f} ids20_30_unchanged")


def g5():
    """부수 변경 없음 — 5개 파일 외 바이트 동일, world.sdf는 손댄 링크 외 동일, DXF는 FEATURES 외 동일."""
    fo, fn = files(OLD), files(NEW)
    assert fo == fn, set(fo) ^ set(fn)
    diff = sorted(f for f in fn if sha(os.path.join(OLD, f)) != sha(os.path.join(NEW, f)))
    assert set(diff) <= CHANGED, diff
    lo, ln = links(OLD), links(NEW)
    keep_o = {k: ET.tostring(v) for k, v in lo.items() if not TOUCHED_LINK.match(k)}
    keep_n = {k: ET.tostring(v) for k, v in ln.items() if not TOUCHED_LINK.match(k)}
    assert keep_o == keep_n, sorted(set(keep_o) ^ set(keep_n)) or "링크 내용 변경"
    so, sn = scene(OLD), scene(NEW)
    changed_keys = sorted(k for k in so if so[k] != sn[k])
    assert set(changed_keys) <= {"start_finish", "speed_bumps", "traffic_light", "aruco_markers"}, changed_keys
    assert {k: v for k, v in so["start_finish"].items() if k != "note"} == \
           {k: v for k, v in sn["start_finish"].items() if k != "note"}, "출발선 위치가 바뀜"
    import ezdxf
    def ents(p, skip):
        return sorted((e.dxftype(), e.dxf.layer, str(e.dxfattribs().get("text", "")),
                       str([tuple(round(c, 6) for c in pt) for pt in e.get_points()] if e.dxftype() == "LWPOLYLINE" else ""))
                      for e in ezdxf.readfile(p).modelspace() if e.dxf.layer not in skip)
    assert ents(os.path.join(OLD, "venue_layout.dxf"), {"FEATURES"}) == \
           ents(os.path.join(NEW, "venue_layout.dxf"), {"FEATURES"}), "FEATURES 외 DXF 변경"
    print(f"G5_OK changed={diff} untouched_links={len(keep_n)} scene_keys={changed_keys}")


def g6():
    """양성 대조 — v2026.10.24는 G1~G4 검사에서 각각 실패해야 한다."""
    fails = []
    for name, fn in (("bump", lambda: bump_gone(OLD)), ("grid", lambda: grid_black(OLD)),
                     ("light", lambda: light_ok(OLD)), ("markers", lambda: markers_ok(OLD, OLD))):
        try:
            fn()
        except (AssertionError, KeyError):
            fails.append(name)
    assert fails == ["bump", "grid", "light", "markers"], f"구버전이 통과한 검사 있음: {fails}"
    print(f"G6_OK old_rejected={fails}")


def g7():
    """재생성 재현성 — 생성기 재실행 결과가 설치본과 같다 (dxf 엔티티 비교, pdf 타임스탬프 제외)."""
    rerun = os.path.join(SP, "rerun1101")
    shutil.rmtree(rerun, ignore_errors=True)
    r = subprocess.run([PY, "track_gen.py", "--design", "design_final.json", "--outdir", rerun],
                       cwd=GEN, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    vol = {"venue_layout.dxf", "aruco_print_sheet.pdf"}
    bad = [f for f in files(NEW) if f not in vol and sha(os.path.join(NEW, f)) != sha(os.path.join(rerun, f))]
    assert not bad, bad
    strip = lambda d: re.sub(rb"/(CreationDate|ModDate) \(D:[^)]*\)", b"", d)
    assert strip(open(os.path.join(NEW, "aruco_print_sheet.pdf"), "rb").read()) == \
           strip(open(os.path.join(rerun, "aruco_print_sheet.pdf"), "rb").read()), "PDF 내용 다름"
    import ezdxf
    e = lambda p: sorted(f"{x.dxftype()}|{x.dxf.layer}" for x in ezdxf.readfile(p).modelspace())
    assert e(os.path.join(NEW, "venue_layout.dxf")) == e(os.path.join(rerun, "venue_layout.dxf"))
    print("G7_OK deterministic")


def g8():
    """Gazebo 실기동 — gz sdf -k Valid, gz sim Err/Wrn 0, 깨진 world 음성 대조가 걸림.
    gz sim은 파싱 실패에도 exit 0 -> 종료 코드로 판정하지 않는다."""
    def probe(world, mount):
        sh = (f'. /opt/ros/jazzy/setup.sh; cd /world; '
              f'gz sdf -k {world} >/dev/null 2>&1; echo SPEC_EXIT=$?; '
              f'gz sim -s -r --iterations 200 -v 3 {world} 2>&1 '
              r'| sed "s/\x1b\[[0-9;]*m//g" | grep -cE "^\[(Err|Wrn)"')
        out = subprocess.run(["docker", "run", "--rm", "-v", f"{mount}:/world:ro", "gzcheck:jazzy",
                              "bash", "-lc", sh], capture_output=True, text=True).stdout
        return (int(re.search(r"SPEC_EXIT=(\d+)", out).group(1)),
                int([l for l in out.splitlines() if l.strip().isdigit()][-1]))
    spec, noise = probe("world.sdf", NEW)
    assert spec == 0 and noise == 0, (spec, noise)
    shutil.rmtree(GZ_BROKEN, ignore_errors=True)
    shutil.copytree(NEW, GZ_BROKEN)
    open(os.path.join(GZ_BROKEN, "bad.sdf"), "w").write(
        open(os.path.join(NEW, "world.sdf")).read().replace("</sdf>", ""))
    bspec, bnoise = probe("bad.sdf", GZ_BROKEN)
    assert bspec != 0 and bnoise > 0, f"깨진 world 통과 — 검사 무효 ({bspec},{bnoise})"
    print(f"G8_OK spec=valid err_wrn=0 neg_control=({bspec},{bnoise})")


def g9():
    """문서 — 회의 결정 5건·일정이 MANUAL에, 변경 이력이 README에. 공개 repo에 반납 주소·전화번호 없음."""
    mn = open(os.path.join(REPO, "MANUAL.md")).read()
    rd = open(os.path.join(GEN, "README.md")).read()
    for kw in ("15 × 20 cm 사각틀", "과속방지턱", "검정 테이프", "세이브 포인트", "ArUco 0", "교차 검차", "11:00"):
        assert kw in mn, f"MANUAL에 '{kw}' 없음"
    assert "v2026.11.01" in rd, "README 변경 이력 없음"
    pii = r"010-[0-9]{3,4}-[0-9]{4}|지혜관|대학로 291"
    leak = subprocess.run(["git", "grep", "--untracked", "-nE", pii, "--", "*.md", "*.py", "*.json", "*.html", "*.txt"],
                          cwd=REPO, capture_output=True, text=True).stdout
    assert not leak.strip(), f"민감정보 노출: {leak[:300]}"
    # 양성 대조: 같은 검색이 비공개 회의록(repo 밖)의 주소·번호는 잡아야 한다
    priv = os.path.join(os.path.dirname(REPO), "2026-11-01 3차 회의록.md")
    assert len(re.findall(pii, open(priv).read())) >= 2, "PII 검사가 실제 주소·번호를 못 잡음"
    print("G9_OK manual_rules=7 changelog no_pii")


def g10():
    """릴리즈 zip == 커밋 트리."""
    d = os.path.join(SP, "rel1101")
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    subprocess.run(["gh", "release", "download", "v2026.11.01", "-D", d, "-p", "*.zip"], cwd=REPO, check=True)
    subprocess.run(["unzip", "-q", "it_arena_track_v2026.11.01.zip", "-d", "x"], cwd=d, check=True)
    dirty = subprocess.run(["git", "status", "--porcelain", "track"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    assert not dirty, dirty
    tree = subprocess.run(["git", "ls-files", "track"], cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    zf, tf = files(os.path.join(d, "x")), sorted(os.path.relpath(t, "track") for t in tree)
    assert zf == tf, set(zf) ^ set(tf)
    bad = [f for f in zf if sha(os.path.join(d, "x", f)) != sha(os.path.join(GEN, f))]
    assert not bad, bad
    print(f"G10_OK zip==HEAD files={len(zf)}")


GATES = {f"g{i}": globals()[f"g{i}"] for i in range(1, 11)}

if __name__ == "__main__":
    which = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    for k in (sorted(GATES, key=lambda s: int(s[1:])) if which == "all" else [which]):
        GATES[k]()
