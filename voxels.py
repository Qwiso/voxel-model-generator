"""
Voxel sculpting, for characters and their gear: a sparse grid of coloured cells, shapes to fill and
carve it with (signed distances, so a rounded box or an ellipsoid comes out as clean voxel steps),
and the bits of paint that make it look sculpted rather than filled: per-cell colour jitter, smooth
noise, strands. Coordinates are in voxels; cell (x, y, z) spans x..x+1 and so on, and is filled if
its centre is inside a shape.

Ported from bellweather-v2 (commit 3ea05c9, `packages/assets/tools/characters/voxels.ts`). The
models must come out the same voxel for voxel, so the JavaScript number semantics the original
leaned on are kept here on purpose: `js_hypot` (V8's), `js_round` (halves up), `imul` (32-bit).
Cells are kept in insertion order, as a JS Map keeps them; which cell wins a tie depends on it.
"""

from __future__ import annotations

import math
from typing import Callable, Iterator, Optional

# How a cell's surface is finished: what material it's drawn in. `skin`, `hair` and `iris` are
# tinted: their colour is shading only (near white), and the character's own colour is multiplied in.
FINISHES = ("cloth", "leather", "metal", "gloss", "skin", "hair", "iris")


class Voxel:
    __slots__ = ("color", "finish", "bone")

    def __init__(self, color: int, finish: str, bone: Optional[str] = None):
        self.color = color  # sRGB, 0xRRGGBB
        self.finish = finish
        # The bone it moves with, where the body's own (bone_at) won't do: a beard hangs from the head.
        self.bone = bone

    def but(self, **kw) -> "Voxel":
        """A copy with these fields changed (`{ ...v, color }`)."""
        return Voxel(kw.get("color", self.color), kw.get("finish", self.finish), kw.get("bone", self.bone))


# --- JavaScript arithmetic ----------------------------------------------------------------------


def js_hypot(*v: float) -> float:
    """Math.hypot as V8 computes it (scaled, Kahan-summed), which isn't always Python's to the last bit."""
    a = [abs(x) for x in v]
    m = max(a)
    if m == 0:
        return 0.0
    s = 0.0
    comp = 0.0
    for x in a:
        n = x / m
        summand = n * n - comp
        pre = s + summand
        comp = (pre - s) - summand
        s = pre
    return math.sqrt(s) * m


def js_round(v: float) -> int:
    """Math.round: to the nearest integer, halves toward +∞."""
    r = math.floor(v)
    return r + 1 if v - r >= 0.5 else r


def imul(a: int, b: int) -> int:
    """Math.imul, as an unsigned 32-bit result."""
    return (a * b) & 0xFFFFFFFF


def sign(v: float) -> int:
    return (v > 0) - (v < 0)


# --- The grid -----------------------------------------------------------------------------------


class Grid:
    __slots__ = ("cells",)

    def __init__(self):
        self.cells: dict[tuple[int, int, int], Voxel] = {}

    def get(self, x, y, z) -> Optional[Voxel]:
        return self.cells.get((x, y, z))

    def has(self, x, y, z) -> bool:
        return (x, y, z) in self.cells

    def set(self, x, y, z, v: Voxel) -> None:
        self.cells[(x, y, z)] = v

    def delete(self, x, y, z) -> None:
        self.cells.pop((x, y, z), None)

    @property
    def size(self) -> int:
        return len(self.cells)

    def __iter__(self) -> Iterator[tuple[int, int, int, Voxel]]:
        for (x, y, z), v in list(self.cells.items()):
            yield x, y, z, v

    def add(self, other: "Grid") -> "Grid":
        """Every cell of `other` laid into this one, over what's here."""
        self.cells.update(other.cells)
        return self

    def filter(self, keep: Callable[[int, int, int, Voxel], bool]) -> "Grid":
        out = Grid()
        for (x, y, z), v in self.cells.items():
            if keep(x, y, z, v):
                out.cells[(x, y, z)] = v
        return out

    def repaint(self, paint: Callable[[int, int, int, Voxel], Optional[Voxel]]) -> "Grid":
        """Repaints every cell (`paint` returning None leaves one as it is); it keeps the bone it moves with."""
        for (x, y, z), v in list(self.cells.items()):
            p = paint(x, y, z, v)
            if p:
                self.cells[(x, y, z)] = p if p.bone or not v.bone else p.but(bone=v.bone)
        return self


