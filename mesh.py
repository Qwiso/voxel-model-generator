"""
Voxels into skinned mesh data: a quad for each face of a cell that's open (no cell beside it, in the
grid or in `context`, the body it's worn on, that moves with it), coloured by its cell, darkened where cells crowd its
corners (voxel ambient occlusion, baked into the vertex colours, which gives the hand-shaded look),
and weighted to the bones (corner_weights). A primitive for each finish.

Ported from bellweather-v2 (commit 3ea05c9, `packages/assets/tools/characters/mesh.ts`), with one
fix: the original hid every face against a filled cell, so where parts that move apart touched (the
two feet, a glove against the hip) there was nothing there once they did, and you could see into
them. Now a face is hidden only against a cell that moves with it (see `moves_with`).
"""

from rig import BONE_INDEX, VOXEL, bone_at, corner_weights, joined
from voxels import Grid, Voxel, js_round

# How dark a corner gets with 0, 1, 2 or 3 of its neighbours filled (index: 3 − filled).
AO = (0.52, 0.7, 0.85, 1)


def linear(c: int) -> float:
    v = c / 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


class Build:
    __slots__ = ("positions", "normals", "colors", "joints", "weights", "indices")

    def __init__(self):
        self.positions: list[float] = []
        self.normals: list[int] = []
        # Linear colour, RGBA, as unsigned 16-bit normalized.
        self.colors: list[int] = []
        self.joints: list[int] = []
        # Unsigned 8-bit normalized, adding up to 255.
        self.weights: list[int] = []
        self.indices: list[int] = []


# Corners in (u, w), counter-clockwise seen from outside.
CORNERS = {1: ((0, 0), (1, 0), (1, 1), (0, 1)), -1: ((0, 0), (0, 1), (1, 1), (1, 0))}


def _step(p, axis, by):
    return [v + by if i == axis else v for i, v in enumerate(p)]


def moves_with(a: Voxel, a_bone: str, b: Voxel, b_bone: str) -> bool:
    """
    Whether the face between two touching cells stays closed however the character moves, and so
    can be left out: they're on the same bone, or on joined bones (whose shared corners are weighted
    alike, corner_weights) where neither is held to its bone outright.
    """
    if a_bone == b_bone:
        return True
    return joined(a_bone, b_bone) and not a.bone and not b.bone


def voxel_faces(grid: Grid, context: Grid | None = None) -> dict[str, Build]:
    """The open faces of `grid`'s cells, by finish."""
    cells = grid.cells
    ctx = context.cells if context is not None else {}

    def solid(x, y, z):
        k = (x, y, z)
        return k in cells or k in ctx

    def covered(v: Voxel, bone: str, x, y, z) -> bool:
        """Whether the face toward (x, y, z) is hidden by a cell there that moves with this one."""
        k = (x, y, z)
        n = cells.get(k) or ctx.get(k)
        if n is None:
            return False
        return moves_with(v, bone, n, n.bone or bone_at(x + 0.5, y + 0.5, z + 0.5))

    out: dict[str, Build] = {}
    for (x, y, z), v in cells.items():
        c = (x, y, z)
        bone = v.bone or bone_at(x + 0.5, y + 0.5, z + 0.5)
        rgb = [linear((v.color >> 16) & 255), linear((v.color >> 8) & 255), linear(v.color & 255)]
        for axis in range(3):
            for sign in (1, -1):
                n = [0, 0, 0]
                n[axis] = sign
                if covered(v, bone, x + n[0], y + n[1], z + n[2]):
                    continue
                b = out.get(v.finish)
                if b is None:
                    b = out[v.finish] = Build()
                u = (axis + 1) % 3
                w = (axis + 2) % 3
                base = len(b.positions) // 3
                ao = []
                for du, dw in CORNERS[sign]:
                    p = _step(_step(_step(c, axis, 1 if sign > 0 else 0), u, du), w, dw)
                    # The three cells in front of the face that share this corner.
                    fr = [c[0] + n[0], c[1] + n[1], c[2] + n[2]]
                    su = _step(fr, u, 1 if du else -1)
                    sw = _step(fr, w, 1 if dw else -1)
                    sc = _step(su, w, 1 if dw else -1)
                    s1 = 1 if solid(*su) else 0
                    s2 = 1 if solid(*sw) else 0
                    s3 = 1 if solid(*sc) else 0
                    level = 0 if s1 and s2 else 3 - (s1 + s2 + s3)
                    ao.append(level)
                    b.positions += (p[0] * VOXEL, p[1] * VOXEL, p[2] * VOXEL)
                    b.normals += n
                    k = AO[level]
                    b.colors += (js_round(rgb[0] * k * 65535), js_round(rgb[1] * k * 65535), js_round(rgb[2] * k * 65535), 65535)
                    weights = {v.bone: 1} if v.bone else corner_weights(bone, p[0], p[1], p[2])
                    top = sorted(weights.items(), key=lambda t: -t[1])[:4]
                    total = sum(n_ for _, n_ in top)
                    # As bytes (255 is all of it), the largest taking what rounding leaves so they add up.
                    bs = [js_round((top[i][1] if i < len(top) else 0) / total * 255) for i in range(4)]
                    bs[0] = 255 - bs[1] - bs[2] - bs[3]
                    for i in range(4):
                        b.joints.append(BONE_INDEX[top[i][0]] if i < len(top) else 0)
                        b.weights.append(bs[i])
                # Split the quad along the diagonal whose ends are less shaded, so the shading doesn't streak.
                if ao[0] + ao[2] >= ao[1] + ao[3]:
                    b.indices += (base, base + 1, base + 2, base, base + 2, base + 3)
                else:
                    b.indices += (base + 1, base + 2, base + 3, base + 1, base + 3, base)
    return out


# The finishes' materials: (roughness, metallic, default tint sRGB). Tinted ones' colours are the
# defaults the game replaces with the character's own.
MATERIALS = {
    "cloth": (0.95, 0, None),
    "leather": (0.72, 0, None),
    "metal": (0.38, 0.8, None),
    "gloss": (0.22, 0, None),
    "skin": (0.78, 0, (0xE5, 0xB0, 0x88)),
    "hair": (0.85, 0, (0x6E, 0x46, 0x28)),
    "iris": (0.25, 0, (0x3A, 0x6E, 0xA8)),
}
