"""
The gear, sculpted onto the body: each piece is built out from the surface of the parts of the body
it covers, in bands so many voxels deep, then shaped and painted. Every body of a race is the same
underneath, so every piece fits every character; and where a piece starts and stops (a hem, a cuff,
the belt's rows) is placed from the race's landmarks (races.py), so it fits every race.

Pieces that cover the same part of the body are layered by how far out they go, so whichever are
worn together, the outer one covers the inner one where they meet and their faces don't fight:

  trousers 1½ · shirt and tunic 1½ (2½ for a skirt over the trousers) · cuirass 2
  belt 3 · necklace 2 · bracers 1½ · pauldrons 3 · gloves 1½ · boots 1½ (2½ up the shin)

A piece that hides a part of the body (boots the feet, gloves the hands) is built from that part as
well, so it's whole on its own.

Ported from bellweather-v2 (commit 3ea05c9, `packages/assets/tools/characters/gear.ts`).
"""

import math

from body import body_grid, ears_grid, regions, skull_grid
from races import current
from rig import bone_at, joined, pole
from voxels import Grid, Voxel, capsule, fill, hash3, jitter, js_hypot, js_round, mix, noise3, round_box, shade, shell, sign

_bodies: dict = {}


def the_body():
    """The whole body below the head, the skull and the ears (`all`: nothing's built inside these)."""
    r = current()
    hit = _bodies.get(r.name)
    if hit is None or hit["race"] is not r:
        b = body_grid()
        skull = skull_grid()
        ears = ears_grid()
        hit = _bodies[r.name] = {
            "race": r,
            "all": Grid().add(b).add(skull).add(ears),
            "parts": regions(b),
            "skull": skull,
            "ears": ears,
        }
    return hit


def part(*rs: str) -> Grid:
    g = Grid()
    for r in rs:
        p = the_body()["parts"].get(r)
        if p:
            g.add(p)
    return g


def band(g: Grid, of: Grid, to: float, paint, frm: float = 0) -> Grid:
    """
    Paints the cells around `of`, more than `frm` and at most `to` from its surface (and outside the
    body), into `g`; a None paint leaves a cell out. `paint` is given (x, y, z, distance).
    """
    body = the_body()["all"]
    nearest: dict = {}
    for (x, y, z), d in shell(of, to, frm, None, nearest).items():
        if body.has(x, y, z):
            continue
        v = paint(x, y, z, d)
        if not v:
            continue
        # It moves with the part of the body it's on: where the space it's in is another part's
        # altogether (the inside of a glove, by the thigh), it's held to its own.
        sx, sy, sz = nearest[(x, y, z)]
        own = body.get(sx, sy, sz).bone or bone_at(sx + 0.5, sy + 0.5, sz + 0.5)
        there = bone_at(x + 0.5, y + 0.5, z + 0.5)
        if not v.bone and there == "head" and own != "head":
            # Worn on the neck or the shoulders and reaching up beside the head (a collar, a
            # pauldron's crown): it goes with what it rises from, not the head.
            v = v.but(bone=bone_at(x + 0.5, current().head_bottom - 0.5, z + 0.5))
        g.set(x, y, z, v if v.bone or joined(own, there) else v.but(bone=own))
    return g


def edge(g: Grid, x, y, z, d) -> bool:
    """Whether the cell has nothing of `g` next to it in direction `d`: an edge, to trim."""
    return not g.has(x + d[0], y + d[1], z + d[2])


def trim(g: Grid, dirs, paint) -> None:
    """
    Recolours the edges of `g` facing these ways (the hem of a skirt is its edge facing down),
    keeping the bones they move with.
    """
    was = Grid().add(g)
    for x, y, z, v in was:
        if any(edge(was, x, y, z, d) for d in dirs):
            p = paint(x, y, z, v)
            if p:
                g.set(x, y, z, p if p.bone or not v.bone else p.but(bone=v.bone))


def out(x) -> float:
    return abs(x + 0.5)


def mirror_x(x: int) -> int:
    """The cell across the middle from column x."""
    return -1 - x


UP = (0, 1, 0)
DOWN = (0, -1, 0)

# --- Materials ----------------------------------------------------------------------------------


def cloth(c: int, seed: int = 0):
    return lambda x, y, z, *_: Voxel(
        jitter(shade(c, 0.9 + noise3(x, y, z, 4, seed) * 0.2), x, y, z, 0.05, seed + 1), "cloth"
    )


def leather(c: int, seed: int = 0):
    return lambda x, y, z, *_: Voxel(
        jitter(shade(c, 0.86 + noise3(x, y, z, 3, seed) * 0.28), x, y, z, 0.05, seed + 1), "leather"
    )


