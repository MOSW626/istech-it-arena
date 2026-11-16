# Gates: 610mm 직각 코스 배포 준비 (2026-11-06)

OWNS: istech-it-arena/track/**, istech-it-arena/README.md, istech-it-arena/MANUAL.md, verify/**

Scope: 610mm 직각 코스 시뮬 패키지가 도면과 일치하고, 각 팀이 Gazebo·ROS 맵·신호등·마커 검출로 실제 시뮬을 돌릴 수 있는 상태임을 증명한다.

- [x] G1: 시뮬 기하 == PDF 도면 P01~P22·W01~W61 (구 코스는 같은 검사에 탈락)
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/84357235-bb7d-43e3-b055-378602f522c9/scratchpad/venv/bin/python check7.py g1
  EXPECT: G1_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=ecf2d3593ca6cb33c80e63f55d25012e1c33cc2707a35376e58520534ac94db5; output-bytes=19

- [x] G2: ROS 점유격자 맵의 도로·벽이 Gazebo world와 1 px 안에서 일치 (구 맵은 탈락)
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/84357235-bb7d-43e3-b055-378602f522c9/scratchpad/venv/bin/python check7.py g2
  EXPECT: G2_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=518eb4dd45a550ecb6211b82eb321ade37cefa646da85f7010cda6db02665b36; output-bytes=58

- [x] G3: Gazebo 실주행: 15x20 cm 차가 그리드 맨 앞칸에서 본선 1랩 + 지름길 2개 랩을 벽 접촉·멈춤·이음매 튐 없이 완주 (구 기하 대조는 탈락)
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/84357235-bb7d-43e3-b055-378602f522c9/scratchpad/venv/bin/python check7.py g3
  EXPECT: G3_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=92e8a71b356f3558622170869670c48f8b02934f7dc37f6a4b39ed599ba82ccf; output-bytes=151

- [x] G4: 카메라(7.8 cm, VFOV 42.5°)가 마커 0·20·30·45를 각각 도로를 따라 1.0~1.8 m 앞 3곳 중 2곳 이상에서 검출
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/84357235-bb7d-43e3-b055-378602f522c9/scratchpad/venv/bin/python check7.py g4
  EXPECT: G4_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=208d558b8863b06aa54a642f85b90dbca4dc4ef5260f8c41a23e09c58c2e8731; output-bytes=84

- [x] G5: Gazebo 로드: gz sdf -k Valid, Err/Wrn 0, 깨진 world 음성 대조가 걸림
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/84357235-bb7d-43e3-b055-378602f522c9/scratchpad/venv/bin/python check7.py g5
  EXPECT: G5_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=b661f34d7f6bc08cbb3fb6f5c19b7a565741da4230924edf767bde859096ccb7; output-bytes=39

- [x] G6: 재현성: design 스크립트와 생성기 재실행 결과가 커밋본과 동일
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/84357235-bb7d-43e3-b055-378602f522c9/scratchpad/venv/bin/python check7.py g6
  EXPECT: G6_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=5c56f6d1e622facf59314bc7939f702b3e19d98996a3035ee5ae15c733541b37; output-bytes=29

- [x] G7: 신호등 selftest 통과, ArUco PNG 4장이 0·20·30·45로 해독
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/84357235-bb7d-43e3-b055-378602f522c9/scratchpad/venv/bin/python check7.py g7
  EXPECT: G7_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=3f8e794c244a396a25449b538813fe44a90ca969e61e0aaea2dbb0159d131701; output-bytes=38

- [x] G8: 문서 숫자 == scene.json, '다시 바뀔 수' 문구 없음, 미푸시 diff·PDF에 연락처·후원 정보 없음
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/84357235-bb7d-43e3-b055-378602f522c9/scratchpad/venv/bin/python check7.py g8
  EXPECT: G8_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=16bd5740326d8d1241fcbceae6d27eb56db665f99098a318b2ea9334e91845b8; output-bytes=22

- [x] G10: 그리드 맨 앞칸 카메라가 신호등 마커 0·45를 검출, 신호등-그리드 간격 0.5 m 이상 (11-01 간격 0.30 m 자리는 음성 대조로 미검출)
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/84357235-bb7d-43e3-b055-378602f522c9/scratchpad/venv/bin/python check7.py g10
  EXPECT: G10_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=52b6c6c976aeceba624e69167bc1d37c6ef8eeb1e7d5f6821b4f6c7159ecaa31; output-bytes=78

- [x] G9: 릴리즈 때 — G1~G8 재실행, 릴리즈 zip == 커밋 트리
  EVIDENCE: 2026-11-06 수동 — zip(git archive HEAD:track) 25파일 == HEAD 45691ae 바이트 동일, 업로드본 cmp SAME
