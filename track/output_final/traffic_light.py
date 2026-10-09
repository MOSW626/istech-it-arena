#!/usr/bin/env python3
"""
traffic_light.py -- race-start light controller for the ISTech IT Arena track.

Mirrors the ACTUAL start light built by Pinocchio (spec + Arduino source posted
to issue #3 on 2026-10-09). The timings below are not placeholders any more --
they are the delays in the real sketch.

Hardware
    5 light sets in a row, left to right:  RED RED RED RED GREEN
    Each set is two diffused sources 5 mm apart vertically (4x 5mm LEDs behind
    a diffuser), emitting face ~15 mm across, sets spaced 15 mm apart.
    Relay-switched, 4x 1.5 V cells. randomSeed comes from A0 pin noise, so
    every race differs.

Sequence (exactly the Arduino runStartingSequence())
    all off                 1.000 s
    red 1 on                1.000 s
    red 2 on                1.000 s
    red 3 on                random 1.000 .. 3.000 s
    red 4 on                random 1.000 .. 3.000 s
    reds OFF + GREEN ON  == RACE ON    (green holds 5 s, then all off)

    Total 5.00 .. 9.00 s, mean 7.00 s.

>>> THE START IS: ALL FOUR REDS GO OUT AND THE GREEN COMES ON, TOGETHER. <<<

Both edges happen in the same instant, so you may trigger on either one.
What you cannot do is predict when. The 3rd and 4th reds each hold for a random
1-3 s, so the gap before the start is never the same twice.

--- If you built against an earlier version, read this ---
  v2026.10.06 modelled a single-colour F1 bar where the start was ALL lights
  going out and every interval was randomised. The real light is not single
  colour, the green does come on, and the first two steps are fixed at 1 s.
  Before that the script was a road signal (red -> red+yellow -> green) on
  fixed 3.0 s / 1.0 s timing, with no randomness at all.

Wire format (UDP broadcast, JSON, on change + heartbeat every 0.2 s)

    {"t": <unix_s>, "seq": <int>, "schema": 3,
     "state": "armed" | "red1" | "red2" | "red3" | "red4" | "go" | "off",
     "reds": [bool, bool, bool, bool], "reds_on": <0..4>,
     "green": <bool>, "go": <bool>}

In the real race there is no UDP. Start detection must be visual; this exists
so you can exercise that logic in simulation.

Usage
    python3 traffic_light.py                 # broadcast, repeating
    python3 traffic_light.py --once
    python3 traffic_light.py --seed 42       # reproducible
    python3 traffic_light.py --selftest      # checks, no socket
"""
import argparse
import json
import random
import socket
import sys
import time

UDP_PORT = 47810
N_RED = 4
ARM_S = 1.0                      # turnOffAllLights(); delay(1000)
FIXED_STEP_S = 1.0               # delay(1000) after red 1 and red 2
RANDOM_STEP_MS = (1000, 3000)    # Arduino random(1000, 3001), inclusive ms
GREEN_HOLD_S = 5.0               # delay(5000) before turnOffAllLights()
HEARTBEAT = 0.2


def plan_sequence(rng):
    """The two random delays for this race, in seconds. Drawn as integer
    milliseconds exactly like the Arduino random(1000, 3001)."""
    return (rng.randint(*RANDOM_STEP_MS) / 1000.0,
            rng.randint(*RANDOM_STEP_MS) / 1000.0)


def iter_states(d3, d4):
    """(state, reds_on, green, duration). Pure, so it can be tested."""
    yield ("armed", 0, False, ARM_S)
    yield ("red1", 1, False, FIXED_STEP_S)
    yield ("red2", 2, False, FIXED_STEP_S)
    yield ("red3", 3, False, d3)
    yield ("red4", 4, False, d4)
    yield ("go", 0, True, GREEN_HOLD_S)
    yield ("off", 0, False, None)


def broadcast_loop(port=UDP_PORT, host="255.255.255.255", loop=True, seed=None,
                   idle_s=3.0):
    rng = random.Random(seed)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    seq = 0

    def send(state, reds_on, green):
        nonlocal seq
        seq += 1
        sock.sendto(json.dumps({
            "t": time.time(), "seq": seq, "schema": 3, "state": state,
            "reds": [i < reds_on for i in range(N_RED)], "reds_on": reds_on,
            "green": green, "go": (state == "go"),
        }).encode(), (host, port))

    print("[traffic_light] broadcasting UDP JSON on port %d" % port)
    print("[traffic_light] START = four reds go out and the green comes on")
    while True:
        d3, d4 = plan_sequence(rng)
        print("[traffic_light] this race: red3 holds %.3fs, red4 holds %.3fs "
              "(start at T+%.3fs)" % (d3, d4, ARM_S + 2 * FIXED_STEP_S + d3 + d4))
        for state, reds_on, green, duration in iter_states(d3, d4):
            if state == "go":
                print("[traffic_light] GREEN -- GO")
            elif state.startswith("red"):
                print("[traffic_light] red %d/%d on" % (reds_on, N_RED))
            t_end = time.time() + (idle_s if duration is None else duration)
            while time.time() < t_end:
                send(state, reds_on, green)
                time.sleep(HEARTBEAT)
        if not loop:
            break


def selftest():
    d3, d4 = plan_sequence(random.Random(0))
    st = list(iter_states(d3, d4))

    names = [s for s, _, _, _ in st]
    assert names == ["armed", "red1", "red2", "red3", "red4", "go", "off"], names

    # reds light one at a time, then all four drop at once
    assert [r for _, r, _, _ in st] == [0, 1, 2, 3, 4, 0, 0]
    # green is on only at go, and go happens only after all four reds
    assert [g for _, _, g, _ in st] == [False] * 5 + [True, False]
    go_i = names.index("go")
    assert st[go_i - 1][1] == N_RED, "green must follow all four reds"
    assert st[go_i][1] == 0, "reds must drop as the green comes on"

    # the two fixed steps are fixed, the other two are random and in range
    draws = [plan_sequence(random.Random(s)) for s in range(500)]
    assert len({d for d, _ in draws}) > 1 and len({d for _, d in draws}) > 1
    lo, hi = RANDOM_STEP_MS[0] / 1000.0, RANDOM_STEP_MS[1] / 1000.0
    assert all(lo <= a <= hi and lo <= b <= hi for a, b in draws)
    assert plan_sequence(random.Random(7)) == plan_sequence(random.Random(7))

    # total start time matches the real sketch: 5.00 .. 9.00 s
    base = ARM_S + 2 * FIXED_STEP_S
    totals = [base + a + b for a, b in draws]
    assert min(totals) >= 5.0 - 1e-9 and max(totals) <= 9.0 + 1e-9
    assert 5.0 <= base + d3 + d4 <= 9.0

    print("selftest OK -- 4 red + 1 green, start at T+%.3fs (range 5.00-9.00s)"
          % (base + d3 + d4))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="ISTech IT Arena race-start lights")
    ap.add_argument("--port", type=int, default=UDP_PORT)
    ap.add_argument("--host", default="255.255.255.255")
    ap.add_argument("--once", action="store_true", help="run one sequence and exit")
    ap.add_argument("--seed", type=int, default=None, help="reproducible randomisation")
    ap.add_argument("--selftest", action="store_true", help="run checks without a socket")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        sys.exit(0)
    broadcast_loop(port=args.port, host=args.host, loop=not args.once, seed=args.seed)
