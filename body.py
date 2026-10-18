"""
A body, sculpted in voxels from its proportions (races.py): every race has a man's and a woman's.
The human man's is stocky, big-headed (the head is two fifths of the height), short in the leg, with
block hands and heavy feet. Every body wears plain linen and wool underneath whatever's put on it.
Characters with the same body differ from the neck up (face, hair, beard, colours), so every piece
of gear built for a body fits all of them; and gear is built out from the body's own surface, so it
fits every body.

The face is in pieces a player picks from: eyes, brows, nose and mouth. The skull (`head`) leaves
holes for the eyes and the mouth, which each eye and mouth style fills; brows and noses stand
proud of it. A race adds its own to the head: an orc's tusks and jutting jaw, the undead's rot.

Ported from bellweather-v2 (commit 3ea05c9, `packages/assets/tools/characters/body.ts`).
"""

import math

from defs import BEARD_STYLES, BROW_STYLES, EYE_STYLES, HAIR_STYLES, MOUTH_STYLES, NOSE_STYLES
from voxels import (
    Grid,
    Shape,
    Voxel,
    both,
    capsule,
    ellipsoid,
    fill,
    hash3,
    intersect,
    jitter,
    mix,
    noise3,
    round_box,
    shade,
    shell,
    union,
)
from races import Race, current
from rig import bone_at


def region_at(x: int, y: int, z: int) -> str:
    """Which part of the body the cell at (x, y, z) is."""
    r = current()
    cx = x + 0.5
    cy = y + 0.5
    out = abs(cx)
    # Beside the head up to the shoulder's crown is the shoulders' (as in rig.bone_at).
    if not (out >= r.head_half[0] and cy < r.arm_top):
        if cy >= r.head_bottom + 0.5 and out >= r.head_half[0]:
            return "ears"
        if cy >= r.head_bottom:
            return "head"
    if out >= r.arm_in:
        if cy >= r.elbow:
            return "upper_arms"
        if cy >= r.wrist:
            return "forearms"
        return "hands"
    if cy < r.ankle:
        return "feet"
    if cy < r.hip:
        return "legs"
    if cy < r.waist:
        return "hips"
    return "torso"


# --- Palette ------------------------------------------------------------------------------------

# Skin is drawn near white and tinted by the character's own tone.
SKIN = 0xF7F3F0
LINEN = 0xCDB894
WOOL = 0x5C4838
SHOE = 0x3E2C22
LIP = 0xB06A5E
# Women's lips are redder.
LIP_F = 0xC4545A
DARK = 0x231A16
# Bare bone and teeth, and the dark of a rotted mouth or an empty socket.
BONE = 0xDDD3B8
ROT_DARK = 0x2A1A1A


def rot(x, y, z) -> float:
    """How rotten the skin is at a cell, 0 (sound) to 1, for the undead: blotches across the body."""
    return noise3(x, y, z, 3.5, 61)


def skin(x, y, z, *_):
    v = Voxel(jitter(SKIN, x, y, z, 0.03, 1), "skin")
    if current().decay:
        # Blotched: patches darker and greener, the odd one darker still.
        k = rot(x, y, z)
        if k > 0.58:
            return v.but(color=shade(mix(v.color, 0xB8C8A0, 0.5), 0.78 - (k - 0.58)))
        if k < 0.3:
            return v.but(color=shade(v.color, 0.9))
    return v


def linen(x, y, z, *_):
    """Undyed linen, its weave showing as faint rows."""
    row = 1 if y % 2 == 0 else 0.94
    # A darker hem at the shirt's foot and the sleeves' ends.
    r = current()
    hem = 0.8 if y == r.waist or y == r.sleeve else 1
    return Voxel(jitter(shade(LINEN, hem * row * (0.92 + noise3(x, y, z, 5, 3) * 0.12)), x, y, z, 0.04, 2), "cloth")


def wool(x, y, z, *_):
    # Turned up at the ankle, gathered at the waist.
    r = current()
    fold = 0.78 if y == r.ankle or y == r.waist - 1 else 1
    return Voxel(jitter(shade(WOOL, fold * (0.9 + noise3(x, y, z, 4, 5) * 0.2)), x, y, z, 0.06, 4), "cloth")


def shoe(x, y, z, *_):
    r = current()
    if y == r.sole:
        return Voxel(jitter(0x221812, x, y, z, 0.05), "leather")
    # Laced up the front.
    if z >= 2 and y >= r.sole + 2 and abs(abs(x + 0.5) - r.leg_x) < 1 and (y + z) % 2 == 0:
        return Voxel(jitter(0xA08A66, x, y, z, 0.05), "cloth")
    return Voxel(jitter(shade(SHOE, 0.9 + noise3(x, y, z, 3, 7) * 0.2), x, y, z, 0.05, 6), "leather")


# --- Shapes -------------------------------------------------------------------------------------

