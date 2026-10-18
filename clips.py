"""
The character's animations, keyed in code: each a pose for every moment of it (bones turned about
the character's own axes, which the bind pose leaves them aligned to; the hips moved), sampled into
glTF clips. The angles' signs, with the character facing +z and its left at +x: about x, negative
swings a limb forward and positive tips the body forward; about z, positive takes a left limb out to
the side (negative a right one).

The gaits (walk, run, backpedal, strafing) are built from where the feet go, not from angles: each
foot is planted on the ground and slides back under the body at exactly the gait's speed while it's
down, then lifts and swings forward to plant again, and the legs are bent to reach it (two-bone IK,
with this body's thigh and shin). So played at the speed the character moves (SPEEDS), a planted
foot stays put: nothing skates. A body's cadence goes with the root of its leg's length, as an
animal's does: a gnome scurries, an ogre lumbers, and both cover the ground at the same speed.

A loop's left foot comes down at 0 and its right at 0.5; the footsteps are counted there. Strafing
is the exception: the leading foot comes down at 0 and the trailing one closes up after it at
SIDESTEP_TRAIL, then the body flies.

Ported from bellweather-v2 (commit 3ea05c9, `packages/assets/tools/characters/clips.ts`); the gaits
are new.
"""

import math

from defs import BONE_PARENT, BONES, CLIP_NAMES, CLIPS, MARKS, REEL_BLEND
from races import current
from rig import joints, pole
from voxels import js_round

TAU = math.pi * 2

# Keys a second, sampled; linear between them is smooth enough at this rate.
RATE = 30


def _add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]] if a else b


def arms_rest(t: dict, out: float = 0.1, bend: float = -0.18) -> None:
    """The arms' rest: a little out from the sides and bent at the elbow, so they read as arms."""
    t["upper_arm_L"] = _add(t.get("upper_arm_L"), [0, 0, out])
    t["upper_arm_R"] = _add(t.get("upper_arm_R"), [0, 0, -out])
    t["forearm_L"] = _add(t.get("forearm_L"), [bend, 0, 0])
    t["forearm_R"] = _add(t.get("forearm_R"), [bend, 0, 0])


# The gaits: how fast each carries a body (m/s; the game moves characters at these, see
# shared/src/lib.rs), how long a cycle takes the human body (others' go with the root of their leg's
# length), how much of a cycle each foot is down at most (less leaves a moment both are off the
# ground: a run's flight), and how far the hips sink to give the legs their reach, as a share of the
# leg.
SPEEDS = {"walk": 0.8, "run": 4.5, "backpedal": 2.6, "strafe_left": 2.8, "strafe_right": 2.8}
CYCLES = {"walk": 0.85, "run": 0.42, "backpedal": 0.56, "strafe_left": 0.42, "strafe_right": 0.42}
DUTY = {"walk": 0.6, "run": 0.32, "backpedal": 0.42, "strafe_left": 0.3, "strafe_right": 0.3}
CROUCH = {"walk": 0.08, "run": 0.22, "backpedal": 0.16, "strafe_left": 0.2, "strafe_right": 0.2}
# Where in a sidestep's cycle the trailing foot comes down, after the leading one at 0.
SIDESTEP_TRAIL = 0.25
# The human body's leg, ankle to hip, voxels.
HUMAN_LEG = 9
VOXEL = 1.8 / 48


def leg_length(r=None) -> int:
    r = r or current()
    return r.hip - r.ankle


def duration(clip: str) -> float:
    """How long a clip lasts on the body being built, seconds."""
    if clip in SPEEDS:
        return CYCLES[clip] * math.sqrt(leg_length() / HUMAN_LEG)
    return CLIPS[clip][0]


def qx(a):
    return (math.sin(a / 2), 0.0, 0.0, math.cos(a / 2))


def qz(a):
    return (0.0, 0.0, math.sin(a / 2), math.cos(a / 2))


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def leg_ik(t: dict, side: str, out: float, down: float, ahead: float, toe: float) -> None:
    """
    Turns a leg so its ankle is `out` (to the character's left), `down` and `ahead` of the hip joint
    (voxels), the knee bending forward, and the foot turned `toe` from level (positive drops the
    toe). Thigh, shin and foot get quaternions.
    """
    r = current()
    a, b = r.hip - r.knee, r.knee - r.ankle
    # Swing the leg's plane out to the side, then bend in it.
    swing = math.atan2(out, down)
    plane_down = math.hypot(out, down)
    d = min(math.hypot(plane_down, ahead), (a + b) * 0.9999)
    toward = math.atan2(ahead, plane_down)
    hip_bend = math.acos(max(-1, min(1, (a * a + d * d - b * b) / (2 * a * d))))
    knee = math.pi - math.acos(max(-1, min(1, (a * a + b * b - d * d) / (2 * a * b))))
    # About x, negative swings the leg forward; the knee in front of the line to the ankle.
    thigh = -(toward + hip_bend)
    t["thigh_" + side] = qmul(qz(swing), qx(thigh))
    t["shin_" + side] = qx(knee)
    # Level in the world (undoing the thigh and shin), then the toe's own turn.
    t["foot_" + side] = qmul(qmul(qx(-(thigh + knee)), qz(-swing)), qx(toe))