DIRS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def exposed(g: Grid, x, y, z, also: Optional[Grid] = None) -> bool:
    """Whether a cell of `g` has an open face (a neighbour empty in `g` and in `also`)."""
    c = g.cells
    for a, b, d in DIRS:
        k = (x + a, y + b, z + d)
        if k not in c and not (also is not None and k in also.cells):
            return True
    return False


# --- Shapes -------------------------------------------------------------------------------------


class Shape:
    """A signed distance (negative inside), in voxels, with a box it's inside."""

    __slots__ = ("min", "max", "d")

    def __init__(self, mn, mx, d: Callable[[float, float, float], float]):
        self.min = tuple(mn)
        self.max = tuple(mx)
        self.d = d


def round_box(center, half, r: float = 0) -> Shape:
    """A box `half` from its `center` each way, its edges rounded by `r`."""
    rr = min(r, half[0], half[1], half[2])
    cx, cy, cz = center
    hx, hy, hz = half

    def d(x, y, z):
        q0 = abs(x - cx) - hx + rr
        q1 = abs(y - cy) - hy + rr
        q2 = abs(z - cz) - hz + rr
        outside = js_hypot(max(q0, 0), max(q1, 0), max(q2, 0))
        return outside + min(max(q0, q1, q2), 0) - rr

    return Shape((cx - hx, cy - hy, cz - hz), (cx + hx, cy + hy, cz + hz), d)


def ellipsoid(center, radii) -> Shape:
    m = min(radii)
    cx, cy, cz = center
    rx, ry, rz = radii

    def d(x, y, z):
        k = js_hypot((x - cx) / rx, (y - cy) / ry, (z - cz) / rz)
        return (k - 1) * m

    return Shape((cx - rx, cy - ry, cz - rz), (cx + rx, cy + ry, cz + rz), d)


