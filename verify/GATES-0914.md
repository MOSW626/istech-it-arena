# GATES — v2026.09.14 검증 (ArUco 갠트리 설치 + 벽 0.40 m)

**베이스라인:** v2026.09.02 (`gh release download v2026.09.02`)
**검사기:** `verify/check3.py` — 산출물을 직접 파싱. `track_gen.py`의 자기 보고는 근거로 쓰지 않음.
**변경 내용:** 2026-09-14 회의 R2-4 결정 반영 — 벽 높이 0.30 → 0.40 m, ArUco를 벽면 부착에서
도로 중앙 갠트리식(중심 높이 0.40 m, 접근 차량 정면 지향)으로 변경. 마커 크기는 10×10 cm 유지.

실행: `<venv>/bin/python3 check3.py <g1..g8|all>` (cwd = `verify/`)

---

- [x] **G1: 벽 높이 0.40 m** — world.sdf의 모든 벽 박스가 높이 0.40이고 pose z = 0.20 (바닥 밀착)
      EXPECT `G1_OK` → `G1_OK walls=1388 height=0.4 pose_z=0.2` (rc=0)

- [x] **G2: ArUco 기하** — 4개 전부 센터라인 위(≤1 cm), 중심 높이 0.40 m(±1 mm), 10×10 cm,
      진행 방향 반대(±2°)로 지향
      EXPECT `G2_OK` → `G2_OK markers=4 max_center_offset=6.79mm max_facing_err=0.12deg size=0.1` (rc=0)
      *주: 6.79 mm는 centerline.csv의 2 cm 샘플 간격에서 오는 이산화 오차(최대 1 cm)이며 실제 이탈이 아님.*

- [x] **G3: 주행 간섭** — 마커 하단 높이·좌우 통과폭이 차량 규격(폭 0.15 m)을 허용
      EXPECT `G3_OK` → `G3_OK bottom=0.35m side_gap=0.175m car_margin=2.5cm/side` (rc=0)

- [x] **G4: 의도치 않은 부수 변경 없음** — 2D 산출물 14종(센터라인·경계·갈림길·점유격자 2종·
      traffic_light.py·ArUco PNG 4종)이 v2026.09.02와 **바이트 동일**, 높이 관련 2종만 변경
      EXPECT `G4_OK` → `G4_OK unchanged=14 changed=['world.sdf', 'scene.json']` (rc=0)

- [x] **G5: 양성 대조** — 구버전 v2026.09.02가 같은 검사에서 실패함을 확인 (검사가 실제로 무언가를 잡는가)
      EXPECT `G5_OK` → `G5_OK old_wall_h=0.30 old_marker_min_offset=0.425m old_marker_z=[0.1]` (rc=0)
      → 구버전은 벽 0.30 m, 마커가 도로 중앙에서 0.425 m 벗어나 있고 하단 0.10 m. G1·G2 기준 미달.

- [x] **G6: 재생성 재현성** — 동일 입력 재실행 시 타임스탬프를 품는 3종(dxf/pdf/preview.png) 외 바이트 동일
      EXPECT `G6_OK` → `G6_OK deterministic (volatile-excluded), volatile=['aruco_print_sheet.pdf', 'preview.png', 'venue_layout.dxf']` (rc=0)
      *dxf/pdf 차이는 율리우스 날짜·UUID·생성 시각 12줄뿐이며 기하 변화 없음(사전 확인). preview.png는 픽셀 동일.*

- [x] **G7: SDF 위생** — XML well-formed, `<script>` 태그 0(이슈 #7 회귀 방지), albedo_map 4개 경로 실재
      EXPECT `G7_OK` → `G7_OK xml_ok script=0 textures=4` (rc=0)

- [x] **G8: scene.json ↔ world.sdf 정합** — 벽 높이·마커 pose·중심 높이·설치 방식 표기 일치
      EXPECT `G8_OK` → `G8_OK wall_h=0.4 center_h=0.4 markers=4` (rc=0)

- [x] **G9: Gazebo 실기동** — 헤드리스 서버로 실제 로드, `gz sdf -k` 스펙 통과, 로그 `[Err]`/`[Wrn]` 0건,
      파싱된 ArUco 링크 4개. 음성 대조(깨뜨린 world)가 잡히는 것까지 확인
      EXPECT `G9_OK` → `G9_OK spec=valid err_wrn=0 aruco_links=4 neg_control(spec_exit=255, err_wrn=2)` (rc=0)

      > ⚠️ **`gz sim`은 world 파싱에 실패해도 exit 0을 반환합니다.** 종료 코드로 판정하면 안 됩니다.
      > 처음에 exit 0을 통과 조건으로 썼다가, 음성 대조에서 "깨진 world도 exit 0"이 나와 발견했습니다.
      > 판정은 `[Err]`/`[Wrn]` 건수와 `gz sdf -k`(이쪽은 정직하게 255를 냅니다)로 합니다.

### G9 실행 환경 (한 번만 준비)

로컬 macOS(arm64)에는 gz가 없고 Homebrew에도 없어 컨테이너로 돌립니다.

```bash
brew install colima docker
colima start --cpu 4 --memory 6 --disk 30
cd verify && docker build -t gzcheck:jazzy -f Dockerfile.gz .   # ros:jazzy-ros-base + ros-jazzy-ros-gz-sim, arm64 네이티브
```

> colima는 `$HOME` 아래만 VM에 마운트합니다. 그래서 G9은 scratchpad(`/private/tmp`)가 아니라
> 리포 안의 `track/output_final`을 봅니다. 설치 후라 두 곳은 바이트 동일하고 G4·G6이 그걸 보증합니다.
> 이 점을 몰랐을 때 "파일 없음"으로 난 exit 255를 음성 대조 통과로 착각한 적이 있습니다.

---

## 미충족 / 이관

- **렌더링 검증**: G9은 헤드리스 서버(`-s`)라 렌더링 경로를 타지 않습니다. world가 로드되고
  텍스처 경로가 유효한 것까지는 확인되지만, **ArUco 마커가 화면에 실제로 보이는지는 미확인**입니다.
  GUI 렌더링까지 보려면 X11 포워딩 또는 WSLg가 있는 Windows 쪽이 편합니다.
- **실물 검출 거리 측정**: 갠트리식 배치가 실제로 검출 거리를 늘리는지는 현물 측정이 필요합니다.
  이슈 #12에 재측정을 요청해 두었습니다.

## 배포 전 확인

- [x] 릴리즈 zip == 커밋 트리 (`track/` 그대로 압축)
- [x] 커밋 diff가 `track_gen.py` + 산출물 5종 + `track/README.md`로 한정