def metal(c: int, seed: int = 0):
    return lambda x, y, z, *_: Voxel(
        jitter(shade(c, 0.95 + noise3(x, y, z, 6, seed) * 0.1), x, y, z, 0.035, seed + 1), "metal"
    )


IRON = 0x9AA1A8
DARK_IRON = 0x5C6168
GOLD = 0xD0A040
BRASS = 0xB08A3C
RUBY = 0xC0182C
SAPPHIRE = 0x2A64D0
EMERALD = 0x1F9A5A

# --- Head ---------------------------------------------------------------------------------------


def leather_cap() -> Grid:
    r = current()
    g = Grid()
    hide = leather(0x7A5236, 11)

    def crown(x, y, z, _d):
        # Over the brows at the front, lower behind.
        low = r.eye_row + (6 if z >= r.front - 4 else 5 if z >= 0 else 2)
        return hide(x, y, z) if y >= low else None

    band(g, the_body()["skull"], 1.5, crown)
    # A seam over the crown from brow to nape, and a nub on top.
    g.repaint(lambda x, y, _z, v: v.but(color=shade(v.color, 0.75)) if out(x) < 1 and y >= r.head_top - 1 else None)
    fill(g, round_box((0, r.head_top + 2, r.head_z), (1, 0.7, 1), 0.2), leather(0x5A3A24, 12))
    # A turned-up brim, darker, stitched.
    trim(g, [DOWN], lambda x, y, z, v: Voxel(0xC8A878 if (x + z) % 3 == 0 else jitter(0x553620, x, y, z, 0.05), v.finish))
    return g


def horned_helm() -> Grid:
    r = current()
    g = Grid()
    iron = metal(IRON, 21)
    eye = r.eye_row

    def dome(x, y, z, _d):
        over_ear = out(x) > r.head_half[0] - 2 and y < eye + 6 and -4 < z < 4
        # Down over the nape behind.
        low = eye + 5 if z >= r.front - 3 else eye + 2 if z >= -3 else r.head_bottom + 2
        return None if y < low or over_ear else iron(x, y, z)

    band(g, the_body()["skull"], 2.2, dome)
    # A ridge front to back over the crown.
    g.repaint(lambda x, y, _z, v: v.but(color=shade(v.color, 1.15)) if out(x) < 1 and y >= r.head_top else None)
    # A bronze band round the brow, riveted.
    rim = Grid().add(g)
    trim(g, [DOWN], lambda x, y, z, _v: Voxel(0xF0D890 if (x + z) % 3 == 0 else jitter(BRASS, x, y, z, 0.04), "metal"))
    for x, y, z, _ in rim:
        if not edge(rim, x, y, z, DOWN) and edge(rim, x, y - 1, z, DOWN):
            here = g.get(x, y, z)
            if here and here.finish == "metal":
                g.set(x, y, z, here.but(color=jitter(shade(BRASS, 0.85), x, y, z, 0.04)))
    # A nose guard down from the brow.
    nose_z = r.front + 1
    for y in range(eye + 1, eye + 7):
        for x in (-1, 0):
            g.set(x, y, nose_z, iron(x, y, nose_z))
    # Horns: out from the temples, up, curling forward at their tips; ivory, ringed, darker at the root.
    # Placed from the side of the skull, 3½ below its top.
    side, root = r.head_half[0] + 0.5, r.head_top - 3.5
    for s in (1, -1):
        path = [
            ((s * side, root, 0), (s * (side + 3.5), root + 2, 0.5), 1.7),
            ((s * (side + 3.5), root + 2, 0.5), (s * (side + 5.5), root + 6, 1.5), 1.3),
            ((s * (side + 5.5), root + 6, 1.5), (s * (side + 5.7), root + 9.5, 2.8), 0.9),
        ]
        for i, (a, b, radius) in enumerate(path):

            def horn(x, y, z, i=i):
                t = (i + (y - (root - 0.5)) / 10) / 3
                ring = 0.85 if (y + js_round(out(x))) % 3 == 0 else 1
                return Voxel(jitter(shade(mix(0xB09878, 0xF0E6D0, min(1, t * 1.4)), ring), x, y, z, 0.04), "leather", "head")

            fill(g, capsule(a, b, radius), horn)
    return g