class Shapes:
    """
    The body's parts as shapes, from a race's proportions: each part spans its joints (y) and is as
    wide and deep as the race says (x, z). The right side's limbs are the left's mirrored (`both`).
    """

    def __init__(self, r: Race):
        self.race = r
        if r.waist_half:
            # Narrower below the chest: the waist; the chest full width above it.
            chest = union(
                round_box(
                    (0, (r.chest - 1 + r.head_bottom) / 2, 0),
                    (r.torso_half[0], (r.head_bottom - r.chest + 1) / 2, r.torso_half[1]),
                    r.torso_round,
                ),
                round_box(
                    (0, (r.waist + r.chest + 1) / 2, 0),
                    (r.waist_half, (r.chest + 1 - r.waist) / 2, r.torso_half[1] - 0.4),
                    r.torso_round,
                ),
            )
        else:
            chest = round_box(
                (0, (r.waist + r.head_bottom) / 2, 0),
                (r.torso_half[0], (r.head_bottom - r.waist) / 2, r.torso_half[1]),
                r.torso_round,
            )
        self.torso = union(
            chest,
            # A barrel: the belly round and forward.
            ellipsoid((0, r.belly, r.belly_z), r.belly_radii),
        )
        if r.bust:
            bx, by, bz = r.bust_at
            self.torso = union(self.torso, both(ellipsoid((bx, by, bz), r.bust)))
        self.neck = round_box((0, r.head_bottom, 0), r.neck_half, r.neck_round)
        self.hips = round_box((0, r.belt, r.leg_z), r.hips_half, r.hips_round)
        self.leg = union(
            round_box(
                (r.leg_x, (r.ankle + r.hip) / 2, r.leg_z),
                (r.shin_half[0], (r.hip - r.ankle) / 2 + 0.3, r.shin_half[1]),
                r.shin_round,
            ),
            # The thigh's bulk.
            round_box(
                (r.leg_x, (r.knee + r.hip) / 2 + 0.5, r.leg_z),
                (r.thigh_half[0], (r.hip - r.knee) / 2 + 0.1, r.thigh_half[1]),
                r.thigh_round,
            ),
        )
        self.foot = union(
            round_box(
                (r.leg_x, (r.sole + r.ankle) / 2, r.foot_z),
                (r.foot_half[0], (r.ankle - r.sole) / 2, r.foot_half[1]),
                r.foot_round,
            ),
            round_box((r.leg_x, r.sole + 0.5, r.sole_z), (r.sole_half[0], 0.5, r.sole_half[1]), r.sole_round),
        )
        self.upper_arm = union(
            round_box(
                (r.arm_x, (r.elbow + r.neck) / 2, 0),
                (r.upper_arm_half[0], (r.neck - r.elbow) / 2 + 0.5, r.upper_arm_half[1]),
                r.upper_arm_round,
            ),
            ellipsoid((r.arm_x + r.deltoid_at[0], r.shoulder + r.deltoid_at[1], 0), r.deltoid_radii),
        )
        self.forearm = round_box(
            (r.arm_x, (r.wrist + r.elbow) / 2, r.forearm_z),
            (r.forearm_half[0], (r.elbow - r.wrist) / 2 + 0.3, r.forearm_half[1]),
            r.forearm_round,
        )
        self.hand = union(
            round_box((r.arm_x + r.fist_at[0], r.wrist + r.fist_at[1], r.fist_at[2]), r.fist_half, r.fist_round),
            round_box((r.arm_x + r.thumb_at[0], r.wrist + r.thumb_at[1], r.thumb_at[2]), r.thumb_half, r.thumb_round),
        )
        self.skull = round_box(
            (0, (r.head_bottom + r.head_top) / 2, r.head_z),
            (r.head_half[0], (r.head_top - r.head_bottom) / 2, r.head_half[1]),
            r.head_round,
        )

        # The ears, placed from the side of the skull at the eyes' row.
        def at(p):
            return (r.head_half[0] + p[0], r.eye_row + p[1], p[2])

        self.ear = union(
            capsule(at(r.ear_root), at(r.ear_tip), r.ear_radius),
            capsule(at(r.lobe), at(r.lobe_end), r.lobe_radius),
        )


_SHAPES: dict = {}


def shapes() -> Shapes:
    """The current race's body shapes."""
    r = current()
    s = _SHAPES.get(r.name)
    if s is None or s.race is not r:
        s = _SHAPES[r.name] = Shapes(r)
    return s


def misbound(g: Grid) -> dict[tuple[str, str], int]:
    """
    The body's cells that move with a bone that isn't their part's, counted by (part, bone): a part
    reaching into another's space (rig.bone_at cuts the space up, not the parts), as thighs out where
    the arms hang would swing with the hands. Only bones a part's own joints share with it are its.
    """
    s = shapes()

    def sided(shape):
        return lambda x, y, z: shape.d(abs(x), y, z)

    parts = (
        ("torso", s.torso.d, lambda side: {"hips", "spine", "chest", "neck"}),
        ("neck", s.neck.d, lambda side: {"neck", "chest"}),
        ("hips", s.hips.d, lambda side: {"hips", "spine", "thigh_" + side}),
        ("leg", sided(s.leg), lambda side: {"hips", "thigh_" + side, "shin_" + side, "foot_" + side}),
        ("foot", sided(s.foot), lambda side: {"shin_" + side, "foot_" + side}),
        ("upper arm", sided(s.upper_arm), lambda side: {"chest", "shoulder_" + side, "upper_arm_" + side, "forearm_" + side}),
        ("forearm", sided(s.forearm), lambda side: {"upper_arm_" + side, "forearm_" + side, "hand_" + side}),
        ("hand", sided(s.hand), lambda side: {"forearm_" + side, "hand_" + side}),
    )
    out: dict[tuple[str, str], int] = {}
    for x, y, z, v in g:
        c = (x + 0.5, y + 0.5, z + 0.5)
        side = "L" if c[0] >= 0 else "R"
        bone = v.bone or bone_at(*c)
        inside = [(name, ok(side)) for name, d, ok in parts if d(*c) <= 0]
        if not inside or any(bone in ok for _, ok in inside):
            continue
        k = (" and ".join(name for name, _ in inside), bone)
        out[k] = out.get(k, 0) + 1
    return out


def skull_grid() -> Grid:
    """The skull's cells, unpainted: what hair, beards and helms are built out from."""
    return held_to_head(fill(Grid(), shapes().skull, lambda *_: Voxel(0, "skin")))


