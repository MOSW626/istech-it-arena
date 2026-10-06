#!/usr/bin/env python3
"""
traffic_light.py -- race-start light controller for the ISTech IT Arena track.

Implements the start sequence confirmed at the 2026-09-14 meeting (R1-5 / R2-5):

    F1 style. Several single-colour LEDs light up one at a time, and the race
    starts the moment they ALL GO OUT. The Arduino randomises the lighting
    speed, so the sequence takes a different amount of time every race.

    armed  -> all off
    lighting -> 1, 2, ... N lights on, one step at a time
    hold   -> all N on, held
    go     -> ALL OFF == RACE ON

>>> THE START EVENT IS LIGHTS GOING OUT, NOT A GREEN LIGHT TURNING ON. <<<

An earlier version of this file broadcast a road-traffic signal
(red -> red+yellow -> green) with fixed 3.0 s / 1.0 s timing. That was wrong on
both counts: the real start is signalled by lights going OUT, and the timing is
random. If you built a detector against that version, it will not work on race
day. Rebuild it against this contract.

--- Numbers are PLACEHOLDERS ---
The structure above is decided. The exact LED count and the random ranges come
from Pinocchio and are tracked in issue #3; they will be dropped in here when
they arrive (issue #5). Do NOT tune your detector to these specific numbers --
make it work for any N and any interval inside a plausible range.

    lights        5
    step interval 0.6 .. 1.4 s   (randomised per race)
    hold          0.2 .. 3.0 s   (randomised per race)

Wire format (UDP broadcast, JSON, one packet per change + heartbeat every 0.2 s):

    {"t": <unix_s>, "seq": <int>, "schema": 2,
     "state": "armed" | "lighting" | "hold" | "go",
     "lights_total": <int>, "lights_on": <int>,
     "go": <bool>, "green": <bool>}

`go` is the field to act on. `green` carries the same value purely so older
clients fail loudly rather than silently: the `red` and `yellow` fields are gone
because the real signal has no colours to tell apart -- every LED is the same
colour and you must COUNT them, not classify them.

In the real race there is no UDP at all. Start detection must be visual.
This script exists so you can exercise that logic in simulation.

Usage:
    python3 traffic_light.py                 # broadcast, repeating
    python3 traffic_light.py --once          # one sequence, then exit
    python3 traffic_light.py --seed 42       # reproducible randomisation
    python3 traffic_light.py --selftest      # run checks, no socket
"""
import argparse
import json
import random
import socket
import sys
import time

UDP_PORT = 47810
N_LIGHTS = 5
STEP_RANGE = (0.6, 1.4)
HOLD_RANGE = (0.2, 3.0)
HEARTBEAT = 0.2


def plan_sequence(rng, n_lights=N_LIGHTS, step_range=STEP_RANGE, hold_range=HOLD_RANGE):
    """One race worth of timing. Returns (step_s, hold_s).

    The Arduino randomises the lighting speed, so a single step interval is
    drawn per race and used for every light -- the lights come on evenly, but
    at a pace you cannot know in advance.
    """
    step = rng.uniform(*step_range)
    hold = rng.uniform(*hold_range)
    return step, hold


def iter_states(step, hold, n_lights=N_LIGHTS):
    """The sequence as (state, lights_on, duration) triples. Pure, so testable."""
    yield ("armed", 0, step)
    for k in range(1, n_lights + 1):
        yield ("lighting", k, step)
    yield ("hold", n_lights, hold)
    yield ("go", 0, None)          # None == hold until stopped / re-armed


def broadcast_loop(port=UDP_PORT, host="255.255.255.255", loop=True, seed=None,
                   n_lights=N_LIGHTS, green_hold=20.0):
    rng = random.Random(seed)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    seq = 0

    def send(state, lights_on):
        nonlocal seq
        seq += 1
        go = (state == "go")
        sock.sendto(json.dumps({
            "t": time.time(), "seq": seq, "schema": 2, "state": state,
            "lights_total": n_lights, "lights_on": lights_on,
            "go": go, "green": go,
        }).encode(), (host, port))

    print("[traffic_light] broadcasting UDP JSON on port %d" % port)
    print("[traffic_light] START EVENT = ALL LIGHTS OUT (not a green light)")
    while True:
        step, hold = plan_sequence(rng, n_lights=n_lights)
        print("[traffic_light] this race: step %.2fs, hold %.2fs" % (step, hold))
        for state, lights_on, duration in iter_states(step, hold, n_lights):
            if state == "go":
                print("[traffic_light] LIGHTS OUT -- GO")
            elif state == "lighting":
                print("[traffic_light] light %d/%d on" % (lights_on, n_lights))
            t_end = time.time() + (green_hold if duration is None else duration)
            while time.time() < t_end:
                send(state, lights_on)
                time.sleep(HEARTBEAT)
        if not loop:
            break


def selftest():
    rng = random.Random(0)
    step, hold = plan_sequence(rng)
    states = list(iter_states(step, hold))

    # lights come on one at a time, 0 .. N, then all go out together
    counts = [c for _, c, _ in states]
    assert counts == list(range(N_LIGHTS + 1)) + [N_LIGHTS, 0], counts
    assert states[-1][0] == "go" and states[-1][1] == 0, "start must be lights-out"
    assert states[-2][0] == "hold" and states[-2][1] == N_LIGHTS, "hold must be fully lit"

    # go is reached exactly once, and only after every light is on
    assert [s for s, _, _ in states].count("go") == 1
    first_full = next(i for i, (_, c, _) in enumerate(states) if c == N_LIGHTS)
    assert first_full < len(states) - 1

    # timing is randomised per race, and inside the declared ranges
    draws = [plan_sequence(random.Random(s)) for s in range(50)]
    assert len({round(a, 6) for a, _ in draws}) > 1, "step interval must vary between races"
    assert len({round(b, 6) for _, b in draws}) > 1, "hold must vary between races"
    assert all(STEP_RANGE[0] <= a <= STEP_RANGE[1] for a, _ in draws)
    assert all(HOLD_RANGE[0] <= b <= HOLD_RANGE[1] for _, b in draws)

    # a fixed seed reproduces a race exactly
    assert plan_sequence(random.Random(7)) == plan_sequence(random.Random(7))

    total = sum(d for _, _, d in states if d is not None)
    assert STEP_RANGE[0] * (N_LIGHTS + 1) + HOLD_RANGE[0] <= total <=            STEP_RANGE[1] * (N_LIGHTS + 1) + HOLD_RANGE[1]

    print("selftest OK -- %d lights, lights-out start, step %.2fs hold %.2fs (total %.2fs)"
          % (N_LIGHTS, step, hold, total))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="ISTech IT Arena race-start lights")
    ap.add_argument("--port", type=int, default=UDP_PORT)
    ap.add_argument("--host", default="255.255.255.255", help="UDP target (broadcast by default)")
    ap.add_argument("--once", action="store_true", help="run one sequence and exit")
    ap.add_argument("--seed", type=int, default=None, help="reproducible randomisation")
    ap.add_argument("--lights", type=int, default=N_LIGHTS, help="LED count (see issue #3)")
    ap.add_argument("--selftest", action="store_true", help="run checks without a socket")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        sys.exit(0)
    broadcast_loop(port=args.port, host=args.host, loop=not args.once,
                   seed=args.seed, n_lights=args.lights)