def hood() -> Grid:
    r = current()
    g = Grid()
    wool = cloth(0x8C2C26, 31)
    # Over the ears (which it hides), moving with them, and round the skull.
    for x, y, z, ear in the_body()["ears"]:
        g.set(x, y, z, wool(x, y, z).but(bone=ear.bone))

    def cowl_head(x, y, z, _d):
        opening = z >= r.front - 5 and out(x) < r.head_half[0] - 1.5 and y < r.head_top - 2
        return None if opening or y < r.head_bottom + 1 else wool(x, y, z)

    band(g, Grid().add(the_body()["skull"]).add(the_body()["ears"]), 1.8, cowl_head)

    # The cowl over the shoulders and round the back of the neck, open at the front.
    def cowl(x, y, z, _d):
        return None if y < r.shoulder - 1 or (z >= 2 and out(x) < 7) else wool(x, y, z)

    band(g, part("torso", "upper_arms"), 2.5, cowl)
    # A point at the back of the crown.
    fill(g, capsule((0, r.head_top, r.back + 2), (0, r.head_top - 1.5, r.back - 3), 1.4), wool)
    # Hemmed darker round the face and the cowl's edge.
    trim(g, [(0, 0, 1), DOWN], lambda _x, _y, _z, v: v.but(color=shade(v.color, 0.72)))
    return g


# --- Neck ---------------------------------------------------------------------------------------


def necklace(paint) -> Grid:
    """
    A string round the neck, low over the chest at the front: the cells within reach of the torso's
    surface along a curve high at the back and dropping toward the front.
    """
    r = current()
    g = Grid()

    def string(x, y, z, _d):
        curve = r.neck + 0.5 - max(0, z + 1) * 0.75 - ((4 - out(x)) * 0.2 if out(x) < 4 else 0)
        if abs(y + 0.5 - curve) > 0.5 or y < r.chest:
            return None
        return paint(x, y, z, js_round(math.atan2(z, x + 0.5) * 6))

    band(g, part("torso"), 2.2, string, 1)
    return g


def gold_amulet() -> Grid:
    r = current()
    gold = metal(GOLD, 41)
    g = necklace(lambda x, y, z, _i: gold(x, y, z))
    # The amulet: a gold disc on the chest with a ruby set in it, 6½ below the neck.
    y, z = r.neck - 6.5, r.chest_front
    fill(g, round_box((0, y, z), (2, 2, 0.5), 0.8), gold)
    for x in (-1, 0):
        for ry in (r.neck - 7, r.neck - 6):
            g.set(x, ry, z, Voxel(RUBY, "gloss"))
    return g


def bead_necklace() -> Grid:
    beads = (0x8A5A32, 0x6A3A22, 0x2A8A8A, 0x8A5A32, 0x6A3A22, 0xD8C8A0)
    g = necklace(lambda x, y, z, i: Voxel(jitter(beads[i % len(beads)], x, y, z, 0.05), "gloss"))
    # A claw hanging at the front, curved, dark at the root.
    r = current()
    for x, dy, c in ((0, 6, 0x6A5A48), (0, 7, 0xD8CCB0), (-1, 8, 0xE8E0CC), (-1, 9, 0xF4EEE0)):
        g.set(x, r.neck - dy, r.chest_front, Voxel(c, "leather"))
    return g


# --- Chest --------------------------------------------------------------------------------------


def bodice(g: Grid, paint, sleeve, to: float = 1.5) -> None:
    """Over the torso (and the top of the hips) `to` deep, with sleeves to `sleeve` on the upper arm."""
    r = current()

    def body_part(x, y, z, _d):
        if y < r.waist - 1:
            return None
        # Open at the neck.
        if y >= r.shoulder and z >= 3 and out(x) < 3.5 + (y - r.shoulder):
            return None
        if out(x) >= r.arm_in and sleeve is None:
            return None
        return paint(x, y, z)

    band(g, part("torso", "hips"), to, body_part)
    if sleeve is not None:
        band(g, part("upper_arms"), to, lambda x, y, z, _d: paint(x, y, z) if y >= sleeve else None)


def skirt(g: Grid, paint, hem: float, panels: bool = False) -> None:
    """A skirt over the trousers from the waist to `hem`, flaring a little (front and back panels only, `panels`)."""
    r = current()
    top = r.waist - 1

    def panel(x, y, z, d):
        if y >= top or y < hem:
            return None
        if d > 2.5 + (top - y) * 0.15:
            return None
        if panels and out(x) > r.hips_half[0] - 2.2:
            return None
        return paint(x, y, z)

    band(g, part("hips", "legs"), 3, panel)


