#!/usr/bin/env python3
"""
traffic_light.py -- simulator-agnostic race-start traffic light controller
for the ISTech IT Arena track.

Broadcasts the light state as JSON over UDP broadcast on port 47810, so any
team's stack (F1TENTH gym, ROS 2 node, a bare Python client, Gazebo bridge,
...) can subscribe without depending on a specific simulator's message type.

Sequence (matches a standard F1-style start):
    RED          3.0 s
    RED + YELLOW 1.0 s
    GREEN        (race on, held until stopped / re-armed)

Wire format (UDP, JSON, one packet per state change and one heartbeat/0.2s):
    {"t": <unix_time_s>, "state": "red"|"red_yellow"|"green",
     "red": bool, "yellow": bool, "green": bool, "seq": <int>}

--- Hooking this into Gazebo (Gazebo Sim / gz) ---
This script does NOT talk to Gazebo directly (kept simulator-neutral). If you
want the lamp_red / lamp_yellow / lamp_green links in world.sdf to actually
light up, run a small bridge that listens on this UDP socket and toggles the
material's <emissive> via the transport service, e.g.:

    gz service -s /world/it_arena_track/state ...  # or
    gz topic -t /world/it_arena_track/visual_config -m gz.msgs.Visual -p '...'

or, in ROS 2 + ros_gz, remap the state to a `std_msgs/ColorRGBA` topic and use
an `ignition::gazebo::systems::UserCommands` / material-switch plugin. Because
exact topic names depend on your Gazebo version, wire this up on the
integration side; this script only guarantees the UDP JSON contract above.
"""
import argparse
import json
import socket
import time

UDP_PORT = 47810


def broadcast_loop(port=UDP_PORT, host="255.255.255.255", loop=True):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    seq = 0

    def send(state, red, yellow, green):
        nonlocal seq
        seq += 1
        payload = json.dumps({"t": time.time(), "state": state, "red": red,
                               "yellow": yellow, "green": green, "seq": seq}).encode()
        sock.sendto(payload, (host, port))

    def hold(state, red, yellow, green, duration):
        t_end = time.time() + duration
        while time.time() < t_end:
            send(state, red, yellow, green)
            time.sleep(0.2)

    print(f"[traffic_light] broadcasting UDP JSON on port {port} ...")
    while True:
        print("[traffic_light] RED")
        hold("red", True, False, False, 3.0)
        print("[traffic_light] RED+YELLOW")
        hold("red_yellow", True, True, False, 1.0)
        print("[traffic_light] GREEN - go!")
        t_end = time.time() + 3600 if loop else time.time() + 5
        while time.time() < t_end:
            send("green", False, False, True)
            time.sleep(0.2)
        if not loop:
            break


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=UDP_PORT)
    ap.add_argument("--host", default="255.255.255.255", help="UDP target (broadcast by default)")
    ap.add_argument("--once", action="store_true", help="run one red->green sequence and exit")
    args = ap.parse_args()
    broadcast_loop(port=args.port, host=args.host, loop=not args.once)