def held_to_head(g: Grid) -> Grid:
    """
    Holds a piece of the head to the head bone wherever it reaches into another part's space (a jaw
    jutting below the head's bottom, an ear beside a brawny shoulder), so all of it turns together.
    """
    def hold(x, y, z, v):
        return None if v.bone or bone_at(x + 0.5, y + 0.5, z + 0.5) == "head" else v.but(bone="head")

    return g.repaint(hold)


def outside_skull(x, y, z, *_) -> bool:
    return shapes().skull.d(x + 0.5, y + 0.5, z + 0.5) > 0


def body_grid() -> Grid:
    """
    The body below the head, each cell painted as its region is dressed: a linen shirt with short
    sleeves over the torso and upper arms, wool trousers, leather shoes; bare forearms and hands.
    """
    r = current()
    s = shapes()
    g = Grid()
    # The neck up to the head (above that it's inside the skull, which is the head's: head_skull).
    fill(
        g,
        union(s.torso, s.neck),
        lambda x, y, z: skin(x, y, z) if y >= r.neck and abs(x + 0.5) < r.neck_half[0] - 0.3 else linen(x, y, z),
        lambda _x, y, _z: y < r.head_bottom,
    )
    # The shirt's open neck: skin in a V at the front, from two below the shoulders.
    v_neck = r.shoulder - 2
    g.repaint(
        lambda x, y, z, v: skin(x, y, z)
        if v.finish == "cloth"
        and y >= v_neck
        and z >= r.torso_half[1] - 1
        and abs(x + 0.5) <= (y - v_neck) * 0.9 + 0.5
        else None
    )
    fill(g, s.hips, wool)
    fill(g, both(s.leg), wool)
    fill(g, both(s.foot), shoe)
    fill(g, both(s.upper_arm), lambda x, y, z: linen(x, y, z) if y >= r.sleeve else skin(x, y, z))
    fill(g, both(s.forearm), skin)
    knuckles = r.wrist - 3

    def hand(x, y, z):
        v = skin(x, y, z)
        # The fist: fingers curled under at the front, a crease between each, the knuckles above.
        out = abs(x + 0.5)
        if z >= 3 and y <= knuckles and out >= r.arm_x - 1.5 and out % 1.5 < 0.6:
            return v.but(color=shade(v.color, 0.84))
        if y == knuckles and z >= 2:
            return v.but(color=shade(v.color, 0.9))
        return v

    fill(g, both(s.hand), hand)
    if r.decay:
        # The shirt's rotted through in places, the ribs showing; bone shows through the forearms.
        def ragged(x, y, z, v):
            if v.finish != "cloth" or not (r.waist + 1 < y < r.shoulder - 1) or abs(x + 0.5) >= r.arm_in:
                return None
            if noise3(x, y, z, 2.5, 71) < 0.68:
                return None
            sk = skin(x, y, z)
            return sk.but(color=shade(sk.color, 0.62)) if y % 2 == 0 else sk

        g.repaint(ragged)
        g.repaint(
            lambda x, y, z, v: Voxel(jitter(BONE, x, y, z, 0.05, 72), "gloss")
            if v.finish == "skin"
            and r.wrist + 1 < y < r.elbow - 1
            and abs(x + 0.5) >= r.arm_x + r.forearm_half[0] - 1
            and hash3(x, y, z, 73) < 0.55
            and (x < 0 or y % 3 != 0)
            else None
        )
    # The wrist, a little in from the fist.
    g.repaint(
        lambda x, y, _z, v: v.but(color=shade(v.color, 0.9))
        if y == r.wrist and v.finish == "skin" and abs(x + 0.5) >= r.arm_x - r.forearm_half[0]
        else None
    )
    return g


def regions(g: Grid) -> dict[str, Grid]:
    """Cuts a grid into the body's regions."""
    out: dict[str, Grid] = {}
    for x, y, z, v in g:
        r = region_at(x, y, z)
        if r not in out:
            out[r] = Grid()
        out[r].set(x, y, z, v)
    return out


# --- Head ---------------------------------------------------------------------------------------

# Faces are drawn on the skull's front (the race's `front`: the last layer of its cells, z = 8 for the
# default race), features standing a voxel or two proud of it, in rows from the race's eye, nose and mouth
# rows. Their columns are the same for every race.


def ears_grid() -> Grid:
    """The ears, pointed and swept back, a darker fold inside."""
    r = current()
    g = Grid()
    side = r.head_half[0]

    def ear(x, y, z):
        v = skin(x, y, z)
        inner = z >= 0 and side + 1 <= abs(x + 0.5) <= side + 2 and r.eye_row <= y <= r.eye_row + r.ear_fold
        return v.but(color=shade(v.color, 0.82)) if inner else v

    fill(g, both(shapes().ear), ear)
    # Only the part outside the skull.
    return held_to_head(g.filter(outside_skull))


def skull_paint(x, y, z) -> Voxel:
    """The skull's skin: ruddy cheeks below the eyes, a touch of warmth; the undead's rot instead."""
    r = current()
    v = skin(x, y, z)
    if r.decay:
        # A cheek rotted through to the bone.
        if z >= r.front - 2 and r.mouth_row <= y <= r.nose_row + 1 and 5 <= x <= 7:
            return Voxel(jitter(BONE, x, y, z, 0.05, 74), "gloss")
        cheek = z >= r.front - 1 and r.nose_row <= y <= r.eye_row - 1 and 4.5 <= abs(x + 0.5) <= 7.5
        return v.but(color=shade(v.color, 0.82)) if cheek else v
    cheek = z >= r.front - 1 and r.nose_row <= y <= r.eye_row - 1 and 4.5 <= abs(x + 0.5) <= 7.5
    blush = 0.45 if r.sex == "female" else 0.35
    return v.but(color=mix(v.color, 0xF0B0A0, blush)) if cheek else v


