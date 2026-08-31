# ISTech IT Arena 트랙 맵 패키지 — 최종 코스 (2026-08-31 개정)

조직위가 `track_editor.html`로 직접 그린 코스(`design_final.json`)가 최종 레이아웃입니다.
`track_gen.py`를 `--design` 모드로 실행하면 `output_final/` 아래 모든 산출물이 재생성됩니다.
대회장 홀은 **11.0 × 14.5 m (실측 확인 완료)** 입니다.

```bash
python3 -m venv venv && venv/bin/pip install numpy matplotlib opencv-python-headless ezdxf pyyaml shapely
venv/bin/python3 track_gen.py --design design_final.json --outdir output_final
```

> ⚠️ 인자 없이 `python3 track_gen.py`만 실행하면 초기 검토용 내장 코스("후보1 통합 코스 A+B")가
> 생성됩니다. 그건 최종 코스가 아닙니다. 반드시 `--design design_final.json`을 붙이세요.

## 1. 코스 사양 (규정 연동)

| 항목 | 값 | 비고 |
|---|---|---|
| 랩 길이 (메인) | **46.63 m** | |
| 도로 폭 | **0.45 m** | 회의 확정값 (차량 3대 폭) |
| 차량 규격 | **폭 0.15 × 길이 0.20 m** | 대회 규정. 설계 전체가 이 규격 기준 |
| 갈림길(지름길) | 2개, 폭 **0.20 m** | 차폭 15cm + 좌우 2.5cm 여유. 1대만 통과 |
| 벽 | 높이 0.30 m, 두께 0.05 m | 외곽 + 갈림길 분리 섬 |
| 잔디 완충구간 | 트랙 양옆 0.20 m | 잔디 매트, 트랙 외 노면변화 역할 |
| 과속방지턱 | 1개 (길이 0.05 m) | 높이 `--bump-height` low/mid/high = 0.005/0.010/0.015 m |
| 출발 그리드 | 6대, 2열 지그재그, 슬롯 **0.25 × 0.17 m** | 차량 + 길이 5cm / 폭 2cm 여유 |
| 신호등 | 적/황/녹 갠트리, 출발선 좌측 | 실전: LED 시각 인식 출발 (아래 §6 주의) |

갈림길 (양쪽 모두 주행 가능, 점유격자에 자유공간으로 포함)

| 이름 | 분기 s (m) | 합류 s (m) | 대체경로 길이 (m) |
|---|---|---|---|
| 갈림길① | 13.20 | 16.80 | 3.10 |
| 갈림길② | 32.90 | 36.40 | 2.83 |

## 2. 검증 결과 (`track_gen.py` 실행 시 자동 출력)

| 항목 | 값 | 기준 | 결과 |
|---|---|---|---|
| 랩 길이 | 46.63 m | 35–55 m | PASS |
| 홀 적합 (외곽 bbox) | 9.67 × 13.18 m | 11.0 × 14.5 m 이내 | PASS |
| 홀 여유 마진 (각 변) | 0.665 / 0.66 m | ≥ 0.5 m | PASS |
| 인접 구간 최소 클리어런스 | 0.49 m | ≥ 0.35 m | PASS |
| 자기교차 | 없음 | 없음 | PASS |
| 그리드 슬롯 vs 벽 겹침 | 없음 | 없음 | PASS |
| 갈림길 기하 (2개) | OK | - | PASS |
| 최소 회전반경 | **0.299 m** | 0.45 m | **의도적 예외** |

> **최소 회전반경 0.299 m 코너에 대하여**: 검증상 FAIL로 출력되지만, 조직위 결정(2026-08-31)으로
> **"그 정도는 해봐야 할 어려운 코너"로 의도적으로 유지**합니다. 차량 개발 시 이 반경을 돌 수 있는
> 조향 설계를 감안하세요.

## 3. ArUco 마커 (DICT_4X4_50, 10×10 cm, 바닥에서 0.05 m 높이, 트랙을 향해 벽에 부착)

**진짜 4개뿐이며, 가짜(디코이) 마커는 없습니다.**

| ID | 위치 (s) | 역할 |
|---|---|---|
| 0 | 0.00 | 출발/결승선 (랩 타이밍 기준) |
| 20 | 12.60 | 갈림길① 분기 직전 표시 |
| 30 | 32.90 | 갈림길② 분기 표시 |
| 45 | 45.95 | 그리드 진입 |

## 4. 산출물 파일 목록 (`output_final/`)

