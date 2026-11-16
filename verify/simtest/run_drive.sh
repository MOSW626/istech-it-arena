#!/bin/bash
# usage: run_drive.sh <workdir under $HOME>   (needs colima running + gzcheck:jazzy)
WD="$1"
docker run --rm -v "$WD":/w gzcheck:jazzy bash -c '
source /opt/ros/jazzy/setup.bash
gz sim -s -r /w/world_car.sdf > /w/gz.log 2>&1 &
sleep 8
python3 /w/drive.py /w
kill %1; wait
echo GZ_ERR=$(grep -c "\[Err\]" /w/gz.log) GZ_WRN=$(grep -c "\[Wrn\]" /w/gz.log)'
