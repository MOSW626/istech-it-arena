#!/usr/bin/env python3
"""독립 게이트 검증 — v2026.10.24 (시뮬 색을 실물 자재에 맞춤).

변경: 도로 0.12(거의 검정) → 0.90(백색 포맥스), 벽 0.85 → 0.50(회색 포맥스),
홀 바닥 0.55 회색 → 목재 톤. 기하는 한 군데도 바뀌면 안 된다.

track_gen.py의 자기 보고를 신뢰하지 않고 산출물을 직접 파싱한다.
양성 대조: 직전 릴리즈(v2026.10.10)가 같은 색 검사에서 실패해야 검사가 유효하다.

  usage: python3 check4.py <gate>      gate = g1..g7 | all
"""
import hashlib, os, re, subprocess, sys, shutil, xml.etree.ElementTree as ET

SP   = "/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad"
OLD  = os.path.join(SP, "rel1010", "x", "output_final")   # 양성 대조 (v2026.10.10)
GEN  = "/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/istech-it-arena/track"
REPO_OUT  = os.path.join(GEN, "output_final")             # 설치된 릴리즈 후보
GZ_BROKEN = "/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/.gzbroken"

ROAD  = "0.9 0.9 0.9 1"
WALL  = "0.5 0.5 0.5 1"
FLOOR = "0.55 0.4 0.26 1"
GRASS = "0.13 0.55 0.13 1"

COLOR_RE = re.compile(r"<(ambient|diffuse)>[^<]*</(ambient|diffuse)>")


def norm(rgba):
    return " ".join(f"{float(v):g}" for v in rgba.split())


def link_colors(path):
    """{link_name: set of normalized diffuse values over its visuals}"""
    out = {}
    for link in ET.parse(path).getroot().iter("link"):
        vals = {norm(d.text) for d in link.iter("diffuse")}
        out[link.get("name")] = vals
    return out


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def files(root):
    return sorted(os.path.relpath(os.path.join(r, f), root)
                  for r, _, fs in os.walk(root) for f in fs)


def check_colors(path):
    c = link_colors(path)
    got = {k: c[k] for k in ("track_surface", "walls", "ground_plane_link", "grass")}
    want = {"track_surface": {ROAD}, "walls": {WALL}, "ground_plane_link": {FLOOR}, "grass": {GRASS}}
    return got, got == want

# ---------- gates ----------

def g1():
    """색 — 도로 전 박스 백색, 벽 전 박스 회색, 홀 바닥 목재, 잔디 불변."""
    got, ok = check_colors(os.path.join(REPO_OUT, "world.sdf"))
    assert ok, f"색 불일치: {got}"
    txt = open(os.path.join(REPO_OUT, "world.sdf")).read()
    n_road = txt.count(f"<diffuse>0.90 0.90 0.90 1</diffuse>")
    n_wall = txt.count(f"<diffuse>0.50 0.50 0.50 1</diffuse>")
    assert n_road > 600 and n_wall > 600, (n_road, n_wall)
    print(f"G1_OK road_boxes={n_road} wall_boxes={n_wall} floor=wood grass=unchanged")


def g2():
    """기하 무변경 — 색 태그를 지운 world.sdf가 v2026.10.10과 한 글자도 다르지 않다."""
    a = COLOR_RE.sub("", open(os.path.join(OLD, "world.sdf")).read())
    b = COLOR_RE.sub("", open(os.path.join(REPO_OUT, "world.sdf")).read())
    assert a == b, "색 외의 내용이 바뀜"
    # 색 외 링크의 색(신호등·방지턱·그리드·마커)도 그대로인지
    co, cn = link_colors(os.path.join(OLD, "world.sdf")), link_colors(os.path.join(REPO_OUT, "world.sdf"))
    changed = sorted(k for k in co if co[k] != cn[k])
    assert changed == ["ground_plane_link", "track_surface", "walls"], changed
    print(f"G2_OK geometry_identical changed_links={changed}")


def g3():
    """부수 변경 없음 — 릴리즈 트리가 v2026.10.10과 world.sdf 하나만 다르다."""
    fo, fn = files(OLD), files(REPO_OUT)
    assert fo == fn, f"파일 목록 다름: {set(fo) ^ set(fn)}"
    diff = [f for f in fn if sha(os.path.join(OLD, f)) != sha(os.path.join(REPO_OUT, f))]
    assert diff == ["world.sdf"], diff
    print(f"G3_OK files={len(fn)} changed={diff}")


def g4():
    """양성 대조 — 구버전은 G1 색 검사에서 실패해야 한다."""
    got, ok = check_colors(os.path.join(OLD, "world.sdf"))
    assert not ok, "구버전이 색 검사를 통과함 — 검사 무효"
    assert got["track_surface"] == {"0.12 0.12 0.13 1"} and got["walls"] == {"0.85 0.85 0.85 1"}, got
    print(f"G4_OK old_road={got['track_surface']} old_wall={got['walls']} -> rejected")


