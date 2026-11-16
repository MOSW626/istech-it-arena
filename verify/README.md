# 릴리즈 검증 스크립트 (2026 대회 기록)

트랙 릴리즈마다 돌린 독립 검사입니다. 고친 사람과 다른 검사를 두고, 구버전이 같은 검사에서 **실패하는지(양성 대조)**까지 확인하는 방식이었습니다.

| 릴리즈 | 스크립트 | 게이트 |
|---|---|---|
| v2026.09.01 (#7~#11) | `check.py` | `GATES-0901.md` |
| v2026.09.02 (#13) | `check2.py` | `GATES-0902.md` |
| v2026.09.14 (갠트리 ArUco·벽 0.40 m) | `check3.py` | `GATES-0914.md` |
| v2026.10.24 (바닥·벽 색) | `check4.py` | `GATES-1024.md` |
| v2026.11.01 (3차 회의) | `check5.py` | `GATES-1101.md` |
| v2026.11.06 (610 mm 직각 코스) | `check6.py`, `check7.py` | `GATES-1106.md` |

- `Dockerfile.gz`: macOS(arm64)에서 Gazebo를 돌리는 컨테이너(`ros:jazzy` + `ros-gz-sim`). `gz sim`은 world 파싱에 실패해도 exit 0이라 `[Err]` 건수와 `gz sdf -k`로 판정합니다.
- `simtest/`: 15×20 cm 차 완주 주행(`make_world.py`·`drive.py`·`analyze.py`)과 카메라 렌더 + ArUco 검출(`make_cam.py`·`grab.py`, `gz sim --headless-rendering`).
- 스크립트 안 경로는 당시 작업 PC 기준입니다. 다시 쓸 때는 맨 위 경로 상수만 고치면 됩니다.
- `check7.py`의 개인정보 검사는 공개용 기본 패턴만 들어 있습니다. 비공개 키워드는 `PII_EXTRA="|키워드"` 환경변수로 넣으세요.
