# Gates: v2026.10.24 — 시뮬 색을 실물 자재에 맞춤

OWNS: istech-it-arena/track/**, istech-it-arena/MANUAL.md, verify/**

Scope: 주문 완료된 자재(도로 백색 포맥스 · 벽 회색 포맥스)에 맞춰 world.sdf 색만 바꾸고, 기하·다른 산출물은 그대로 두고, 문서·릴리즈·이슈로 공지한다.

- [x] G1: world.sdf 도로 전 박스 백색, 벽 전 박스 회색, 홀 바닥 목재, 잔디 불변
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check4.py g1
  EXPECT: G1_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=b223ea916f18479c1bff966fcd7dc99493657bed5d47061ac234c13b16937a79; output-bytes=63

- [x] G2: 색 태그를 지운 world.sdf가 v2026.10.10과 동일 (기하 무변경, 바뀐 링크는 도로·벽·바닥 3개뿐)
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check4.py g2
  EXPECT: G2_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=b5ba7370b9b447167194097782db99d554e39b6f8cf030f51194b21a696746a4; output-bytes=87

- [x] G3: 릴리즈 트리 output_final이 v2026.10.10과 world.sdf 하나만 다름
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check4.py g3
  EXPECT: G3_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=c4de017057aa6ecf21af7da57faff85f3e8906d779ca7777f157b1d280927890; output-bytes=37

- [x] G4: 양성 대조 — v2026.10.10은 G1 색 검사에서 탈락
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check4.py g4
  EXPECT: G4_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=0b82089c32c056764bfae4e576d463297fd1741cf4bc094d44202ec8c4d75210; output-bytes=78

- [x] G5: 생성기 재실행 결과가 설치본과 동일 (dxf는 엔티티 비교, pdf 타임스탬프 제외)
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check4.py g5
  EXPECT: G5_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=e6c5efe45dba8799120cf42a1793ac4172d5f29b0dcaaa66b087d0c08a8c9e92; output-bytes=92

- [x] G6: SDF 위생 — XML 정상, script 0, 텍스처 4개 실재
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check4.py g6
  EXPECT: G6_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=b6b2d88cdf46cdc299759d23b65fa44e225871a16cc6858d0a97aec922384fe7; output-bytes=33

- [x] G7: Gazebo 실기동 — gz sdf -k Valid, gz sim Err/Wrn 0, 깨진 world 음성 대조가 걸림
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check4.py g7
  EXPECT: G7_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=53981d5862f93284f9714c224ae4f5db7391fa1cff6e2da8be60814efc75ae7c; output-bytes=65

- [x] G8: README·MANUAL에 실물 색과 시뮬 RGBA, 변경 이력 기재
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check4.py g8
  EXPECT: G8_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=f2ab2093c27bc02a28058a66a35883197546110bc2bbdac97ecd8893636deced; output-bytes=61

- [x] G9: 내려받은 릴리즈 zip이 커밋된 track/과 바이트 동일
  CHECK: /private/tmp/claude-501/-Users-an-yeonsu-Desktop-vivecoding-ISTech-IT-Arena/d77eee27-e5d6-49a4-8acd-ddc9875c8c35/scratchpad/v/bin/python /Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify/check4.py g9
  EXPECT: G9_OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/verify; path=5868e55fac79/31 entries; EXPECT=matched; output-sha256=29b553647b6188b2b5a618347943d4f3c9dc435ba6803ebed89b82468319b335; output-bytes=25

- [x] G10: 이슈로 공지 — 그리드 라인(흰 테이프 on 백색 바닥) 미해결 질문 포함, 사람이 읽고 확인
  EVIDENCE: manual 2026-10-24 — issue #16 게시(https://github.com/MOSW626/istech-it-arena/issues/16), 색 표·그리드 색 질문·추정치 고지 포함 확인. 릴리즈 노트가 #16을 링크
