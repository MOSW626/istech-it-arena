# Gates: v2026.11.01 — 3차(최종) 회의 반영

OWNS: istech-it-arena/track/**, istech-it-arena/MANUAL.md, istech-it-arena/README.md, istech-it-arena/meetings/**, istech-it-arena/parts/speed_bump/README.md, istech-it-arena/docs/venue/save_points.png, verify/**

Scope: 방지턱 제거 · 그리드 검정 · 신호등 실물 위치/형상 · ArUco 0·45 신호등 좌우 이동을 시뮬에 반영하고, 회의 결정을 문서·릴리즈·이슈로 공지한다. 코스 기하는 바뀌면 안 된다.

- [x] G1: 방지턱이 world·scene·DXF·design 어디에도 없음
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check5.py g1
  EXPECT: G1_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=4797768e633f61ab4b8c45aa9efa349429b06c569866f9541a94d23055a5cf0c; output-bytes=43

- [x] G2: 그리드 칸 6개 전부 검정
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check5.py g2
  EXPECT: G2_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=4ee60cbd1e68436abb91b1841aa253c2675fd089eb63f3e716135b8fb64e03e5; output-bytes=30

- [x] G3: 신호등이 선두 그리드 앞 0.30 m, 발광 중심 0.419, 60°, 하단 ~0.397, 운전자 기준 RRRRG로 도로를 가로지름
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check5.py g3
  EXPECT: G3_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=49dfb8118293da5d5156932e2fb2ac080854a473233af23405a1b568a8c461fb; output-bytes=72

- [x] G4: ArUco 0(오른쪽)·45(왼쪽)가 신호등과 같은 s, 패널과 안 겹치고 도로 안, 20·30 불변
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check5.py g4
  EXPECT: G4_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=8b952fea1c9b664b8ef3d357c116ae7600fd2b00893a0f813a17a30dc53a4237; output-bytes=56

- [x] G5: 부수 변경 없음 — 5개 파일 외 바이트 동일, world는 손댄 링크 외 동일, 출발선 불변, DXF는 FEATURES 외 동일
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check5.py g5
  EXPECT: G5_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=b7e40beee8034231167a32bfbba015ab20a6e3d34acb9778171afa08dc591b42; output-bytes=197

- [x] G6: 양성 대조 — v2026.10.24가 G1~G4 검사 4개 모두에서 탈락
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check5.py g6
  EXPECT: G6_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=5fb25bb87e3e3e9ffedcbaa943b5689d6cc47f4f74af1fc77a9869d898c3cda0; output-bytes=56

- [x] G7: 생성기 재실행 결과가 설치본과 동일
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check5.py g7
  EXPECT: G7_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=ec97030410d4a0b1b7ec3be2db2fb6bd3edd33cd37347a9b241e4214a08dd3d8; output-bytes=20

- [x] G8: Gazebo 실기동 — gz sdf -k Valid, Err/Wrn 0, 깨진 world 음성 대조가 걸림
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check5.py g8
  EXPECT: G8_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=ccb87f6eeb4eb5df3c04ab6f92268ac6775616a4bc80563d9866800287089da7; output-bytes=47

- [x] G9: MANUAL에 회의 결정 7개 키워드, README 변경 이력, 공개 repo에 주소·전화번호 없음
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check5.py g9
  EXPECT: G9_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=63c4345e0c53123e99037d1e97e74aae14b2b18b3b1c3a4745d10e29af6399b3; output-bytes=38

- [x] G10: 릴리즈 zip == 커밋 트리
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check5.py g10
  EXPECT: G10_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=3b1ce5f1011532e751ae69cbda91aa09b3ed38538dacbc89ad4bf1a9f706d364; output-bytes=26

- [x] G11: 이슈 공지 — #2 종결(제거), #3 반영 안내, #16 그리드 검정, #6 3차 결과
  EVIDENCE: manual 2026-11-02 — #2 댓글+close+제목 [종결], #3 시뮬 반영·추정치 고지·마커 부착 자리 질문, #16 검정 테이프 확정, #4 5팀 완료 close, #6 3차 결과 표+제목 갱신. 릴리즈 노트가 #2·#3·#16 링크