def col(x: int) -> int:
    """A face column counted out from the middle on either side: 0 is the first on each side."""
    return x if x >= 0 else -1 - x


def in_eyes(x, y, z) -> bool:
    """The eyes' patch of the face: what the skull leaves for an eye style to fill."""
    r = current()
    return z == r.front and 1 <= col(x) <= 6 and r.eye_row - 1 <= y <= r.eye_row + 3


def in_mouth(x, y, z) -> bool:
    """The mouth's patch of the face."""
    r = current()
    return z == r.front and -6 <= x <= 5 and r.mouth_row - 1 <= y <= r.mouth_row + 1


def head_grid() -> Grid:
    """
    The head: the skull, with the eyes' and the mouth's patches left out (an eye and a mouth style
    fill them), and what the race adds: tusks and a jutting jaw, bare bone.
    """
    r = current()
    FRONT, MOUTH = r.front, r.mouth_row
    g = fill(Grid(), shapes().skull, skull_paint)
    g = g.filter(lambda x, y, z, _v: not in_eyes(x, y, z) and not in_mouth(x, y, z))

    def jaw_skin(x, y, z):
        v = skin(x, y, z)
        return v.but(color=shade(v.color, 0.94))

    # The lower jaw jutting out under the lip, an underbite.
    for depth in range(1, r.jaw + 1):
        for x in range(-5 + depth - 1, 5 - depth + 1):
            for y in range(MOUTH - 3, MOUTH - 1 + (1 if depth == 1 else 0)):
                g.set(x, y, FRONT + depth, jaw_skin(x, y, FRONT + depth))
    if r.tusks:
        # Up from the jaw past the lip, either side of the mouth: an ogre's thicker and taller.
        def tusk(x, y, z):
            return Voxel(shade(jitter(BONE, x, y, z, 0.04, 75), 0.92 if y == MOUTH - 1 else 1), "gloss")

        cols = (3,) if r.tusks == 1 else (3, 4)
        top = MOUTH + (1 if r.tusks == 1 else 2)
        for c in cols:
            for x in (c, -1 - c):
                for y in range(MOUTH - 1, top + 1):
                    g.set(x, y, FRONT + 1, tusk(x, y, FRONT + 1))
                if r.tusks == 2:
                    for y in range(MOUTH - 1, top):
                        g.set(x, y, FRONT + 2, tusk(x, y, FRONT + 2))
    return held_to_head(g)


# The pieces of a face, drawn as maps of one eye or brow (the left; the right is its mirror), from the
# middle out (columns 1–6), top row first. Eyes: L lid, W the white, I iris, i the iris in shadow, G a
# glint, l a lash (a woman's), S a heavy lid in shadow, . skin.
EYES = {
    "round": ("....l.", ".LLLl.", ".GIW..", ".iiW..", "......"),
    "narrow": ("......", "....ll", ".LLLL.", ".GIW..", "......"),
    "wide": ("......", ".LLLLl", ".GIWW.", ".iiWW.", "......"),
    "small": ("......", "....l.", "..LLl.", "..GW..", "......"),
    "fierce": ("......", "..LLLl", ".LGIW.", "..iW..", "......"),
    "sleepy": ("......", ".SSSS.", ".LLLLl", ".GiW..", "......"),
    "almond": ("....ll", "...LL.", ".LGIW.", "..ii..", "......"),
}

# Brows, rows from the eyes' row + 5 down to + 3, standing a voxel proud: B brow.
BROWS = {
    "heavy": ("......", ".BBBB.", "BBBBB."),
    "thin": ("......", "BBBBB.", "......"),
    "arched": (".BBB..", "B...B.", "......"),
    "low": ("......", "......", "BBBBBB"),
    "angry": ("....B.", "..BB..", "BB...."),
    "bushy": (".BBBB.", "BBBBBB", "BBBBBB"),
    "short": ("......", ".BBB..", "......"),
}


def eyes_grid(style: str) -> Grid:
    """An eye style: the eyes' patch, skin, with the eyes drawn in it."""
    r = current()
    FRONT, EYE = r.front, r.eye_row
    female = r.sex == "female"
    rows = EYES[style]
    g = Grid()
    for x in range(-7, 7):
        for y in range(EYE - 1, EYE + 4):
            if not in_eyes(x, y, FRONT):
                continue
            c = col(x)
            ch = rows[EYE + 3 - y][c - 1]
            v = skull_paint(x, y, FRONT)
            if ch == "L":
                v = Voxel(jitter(DARK, x, y, FRONT, 0.04), "gloss")
            elif ch == "l" and female:
                v = Voxel(DARK, "gloss")
            elif ch == "S":
                v = v.but(color=shade(v.color, 0.8))
            elif ch == "W":
                v = Voxel(ROT_DARK, "gloss") if r.hollow_eyes else Voxel(0xF4F1EA, "gloss")
            elif ch == "G":
                v = Voxel(0xFFFFFF, "iris") if r.hollow_eyes else Voxel(0xFFFFFF, "gloss")
            elif ch in "Ii":
                v = Voxel(0xD8D8D8 if ch == "i" else 0xFFFFFF, "iris")
            g.set(x, y, FRONT, v)
    return g


