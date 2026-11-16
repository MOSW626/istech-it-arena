# GATES — v2026.09.01 이슈 #7~#11 수정 딥 검증

- [x] G1: (#7) 마커 재질의 잘못된 <script> 블록이 제거됨 (베이스라인엔 존재해야 함)
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check.py g1
    EXPECT: G1_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0901; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=12f841018a5fb79f124a27a4fae08421644bf1e3d94346a382aff5761ae59efb; output-bytes=6
- [x] G2: (#7) ArUco 텍스처 경로가 aruco/ 이고 파일이 실제 존재 (베이스라인은 ../aruco/)
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check.py g2
    EXPECT: G2_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0901; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=e08b6024499f7063fc7e93eefd5be0951553d7144840d659c4857e5c5c167691; output-bytes=6
- [x] G3: (#7) 마커 4개 전부 diffuse 1 1 1 1 보유 (베이스라인엔 없어야 함)
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check.py g3
    EXPECT: G3_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0901; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=0bfc4273b320f03e14e34bfa2b5ef6d79dc9a76d7611258d18443e32b2bd1c80; output-bytes=6
- [x] G4: (#7) 링크 1113→소수 병합, visual/collision/마찰(mu 0.8) 개수 전후 동일
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check.py g4
    EXPECT: G4_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0901; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=e2f9628966105efbc3183d1796ef398dcbaaca26fe67c5df8088aaf1a5729500; output-bytes=59
- [x] G5: (#7) 정적 박스 visual의 월드 pose·크기 다중집합이 릴리즈 간 완전 동일 (그리드·마커 제외)
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check.py g5
    EXPECT: G5_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0901; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=21afdb1b3e3f9a1a9c533c19e35db431128e0a1817dabf7bef32d6046751d05e; output-bytes=57
- [x] G6: (#8) 마커 4개가 벽 안쪽 면에서 5mm 이내 — design_final.json에서 독립 재계산한 corridor 기준
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check.py g6
    EXPECT: G6_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0901; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=287ccb44fcdc7d3d3b61cd70c7061c18236b2770ddfeb71df4556dd269c0232a; output-bytes=53
- [x] G7: (#8) 어떤 마커 판도 주행 코리도(본선+갈림길 2개)와 안 겹침 (베이스라인 ID30은 겹쳐야 함)
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check.py g7
    EXPECT: G7_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0901; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=436ae402db917c452120a3bdd050cbf70688c6693c87c842b26c94535824d190; output-bytes=52
- [x] G8: (#8) scene.json·world.sdf·DXF의 마커 좌표 일치
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check.py g8
    EXPECT: G8_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0901; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=494fc31193b0a1d92d992508d2c9878b8c90401fff3813926aa18ffb0bfec18f; output-bytes=60
- [x] G9: (#9) longitudinal_stagger_m == 슬롯 s 실측 차이 (베이스라인은 불일치해야 함)
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check.py g9
    EXPECT: G9_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0901; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=c560fb80e7377d1508179fd8ed3929c40d1fac2f0b40fcfddedd0c59825351df; output-bytes=83
- [x] G10: (#10) 그리드 표시 상단 z > 노면 상단 0.003, XY·크기·무충돌 유지 (베이스라인은 노면 아래)
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check.py g10
    EXPECT: G10_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0901; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=cbbdd2a995e55fe9e6e262c677fda4e01c476a228a4774fadf46d03992e904e6; output-bytes=65
- [x] G11: (#11) 출발선 s=0 정본화: design=0.0, scene.start_finish pose == centerline 원점
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check.py g11
    EXPECT: G11_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0901; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=3e9694b5f285bb2acc9b32fe4dc0830cd2dca31e6c19b238c6781cfff898cc98; output-bytes=67
- [x] G12: 재생성 재현성: track_gen 재실행 산출물이 커밋본과 바이트 동일 + 검증 예외는 min_radius 하나뿐
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check.py g12
    EXPECT: G12_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0901; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=ca8dbe46c1a2419e96bc88358cdc3be8bcf2b0b6f0a79f01a49261c5edbc5725; output-bytes=66
- [x] G13: 릴리즈 zip == 커밋된 track/ (배포 패키징 무결성)
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check.py g13
    EXPECT: G13_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0901; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=9e43c431d970ca9477aef319c26fb63d8d04f3c55cd91ae58a26435ed6d1a913; output-bytes=51
- [x] G14: 내장 코스 경로 회귀 없음 (--design 없이 실행 성공)
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check.py g14
    EXPECT: G14_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0901; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=afdc55e6fdbd2ddadfd1d634bc642afce5ee5e8b31f9f4da52b1f46305188f12; output-bytes=39
- [ ] G15: (#7) Gazebo 실기동 (수동: 로컬에 Gazebo 없음 — 제보자에게 재확인 요청함, 이슈 #7 댓글)