def g5():
    """재생성 재현성 — 생성기 재실행 결과가 설치본과 같다 (dxf/pdf 타임스탬프 제외)."""
    rerun = os.path.join(SP, "rerun_out")
    shutil.rmtree(rerun, ignore_errors=True)
    r = subprocess.run([os.path.join(SP, "v/bin/python"), "track_gen.py",
                        "--design", "design_final.json", "--outdir", rerun],
                       cwd=GEN, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    volatile = {"venue_layout.dxf", "aruco_print_sheet.pdf"}
    diff = [f for f in files(REPO_OUT) if f not in volatile
            and sha(os.path.join(REPO_OUT, f)) != sha(os.path.join(rerun, f))]
    assert not diff, f"재생성 불일치: {diff}"
    import ezdxf
    def ents(p):
        return sorted(f"{e.dxftype()}|{e.dxf.layer}|{getattr(e.dxf,'handle','')}"
                      for e in ezdxf.readfile(p).modelspace())
    eo, en = ents(os.path.join(REPO_OUT, "venue_layout.dxf")), ents(os.path.join(rerun, "venue_layout.dxf"))
    assert eo == en, "DXF 엔티티 다름"
    print(f"G5_OK deterministic dxf_entities={len(en)} volatile={sorted(volatile)}")


def g6():
    """SDF 위생 — XML 정상, script 태그 0, ArUco 텍스처 4개 실재."""
    p = os.path.join(REPO_OUT, "world.sdf")
    ET.parse(p)
    txt = open(p).read()
    assert "<script>" not in txt
    imgs = set(re.findall(r"<albedo_map>([^<]+)</albedo_map>", txt))
    assert len(imgs) == 4 and all(os.path.exists(os.path.join(REPO_OUT, i)) for i in imgs), imgs
    print(f"G6_OK xml_ok script=0 textures={len(imgs)}")


def g7():
    """Gazebo 실기동 — gz sdf -k Valid, gz sim 헤드리스 [Err]/[Wrn] 0, 음성 대조 포함.
    gz sim은 파싱 실패에도 exit 0을 낸다 -> 종료 코드로 판정하지 않는다."""
    def run(sh, mount):
        return subprocess.run(["docker", "run", "--rm", "-v", f"{mount}:/world:ro",
                               "gzcheck:jazzy", "bash", "-lc", sh], capture_output=True, text=True)

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
    assert spec == 0 and noise == 0, (spec, noise)
    shutil.rmtree(GZ_BROKEN, ignore_errors=True)
    shutil.copytree(REPO_OUT, GZ_BROKEN)
    open(os.path.join(GZ_BROKEN, "world_badxml.sdf"), "w").write(
        open(os.path.join(REPO_OUT, "world.sdf")).read().replace("</sdf>", ""))
    bspec, bnoise = probe("world_badxml.sdf", GZ_BROKEN)
    assert bspec != 0 and bnoise > 0, f"깨진 world 통과 — 검사 무효 ({bspec},{bnoise})"
    print(f"G7_OK spec=valid err_wrn=0 neg_control(spec_exit={bspec}, err_wrn={bnoise})")


def g8():
    """문서 정합 — README·MANUAL이 실물 색을 적고, 옛 시뮬 색(검정 도로) 서술이 남지 않았다."""
    repo = os.path.dirname(GEN)
    rd = open(os.path.join(GEN, "README.md")).read()
    mn = open(os.path.join(repo, "MANUAL.md")).read()
    for doc, name in ((rd, "track/README.md"), (mn, "MANUAL.md")):
        assert "백색 포맥스" in doc and "회색 포맥스" in doc, f"{name}에 실물 색 표기 없음"
    assert "0.90 0.90 0.90" in rd and "0.50 0.50 0.50" in rd, "README에 시뮬 RGBA 없음"
    assert "v2026.10.24" in rd, "README 변경 이력 없음"
    print("G8_OK docs=README,MANUAL colors_listed rgba_listed changelog")


def g9():
    """릴리즈 zip == 커밋 트리 — 내려받은 v2026.10.24 zip이 HEAD의 track/과 바이트 동일."""
    repo = os.path.dirname(GEN)
    d = os.path.join(SP, "rel1024")
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    subprocess.run(["gh", "release", "download", "v2026.10.24", "-D", d], cwd=repo, check=True)
    subprocess.run(["unzip", "-q", "it_arena_track_v2026.10.24.zip", "-d", "x"], cwd=d, check=True)
    tree = subprocess.run(["git", "ls-files", "track"], cwd=repo, capture_output=True,
                          text=True, check=True).stdout.split()
    dirty = subprocess.run(["git", "status", "--porcelain", "track"], cwd=repo,
                           capture_output=True, text=True).stdout.strip()
    assert not dirty, f"track/에 커밋 안 된 변경: {dirty}"
    zf = files(os.path.join(d, "x"))
    tf = sorted(os.path.relpath(t, "track") for t in tree)
    assert zf == tf, f"파일 목록 다름: {set(zf) ^ set(tf)}"
    bad = [f for f in zf if sha(os.path.join(d, "x", f)) != sha(os.path.join(GEN, f))]
    assert not bad, bad
    print(f"G9_OK zip==HEAD files={len(zf)}")


GATES = dict(g1=g1, g2=g2, g3=g3, g4=g4, g5=g5, g6=g6, g7=g7, g8=g8, g9=g9)

if __name__ == "__main__":
    which = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    for k in (sorted(GATES) if which == "all" else [which]):
        GATES[k]()