def brows_grid(style: str) -> Grid:
    """A brow style, in the hair's colour, a voxel proud of the face."""
    r = current()
    z, EYE = r.front + 1, r.eye_row
    rows = BROWS[style]
    female = r.sex == "female"
    g = Grid()
    for i, row in enumerate(rows):
        y = EYE + 5 - i
        for c, ch in enumerate(row):
            if ch != "B":
                continue
            # A woman's are finer: the lowest row of a heavy brow is plucked away.
            if female and style in ("heavy", "bushy") and i == 2 and c in (0, 5):
                continue
            for x in (c + 1, -2 - c):
                g.set(x, y, z, Voxel(jitter(0xE8E4E0, x, y, z, 0.08, 9), "hair"))
    if style == "bushy" and not female:
        # Meeting in the middle.
        for x in (0, -1):
            g.set(x, EYE + 3, z, Voxel(jitter(0xE8E4E0, x, EYE + 3, z, 0.08, 9), "hair"))
    return g


def nose_grid(style: str) -> Grid:
    """A nose, standing a voxel or two proud of the face, shaded under its tip."""
    r = current()
    F, N = r.front, r.nose_row
    g = Grid()

    def nose(x, y, z, k=1):
        return Voxel(shade(mix(jitter(SKIN, x, y, z, 0.03, 1), 0xF0C0B0, 0.25), k), "skin")

    def put(xs, ys, z, k=1):
        for x in xs:
            for y in ys:
                g.set(x, y, z, nose(x, y, z, k))

    mid = (-1, 0)
    if style == "broad":
        put((-2, -1, 0, 1), (N, N + 1), F + 1)
        put(mid, (N + 2, N + 3), F + 1)
        put(mid, (N + 1,), F + 2)
        put(mid, (N,), F + 2, 0.92)
        put((-2, 1), (N,), F + 1, 0.7)
    elif style == "small":
        put(mid, (N + 1, N + 2), F + 1)
        put(mid, (N,), F + 1, 0.85)
    elif style == "button":
        put(mid, (N + 1,), F + 1)
        put((-2, -1, 0, 1), (N,), F + 1, 0.92)
        put(mid, (N,), F + 2, 0.95)
        put((-2, 1), (N,), F + 1, 0.75)
    elif style == "long":
        put(mid, (N, N + 1, N + 2, N + 3), F + 1)
        put(mid, (N + 1,), F + 2)
        put(mid, (N,), F + 2, 0.88)
    elif style == "hooked":
        put(mid, (N + 1, N + 2, N + 3), F + 1)
        put(mid, (N + 2,), F + 2)
        put(mid, (N + 1,), F + 2, 0.95)
        put(mid, (N,), F + 2, 0.8)
        put(mid, (N,), F + 1, 0.7)
    elif style == "flat":
        put((-2, -1, 0, 1), (N, N + 1), F + 1)
        put(mid, (N + 2,), F + 1)
        put(mid, (N,), F + 1, 0.55)
    elif style == "bulbous":
        put((-2, -1, 0, 1), (N, N + 1), F + 1)
        put(mid, (N + 2, N + 3), F + 1)
        put((-2, -1, 0, 1), (N, N + 1), F + 2)
        put(mid, (N,), F + 3, 0.95)
        put((-2, 1), (N,), F + 1, 0.7)
    else:
        raise ValueError(style)
    return g


def mouth_grid(style: str) -> Grid:
    """A mouth style: the mouth's patch, skin, with the mouth drawn in it. The undead grin with bare teeth."""
    r = current()
    F, M = r.front, r.mouth_row
    female = r.sex == "female"
    g = Grid()
    for x in range(-6, 6):
        for y in range(M - 1, M + 2):
            if in_mouth(x, y, F):
                g.set(x, y, F, skull_paint(x, y, F))

    def lip(x, y, k=1):
        if r.decay:
            return Voxel(jitter(BONE, x, y, F, 0.05, 76), "gloss") if x % 2 == 0 else Voxel(ROT_DARK, "gloss")
        if style == "thin":
            v = skin(x, y, F)
            return v.but(color=shade(v.color, 0.68 * k))
        return Voxel(shade(jitter(LIP_F if female else LIP, x, y, F, 0.04), k), "cloth")

    def put(xs, y, k=1):
        for x in xs:
            g.set(x, y, F, lip(x, y, k))

    if style == "wide":
        put(range(-3, 3), M, 0.75)
    elif style == "full":
        put(range(-2, 2), M, 0.75)
        put((-1, 0), M, 1.1)
    elif style == "thin":
        put(range(-2, 2), M)
    elif style == "smile":
        put(range(-2, 2), M, 0.75)
        put((-3, 2), M + 1, 0.75)
    elif style == "frown":
        put(range(-2, 2), M, 0.75)
        put((-3, 2), M - 1, 0.75)
    elif style == "small":
        put((-1, 0), M, 0.8)
    elif style == "pout":
        put(range(-2, 2), M, 0.8)
        put((-1, 0), M - 1, 1.05)
    else:
        raise ValueError(style)
    return g


_FACES: dict = {}


def face_grid() -> Grid:
    """Every cell any face could have: what hair and beards are kept clear of."""
    r = current()
    hit = _FACES.get(r.name)
    if hit is not None and hit[0] is r:
        return hit[1]
    g = head_grid()
    for s in EYE_STYLES:
        g.add(eyes_grid(s))
    for s in BROW_STYLES:
        g.add(brows_grid(s))
    for s in NOSE_STYLES:
        g.add(nose_grid(s))
    for s in MOUTH_STYLES:
        g.add(mouth_grid(s))
    _FACES[r.name] = (r, g)
    return g


# --- Hair ---------------------------------------------------------------------------------------