def linen_tunic() -> Grid:
    g = Grid()
    blue = cloth(0x3C5A8C, 51)

    def weave(x, y, z):
        v = blue(x, y, z)
        return v if (x + y + z) % 2 == 0 else v.but(color=shade(v.color, 0.94))

    r = current()
    # Sleeves a row longer than the shirt's; the skirt two fifths of the way down the thigh.
    cuff = r.sleeve + 1
    bodice(g, weave, cuff)
    skirt(g, weave, r.down_thigh(0.4))
    # Yellow trim at the hem, the cuffs and the neck.
    trim(
        g,
        [DOWN],
        lambda x, y, z, v: v.but(color=jitter(0xC8A040, x, y, z, 0.05)) if y < r.waist - 1 or y == cuff else None,
    )
    g.repaint(
        lambda x, y, z, v: v.but(color=jitter(0xC8A040, x, y, z, 0.05))
        if y >= r.shoulder - 1 and z >= 3 and edge(g, x, y, z, (0, 0, 1)) and out(x) < 5.5 + (y - r.shoulder)
        else None
    )
    return g


def leather_jerkin() -> Grid:
    r = current()
    g = Grid()
    hide = leather(0x6E4A2E, 61)
    bodice(g, hide, None)
    skirt(g, hide, r.down_thigh(0.2), True)

    # Studded in rows, laced up the middle.
    def studs(x, y, z, _v):
        if out(x) < 1 and z >= 4 and y >= r.waist:
            return Voxel(0xC8A878 if y % 2 == 0 else 0x3A2414, "leather")
        if y % 3 == 0 and (x + z) % 3 == 0 and y >= r.waist:
            return Voxel(jitter(0xB0B4B8, x, y, z, 0.05), "metal")
        return None

    g.repaint(studs)
    trim(g, [DOWN, UP], lambda x, y, z, _v: Voxel(jitter(0x4A2E1A, x, y, z, 0.05), "leather"))
    return g


def steel_cuirass() -> Grid:
    r = current()
    g = Grid()
    steel = metal(IRON, 71)
    bodice(g, steel, None, 2)
    # Faulds: hooped plates below the waist.
    skirt(g, steel, r.down_thigh(0.2))
    # The breastplate's one piece from just under the chest's joint up; lames below.
    breast = r.chest - 1

    def plates(x, y, z, v):
        # A keel down the breastplate's middle, lit.
        if out(x) < 1 and z >= r.torso_half[1] and y >= r.waist + 2:
            return v.but(color=shade(v.color, 1.18))
        # Lames across the belly and the faulds: each plate's lower edge in shadow.
        if y < breast and y % 2 == 0:
            return v.but(color=shade(v.color, 0.72))
        return None

    g.repaint(plates)
    # Gilt edges at the neck and the arms, and at the faulds' hem.
    trim(g, [UP, DOWN], lambda x, y, z, _v: Voxel(jitter(GOLD, x, y, z, 0.05), "metal"))
    trim(g, [(1, 0, 0), (-1, 0, 0)], lambda x, y, z, v: Voxel(jitter(GOLD, x, y, z, 0.05), "metal") if y >= breast else v)
    return g


# --- Arms ---------------------------------------------------------------------------------------


def leather_bracers() -> Grid:
    r = current()
    g = Grid()
    hide = leather(0x8A5A34, 81)
    # The forearm between the wrist and the elbow, a row clear of each.
    band(g, part("forearms"), 1.5, lambda x, y, z, _d: hide(x, y, z) if r.wrist + 1 <= y <= r.elbow - 1 else None)
    # Laced on the outside, edged darker.
    g.repaint(
        lambda x, y, z, _v: Voxel(0xD8C090 if (y + z) % 2 == 0 else 0x3A2414, "leather")
        if out(x) >= r.arm_x + 1.5 and abs(z) <= 1
        else None
    )
    trim(g, [UP, DOWN], lambda x, y, z, _v: Voxel(jitter(0x4E301C, x, y, z, 0.05), "leather"))
    return g


def steel_pauldrons() -> Grid:
    r = current()
    g = Grid()
    steel = metal(IRON, 91)
    sh = r.shoulder

    def lames(x, y, z, d):
        if out(x) < r.arm_in - 2:
            return None
        # Lames stepping out as they go down: each plate a little wider than the one above.
        reach = 2.2 if y >= sh + 1 else 2.6 if y >= sh - 1 else 3 if y >= sh - 3 else 0
        if d > reach:
            return None
        if out(x) < r.arm_in and y < sh + 1:
            return None
        return steel(x, y, z)

    band(g, part("upper_arms", "torso"), 3, lames)
    g.repaint(lambda _x, y, _z, v: v.but(color=shade(v.color, 0.72)) if y == sh - 2 or y == sh else None)
    trim(g, [DOWN], lambda x, y, z, _v: Voxel(jitter(GOLD, x, y, z, 0.05), "metal"))
    # A rivet at the top of each, over the arm's middle.
    for s in (1, -1):
        x = math.floor(r.arm_x - 0.5)
        x = x if s > 0 else mirror_x(x)
        for y in range(sh + 6, sh - 1, -1):
            if g.has(x, y, 0):
                g.set(x, y, 0, g.get(x, y, 0).but(color=0xF0D890, finish="metal"))
                break
    return g