def smooth(u: float) -> float:
    return u * u * (3 - 2 * u)


def stride(clip: str):
    """
    A gait's numbers on this body: (cycle seconds, share of it a foot is down, how far a foot travels
    while it's down (voxels), how far the hips sink (voxels), how high a foot lifts (voxels)).
    """
    leg = leg_length()
    T = duration(clip)
    crouch = CROUCH[clip] * leg
    # As far as a foot can reach from the sunk hips, either side of under them, with a little spare.
    reach = math.sqrt(max(0.0, (leg * 0.985) ** 2 - (leg - crouch) ** 2))
    side = clip.startswith("strafe")
    most = reach if side else 2 * reach
    duty = DUTY[clip]
    travel = SPEEDS[clip] / VOXEL * duty * T
    if travel > most:
        if clip == "walk":
            # A walk always has a foot down: it goes slower instead.
            travel = most
        else:
            # Fly further between steps instead.
            duty = max(0.1, most / (SPEEDS[clip] / VOXEL * T))
            travel = SPEEDS[clip] / VOXEL * duty * T
    lift = {"walk": 0.16, "run": 0.4, "backpedal": 0.26}.get(clip, 0.3) * leg
    return T, duty, travel, crouch, lift


def bob(w: float, down: float, dip: float, rise: float) -> float:
    """
    How far the hips are above where they sink to, `w` through a bounce (0–1) whose first `down` of
    it has a foot on the ground: dipping while the feet take the weight (never higher, so a planted
    foot can always reach the ground), rising between.
    """
    if w < down:
        return -dip * math.sin(math.pi * w / down)
    return rise * math.sin(math.pi * (w - down) / (1 - down))


def foot_path(u: float, duty: float, travel: float, lift: float, back: bool):
    """
    Where a foot is (along the way of travel, up from the ground) and its toe's turn, `u` through
    its own cycle (0: coming down). Down, it slides back by `travel`; up, it swings forward again.
    """
    if u < duty:
        k = u / duty
        along = travel / 2 - travel * k
        return along, 0.0, 0.0
    k = (u - duty) / (1 - duty)
    along = -travel / 2 + travel * smooth(k)
    up = lift * math.sin(math.pi * k)
    # Heel up behind as it leaves the ground (forward), the toe down as it swings through.
    return along, up, (0.35 if not back else 0.15) * math.sin(math.pi * k)


def clear_toe(toe: float, up: float) -> float:
    """The toe's turn, eased off until neither end of the sole goes below the ground `up` over it."""
    r = current()
    f = r.ankle - r.sole
    ends = (r.foot_z + r.foot_half[1] - r.leg_z, r.foot_z - r.foot_half[1] - r.leg_z)
    for _ in range(40):
        if all(f + up - f * math.cos(toe) - e * math.sin(toe) >= 0.2 for e in ends):
            return toe
        toe *= 0.8
    return 0.0


def gait(clip: str, p: float, arm, elbow, lean, twist, back=False):
    """A forward gait (or a backward one): the feet on their paths, the arms against them, the body bobbing."""
    r = current()
    T, duty, travel, crouch, lift = stride(clip)
    dir = -1 if back else 1
    t: dict = {}
    # The hips lowest as a foot takes the weight, highest between.
    leg = leg_length()
    rise = (0.03 if clip == "walk" else 0.08) * leg
    hip_y = r.hip - crouch + bob((p % 0.5) * 2, min(1.0, 2 * duty), 0.04 * leg, rise)
    for side, shift in (("L", 0), ("R", 0.5)):
        along, up, toe = foot_path((p + 1 - shift) % 1, duty, travel, lift, back)
        down = hip_y - (r.ankle + up)
        leg_ik(t, side, 0, down, along * dir, clear_toe(toe, up) if up > 0 else 0.0)
    c = math.cos(TAU * p)
    t["upper_arm_L"] = [arm * c * dir, 0, 0]
    t["upper_arm_R"] = [-arm * c * dir, 0, 0]
    t["forearm_L"] = [-elbow - max(0, -c * dir) * elbow * 0.4, 0, 0]
    t["forearm_R"] = [-elbow - max(0, c * dir) * elbow * 0.4, 0, 0]
    arms_rest(t, 0.12, 0)
    # The twist's in the spine: the hips carry the legs, and stay square.
    t["spine"] = [lean * 0.5, twist * c * dir, 0]
    t["chest"] = [lean * 0.5, -twist * 2.2 * c * dir, 0]
    t["head"] = [-lean * 0.7, twist * 0.9 * c * dir, 0]
    return t, [0, (hip_y - r.hip) * VOXEL, 0]