| 파일 | 설명 |
|---|---|
| `centerline.csv` | 메인 센터라인 x,y,s(아크길이),트랙폭 |
| `left_boundary.csv` / `right_boundary.csv` | 메인 트랙 좌/우 경계선 |
| `branch_0.csv` / `branch_1.csv` | 갈림길①/② 센터라인 (x,y,s,폭) |
| `map.png` + `map.yaml` | ROS/F1TENTH 점유격자 맵 (해상도 0.01 m/px) |
| `map_with_grass.png` + `.yaml` | 동일 맵, 잔디를 회색(150)으로 별도 표시 |
| `world.sdf` | Gazebo Sim(gz) 정적 월드 — 벽/노면/방지턱/그리드/신호등/ArUco(실제 텍스처) 포함 |
| `traffic_light.py` | UDP JSON 신호등 컨트롤러 (포트 47810) — **시뮬 전용**, §6 참고 |
| `venue_layout.dxf` | 현장 시공용 1:1 DXF (레이어: HALL/TRACK/WALLS/GRASS/MARKERS/FEATURES/GRID/FORKS) |
| `aruco/aruco_id*.png` | ArUco 마커 PNG 4종 (1000×1000 px, 여백 포함) |
| `aruco_print_sheet.pdf` | 마커별 A4 1장, 실제 10 cm 크기로 인쇄 |
| `scene.json` | 통합 씬 데이터 (차량 규격/섹션/갈림길/그리드 슬롯 pose/검증 결과 포함) |
| `preview.png` | 상단뷰 렌더링 (한글 범례 + 치수) |

## 5. 시뮬레이터별 사용법

| 시뮬레이터 | 사용 파일 | 방법 |
|---|---|---|
| F1TENTH gym | `map.png` + `map.yaml` (+ `centerline.csv`) | `map.yaml`을 gym 맵 설정에 지정, 레이스라인은 `centerline.csv`를 waypoint로 로드 |
| ROS map_server / Nav2 | `map.yaml` | `ros2 run nav2_map_server map_server --ros-args -p yaml_filename:=map.yaml` |
| Gazebo Sim (gz) | `world.sdf` | `gz sim world.sdf` (플러그인 없이 로드, 정적 모델). ArUco 텍스처는 `aruco/` 상대경로 참조 — 폴더 구조 유지 필요 |
| 커스텀 시뮬레이터 | `scene.json` | JSON 직접 파싱: 홀 크기, 갈림길 branch/merge s, 그리드 슬롯 pose, 검증 결과 등 |
| 신호등 연동 | `traffic_light.py` | UDP 47810 JSON 브로드캐스트, 소켓 수신만 하면 시뮬레이터 무관 |
| 현장 시공 | `venue_layout.dxf` | CAD에서 1:1로 열어 벽/마커/방지턱/그리드 위치 실측 시공 |

## 6. 시뮬 ↔ 실전 차이 (개발 시 반드시 감안)

- **신호등**: 실전 규칙은 "신호등이 **랜덤하게** 켜지고, 차량이 **카메라로 센싱**하여 출발"입니다.
  `traffic_light.py`(UDP)는 시뮬 편의용일 뿐이며, **실전에서는 UDP 신호가 없습니다.**
  반드시 시각 인식 기반 출발을 개발하세요. 현재 스크립트의 RED 3.0 s는 고정값이므로
  타이밍 학습에 쓰지 마세요 (실전은 랜덤 홀드).
- **바닥/벽 재질**: 실제 경기장은 포맥스/EVA폼 (각 학교에 1×1 m 폼 지급: 바닥재 5 + 벽면 색 3).
  시뮬 마찰계수와 다를 수 있습니다.
- 트랙은 대회 전 공개 정책이며 이 패키지가 그 공개본입니다.

## 7. 파라미터 (CLI)

| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `--design` | - | **최종 코스 생성에 필수**: `design_final.json` 지정 |
| `--bump-height` | `mid` (0.010 m) | `low`/`mid`/`high` 또는 미터 실수 직접 입력 |
| `--resolution` | 0.01 m/px | 점유격자 맵 해상도 |
| `--grid-cars` | 6 | 출발 그리드 슬롯 수 (design.json 값보다 우선) |
| `--outdir` | `output` | 출력 디렉터리 (최종본은 `output_final` 사용) |
| `--scale` | 1.0 | **design 모드에서는 무시됨** |

## 변경 이력

- **2026-08-31**: 차량 규격을 대회 규정(15×20 cm)으로 정정하고 연동 값 전면 수정 —
  도로 폭 0.35→**0.45 m**, 갈림길 폭 0.12→**0.20 m**(0.12는 차폭보다 좁아 통과 불가였음),
  그리드 슬롯 0.20×0.12→**0.25×0.17 m**. 벽 생성을 폴리곤 유니온 방식으로 교체해
  갈림길 접속부의 끊긴 벽(스텁) 문제 해결. README를 실제 산출물 기준으로 재작성
  (구버전의 협로·가짜 ArUco·피트레인 서술 삭제 — 이 코스에는 없음).
- **2026-07-27**: 최초 배포본 (`it_arena_track_final.zip`).