def strand(x, y, z, along="down") -> Voxel:
    """Hair is drawn near white with darker strands, and tinted with the character's own colour."""
    # A strand is a run of cells sharing a colour; neighbouring strands differ.
    col = hash3(x, 0, z, 21) if along == "down" else hash3(x, y, 0, 21)
    k = 0.72 + col * 0.34 + (noise3(x, y, z, 3, 22) - 0.5) * 0.12
    return Voxel(shade(0xFFFFFF, min(1, k)), "hair", "head")


def strand_back(x, y, z, *_):
    return strand(x, y, z, "back")


def strand_down(x, y, z, *_):
    return strand(x, y, z)


def scalp(x, y, z) -> bool:
    """
    Where hair grows: from a hairline over the brow, down the back to the nape, clear of the ears.
    Heights are from the eyes' row (the human man's 35) and the head's bottom (30); widths and depths
    from the skull's sides and front.
    """
    r = current()
    side = r.head_half[0]
    out = abs(x + 0.5)
    if z >= r.front - 3:
        return y >= r.eye_row + 7 + (-1 if out > side - 4 else 0)
    if z >= r.front - 7:
        return y >= r.eye_row + (4 if out > side - 2 else 6)
    if out > side - 2 and z > r.front - 12:
        return y >= r.eye_row + 4
    return y >= r.head_bottom + 3


def cap(thick: float, where=scalp) -> Grid:
    """A cap of hair `thick` voxels over the scalp."""
    g = Grid()
    for (x, y, z) in shell(skull_grid(), thick):
        if where(x, y, z):
            g.set(x, y, z, strand(x, y, z))
    return g