def sidestep(clip: str, p: float, side: int):
    """
    Side-stepping toward `side` (+1 the character's left): the leading foot steps out and takes the
    weight, sliding in under the body, then the trailing one closes up and does the same on its
    side, and the body flies: one bounce a cycle, a gallop sideways. The feet never cross. Leaning
    into it, arms out.
    """
    r = current()
    T, duty, travel, crouch, lift = stride(clip)
    t: dict = {}
    leg = leg_length()
    hip_y = r.hip - crouch + bob(p, min(1.0, SIDESTEP_TRAIL + duty), 0.04 * leg, 0.1 * leg)
    lead, trail = ("L", "R") if side > 0 else ("R", "L")
    for leg, shift, outward in ((lead, 0, 1), (trail, SIDESTEP_TRAIL, -1)):
        u = (p + 1 - shift) % 1
        if u < duty:
            k = u / duty
            # The lead foot from out to under the hip; the trail from under the hip to out.
            off = travel * (1 - k) if outward > 0 else -travel * k
            up = 0.0
        else:
            k = smooth((u - duty) / (1 - duty))
            off = travel * k if outward > 0 else -travel * (1 - k)
            up = lift * math.sin(math.pi * (u - duty) / (1 - duty))
        down = hip_y - (r.ankle + up)
        leg_ik(t, leg, off * side, down, 0, 0)
    sway = math.cos(TAU * p)
    t["spine"] = [0.08, 0, -0.06 * side]
    t["chest"] = [0.08, 0, -0.04 * side + 0.03 * side * sway]
    t["upper_arm_L"] = [-0.35, 0, 0.25 + 0.1 * sway]
    t["upper_arm_R"] = [-0.35, 0, -0.25 - 0.1 * sway]
    t["forearm_L"] = [-1.0, 0, 0]
    t["forearm_R"] = [-1.0, 0, 0]
    t["head"] = [-0.08, 0, 0.08 * side]
    return t, [0, (hip_y - r.hip) * VOXEL, 0]


def pose(clip: str, p: float):
    """The pose of `clip` at `p` through it (0–1): (turns by bone, the hips' lift in metres)."""
    if clip == "idle":
        breath = math.sin(TAU * p)
        shift = math.sin(TAU * p + 1)
        t = {
            "spine": [0.02 * breath, 0, 0.015 * shift],
            "chest": [-0.03 * breath, 0, -0.01 * shift],
            "neck": [0.015 * breath, 0, 0],
            "head": [0.02 * breath, 0.06 * math.sin(TAU * p * 2 + 0.5) * 0.5, 0.02 * shift],
            "shoulder_L": [0, 0, 0.03 * breath],
            "shoulder_R": [0, 0, -0.03 * breath],
            "thigh_L": [-0.04, 0, 0.04],
            "thigh_R": [0.05, 0, -0.04],
            "shin_L": [0.08, 0, 0],
            "shin_R": [0.04, 0, 0],
            "foot_L": [-0.04, 0, -0.04],
            "foot_R": [-0.09, 0, 0.04],
        }
        arms_rest(t, 0.1 + 0.02 * breath, -0.2)
        return t, [0.01 * shift, 0.008 * breath - 0.006, 0]
    if clip == "walk":
        return gait(clip, p, arm=0.42, elbow=0.2, lean=0.04, twist=0.08)
    if clip == "run":
        return gait(clip, p, arm=0.8, elbow=1.1, lean=0.22, twist=0.12)
    if clip == "backpedal":
        return gait(clip, p, arm=0.35, elbow=0.5, lean=-0.06, twist=0.06, back=True)
    if clip == "strafe_left":
        return sidestep(clip, p, 1)
    if clip == "strafe_right":
        return sidestep(clip, p, -1)
    if clip == "jump":
        # Springing up: crouched at the start, legs tucking and arms rising.
        k = min(1, p * 1.4)
        t = {
            "spine": [0.1 * (1 - k), 0, 0],
            "chest": [-0.08 * k, 0, 0],
            "head": [-0.1 * k, 0, 0],
            "thigh_L": [-0.9 * k, 0, 0.06],
            "thigh_R": [-0.3 * k, 0, -0.06],
            "shin_L": [1.3 * k, 0, 0],
            "shin_R": [0.7 * k, 0, 0],
            "foot_L": [-0.3 * k, 0, 0],
            "foot_R": [0.2 * k, 0, 0],
            "upper_arm_L": [-0.9 * k, 0, 0.5 * k],
            "upper_arm_R": [-0.6 * k, 0, -0.6 * k],
            "forearm_L": [-0.6, 0, 0],
            "forearm_R": [-0.8, 0, 0],
        }
        arms_rest(t, 0.1, 0)
        return t, [0, 0, 0]
    if clip == "fall":
        w = math.sin(TAU * p)
        t = {
            "chest": [-0.1, 0, 0],
            "head": [-0.15, 0, 0],
            "thigh_L": [-0.55 + 0.08 * w, 0, 0.08],
            "thigh_R": [-0.1 - 0.08 * w, 0, -0.08],
            "shin_L": [0.8, 0, 0],
            "shin_R": [0.5, 0, 0],
            "foot_L": [-0.2, 0, 0],
            "foot_R": [-0.1, 0, 0],
            "upper_arm_L": [-0.5, 0, 0.9 + 0.12 * w],
            "upper_arm_R": [-0.5, 0, -0.9 + 0.12 * w],
            "forearm_L": [-0.5, 0, 0],
            "forearm_R": [-0.5, 0, 0],
        }
        return t, [0, 0, 0]
    if clip.startswith("fish_"):
        return fishing(clip, p)
    if clip == "land":
        # Down into a crouch and up again, the feet flat.
        k = math.sin(math.pi * min(1, p * 1.15))
        t = {
            "spine": [0.25 * k, 0, 0],
            "chest": [0.1 * k, 0, 0],
            "head": [-0.3 * k, 0, 0],
            "thigh_L": [-0.75 * k, 0, 0.06],
            "thigh_R": [-0.75 * k, 0, -0.06],
            "shin_L": [1.3 * k, 0, 0],
            "shin_R": [1.3 * k, 0, 0],
            "foot_L": [-0.55 * k, 0, 0],
            "foot_R": [-0.55 * k, 0, 0],
            "upper_arm_L": [-0.3 * k, 0, 0.3 * k],
            "upper_arm_R": [-0.3 * k, 0, -0.3 * k],
        }
        arms_rest(t, 0.1, -0.2 - 0.4 * k)
        return t, [0, -0.16 * k, 0]
    raise ValueError(clip)


