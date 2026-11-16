#!/bin/bash
# Gazebo를 컨테이너 안에서 띄우고 화면만 VNC로 받아 맥에서 조작한다.
#   ./gz-gui.sh                  # 대회 트랙 (track/output_final/world.sdf)
#   ./gz-gui.sh v2_id20.sdf      # 같은 폴더의 다른 world
#   ./gz-gui.sh --stop           # 종료
#
# X11 포워딩(XQuartz)을 쓰지 않는다. XQuartz는 Ogre2가 요구하는 GL 비주얼을 못 만들어
# "glx: failed to create drisw screen"으로 죽는다. 렌더링은 컨테이너 안 llvmpipe가 하고
# 픽셀만 VNC로 건너온다. 맥 내장 "화면 공유"로 붙는다 — 별도 설치 없음.
set -e

WORLD_DIR="/Users/an-yeonsu/Desktop/vivecoding/ISTech-IT-Arena/istech-it-arena/track/output_final"
NAME=gz-gui
PORT=5901
RES=1440x900
VNCPASS=arena   # 맥 화면 공유는 인증 없는 VNC를 거부하는 경우가 있어 비번을 건다

if [ "$1" = "--stop" ]; then
  docker logs "$NAME" > /tmp/gz-gui-last.log 2>&1 || true   # 죽은 이유를 볼 수 있게 남긴다
  docker rm -f "$NAME" >/dev/null 2>&1 && echo "Gazebo를 종료했습니다. (로그: /tmp/gz-gui-last.log)" || echo "떠 있는 게 없습니다."
  exit 0
fi

WORLD="${1:-world.sdf}"

colima status >/dev/null 2>&1 || colima start
docker rm -f "$NAME" >/dev/null 2>&1 || true

docker run -d --name "$NAME" -p ${PORT}:5900 \
  -v "$WORLD_DIR":/world:ro \
  -e VNCPASS="${VNCPASS}" \
  gzvnc:jazzy \
  bash -lc "
    . /opt/ros/jazzy/setup.sh
    Xvfb :99 -screen 0 ${RES}x24 >/dev/null 2>&1 &
    sleep 3
    export DISPLAY=:99
    openbox >/dev/null 2>&1 &
    x11vnc -display :99 -forever -shared -passwd ${VNCPASS} -rfbport 5900 -quiet >/dev/null 2>&1 &
    cd /world
    exec gz sim -r ${WORLD}
  " >/dev/null

echo "Gazebo 시작 중 — 창이 그려지기까지 30초쯤 걸립니다 (소프트웨어 렌더링)."
printf "  화면 공유 앱이 열립니다"
for i in $(seq 1 30); do printf "."; sleep 1; done
echo
open "vnc://localhost:${PORT}"
echo "  비밀번호: ${VNCPASS}"

cat <<'TIP'

  조작 — 왼쪽 드래그: 회전 / 가운데 드래그: 이동 / 휠: 줌
         왼쪽 패널에서 엔티티 트리·플레이 제어를 쓸 수 있습니다
  종료 — ./gz-gui.sh --stop
TIP
