"""
The character's armature, and which bone moves each bit of space. Every race has the same bones,
placed by its proportions (races.py); in voxels, y up from the soles, the character facing +z with
its left at +x. The human man's:

  head 30–47 (18 wide) · neck 29 · chest 22–29 · spine (belly) 17–22 · hips 13–17
  thigh 8–13 · shin 4–8 · foot 0–4, legs centred 3.5 out
  shoulder 8–9 out · upper arm 21–29 · forearm 15–21 · hand 10–15, arms centred 11.5 out

Ported from bellweather-v2 (commit 3ea05c9, `packages/assets/tools/characters/rig.ts`).
"""

import math
from types import SimpleNamespace

from defs import BONE_PARENT, BONES, HEIGHT
from races import DEFAULT, current

# One voxel, in metres: the human man's 48 voxels are the collision body's height. Every race's voxel is
# the same size.
VOXEL = HEIGHT / DEFAULT.height


def height_voxels() -> int:
    """The race's height in voxels, to the top of its hair."""
    return current().height


def fist(r, side: int) -> tuple[float, float, float]:
    """The middle of a fist (+1 the left), where anything held is held."""
    return (side * (r.arm_x + r.fist_at[0]), r.wrist + r.fist_at[1], r.fist_at[2])


def pole(r=None) -> SimpleNamespace:
    """
    Where a fishing pole lies in the right fist, in the bind pose: a rod one voxel thick through the
    fist's middle, pointing ahead (+z), its length going with the body's height. `x`, `y`: the rod's
    cell column and row. Along it (z, cells): the butt's end, the fist, then the reel, as far up the
    rod as the left fist can reach to crank it with the rod held across the body (a shoulders' width
    from the right fist), hanging under the rod, cranked from its left; then the rod's joints out to
    the tip. `axle`: the crank's joint, turning about x; `knob`: the middle of the crank's knob, from
    the axle, as the crank hangs straight down.
    """
    r = r or current()
    x = math.floor(-(r.arm_x + r.fist_at[0]))
    y = math.floor(r.wrist + r.fist_at[1])
    back = math.floor(r.fist_at[2] - r.fist_half[2])
    front = math.ceil(r.fist_at[2] + r.fist_half[2])
    butt = back - 3
    reel = math.floor(r.fist_at[2] + 1.3 * r.arm_x)
    rod = reel + 3
    tip = butt + round(1.15 * r.height)
    return SimpleNamespace(
        x=x,
        y=y,
        butt=butt,
        back=back,
        front=front,
        reel=reel,
        rod=rod,
        mid=rod + round(0.36 * (tip - rod)),
        top=rod + round(0.7 * (tip - rod)),
        tip=tip,
        axle=(x + 2.5, y - 2.5, reel + 0.5),
        knob=(1.0, -2.0, 0.0),
    )


def joints(r=None) -> dict:
    """Where each bone's joint is, in voxels, in the bind pose (standing, arms down)."""
    r = r or current()
    p = pole(r)
    line = (p.x + 0.5, p.y + 0.5)
    return {
        "root": (0, r.sole, 0),
        "hips": (0, r.belt, r.leg_z),
        "spine": (0, r.waist, r.leg_z),
        "chest": (0, r.chest, 0),
        "neck": (0, r.neck, 0),
        "head": (0, r.head_bottom + 0.5, 0),
        "shoulder_L": (r.arm_in, r.shoulder, 0),
        "upper_arm_L": (r.arm_x, r.shoulder, 0),
        "forearm_L": (r.arm_x, r.elbow, 0),
        "hand_L": (r.arm_x, r.wrist, 0),
        "shoulder_R": (-r.arm_in, r.shoulder, 0),
        "upper_arm_R": (-r.arm_x, r.shoulder, 0),
        "forearm_R": (-r.arm_x, r.elbow, 0),
        "hand_R": (-r.arm_x, r.wrist, 0),
        "thigh_L": (r.leg_x, r.hip, r.leg_z),
        "shin_L": (r.leg_x, r.knee, r.leg_z),
        "foot_L": (r.leg_x, r.ankle, r.leg_z),
        "thigh_R": (-r.leg_x, r.hip, r.leg_z),
        "shin_R": (-r.leg_x, r.knee, r.leg_z),
        "foot_R": (-r.leg_x, r.ankle, r.leg_z),
        "grip_L": fist(r, 1),
        "grip_R": (*line, r.fist_at[2]),
        "reel": p.axle,
        "rod_1": (*line, p.rod),
        "rod_2": (*line, p.mid),
        "rod_3": (*line, p.top),
        "rod_tip": (*line, p.tip + 1),
    }


BONE_INDEX = {b: i for i, b in enumerate(BONES)}


def bone_at(x: float, y: float, z: float) -> str:
    """
    The bone that moves the cell centred at (x, y, z): the space around the body cut up the way
    it's jointed, so the body and anything worn over it bend alike. Arms are anything `arm_in` out
    or more below the head, or beside it up to the shoulder's crown; legs anything below the hips;
    the neck only as wide as it is (the shoulders' slope either side of it is the chest's).
    """
    r = current()
    side = "L" if x >= 0 else "R"
    out = abs(x)
    if out >= r.arm_in and (y < r.head_bottom or (out >= r.head_half[0] and y < r.arm_top)):
        if out < r.arm_in + 1 and y >= r.shoulder_cap:
            return "shoulder_" + side
        if y >= r.elbow:
            return "upper_arm_" + side
        if y >= r.wrist:
            return "forearm_" + side
        return "hand_" + side
    if y < r.hip and out < r.arm_in + 1:
        if y < r.ankle:
            return "foot_" + side
        if y < r.knee:
            return "shin_" + side
        return "thigh_" + side
    if y < r.waist:
        return "hips"
    if y < r.chest:
        return "spine"
    # Beside the head up to the shoulder's crown is the chest's too: a brawny body's rises past the
    # head's bottom.
    beside_head = out >= r.head_half[0] and y < r.arm_top
    if y < r.neck or beside_head or (y < r.head_bottom and out > r.neck_half[0] + 1):
        return "chest"
    if y < r.head_bottom:
        return "neck"
    return "head"


def joined(a: str, b: str) -> bool:
    """Whether two bones are joined (one the other's parent), and so can share a vertex."""
    return a == b or BONE_PARENT[a] == b or BONE_PARENT[b] == a


_CORNERS: dict = {}


def corner_weights(bone: str, x: int, y: int, z: int) -> dict[str, float]:
    """
    How the vertex at corner (x, y, z) of a cell moved by `bone` is weighted: by the bones of the
    eight cells around the corner, those joined to `bone`. Inside a part all eight are its own
    (rigid); on a joint half are the next bone's, so the joint bends without opening.
    """
    k = (current().name, bone, x, y, z)
    hit = _CORNERS.get(k)
    if hit is not None:
        return hit
    count: dict[str, float] = {}
    for a in (-1, 0):
        for b in (-1, 0):
            for c in (-1, 0):
                near = bone_at(x + a + 0.5, y + b + 0.5, z + c + 0.5)
                if joined(bone, near):
                    count[near] = count.get(near, 0) + 1
    if bone not in count:
        count[bone] = 1
    total = sum(count.values())
    out = {b: n / total for b, n in count.items()}
    _CORNERS[k] = out
    return out


def joint_metres(b: str) -> tuple[float, float, float]:
    j = joints()[b]
    return (j[0] * VOXEL, j[1] * VOXEL, j[2] * VOXEL)