def capsule(a, b, r: float) -> Shape:
    """A rod of radius `r` from `a` to `b`, rounded at its ends."""
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    len2 = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2 or 1

    def d(x, y, z):
        ap = (x - a[0], y - a[1], z - a[2])
        t = max(0, min(1, (ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / len2))
        return js_hypot(ap[0] - ab[0] * t, ap[1] - ab[1] * t, ap[2] - ab[2] * t) - r

    return Shape(
        (min(a[0], b[0]) - r, min(a[1], b[1]) - r, min(a[2], b[2]) - r),
        (max(a[0], b[0]) + r, max(a[1], b[1]) + r, max(a[2], b[2]) + r),
        d,
    )


def union(*shapes: Shape) -> Shape:
    ds = [s.d for s in shapes]
    return Shape(
        [min(s.min[i] for s in shapes) for i in range(3)],
        [max(s.max[i] for s in shapes) for i in range(3)],
        lambda x, y, z: min(f(x, y, z) for f in ds),
    )


def subtract(a: Shape, b: Shape) -> Shape:
    return Shape(a.min, a.max, lambda x, y, z: max(a.d(x, y, z), -b.d(x, y, z)))


def intersect(a: Shape, b: Shape) -> Shape:
    return Shape(
        [max(a.min[i], b.min[i]) for i in range(3)],
        [min(a.max[i], b.max[i]) for i in range(3)],
        lambda x, y, z: max(a.d(x, y, z), b.d(x, y, z)),
    )


def mirror(s: Shape) -> Shape:
    """The same shape on the other side (x → −x)."""
    return Shape((-s.max[0], s.min[1], s.min[2]), (-s.min[0], s.max[1], s.max[2]), lambda x, y, z: s.d(-x, y, z))


def both(s: Shape) -> Shape:
    """A shape and its mirror image."""
    return union(s, mirror(s))


def fill(g: Grid, shape: Shape, paint, where=None) -> Grid:
    """The cells whose centres are inside `shape`, painted (a None paint leaves a cell out)."""
    for x in range(math.floor(shape.min[0]) - 1, math.ceil(shape.max[0]) + 1):
        for y in range(math.floor(shape.min[1]) - 1, math.ceil(shape.max[1]) + 1):
            for z in range(math.floor(shape.min[2]) - 1, math.ceil(shape.max[2]) + 1):
                if shape.d(x + 0.5, y + 0.5, z + 0.5) > 0:
                    continue
                if where is not None and not where(x, y, z):
                    continue
                v = paint(x, y, z)
                if v:
                    g.set(x, y, z, v)
    return g


def carve(g: Grid, shape: Shape) -> Grid:
    """Empties the cells whose centres are inside `shape`."""
    for x, y, z, _ in g:
        if shape.d(x + 0.5, y + 0.5, z + 0.5) <= 0:
            g.delete(x, y, z)
    return g


_OFFSETS: dict[float, list[tuple[int, int, int, float]]] = {}


def _offsets(to: float):
    if to not in _OFFSETS:
        r = math.ceil(to)
        out = []
        for a in range(-r, r + 1):
            for b in range(-r, r + 1):
                for c in range(-r, r + 1):
                    d = js_hypot(a, b, c)
                    if 0 < d <= to:
                        out.append((a, b, c, d))
        _OFFSETS[to] = out
    return _OFFSETS[to]


def shell(of: Grid, to: float, frm: float = 0, where=None, nearest: Optional[dict] = None) -> dict:
    """
    The cells around `of` (not in it) whose centres are more than `frm` and at most `to` voxels
    from the nearest of its cells: a shell to build gear on. `where` limits which of `of`'s cells
    count. `nearest`, if given, is filled in with the nearest of `of`'s cells to each.
    """
    offsets = _offsets(to)
    cells = of.cells
    out: dict[tuple[int, int, int], float] = {}
    for (x, y, z) in cells:
        if where is not None and not where(x, y, z):
            continue
        if not exposed(of, x, y, z):
            continue
        for a, b, c, d in offsets:
            k = (x + a, y + b, z + c)
            if k in cells:
                continue
            was = out.get(k)
            if was is None or d < was:
                out[k] = d
                if nearest is not None:
                    nearest[k] = (x, y, z)
    return {k: d for k, d in out.items() if d > frm}


# --- Paint --------------------------------------------------------------------------------------


def hash3(x: int, y: int, z: int, seed: int = 0) -> float:
    """A number in [0, 1) for a cell, the same every time."""
    h = imul(x, 374761393) ^ imul(y, 668265263) ^ imul(z, 2147483647) ^ imul(seed, 144665)
    h = imul(h ^ (h >> 13), 1274126177)
    h ^= h >> 16
    return h / 4294967296


def noise3(x: float, y: float, z: float, scale: float, seed: int = 0) -> float:
    """Smooth noise in [0, 1), varying over about `scale` voxels."""
    fx, fy, fz = x / scale, y / scale, z / scale
    ix, iy, iz = math.floor(fx), math.floor(fy), math.floor(fz)

    def s(t):
        return t * t * (3 - 2 * t)

    tx, ty, tz = s(fx - ix), s(fy - iy), s(fz - iz)

    def lerp(a, b, t):
        return a + (b - a) * t

    def h(a, b, c):
        return hash3(ix + a, iy + b, iz + c, seed)

    return lerp(
        lerp(lerp(h(0, 0, 0), h(1, 0, 0), tx), lerp(h(0, 1, 0), h(1, 1, 0), tx), ty),
        lerp(lerp(h(0, 0, 1), h(1, 0, 1), tx), lerp(h(0, 1, 1), h(1, 1, 1), tx), ty),
        tz,
    )


def channels(c: int) -> tuple[int, int, int]:
    return (c >> 16) & 255, (c >> 8) & 255, c & 255


def pack(r: float, g: float, b: float) -> int:
    def q(v):
        return max(0, min(255, js_round(v)))

    return (q(r) << 16) | (q(g) << 8) | q(b)


def shade(c: int, k: float) -> int:
    """A colour lightened (k > 1) or darkened (k < 1)."""
    r, g, b = channels(c)
    return pack(r * k, g * k, b * k)


def mix(a: int, b: int, t: float) -> int:
    p = channels(a)
    q = channels(b)
    return pack(p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t, p[2] + (q[2] - p[2]) * t)


def jitter(c: int, x, y, z, amount: float = 0.06, seed: int = 0) -> int:
    """`c` varied a little cell by cell, by up to `amount` either way: what makes voxels read as voxels."""
    return shade(c, 1 + (hash3(x, y, z, seed) * 2 - 1) * amount)


def paint(c: int, finish: str, amount: float = 0.06, seed: int = 0):
    """A cell of `c` in `finish`, jittered."""
    return lambda x, y, z, *_: Voxel(jitter(c, x, y, z, amount, seed), finish)
