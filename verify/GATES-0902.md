# GATES — 이슈 #13 수정 검증 (베이스라인 v2026.09.01)

- [x] H1: SDF 위생 유지 (script 0, aruco/ 경로+파일, diffuse 4/4, 병합 링크 ≤25)
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check2.py h1
    EXPECT: H1_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0902; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=3be83d7fead35ce78d4c49c1f0a8b082107247a24e55831bf44b6b886b64acd8; output-bytes=37
- [x] H2: 노면 커버리지 — 설계 대비 누락 <0.1%·1cm 초과 공백 없음, visual/collision 동일 (베이스라인은 ~0.32㎡ 검출돼야)
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check2.py h2
    EXPECT: H2_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0902; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=825d8cf8663e39693eb259558e690452cf53108d1acb8c4c3653ff6e19a0675d; output-bytes=83
- [x] H3: 잔디 연속성 — (corridor−drivable) 누락 <1%, 노면 침범 <0.5% (베이스라인은 갈림길 공백 검출돼야)
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check2.py h3
    EXPECT: H3_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0902; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=f0a0fc2bb6bd9d6909ade5ba9481348983b7c6d9ce5874b8bb89b2776ad1ef04; output-bytes=54
- [x] H4: 벽·마커·그리드·신호등·방지턱은 v2026.09.01과 완전 동일 (부수 변경 없음)
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check2.py h4
    EXPECT: H4_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0902; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=f9b5a1b63e1cebd696be88b901e778348b1e6fa63bbe0612aabaa42d9b62fc94; output-bytes=47
- [x] H5: 재생성 재현성 + 검증 예외는 min_radius 1건뿐
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check2.py h5
    EXPECT: H5_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0902; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=07adcc32c968b7e48e359d135bc78966707ee887f542b751726fcdc8e6839c84; output-bytes=61
- [x] H6: 내장 코스 경로 회귀 없음
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check2.py h6
    EXPECT: H6_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0902; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=a497f630a9bb7af69fd17d074d1890b13094dc41280b2f6f83936308c101e9ab; output-bytes=31
- [x] H7: 래스터 확인 — 제보 좌표(9.768,1.244) 공백 해소, 잔디 영역 픽셀 샘플 98%+ 정상
    CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/venv/bin/python3 check2.py h7
    EXPECT: H7_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/0525181e-72c3-40fe-992f-15ca9f5f885f/scratchpad/verify-0902; path=0712ecb45f47/29 entries; EXPECT=matched; output-sha256=0a2d05b193675fc54d9b2db792c20b9c13f331b4bd7d76e1ab7cd5b84e919e9e; output-bytes=64