# --- Fishing ------------------------------------------------------------------------------------
#
# The angler stands side-on to the water (which is ahead, +z), turned to its right, its left shoulder
# to the water, the rod held across its front: the right fist at the butt and the left on the reel's
# crank further up (rig.pole), which is as far apart as a chibi's short arms can hold anything. The
# pose is built from where things go rather than from angles: where the right fist is and which way
# the rod points (relative to the chest, so the rod stays across it however the body turns), where
# the left fist is (on the crank, or free), how far the rod bends; the arms reach there by two-bone
# IK. Each clip is a few such poses, keyed and eased between.


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _plus(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _times(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    n = math.sqrt(_dot(a, a))
    return _times(a, 1 / n) if n > 1e-9 else (0.0, 0.0, 0.0)


def qy(a):
    return (0.0, math.sin(a / 2), 0.0, math.cos(a / 2))


def qconj(q):
    return (-q[0], -q[1], -q[2], q[3])


def qrot(q, v):
    """`v` turned by `q`."""
    x, y, z, w = q
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    return (
        v[0] + w * tx + (y * tz - z * ty),
        v[1] + w * ty + (z * tx - x * tz),
        v[2] + w * tz + (x * ty - y * tx),
    )


def qaxis(axis, a):
    s = math.sin(a / 2)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(a / 2))


def qbasis(x, y, z):
    """The turn that takes the axes to `x`, `y` and `z` (orthonormal, right-handed)."""
    m00, m10, m20 = x
    m01, m11, m21 = y
    m02, m12, m22 = z
    tr = m00 + m11 + m22
    if tr > 0:
        s = math.sqrt(tr + 1) * 2
        return ((m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, s / 4)
    if m00 > m11 and m00 > m22:
        s = math.sqrt(1 + m00 - m11 - m22) * 2
        return (s / 4, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s)
    if m11 > m22:
        s = math.sqrt(1 + m11 - m00 - m22) * 2
        return ((m01 + m10) / s, s / 4, (m12 + m21) / s, (m02 - m20) / s)
    s = math.sqrt(1 + m22 - m00 - m11) * 2
    return ((m02 + m20) / s, (m12 + m21) / s, s / 4, (m10 - m01) / s)


def qmix(a, b, k):
    """Between two turns, `k` of the way (normalized lerp, the short way round)."""
    if sum(a[i] * b[i] for i in range(4)) < 0:
        b = tuple(-c for c in b)
    q = tuple(a[i] + (b[i] - a[i]) * k for i in range(4))
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q)


def posed(t: dict, lift) -> dict:
    """Every bone's place (voxels, the character's space) and turn, with the turns `t` and the hips moved by `lift` (voxels)."""
    j = joints()
    out = {}
    for b in BONES:
        parent = BONE_PARENT[b]
        q = quat(t.get(b, (0, 0, 0)))
        if parent is None:
            out[b] = (j[b], q)
            continue
        local = _sub(j[b], j[parent])
        if b == "hips":
            local = _plus(local, lift)
        pp, pq = out[parent]
        out[b] = (_plus(pp, qrot(pq, local)), qmul(pq, q))
    return out


def arm_ik(t: dict, at: dict, side: str, wrist, elbow) -> tuple:
    """
    Turns the arm on `side` so its wrist is at `wrist` (or as near as it reaches), the elbow out
    toward `elbow` (a direction), bending only at the elbow as the forearm does. `at` is the posed
    body (posed). Returns the forearm's turn, in the character's space.
    """
    r = current()
    a, b = r.shoulder - r.elbow, r.elbow - r.wrist
    root, _ = at["upper_arm_" + side]
    _, shoulder = at["shoulder_" + side]
    to = _sub(wrist, root)
    d = max(abs(a - b) + 1e-3, min(math.sqrt(_dot(to, to)), (a + b) * 0.999))
    ahead = _unit(to)
    out = _unit(_sub(elbow, _times(ahead, _dot(elbow, ahead))))
    ca = (a * a + d * d - b * b) / (2 * a * d)
    upper = _plus(_times(ahead, ca), _times(out, math.sqrt(max(0.0, 1 - ca * ca))))
    fore = _unit(_sub(_times(ahead, d), _times(upper, a)))
    # The upper arm's own axes: down along it, its front the way the forearm bends.
    front = _sub(fore, _times(upper, _dot(fore, upper)))
    front = _unit(front) if _dot(front, front) > 1e-8 else _times(out, -1)
    down = _times(upper, -1)
    q_upper = qbasis(_cross(down, front), down, front)
    t["upper_arm_" + side] = qmul(qconj(shoulder), q_upper)
    bend = math.acos(max(-1.0, min(1.0, _dot(upper, fore))))
    t["forearm_" + side] = qx(-bend)
    return qmul(q_upper, qx(-bend))


def hand_to(t: dict, lift, side: str, fist, turn, elbow) -> None:
    """The fist on `side` (its middle, grip_<side>) at `fist`, turned `turn` (the character's space)."""
    j = joints()
    off = _sub(j["grip_" + side], j["hand_" + side])
    fore = arm_ik(t, posed(t, lift), side, _sub(fist, qrot(turn, off)), elbow)
    t["hand_" + side] = qmul(qconj(fore), turn)


# The rod's frame across the chest, before it's raised: the rod (the right hand's +z) along the
# chest's left (+x), the reel hanging under it, the crank toward the body.
ACROSS = qy(math.pi / 2)
# The line's pull on the rod's tip, in the character's space: out ahead to the water, a little down.
PULL = _unit((0.0, -0.35, 1.0))
# A fish in the left fist hangs straight down, its flank to the camera (behind the character).
HANG = qbasis((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))

# The angler's pose, as numbers that key and ease between: everything a fishing clip moves.
#   turn       the body's turn from facing the water, about y (negative: to its right)
#   sink       how far the hips sink, a share of the leg; sway: how far they shift (left, ahead) in
#              the body's own frame, shares of the leg
#   spine, chest, head   their turns (about x, y, z), as in the other clips
#   grip       the right fist, in the chest's frame: out (a share of the arms' spacing; -1 is the right
#              arm's line), up (from the wrist's row, 0, to the shoulder's, 1) and ahead (a share of
#              the arm's reach)
#   rise, reach, roll    the rod: raised from level across the chest (rad; past pi/2 it's back over
#              the right shoulder), swung ahead of the chest, turned about itself
#   bend       the rod's bend up and down (positive: the tip down, the way it's raised from); whip:
#              side to side (positive: the tip back, the way it's swung from); strain: bent toward
#              the line's pull
#   crank      the left fist on the reel's crank (1) or where `free` puts it (0), as `grip` does;
#              hang: its fist turned so a fish hangs from it
#   step       each foot's lift (left, right), a share of the leg
REST = {
    "turn": -0.75,
    "sink": 0.07,
    "sway": (0.0, 0.0),
    "spine": (0.06, -0.15, 0.0),
    "chest": (0.04, -0.17, 0.0),
    "head": (0.12, 1.15, 0.0),
    "grip": (-0.4, 0.3, 0.85),
    "rise": 0.3,
    "reach": 0.8,
    "roll": 0.0,
    "bend": 0.0,
    "whip": 0.0,
    "strain": 0.04,
    "crank": 1.0,
    "free": (1.0, 0.1, 0.4),
    "hang": 0.0,
    "step": (0.0, 0.0),
}


def eased(p: float, keys: list) -> dict:
    """The pose `p` of the way through a clip keyed [(at, changes to REST)], eased between keys."""
    full = []
    for at, k in keys:
        full.append((at, {**REST, **k}))
    if p <= full[0][0]:
        return full[0][1]
    for (a, ka), (b, kb) in zip(full, full[1:]):
        if p <= b:
            u = smooth((p - a) / (b - a)) if b > a else 1.0
            out = {}
            for name, va in ka.items():
                vb = kb[name]
                if isinstance(va, tuple):
                    out[name] = tuple(x + (y - x) * u for x, y in zip(va, vb))
                else:
                    out[name] = va + (vb - va) * u
            return out
    return full[-1][1]


def left_hand(t: dict, lift, k: dict, crank_turn: float, free) -> tuple:
    """
    Bends the rod and puts the left fist on the crank's knob (or at `free`, as much as `k` says).
    Returns where the fist was meant to go and where it got to.
    """
    t["reel"] = qx(crank_turn)
    at = posed(t, lift)
    _, chest = at["chest"]
    _, grip = at["grip_R"]
    # The rod bends toward the line's pull along it, and in its own plane, the tip most.
    pull = qrot(qconj(grip), PULL)
    axis = _unit(_cross((0.0, 0.0, 1.0), pull))
    for b, share in (("rod_1", 0.22), ("rod_2", 0.33), ("rod_3", 0.45)):
        t[b] = qmul(qaxis(axis, k["strain"] * share), qmul(qx(k["bend"] * share), qy(k["whip"] * share)))
    # On the knob, the fist's grip is along it; free, the fist carries on the line of the arm, its
    # knuckles ahead.
    reel_at, reel = at["reel"]
    knob = _plus(reel_at, qrot(reel, pole().knob))
    shoulder, _ = at["upper_arm_L"]
    fist = _plus(_times(knob, k["crank"]), _times(free, 1 - k["crank"]))
    along = qrot(reel, (1.0, 0.0, 0.0))
    hangs = _unit(_sub(fist, shoulder))
    down = _unit(_sub(hangs, _times(along, _dot(hangs, along))))
    on_knob = qbasis(_cross(_times(down, -1), along), _times(down, -1), along)
    ahead = qrot(chest, (0.0, 0.0, 1.0))
    front = _unit(_sub(ahead, _times(hangs, _dot(ahead, hangs))))
    loose = qbasis(_cross(_times(hangs, -1), front), _times(hangs, -1), front)
    turn = qmix(qmix(loose, on_knob, k["crank"]), HANG, k["hang"])
    hand_to(t, lift, "L", fist, turn, qrot(chest, (1.0, -0.8, -0.6)))
    return fist, posed(t, lift)["grip_L"][0]


def angler(k: dict, crank_turn: float = 0.0):
    """The pose `k` (as REST has it), the reel's crank turned `crank_turn`: (turns by bone, the hips' lift in metres)."""
    r = current()
    leg = leg_length()
    t: dict = {"root": qy(k["turn"]), "spine": k["spine"], "chest": k["chest"], "head": k["head"]}
    t["neck"] = (k["head"][0] * 0.3, k["head"][1] * 0.25, 0)
    # The feet planted apart, the left (to the water) ahead; the hips sunk and swayed over them.
    lift = (k["sway"][0] * leg, -k["sink"] * leg, k["sway"][1] * leg)
    feet = {"L": (r.leg_x + 0.2 * leg, r.ankle, r.leg_z + 0.28 * leg), "R": (-r.leg_x - 0.2 * leg, r.ankle, r.leg_z - 0.1 * leg)}
    j = joints()
    for (side, foot), up in zip(feet.items(), k["step"]):
        hip = _plus(j["thigh_" + side], lift)
        leg_ik(t, side, foot[0] - hip[0], hip[1] - foot[1] - up * leg, foot[2] - hip[2], 0.0)
    chest_at, chest = posed(t, lift)["chest"]

    def in_chest(g):
        """A place given as `grip` gives it, in the character's space."""
        reach = r.shoulder - r.wrist - r.fist_at[1]
        local = (g[0] * r.arm_x, r.wrist + g[1] * (r.shoulder - r.wrist), g[2] * reach)
        return _plus(chest_at, qrot(chest, _sub(local, j["chest"])))

    # The right fist round the rod; then the left on the crank, the right moved over where the left
    # can't reach it (a short arm hauls the rod in closer).
    rod = qmul(chest, qmul(qy(-k["reach"]), qmul(qz(k["rise"]), qmul(ACROSS, qz(k["roll"])))))
    grip = in_chest(k["grip"])
    for _ in range(8):
        hand_to(t, lift, "R", grip, rod, qrot(chest, (-1.0, -0.6, -0.5)))
        fist, held = left_hand(t, lift, k, crank_turn, in_chest(k["free"]))
        miss = _sub(fist, held)
        if _dot(miss, miss) < 0.04 or k["crank"] < 0.5:
            break
        grip = _sub(grip, _times(miss, k["crank"]))
    return t, _times(lift, VOXEL)


def reeling(clip: str, p: float):
    """Cranking the reel round once, holding the rod at `lean` and `strength` (REEL_BLEND)."""
    lean, strength = REEL_BLEND[clip]
    hard = strength
    shake = math.sin(TAU * 3 * p) * hard
    k = {
        **REST,
        "turn": -0.75 - 0.08 * hard,
        "sink": 0.07 + 0.1 * hard,
        "sway": (0.06 * lean, -0.08 * hard - 0.04 * lean),
        "spine": (0.06 + 0.1 * lean - 0.04 * hard, -0.15 - 0.28 * lean, 0.12 * hard),
        "chest": (0.04 + 0.08 * lean, -0.17 - 0.3 * lean, 0.1 * hard + 0.01 * shake),
        "head": (0.08 - 0.1 * hard, 1.15 + 0.35 * lean, -0.05 * hard),
        "grip": (-0.4 + 0.05 * hard, 0.3 + 0.12 * hard, 0.85 - 0.1 * hard),
        "rise": 0.35 + 0.2 * hard,
        "strain": 0.15 + 0.85 * hard + 0.05 * shake,
    }
    # The crank turns toward the angler at the top, as a reel cranked with the left hand does.
    return angler(k, TAU * p)


def fishing(clip: str, p: float):
    """The pose of a fishing clip `p` of the way through it."""
    if clip in REEL_BLEND:
        return reeling(clip, p)
    if clip == "fish_wait":
        # At ease, the rod low, breathing; halfway, a twitch of the rod to work the bait.
        breath = math.sin(TAU * p)
        twitch = math.exp(-(((p - 0.55) / 0.035) ** 2))
        k = {
            "rise": 0.28 + 0.1 * twitch,
            "bend": -0.1 * twitch,
            "spine": (0.06 + 0.015 * breath, -0.15, 0.0),
            "chest": (0.04 - 0.02 * breath, -0.17, 0.0),
            "head": (0.12 + 0.02 * breath, 1.15 + 0.05 * math.sin(TAU * p * 2), 0.0),
            "sink": 0.07 + 0.008 * breath,
        }
        return angler({**REST, **k}, 0.0)
    if clip == "fish_cast":
        # A side cast: the rod drawn back low round the right side, then swept across the front and
        # out over the water, whipping as it stops.
        go = MARKS[clip]["release"]
        back = {"crank": 0.0, "free": (1.1, 0.5, 0.6), "rise": 0.25, "reach": 2.3, "grip": (-1.15, 0.4, 0.2),
                "spine": (0.0, -0.3, 0.06), "chest": (-0.02, -0.35, 0.08), "head": (0.08, 1.35, 0.0),
                "sway": (0.0, -0.1), "sink": 0.06}  # fmt: skip
        throw = {"crank": 0.0, "free": (0.9, 0.2, 0.3), "rise": 0.22, "grip": (-0.55, 0.45, 0.95),
                 "spine": (0.1, 0.05, -0.06), "chest": (0.08, 0.05, -0.08), "head": (0.15, 1.0, 0.0),
                 "sway": (0.0, 0.1), "sink": 0.1}  # fmt: skip
        k = eased(
            p,
            [
                (0.0, {}),
                (0.1, {"crank": 0.0, "free": (1.0, 0.2, 0.5), "reach": 1.3, "grip": (-0.6, 0.35, 0.7)}),
                (0.3, {**back, "whip": 0.12}),
                (0.35, {**back, "reach": 2.4, "whip": -0.15}),
                (go, {**throw, "reach": 0.9, "whip": -0.55}),
                (go + 0.07, {**throw, "reach": 0.5, "whip": 0.35}),
                (go + 0.15, {**throw, "reach": 0.45, "whip": -0.2}),
                (go + 0.23, {**throw, "reach": 0.5, "whip": 0.1}),
                (go + 0.33, {"reach": 0.6, "whip": -0.04, "crank": 0.6}),
                (1.0, {}),
            ],
        )
        return angler(k, 0.0)
    if clip == "fish_land":
        leap, catch = MARKS[clip]["leap"], MARKS[clip]["catch"]
        hard = {"turn": -0.83, "sink": 0.17, "sway": (0.0, -0.08), "spine": (0.02, -0.15, 0.12),
                "chest": (0.04, -0.17, 0.1), "head": (-0.02, 1.15, -0.05), "grip": (-0.35, 0.65, 0.7),
                "rise": 0.55, "strain": 1.0}  # fmt: skip
        # Swept back hard round the right side, low, to haul it out.
        heave = {**hard, "rise": 0.45, "reach": 1.9, "grip": (-1.05, 0.5, 0.35), "spine": (-0.04, -0.3, 0.12),
                 "chest": (-0.06, -0.35, 0.12), "head": (-0.05, 1.2, 0.0), "sway": (0.0, -0.14), "sink": 0.12}  # fmt: skip
        caught = {"crank": 0.0, "hang": 1.0, "free": (0.85, 0.75, 0.75), "strain": 0.25, "head": (0.1, 0.9, 0.0)}
        k = eased(
            p,
            [
                (0.0, hard),
                (leap, {**hard, "reach": 1.2, "strain": 1.0}),
                (0.32, {**heave, "strain": 0.4, "crank": 0.0, "free": (1.15, 1.0, 0.8)}),
                (catch, {**heave, **caught, "reach": 1.8}),
                (0.78, {**heave, **caught, "reach": 1.6, "free": (0.7, 0.55, 0.6), "sink": 0.09}),
                (1.0, {**caught, "rise": 0.5, "reach": 1.4, "free": (0.7, 0.5, 0.6), "grip": (-0.5, 0.6, 0.6),
                       "spine": (0.04, -0.15, 0.04), "chest": (0.04, -0.15, 0.0), "sway": (0.0, 0.0), "sink": 0.08}),
            ],
        )  # fmt: skip
        return angler(k, 0.0)
    if clip == "fish_show":
        stow = MARKS[clip]["stow"]
        held = {"crank": 0.0, "hang": 1.0, "free": (0.7, 0.5, 0.6), "strain": 0.0, "rise": 0.5, "reach": 1.4, "grip": (-0.5, 0.6, 0.6),
                "spine": (0.04, -0.15, 0.04), "chest": (0.04, -0.15, 0.0), "head": (0.1, 0.9, 0.0), "sink": 0.08}  # fmt: skip
        # Round to face the camera, the fish up high in the left fist, the rod held out in front in the right.
        proud = {**held, "turn": -math.pi, "spine": (-0.04, 0.0, 0.0), "chest": (-0.06, 0.0, -0.04),
                 "head": (-0.08, 0.25, 0.1), "grip": (-0.8, 0.45, 0.75), "rise": 0.6, "reach": 1.8,
                 "free": (1.25, 1.95, 0.35), "sink": 0.04}  # fmt: skip
        k = eased(
            p,
            [
                (0.0, held),
                (0.1, {**held, "turn": -1.45, "step": (0.12, 0.0)}),
                (0.18, {**held, "turn": -2.2, "step": (0.0, 0.12), "spine": (0.0, -0.1, 0.0), "chest": (0.0, -0.1, 0.0)}),
                (0.28, {**proud, "step": (0.06, 0.0)}),
                (0.36, proud),
                (0.46, {**proud, "free": (1.3, 2.1, 0.4), "sink": 0.09, "head": (-0.12, 0.35, 0.16)}),
                (0.56, proud),
                (0.66, {**proud, "free": (1.3, 2.1, 0.4), "sink": 0.09, "head": (-0.12, 0.3, 0.14)}),
                (0.72, proud),
                (stow, {**proud, "free": (1.05, -0.15, 0.1), "hang": 0.3, "head": (0.1, 0.1, 0.0)}),
                (0.86, {**proud, "free": (0.95, 0.0, 0.2), "hang": 0.0, "turn": -2.2, "step": (0.12, 0.0),
                        "spine": (0.0, -0.2, 0.0), "chest": (0.0, -0.2, 0.0), "rise": 0.5, "reach": 1.2, "grip": (-0.5, 0.4, 0.7)}),
                (0.93, {"turn": -1.1, "step": (0.0, 0.12), "crank": 0.4}),
                (1.0, {}),
            ],
        )  # fmt: skip
        return angler(k, 0.0)
    raise ValueError(clip)


def quat(e) -> tuple[float, float, float, float]:
    """
    A turn as a quaternion (x, y, z, w): about x, then y, then z, each about the bone's own axes (or
    a quaternion already, as the gaits' legs are).
    """
    if len(e) == 4:
        return tuple(e)
    x, y, z = e
    cx, sx = math.cos(x / 2), math.sin(x / 2)
    cy, sy = math.cos(y / 2), math.sin(y / 2)
    cz, sz = math.cos(z / 2), math.sin(z / 2)
    # q = qx · qy · qz
    return (
        sx * cy * cz + cx * sy * sz,
        cx * sy * cz - sx * cy * sz,
        cx * cy * sz + sx * sy * cz,
        cx * cy * cz - sx * sy * sz,
    )


def sampled(name: str, hips_at):
    """
    A clip sampled at RATE: (times, [(bone, 'rotation' | 'translation', values)]). Every bone a pose
    turns gets a rotation channel, in BONES order; the hips always get a translation.
    """
    duration_s = duration(name)
    frames = max(2, js_round(duration_s * RATE) + 1)
    times = [(i / (frames - 1)) * duration_s for i in range(frames)]
    poses = [pose(name, i / (frames - 1)) for i in range(frames)]
    channels = []
    for b in BONES:
        if not any(b in t for t, _ in poses):
            continue
        channels.append((b, "rotation", [c for t, _ in poses for c in quat(t.get(b, (0, 0, 0)))]))
    channels.append(("hips", "translation", [hips_at[i] + lift[i] for _, lift in poses for i in range(3)]))
    return times, channels


__all__ = ["CLIP_NAMES", "SPEEDS", "duration", "pose", "quat", "sampled"]