def hair_grid(style: str) -> Grid:
    r = current()
    top, back = r.head_top, r.back
    g = Grid()
    if style == "bald":
        return g
    if style == "crop":
        return cap(1.5)
    if style == "mohawk":
        # Shaved sides; a crest along the top from the brow to the nape.
        crest = union(
            round_box((0, top + 0.5, r.head_z), (2, 3.5, r.head_half[1] - 1), 1.5),
            round_box((0, top - 6, back - 0.5), (2, 6, 1.5), 1),
        )
        fill(g, crest, strand_back)
        return g.filter(outside_skull)
    if style == "topknot":
        g.add(cap(1.2))
        # A tie round the knot's root.
        fill(
            g,
            union(ellipsoid((0, top + 2.2, -2), (3.2, 2.6, 3.2)), capsule((0, top - 0.5, -2), (0, top + 1, -2), 1.6)),
            lambda x, y, z: Voxel(0x8A2A20, "leather") if y == top else strand(x, y, z, "back"),
        )
        return g
    if style == "braids":
        g.add(cap(1.6))
        # A braid from in front of each ear down over the chest, clear of anything worn there (as a
        # beard is): plaited, a lighter and darker cell by turns, tied off at the end. From the eyes'
        # row to the mouth's, then as far again as a full beard and a bit.
        z, end = r.front + 1, r.mouth_row - 7.5
        for s in (1, -1):
            fill(g, capsule((s * r.head_half[0], r.eye_row + 1, 4), (s * 7, r.mouth_row, z), 1.5), strand_down)

            def plait(x, y, z):
                v = strand(x, y, z)
                return v.but(color=shade(v.color, 0.7 if (y + (0 if x > 0 else 1)) % 3 == 0 else 1))

            fill(g, capsule((s * 7, r.mouth_row, z), (s * 6.5, end, z), 1.5), plait)
            fill(g, round_box((s * 6.5, end - 1, z), (1.2, 0.8, 1.2), 0.3), lambda *_: Voxel(0x8A2A20, "leather", "head"))
        ear = shapes().ear
        return g.filter(lambda x, y, z, _v: outside_skull(x, y, z) and ear.d(abs(x + 0.5), y + 0.5, z + 0.5) > 0)
    if style == "mane":
        bottom = r.head_bottom
        g.add(cap(2.4, lambda x, y, z: scalp(x, y, z) or (z < 0 and y >= bottom + 1)))
        # Long at the back, down past the shoulders, thinning at the ends.
        fill(g, round_box((0, bottom, back - 0.6), (r.head_half[0] - 0.5, 7, 1.6), 1.5), strand_down)
        return g.filter(lambda x, y, z, _v: outside_skull(x, y, z) and (y > bottom - 3 or hash3(x, y, z, 30) > 0.25))
    side = r.head_half[0]
    eye, bottom = r.eye_row, r.head_bottom
    clear = clear_of_face()
    if style == "ponytail":
        g.add(cap(1.5))
        # Gathered at the back of the head and hanging down the back.
        tie_y, tie_z = eye + 4, back - 1.2
        fill(g, capsule((0, tie_y, tie_z - 0.6), (0, bottom - 7, back - 2.6), 1.7), strand_down)
        fill(g, ellipsoid((0, bottom - 7.5, back - 2.6), (1.3, 1.6, 1.3)), strand_down)
        fill(g, round_box((0, tie_y, tie_z - 1), (1.6, 0.6, 1.4), 0.3), lambda *_: Voxel(0x8A2A20, "leather", "head"))
        return g.filter(clear)
    if style == "bun":
        g.add(cap(1.4))
        fill(g, ellipsoid((0, top - 2.5, back - 1.8), (3.4, 3.2, 3)), strand_back)
        fill(
            g,
            round_box((0, top - 2.5, back - 0.2), (3.2, 0.6, 1.2), 0.2),
            lambda *_: Voxel(0x8A2A20, "leather", "head"),
        )
        return g.filter(clear)
    if style == "long":
        # Long and straight: framing the face to the chin, and down the back past the shoulders.
        g.add(cap(2, lambda x, y, z: scalp(x, y, z) or (z < r.front - 4 and y >= bottom - 1)))
        fill(g, round_box((0, bottom - 3, back - 0.4), (side - 0.4, 6, 1.8), 1.5), strand_down)
        for sgn in (1, -1):
            fill(
                g,
                round_box((sgn * (side + 0.4), (r.mouth_row + eye) / 2 - 1, r.front - 5), (1.4, (eye - r.mouth_row) / 2 + 3, 2.6), 1),
                strand_down,
            )
        return g.filter(lambda x, y, z, v: clear(x, y, z, v) and (y > bottom - 8 or hash3(x, y, z, 31) > 0.3))
    if style == "bob":
        # A helmet of hair cut level at the jaw, with a fringe.
        g.add(cap(2.2, lambda x, y, z: scalp(x, y, z) or (z < r.front - 3 and y >= r.mouth_row - 1)))
        fill(g, round_box((0, eye + 5.5, r.front - 1), (side - 2.5, 1.2, 2), 0.8), strand_down)
        return g.filter(clear)
    if style == "spiky":
        g.add(cap(1.2))
        # Spikes standing up and back from the crown.
        for i, (sx, sz, lean) in enumerate(((0, 2, 1), (-4, 1, 0.6), (4, 1, 0.6), (-2, -3, 1.4), (2, -3, 1.4), (0, -6, 1.8), (-5, -4, 1), (5, -4, 1))):
            base = (sx, top - 1.5, r.head_z + sz)
            tip = (sx * 1.25, top + 3.2 - abs(sx) * 0.2, r.head_z + sz - 2.2 * lean)
            fill(g, capsule(base, tip, 1.3), strand_back)
        return g.filter(clear)
    if style == "pigtails":
        g.add(cap(1.5))
        # Tied high behind the ears, hanging to the shoulders.
        for sgn in (1, -1):
            root = (sgn * (side - 1), eye + 6, -4)
            fill(g, ellipsoid(root, (2, 2, 2)), strand_down)
            fill(g, capsule((sgn * (side + 0.8), eye + 5, -4.6), (sgn * (side + 1.6), bottom - 4, -4.2), 1.6), strand_down)
            fill(g, round_box((sgn * (side + 0.6), eye + 5, -4.5), (1.5, 0.6, 1.5), 0.2), lambda *_: Voxel(0x3A6EA8, "cloth", "head"))
        return g.filter(clear)
    if style == "sidecut":
        # Shaved close at the sides and back; long on top and swept over to the left.
        g.add(cap(0.9))
        g.add(cap(3, lambda x, y, z: scalp(x, y, z) and y >= eye + 6))
        fill(g, round_box((side - 1.5, eye + 5.5, r.head_z + 1), (2.2, 2.4, r.head_half[1] - 2), 1.2), strand_down)
        return g.filter(clear)
    if style == "curly":
        # A big round puff of curls: thick all over, lumpy at its surface.
        def curl(x, y, z):
            v = strand(x, y, z)
            return v.but(color=shade(v.color, 0.72 if hash3(x // 2, y // 2, z // 2, 33) < 0.35 else 1.05))

        for (x, y, z), d in shell(skull_grid(), 4.2).items():
            if not (scalp(x, y, z) or (z < r.front - 4 and y >= eye + 1)):
                continue
            # The outermost layer's cells come and go in clumps.
            if d > 3 and hash3(x // 2, y // 2, z // 2, 35) < 0.5:
                continue
            g.set(x, y, z, curl(x, y, z))
        return g.filter(clear)
    if style == "dreadlocks":
        g.add(cap(1.6))
        # Thick locks hanging all round from the scalp, longer at the back.
        n = 18
        for i in range(n):
            ang = math.pi * (0.03 + 0.94 * (i // 2) / (n // 2 - 1))
            sgn = 1 if i % 2 else -1
            x0 = math.cos(ang) * (side - 0.2) * sgn
            z0 = -math.sin(ang) * (r.head_half[1] - 0.5) + r.head_z - 1
            length = 5 + (4 if z0 < -3 else 0) + (i % 3)
            fill(g, capsule((x0 * 1.05, eye + 4, z0), (x0 * 1.18, bottom - length, z0 * 1.12), 1.25), strand_down)
        return g.filter(clear)
    if style == "tonsure":
        # A ring round the sides and back; bald on top.
        g.add(cap(1.5, lambda x, y, z: scalp(x, y, z) and y <= top - 5 and z < r.front - 3))
        return g.filter(clear)
    raise ValueError(style)


def clear_of_face():
    """A filter for hair: outside the skull, and clear of the ears and the face."""
    face = face_grid()
    ear = shapes().ear
    return lambda x, y, z, _v: (
        outside_skull(x, y, z) and ear.d(abs(x + 0.5), y + 0.5, z + 0.5) > 0 and not face.has(x, y, z)
    )


def beard_grid(style: str) -> Grid:
    """
    The beard: on the jaw and chin, under the nose, and as long as the style is down the chest,
    where it hangs clear of anything worn there (on the human man from 8 voxels out; a cuirass reaches 7).
    """
    r = current()
    FRONT, MOUTH = r.front, r.mouth_row
    g = Grid()
    if style == "none":
        return g
    # Clear of every face's features.
    head = face_grid()

    # The face below the cheekbones, around the jaw from ear to ear; the mouth's row is left for a
    # moustache to cover or not.
    def jaw(x, y, z):
        return y <= r.eye_row - 1 and z >= -1 and not (y >= r.nose_row and abs(x + 0.5) < 3.5 and z >= FRONT)

    if style in ("goatee", "moustache", "chops"):
        return trimmed(style, head)
    thick = 1 if style == "stubble" else 2
    for (x, y, z) in shell(skull_grid(), thick):
        if jaw(x, y, z) and y >= r.neck:
            g.set(x, y, z, strand(x, y, z))
    if style == "short":
        # Close and square: the jaw's two layers and a moustache, nothing hanging.
        moustache(g)
    elif style == "braided":
        # A full beard gathered into one thick plait down the chest, bound in rings.
        moustache(g)
        z = FRONT + 1.4
        fill(g, intersect(round_box((0, MOUTH - 3, z), (7, 3.5, 1.6), 1.5), Shape((-20, MOUTH - 7, 0), (20, MOUTH + 1, FRONT + 4), lambda x, y, _z: abs(x) - (2 + (y - MOUTH + 7) * 1.1))), strand_down)
        end = MOUTH - 15

        def plait(x, y, z):
            v = strand(x, y, z)
            return v.but(color=shade(v.color, 0.7 if (y + (0 if x >= 0 else 1)) % 3 == 0 else 1))

        fill(g, capsule((0, MOUTH - 5, z), (0, end, z + 0.4), 2), plait)
        for y in (MOUTH - 8, MOUTH - 12):
            fill(g, round_box((0, y, z), (2.4, 0.6, 2.4), 0.3), lambda *_: Voxel(0xB08A3A, "metal", "head"))
    elif style != "stubble":
        # A moustache over the mouth, drooping at its ends.
        for x in (-4, -3, -2, -1, 0, 1, 2, 3):
            for z in (FRONT + 1, FRONT + 2):
                g.set(x, MOUTH, z, strand(x, MOUTH, z))
        for x in (-5, -4, 3, 4):
            g.set(x, MOUTH - 1, FRONT + 1, strand(x, MOUTH - 1, FRONT + 1))
        # How far it hangs below the mouth (the human man's mouth is at 31).
        length = MOUTH - (5.5 if style == "full" else 8.5 if style == "forked" else 12.5)
        z = FRONT + 1.4
        if style == "forked":
            hang = union(
                round_box((0, MOUTH - 3, z), (7, 3.5, 1.6), 1.5),
                both(capsule((2.6, MOUTH - 4, z), (2.4, length, FRONT + 1.6), 1.8)),
            )
        else:
            hang = intersect(
                round_box((0, (length + MOUTH) / 2, z), (8 if style == "long" else 7.5, (MOUTH - length) / 2, 1.6), 1.5),
                # Narrowing to the chin's point.
                Shape(
                    (-20, length - 1, 0),
                    (20, MOUTH + 1, FRONT + 4),
                    lambda x, y, _z: abs(x) - (3 + ((y - length) / (MOUTH - length)) * 6),
                ),
            )
        fill(g, hang, strand_down)
        if style == "forked":
            for s in (1, -1):
                fill(
                    g,
                    round_box((s * 2.5, length + 1.5, FRONT + 1.5), (1.6, 0.6, 1.6), 0.2),
                    lambda *_: Voxel(0xB08A3A, "metal", "head"),
                )
    if style == "stubble":
        g.repaint(lambda x, y, z, v: v.but(color=shade(v.color, 0.8)) if hash3(x, y, z, 40) < 0.3 else None)
    return clear_of_body(g, head)


def moustache(g: Grid, ends: bool = True) -> None:
    """A moustache over the mouth, drooping at its ends."""
    r = current()
    FRONT, MOUTH = r.front, r.mouth_row
    for x in (-4, -3, -2, -1, 0, 1, 2, 3):
        for z in (FRONT + 1, FRONT + 2):
            g.set(x, MOUTH, z, strand(x, MOUTH, z))
    if ends:
        for x in (-5, -4, 3, 4):
            g.set(x, MOUTH - 1, FRONT + 1, strand(x, MOUTH - 1, FRONT + 1))


def trimmed(style: str, head: Grid) -> Grid:
    """The beards that aren't a full one: a goatee, a handlebar moustache, mutton chops."""
    r = current()
    FRONT, MOUTH = r.front, r.mouth_row
    g = Grid()
    if style == "goatee":
        moustache(g, ends=False)
        # A tuft on the chin and down from it, joined to the moustache at the mouth's corners.
        fill(g, round_box((0, MOUTH - 3, FRONT + 1.2), (2.6, 2.6, 1.3), 1), strand_down)
        for x in (-4, 3):
            for y in (MOUTH - 1, MOUTH - 2):
                g.set(x, y, FRONT + 1, strand(x, y, FRONT + 1))
    elif style == "moustache":
        # A handlebar: thick over the lip, the ends curling up.
        moustache(g, ends=False)
        for x, y in ((-5, MOUTH), (4, MOUTH), (-6, MOUTH + 1), (5, MOUTH + 1), (-6, MOUTH + 2), (5, MOUTH + 2)):
            g.set(x, y, FRONT + 1, strand(x, y, FRONT + 1))
    elif style == "chops":
        # Mutton chops: thick down the cheeks to the jaw, joined by the moustache, the chin bare.
        for (x, y, z) in shell(skull_grid(), 2):
            if y <= r.eye_row - 1 and y >= MOUTH - 4 and z >= -1 and abs(x + 0.5) >= 4.5:
                g.set(x, y, z, strand(x, y, z))
        moustache(g)
    return clear_of_body(g, head)


def clear_of_body(g: Grid, head: Grid) -> Grid:
    """A beard kept off the face's own cells (eyes, nose), and out of the body below."""
    r = current()
    FRONT = r.front
    body = body_grid()
    return g.filter(
        lambda x, y, z, _v: not head.has(x, y, z) and not body.has(x, y, z) and not (y >= r.eye_row - 1 and z >= FRONT)
    )