# --- Hands --------------------------------------------------------------------------------------


def glove(paint, cuff_top: int, cuff: float) -> Grid:
    """A glove: the hand, and around it, and a cuff up the wrist flaring to `cuff` out."""
    g = Grid()
    for x, y, z, _ in part("hands"):
        g.set(x, y, z, paint(x, y, z))
    band(g, part("hands"), 1.2, paint)
    band(g, part("forearms"), cuff, lambda x, y, z, _d: paint(x, y, z) if y < cuff_top else None)
    return g


def leather_gloves() -> Grid:
    r = current()
    hide = leather(0x5A3A24, 101)
    g = glove(hide, r.wrist + 2, 1.5)
    # Seams between the fingers.
    g.repaint(
        lambda x, y, z, v: v.but(color=shade(v.color, 0.75))
        if z >= 3 and y <= r.wrist - 3 and out(x) % 1.5 < 0.6
        else None
    )
    trim(g, [UP], lambda x, y, z, _v: Voxel(jitter(0x8A6A44, x, y, z, 0.05), "leather"))
    return g


def plate_gauntlets() -> Grid:
    r = current()
    steel = metal(IRON, 111)
    g = glove(steel, r.wrist + 3, 2.3)
    # Plates over the back of the hand and the knuckles, the fingers jointed; dark at the wrist.
    g.repaint(lambda _x, y, _z, v: v.but(color=shade(v.color, 0.74)) if y % 2 == 0 and y <= r.wrist - 1 else None)
    g.repaint(
        lambda x, y, z, v: v.but(color=jitter(DARK_IRON, x, y, z, 0.04)) if r.wrist <= y <= r.wrist + 1 else None
    )
    trim(g, [UP], lambda x, y, z, _v: Voxel(jitter(GOLD, x, y, z, 0.05), "metal"))
    return g


# --- Waist --------------------------------------------------------------------------------------


def belt(paint) -> Grid:
    """A belt round the waist (the race's `belt` row and the one above: the default race's 15 and 16), clear of anything under it."""
    r = current()
    g = Grid()
    band(g, part("hips", "torso"), 3, lambda x, y, z, _d: paint(x, y, z) if y == r.belt or y == r.belt + 1 else None)
    return g


def front(g: Grid, x: int, y: int) -> int:
    z = -100
    for cx, cy, cz, _ in g:
        if cx == x and cy == y:
            z = max(z, cz)
    return z


def leather_belt() -> Grid:
    r = current()
    b = r.belt
    g = belt(leather(0x4E3020, 121))
    z = front(g, 0, b) + 1
    # A brass buckle, its tongue through it: a row bigger than the belt each way.
    for x in range(-3, 3):
        for y in range(b - 1, b + 3):
            ring = x == -3 or x == 2 or y == b - 1 or y == b + 2
            if ring:
                g.set(x, y, z, Voxel(jitter(BRASS, x, y, z, 0.04), "metal"))
            else:
                g.set(x, y, z - 1, Voxel(jitter(0x3A2416, x, y, z, 0.04), "leather"))
    for x in (-1, 0):
        g.set(x, b, z, Voxel(0xE0C070, "metal"))
    # A pouch on the left hip, hanging from the belt, its flap over it: held to the hips, though it
    # hangs where the left arm and the thigh do.
    px = r.hips_half[0] + 0.3
    pouch, bag = round_box((px, b - 2, 1), (1.6, 2, 2.2), 0.6), leather(0x6A4428, 122)
    flap, top = round_box((px, b - 0.4, 1), (1.8, 0.6, 2.4), 0.2), leather(0x4E3020, 123)

    def hung(x, y, z, _d):
        c = (x + 0.5, y + 0.5, z + 0.5)
        v = top(x, y, z) if flap.d(*c) <= 0 else bag(x, y, z) if pouch.d(*c) <= 0 else None
        return v and v.but(bone="hips")

    band(g, part("hips"), 6, hung)
    return g


