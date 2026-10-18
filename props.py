"""
Things a character handles that aren't worn, and are the same whoever holds them: the fish it
catches and the bobber on its line. Each is a model of its own, not skinned: the game hangs it from
a bone (a fish from `grip_L`, the middle of the left fist) or puts it where it goes (a bobber on the
water).

A fish lies along -z from its mouth, which is at its origin: held, the mouth's in the fist. Its back
is toward +x and its flanks face either way along y. The bobber's origin is its waterline, and the
line ties on at the top of its stick (BOBBER_EYE).
"""

import math

from voxels import Grid, Voxel, ellipsoid, fill, hash3, jitter, mix, shade

# Where the line ties on to the bobber, voxels from its origin.
BOBBER_EYE = (-0.5, 4.0, -0.5)


def fish() -> Grid:
    """A fat trout, 15 voxels long (56 cm): olive back, a rosy stripe, silver belly, black spots."""
    g = Grid()

    def scales(x, y, z):
        # Up the body (x) from belly to back.
        up = x + 0.5
        c = mix(0xECEAE0, 0xBCC4BC, max(0.0, min(1.0, (up + 2.5) / 2.5)))
        if up > 0:
            c = mix(0xBCC4BC, 0x56683A, min(1.0, up / 2.5))
        if -0.5 <= up <= 1.0 and z < -2:
            c = mix(c, 0xD86A78, 0.7)
        if up > 0.5 and hash3(x, y, z, 91) < 0.16:
            c = 0x2A2A24
        return Voxel(jitter(c, x, y, z, 0.05, 92), "gloss", "root")

    fill(g, ellipsoid((0.5, 0.5, -5.5), (3.0, 1.6, 6.2)), scales)
    # The gill's edge, the eye on each flank, the mouth.
    for x, y, z, v in g:
        if z == -3 and -2 <= x <= 1:
            g.set(x, y, z, v.but(color=shade(v.color, 0.72)))
    for y in (-1, 1):
        g.set(1, y, -2, Voxel(0x14120E, "gloss", "root"))
        g.set(2, y, -2, Voxel(0xD8B048, "gloss", "root"))
    for y in (-1, 0, 1):
        if g.has(-1, y, 0):
            g.set(-1, y, 0, Voxel(0x6A3A3A, "gloss", "root"))
    fin = 0x6A7A50

    def fin_at(x, y, z):
        if not g.has(x, y, z):
            g.set(x, y, z, Voxel(jitter(shade(fin, 0.9 + hash3(x, y, z, 93) * 0.2), x, y, z, 0.04, 94), "gloss", "root"))

    # The tail: a fork, spreading back from the narrow end of the body.
    for z in range(-15, -10):
        back = -11 - z
        for x in range(-4, 6):
            off = abs(x + 0.5 - 0.5)
            if off <= 0.6 + back * 0.9 and not (back >= 3 and off < back - 2.4):
                fin_at(x, 0, z)
    # The fins: one along the back, one under the tail, a pair behind the gills.
    for z in range(-9, -3):
        for x in range(3, 3 + max(0, min(z + 9, -3 - z) // 2 + 1)):
            fin_at(x, 0, z)
    for z in (-9, -8):
        fin_at(-3, 0, z)
    for y in (-1, 1):
        fin_at(-2, y + (1 if y > 0 else -1), -4)
        fin_at(-3, y + (1 if y > 0 else -1), -5)
    return g


def bobber() -> Grid:
    """A float: red over white, half under the water, with a stick on top to tie the line to."""
    g = Grid()
    fill(
        g,
        ellipsoid((0, 0, 0), (2.1, 2.1, 2.1)),
        lambda x, y, z: Voxel(jitter(0xC8202A if y >= 0 else 0xF0EEE6, x, y, z, 0.04, 95), "gloss", "root"),
    )
    for y in range(2, math.floor(BOBBER_EYE[1])):
        g.set(-1, y, -1, Voxel(0x2A2420, "leather", "root"))
    return g


# Each prop's voxels, by name.
PROPS = {"fish": fish, "bobber": bobber}
