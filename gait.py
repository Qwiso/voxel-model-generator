"""
How fast each clip carries a body over the ground: the speed of the foot that's down, measured by
posing the armature through the clip (forward kinematics, as the engine does it). Played at a
speed where the character moves exactly this fast, its planted foot stays put on the ground; any
faster or slower and it skates.

  python gait.py                       # a table, every body
  python gait.py --rust PATH           # the table as Rust, for the game (shared/src/gait.rs)

The clips are the same for every body, but the bones they turn are placed by each body's
proportions (races.py), so a longer leg carries a body further in a stride.
"""

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clips import duration, pose, quat  # noqa: E402
from defs import BONE_PARENT, BONES  # noqa: E402
from races import BODIES, use  # noqa: E402
from rig import VOXEL, joints  # noqa: E402

# How finely a cycle is sampled.
STEPS = 240
# The clips that go somewhere, and which way: the ground moves under a planted foot the opposite way.
MOVING = {"walk": 2, "run": 2, "backpedal": 2, "strafe_left": 0, "strafe_right": 0}


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def qrot(q, v):
    x, y, z, w = q
    # v' = q v q*
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    return (
        v[0] + w * tx + (y * tz - z * ty),
        v[1] + w * ty + (z * tx - x * tz),
        v[2] + w * tz + (x * ty - y * tx),
    )


def posed(clip: str, p: float) -> dict:
    """Every bone's place and turn in the character's space (metres) at `p` through `clip`."""
    j = {b: tuple(c * VOXEL for c in v) for b, v in joints().items()}
    turns, lift = pose(clip, p)
    out = {}
    for b in BONES:
        parent = BONE_PARENT[b]
        q = quat(turns.get(b, (0, 0, 0)))
        if parent is None:
            out[b] = (j[b], q)
            continue
        if b == "hips":
            local = tuple(j[b][i] + lift[i] - j[parent][i] for i in range(3))
        else:
            local = tuple(j[b][i] - j[parent][i] for i in range(3))
        pp, pq = out[parent]
        at = qrot(pq, local)
        out[b] = ((pp[0] + at[0], pp[1] + at[1], pp[2] + at[2]), qmul(pq, q))
    return out


def sole_points(side: str):
    """Points under a foot, relative to its joint (the ankle): heel, middle and toe."""
    from races import current

    r = current()
    dy = (r.sole - r.ankle) * VOXEL
    front = (r.foot_z + r.foot_half[1] - r.leg_z) * VOXEL
    back = (r.foot_z - r.foot_half[1] - r.leg_z) * VOXEL
    mid = (front + back) / 2
    return [(0, dy, back), (0, dy, mid), (0, dy, front)]


def ground_speed(clip: str) -> float:
    """
    Metres a second at playback speed 1: how fast a foot slides under the body while it's on the
    ground (its sole touching it), both feet's travel over the time they're down.
    """
    T = duration(clip)
    axis = MOVING[clip]
    pts = {s: sole_points(s) for s in ("L", "R")}

    def feet(p):
        bones = posed(clip, p)
        out = {}
        for s in ("L", "R"):
            at, q = bones["foot_" + s]
            ws = [qrot(q, v) for v in pts[s]]
            low = min(at[1] + w[1] for w in ws)
            mid = ws[1]
            out[s] = (low, (at[0] + mid[0], at[1] + mid[1], at[2] + mid[2]))
        return out

    moved = 0.0
    down = 0
    prev = feet(0)
    for i in range(1, STEPS + 1):
        cur = feet(i / STEPS)
        for s in ("L", "R"):
            if cur[s][0] < 1e-5 and prev[s][0] < 1e-5:
                moved += abs(cur[s][1][axis] - prev[s][1][axis])
                down += 1
        prev = cur
    return moved / (down / STEPS * T) if down else 0.0


def ground_slip(clip: str) -> float:
    """The worst a planted foot moves the wrong way or sideways, metres a second: should be nothing."""
    T = duration(clip)
    axis = MOVING[clip]
    pts = sole_points("L")
    worst = 0.0
    prev = None
    for i in range(STEPS + 1):
        bones = posed(clip, i / STEPS)
        at, q = bones["foot_L"]
        ws = [qrot(q, v) for v in pts]
        low = min(at[1] + w[1] for w in ws)
        mid = (at[0] + ws[1][0], at[1] + ws[1][1], at[2] + ws[1][2])
        if prev is not None and low < 1e-5 and prev[0] < 1e-5:
            for k in range(3):
                if k != axis:
                    worst = max(worst, abs(mid[k] - prev[1][k]) * STEPS / T)
        prev = (low, mid)
    return worst


def measure() -> dict:
    out = {}
    for name in BODIES:
        use(name)
        out[name] = {c: ground_speed(c) for c in MOVING}
    return out


def rust(table: dict) -> str:
    lines = [
        "//! How fast each clip carries each body over the ground, metres a second at playback speed 1:",
        "//! play a clip at (speed over ground ÷ this) and the planted foot stays put. Measured from the",
        "//! models by `tools/characters/gait.py`; don't edit, run",
        "//! `python tools/characters/gait.py --rust shared/src/gait.rs` after changing a body or a clip.",
        "",
        "/// (body, [(clip, metres a second)]), a body being `<race>_<sex>` as its model folder's named.",
        "pub const GROUND_SPEEDS: &[(&str, &[(&str, f32)])] = &[",
    ]
    for body, speeds in table.items():
        inner = ", ".join(f'("{c}", {v:.3f})' for c, v in speeds.items())
        lines.append(f'    ("{body}", &[{inner}]),')
    lines.append("];")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rust", help="write the table as Rust here")
    args = ap.parse_args()
    table = measure()
    if args.rust:
        with open(args.rust, "w", newline="\n") as f:
            f.write(rust(table))
        print(f"Wrote {args.rust}.")
        return
    print(f"{'body':16}" + "".join(f"{c:>14}" for c in MOVING))
    for body, speeds in table.items():
        use(body)
        slip = max(ground_slip(c) for c in MOVING)
        print(f"{body:16}" + "".join(f"{v:14.2f}" for v in speeds.values()) + f"   slip {slip:.3f}")


if __name__ == "__main__":
    main()