def gold_belt() -> Grid:
    strap = leather(0x3A2416, 131)
    gold = metal(GOLD, 132)
    # Gold plates linked along a dark leather strap.
    b = current().belt
    g = belt(lambda x, y, z: gold(x, y, z) if ((x + 20) // 2 + (z + 20) // 2) % 2 == 0 else strap(x, y, z))
    z = front(g, 0, b) + 1
    # A big gilt buckle with an emerald.
    for x in range(-3, 3):
        for y in range(b - 2, b + 4):
            g.set(x, y, z, gold(x, y, z))
    for x in (-1, 0):
        for y in (b, b + 1):
            g.set(x, y, z + 1, Voxel(EMERALD, "gloss"))
    return g


# --- Legs ---------------------------------------------------------------------------------------


def wool_trousers() -> Grid:
    r = current()
    g = Grid()
    wool = cloth(0x46553A, 141)
    band(g, part("hips", "legs"), 1.5, lambda x, y, z, _d: wool(x, y, z) if r.ankle <= y < r.waist else None)
    knee = r.knee

    # Patched knees, the patches stitched.
    def patch(x, y, z, v):
        if y < knee - 1 or y > knee + 1 or z < 2:
            return None
        stitch = y == knee + 1 or y == knee - 1
        return Voxel(jitter(0x5A4630 if stitch else 0x7A6040, x, y, z, 0.05), v.finish)

    g.repaint(patch)
    trim(g, [DOWN], lambda x, y, z, _v: Voxel(jitter(0x354229, x, y, z, 0.05), "cloth"))
    return g


def plated_tassets() -> Grid:
    g = Grid()
    steel = metal(IRON, 151)

    def mail(x, y, z):
        return Voxel(
            jitter(0x707880, x, y, z, 0.05) if (x + y + z) % 2 == 0 else jitter(0x3C4248, x, y, z, 0.05), "metal"
        )

    r = current()
    knee = r.knee
    # Mail over the hips and legs, and plate over it: tassets hanging over the thighs, a cop on each knee.
    band(g, part("hips", "legs"), 1.5, lambda x, y, z, _d: mail(x, y, z) if r.ankle <= y < r.waist else None)

    def plate(x, y, z, d):
        if d <= 1.5:
            return None
        tasset = knee + 2 <= y < r.waist - 1 and z >= -1 and out(x) > 0.5
        cop = knee - 1 <= y <= knee + 1 and z >= 1
        greave = r.ankle <= y < knee - 1 and z >= 0
        return steel(x, y, z) if tasset or cop or greave else None

    band(g, part("hips", "legs"), 2.4, plate)
    # The tassets in bands, each lower edge shadowed; a gilt rivet in the middle of each knee.
    g.repaint(
        lambda _x, y, z, v: v.but(color=shade(v.color, 0.72))
        if v.finish == "metal" and (y == knee + 2 or y == r.hip) and z >= -1
        else None
    )
    for s in (1, -1):
        x = math.floor(r.leg_x)
        x = x if s > 0 else mirror_x(x)
        z = front(g, x, knee)
        if z > -100:
            g.set(x, knee, z, Voxel(GOLD, "metal"))
    return g


# --- Feet ---------------------------------------------------------------------------------------


def boot(paint, top: int, shaft: float) -> Grid:
    """A boot: the foot, around it, and a shaft up the shin to `top`."""
    sole = current().sole
    g = Grid()
    for x, y, z, _ in part("feet"):
        g.set(x, y, z, paint(x, y, z))
    band(g, part("feet"), 1.5, lambda x, y, z, _d: paint(x, y, z) if y >= sole else None)
    band(g, part("legs"), shaft, lambda x, y, z, _d: paint(x, y, z) if y < top else None)
    return g


def leather_boots() -> Grid:
    r = current()
    # Up over the knee; the cuff folded down to just under it.
    cuff = r.knee - 1
    g = boot(leather(0x5E3C26, 161), r.knee + 1, 2.5)
    g.repaint(lambda x, y, z, _v: Voxel(jitter(0x2A1C14, x, y, z, 0.05), "leather") if y == r.sole else None)
    # A folded cuff at the top, lighter, and a strap over the instep.
    trim(g, [UP], lambda x, y, z, v: Voxel(jitter(0x8A6040, x, y, z, 0.05), "leather") if y >= cuff else v)
    g.repaint(lambda x, y, z, _v: Voxel(jitter(0x8A6040, x, y, z, 0.05), "leather") if y == cuff and z >= -4 else None)
    g.repaint(
        lambda x, y, z, _v: Voxel(0xC8A050 if (x + z) % 3 == 0 else jitter(0x3A2416, x, y, z, 0.05), "leather")
        if y == r.ankle - 1 and z >= 1
        else None
    )
    return g


def iron_sabatons() -> Grid:
    r = current()
    steel = metal(IRON, 171)
    g = boot(steel, r.knee, 2.4)
    # Pointed toes, just past the sole's front.
    toe = r.sole_z + r.sole_half[1] + 0.9
    for s in (1, -1):
        fill(g, round_box((s * r.leg_x, r.sole + 1, toe), (1.5, 1, 1.2), 0.4), steel)
    # Plates across the foot in bands, a darker sole, a gilt edge at the top.
    g.repaint(lambda x, y, z, _v: Voxel(jitter(0x30343A, x, y, z, 0.05), "metal") if y == r.sole else None)
    g.repaint(
        lambda _x, y, z, v: v.but(color=shade(v.color, 0.74)) if y >= r.sole + 1 and z >= 0 and (z + y) % 3 == 0 else None
    )
    trim(g, [UP], lambda x, y, z, v: Voxel(jitter(GOLD, x, y, z, 0.05), "metal") if y >= r.knee - 2 else v)
    return g


# --- Ears and rings -----------------------------------------------------------------------------


def lobes():
    """The lowest cell at the front of each ear's lobe: where an earring hangs."""
    ears = the_body()["ears"]
    pts = []
    for s in (1, -1):
        best = None
        for x, y, z, _ in ears:
            if sign(x + 0.5) != s:
                continue
            if best is None or y < best[1] or (y == best[1] and z > best[2]):
                best = (x, y, z)
        if best:
            pts.append(best)
    return pts


def not_in_body(x, y, z, _v) -> bool:
    return not the_body()["all"].has(x, y, z)


def gold_hoops() -> Grid:
    g = Grid()
    for x, y, z in lobes():
        # A ring in the plane of the ear, hanging from the lobe.
        for dy in range(-4, 1):
            for dz in range(-2, 3):
                r = js_hypot(dy + 2, dz)
                if abs(r - 1.7) < 0.55:
                    g.set(x, y - 1 + dy, z + dz, Voxel(jitter(GOLD, x, y + dy, z + dz, 0.05), "metal", "head"))
    return g.filter(not_in_body)


def gem_studs() -> Grid:
    g = Grid()
    for x, y, z in lobes():
        s = sign(x + 0.5)
        g.set(x + s, y, z, Voxel(SAPPHIRE, "gloss", "head"))
        g.set(x + s, y + 1, z, Voxel(shade(SAPPHIRE, 1.3), "gloss", "head"))
    return g.filter(not_in_body)


def ring(side: int, band_color: int, stone) -> Grid:
    """A ring round the inner finger of the fist on one side (+1 the left hand), with `stone` set on top."""
    r = current()
    g = Grid()
    hand = part("hands").filter(lambda x, _y, _z, _v: sign(x + 0.5) == side)
    # Four rows under the wrist, on the inner finger (between 2½ and 1 in from the arm's middle).
    row, inner = r.wrist - 4, r.arm_x - 2.5
    band(
        g,
        hand,
        1,
        lambda x, y, z, _d: Voxel(jitter(band_color, x, y, z, 0.04), "metal")
        if y == row and z >= 1 and inner <= out(x) <= inner + 1.5
        else None,
    )
    if stone is not None:
        top = None
        for x, y, z, _ in g:
            if top is None or z > top[2]:
                top = (x, y, z)
        if top:
            g.set(top[0], top[1], top[2] + 1, Voxel(stone, "gloss"))
    return g


# --- Tools --------------------------------------------------------------------------------------

CANE = 0xC9A35E
CORK = 0xB4885A


def fishing_pole() -> Grid:
    """
    A cane fishing pole in the right fist (rig.pole): a cork grip through the fist with a leather
    butt cap, and the cane out ahead, knotted every few voxels, with brass rings under it for the
    line; a shoulders' width up it, a wooden reel hanging under it, its brass crank on its left for
    the left fist. Each section of the cane moves with its own bone, so the rod bends; the spool and
    crank turn with the reel's.
    """
    p = pole()
    g = Grid()
    body = the_body()["all"]

    def put(x, y, z, color, finish, bone, amount=0.05, seed=0):
        if not body.has(x, y, z):
            g.set(x, y, z, Voxel(jitter(color, x, y, z, amount, seed), finish, bone))

    def rod_bone(z):
        return "grip_R" if z < p.rod else "rod_1" if z < p.mid else "rod_2" if z < p.top else "rod_3"

    x, y = p.x, p.y
    for z in range(p.butt, p.tip + 1):
        bone = rod_bone(z)
        if z == p.butt:
            # The butt cap, and the grip's cork, thicker than the cane.
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                put(x + dx, y + dy, z, 0x3A2A20, "leather", bone)
        elif z < p.front + 2:
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                put(x + dx, y + dy, z, shade(CORK, 0.82 + noise3(x + dx, y + dy, z, 1.5, 81) * 0.3), "leather", bone)
        elif abs(z - p.reel) <= 2:
            # The reel's seat, brass-bound.
            put(x, y, z, BRASS, "metal", bone)
        else:
            # Cane, a darker knot every five; the tip a little darker still.
            k = (z - p.front) % 5 == 4
            c = shade(CANE, 0.62 if k else 0.92 + noise3(x, y, z, 3, 82) * 0.16)
            put(x, y, z, shade(c, 0.85) if z > p.top + (p.tip - p.top) // 2 else c, "leather", bone, 0.04, 83)
            if z == p.tip or (z > p.rod and (z - p.rod) % ((p.tip - p.rod) // 4) == 2):
                # A ring under the rod for the line (the tip's on its end).
                put(x, y - 1, z, BRASS, "metal", bone, 0.03)
    # The reel, under the seat on a brass foot: a wooden spool wound with line, turning about x with
    # the crank on its left: hub, arm and knob, hanging straight down in the bind pose.
    put(x, y - 1, p.reel, BRASS, "metal", "grip_R")
    for dz in range(-1, 2):
        for dy in (-2, -3, -4):
            for dx in (-1, 0, 1):
                wood = shade(0x7A4A28, 0.85 + hash3(x + dx, y + dy, p.reel + dz, 84) * 0.25)
                if dx:
                    put(x + dx, y + dy, p.reel + dz, wood, "leather", "reel")
                else:
                    put(x + dx, y + dy, p.reel + dz, 0xE6E2D6, "cloth", "reel", 0.03)
    ax, ay, az = (math.floor(c) for c in p.axle)
    put(ax, ay, az, BRASS, "metal", "reel", 0.03)
    put(ax, ay - 1, az, BRASS, "metal", "reel", 0.03)
    put(ax, ay - 2, az, BRASS, "metal", "reel", 0.03)
    put(ax + 1, ay - 2, az, 0x4A3020, "leather", "reel")
    return g


# --- The lot ------------------------------------------------------------------------------------

# Each item's voxels, as named meshes: one for most, a ring's one for each hand (_L, _R), of which
# the game shows the one for the hand it's worn on.
GEAR = {
    "leather_cap": lambda: {"leather_cap": leather_cap()},
    "horned_helm": lambda: {"horned_helm": horned_helm()},
    "hood": lambda: {"hood": hood()},
    "gold_amulet": lambda: {"gold_amulet": gold_amulet()},
    "bead_necklace": lambda: {"bead_necklace": bead_necklace()},
    "linen_tunic": lambda: {"linen_tunic": linen_tunic()},
    "leather_jerkin": lambda: {"leather_jerkin": leather_jerkin()},
    "steel_cuirass": lambda: {"steel_cuirass": steel_cuirass()},
    "leather_bracers": lambda: {"leather_bracers": leather_bracers()},
    "steel_pauldrons": lambda: {"steel_pauldrons": steel_pauldrons()},
    "leather_gloves": lambda: {"leather_gloves": leather_gloves()},
    "plate_gauntlets": lambda: {"plate_gauntlets": plate_gauntlets()},
    "leather_belt": lambda: {"leather_belt": leather_belt()},
    "gold_belt": lambda: {"gold_belt": gold_belt()},
    "wool_trousers": lambda: {"wool_trousers": wool_trousers()},
    "plated_tassets": lambda: {"plated_tassets": plated_tassets()},
    "leather_boots": lambda: {"leather_boots": leather_boots()},
    "iron_sabatons": lambda: {"iron_sabatons": iron_sabatons()},
    "gold_hoops": lambda: {"gold_hoops": gold_hoops()},
    "gem_studs": lambda: {"gem_studs": gem_studs()},
    "gold_band": lambda: {"gold_band_L": ring(1, GOLD, None), "gold_band_R": ring(-1, GOLD, None)},
    "ruby_ring": lambda: {"ruby_ring_L": ring(1, 0xC8CCD0, RUBY), "ruby_ring_R": ring(-1, 0xC8CCD0, RUBY)},
    "fishing_pole": lambda: {"fishing_pole": fishing_pole()},
}


def gear_context() -> Grid:
    """What gear is drawn against: the whole body (its faces against it are hidden)."""
    return the_body()["all"]
