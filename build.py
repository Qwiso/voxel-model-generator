"""
Builds the character models into `models/` beside this file (or wherever `--out` says), a folder
for each body (races.py: `<race>_<sex>`):

  <body>/body.glb          the armature, the body's regions (`body_<region>`, `body_ears`), the
                           skull (`head_skull`) and the pieces of a face (`eyes_<style>`, `brows_<style>`,
                           `nose_<style>`, `mouth_<style>`), hair (`hair_<style>`), beards
                           (`beard_<style>`, men only), and the clips
  <body>/gear/<item>.glb   each item, skinned to the same armature, built on this body
  props/<prop>.glb         what's handled but not worn (props.py: a fish, a bobber), not skinned,
                           the same for every body

  python build.py                       # every body and every item, into models/
  python build.py hood gold_band        # every body, and only the items named
  python build.py --body elf_female     # only this body (again for more)
  python build.py --no-gear             # bodies only
  python build.py --out DIR             # somewhere else

Ported from bellweather-v2 (commit 3ea05c9, `packages/assets/tools/characters/build.ts`).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from body import (  # noqa: E402
    beard_grid,
    body_grid,
    brows_grid,
    ears_grid,
    eyes_grid,
    hair_grid,
    head_grid,
    mouth_grid,
    nose_grid,
    held_to_head,
    misbound,
    regions,
    skull_grid,
)
from clips import sampled  # noqa: E402
from defs import (  # noqa: E402
    BEARD_STYLES,
    BONE_PARENT,
    BONES,
    BROW_STYLES,
    CLIP_NAMES,
    EYE_STYLES,
    HAIR_STYLES,
    ITEM_IDS,
    MOUTH_STYLES,
    NOSE_STYLES,
)
from gear import GEAR, gear_context  # noqa: E402
from gltf import ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER, FLOAT, UBYTE, UINT, USHORT, GlbWriter  # noqa: E402
from mesh import MATERIALS, linear, voxel_faces  # noqa: E402
from props import PROPS  # noqa: E402
from races import BODIES, current, use  # noqa: E402
from rig import joint_metres  # noqa: E402
from voxels import Grid  # noqa: E402

# Where the models go without --out: `models/` beside this file.
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
GENERATOR = "tideweald tools/characters"


class Doc:
    """
    A model being written: the armature, the skin binding meshes to it, and the materials. Not
    `rigged`, it's just meshes (a prop), its parts at the top of the scene.
    """

    def __init__(self, scene: str, rigged: bool = True):
        self.w = GlbWriter(GENERATOR)
        self.materials: dict[str, int] = {}
        # The parts' names: the game finds a part by its name, and Godot renames one of two alike.
        self.names: set[str] = set()
        if not rigged:
            self.scene = self.w.add("scenes", {"name": scene, "nodes": []})
            self.armature = None
            return
        self.armature = self.w.add("nodes", {"name": "Armature", "children": []})
        self.w.add("scenes", {"name": scene, "nodes": [self.armature]})
        # The bones, each placed relative to its parent and unturned, so a bone's rotation in a clip
        # is about the character's own axes.
        self.bones: dict[str, int] = {}
        for b in BONES:
            p = BONE_PARENT[b]
            at = joint_metres(b)
            frm = joint_metres(p) if p else (0, 0, 0)
            n = self.w.add("nodes", {"name": b, "translation": [at[i] - frm[i] for i in range(3)]})
            parent = self.w.json["nodes"][self.bones[p] if p else self.armature]
            parent.setdefault("children", []).append(n)
            self.bones[b] = n
        inverse = []
        for b in BONES:
            x, y, z = joint_metres(b)
            # Column-major: identity with the joint's place negated in the last column.
            inverse += [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -x, -y, -z, 1]
        self.skin = self.w.add(
            "skins",
            {
                "name": "Armature",
                "inverseBindMatrices": self.w.accessor(inverse, FLOAT, "MAT4", name="inverseBind"),
                "skeleton": self.bones["root"],
                "joints": [self.bones[b] for b in BONES],
            },
        )

    def material(self, finish: str) -> int:
        if finish not in self.materials:
            rough, metal, tint = MATERIALS[finish]
            t = tint or (255, 255, 255)
            self.materials[finish] = self.w.add(
                "materials",
                {
                    "name": finish,
                    "pbrMetallicRoughness": {
                        "baseColorFactor": [linear(t[0]), linear(t[1]), linear(t[2]), 1],
                        "metallicFactor": metal,
                        "roughnessFactor": rough,
                    },
                },
            )
        return self.materials[finish]

    def part(self, name: str, grid: Grid, against: Grid) -> None:
        """
        A part's node: its mesh, skinned, named for the part, the name kept in its extras too (as
        `part`), its faces against `against` left out. A primitive for each finish.
        """
        if grid.size == 0:
            return
        if name in self.names:
            raise ValueError(f"{current().name}: two parts named {name}")
        self.names.add(name)
        w = self.w
        prims = []
        for finish, b in voxel_faces(grid, against).items():
            count = len(b.positions) // 3
            attributes = {
                "POSITION": w.accessor(b.positions, FLOAT, "VEC3", target=ARRAY_BUFFER, bounds=True),
                "NORMAL": w.accessor(b.normals, FLOAT, "VEC3", target=ARRAY_BUFFER),
                # Colour in 16 bits a channel (linear, so 8 would band in the shadows) and
                # weights in 8, both normalized, which keeps a vertex to 40 bytes.
                "COLOR_0": w.accessor(b.colors, USHORT, "VEC4", normalized=True, target=ARRAY_BUFFER),
            }
            if self.armature is not None:
                attributes["JOINTS_0"] = w.accessor(b.joints, UBYTE, "VEC4", target=ARRAY_BUFFER)
                attributes["WEIGHTS_0"] = w.accessor(b.weights, UBYTE, "VEC4", normalized=True, target=ARRAY_BUFFER)
            prims.append(
                {
                    "attributes": attributes,
                    "indices": w.accessor(b.indices, UINT if count > 65535 else USHORT, "SCALAR", target=ELEMENT_ARRAY_BUFFER),
                    "material": self.material(finish),
                }
            )
        mesh = w.add("meshes", {"name": name, "primitives": prims})
        if self.armature is None:
            node = w.add("nodes", {"name": name, "mesh": mesh, "extras": {"part": name}})
            w.json["scenes"][self.scene]["nodes"].append(node)
            return
        node = w.add("nodes", {"name": name, "mesh": mesh, "skin": self.skin, "extras": {"part": name}})
        w.json["nodes"][self.armature]["children"].append(node)

    def clips(self) -> None:
        """Every clip, as an animation on the armature's bones."""
        w = self.w
        hips_at = joint_metres("hips")
        for name in CLIP_NAMES:
            times, channels = sampled(name, hips_at)
            inp = w.accessor(times, FLOAT, "SCALAR", bounds=True, name=f"{name} time")
            samplers, chans = [], []
            for bone, path, values in channels:
                out = w.accessor(values, FLOAT, "VEC4" if path == "rotation" else "VEC3")
                samplers.append({"input": inp, "output": out, "interpolation": "LINEAR"})
                chans.append({"sampler": len(samplers) - 1, "target": {"node": self.bones[bone], "path": path}})
            w.add("animations", {"name": name, "samplers": samplers, "channels": chans})


def body_context() -> Grid:
    """The body, without its head, and the skull every face is on: what the body's parts are drawn against."""
    return body_grid().add(skull_grid())


def check_bones(body: Grid) -> None:
    """Raises if any of the body moves with a bone that isn't its part's (body.misbound), saying where."""
    wrong = misbound(body)
    if not wrong:
        return
    r = current()
    # Where each bone's space is (rig.bone_at), to say what reached where.
    where = {
        "shoulder": f"arm_in ({r.arm_in}) or more out",
        "upper_arm": f"arm_in ({r.arm_in}) or more out",
        "forearm": f"arm_in ({r.arm_in}) or more out",
        "hand": f"arm_in ({r.arm_in}) or more out",
        "head": f"above head_bottom ({r.head_bottom})",
        "thigh": f"below the hip ({r.hip}) and inside arm_in + 1",
        "shin": f"below the knee ({r.knee}) and inside arm_in + 1",
        "foot": f"below the ankle ({r.ankle}) and inside arm_in + 1",
    }
    lines = []
    for (part, bone), n in sorted(wrong.items(), key=lambda kv: -kv[1]):
        space = where.get(bone.rsplit("_", 1)[0], "the trunk's space")
        lines.append(f"  {n} voxels of the {part} move with {bone} ({space})")
    raise ValueError(f"{r.name}: parts of the body reach into others' space and would move with them:\n" + "\n".join(lines))


def body_document() -> bytes:
    doc = Doc("Character")
    context = body_context()
    body = body_grid()
    check_bones(body)
    for region, grid in regions(body).items():
        doc.part(f"body_{region}", grid, context)
    # Ears are their own part (a hood hides them), so the skull isn't drawn against them.
    doc.part("body_ears", ears_grid(), context)
    # The head and the pieces of a face, each drawn against the whole skull (which their patches
    # are part of) and the body.
    # Not "head": that's a bone's name, and Godot renames one of two nodes that share a name.
    doc.part("head_skull", head_grid(), body_grid())
    for style in EYE_STYLES:
        doc.part(f"eyes_{style}", held_to_head(eyes_grid(style)), context)
    for style in BROW_STYLES:
        doc.part(f"brows_{style}", held_to_head(brows_grid(style)), context)
    for style in NOSE_STYLES:
        doc.part(f"nose_{style}", held_to_head(nose_grid(style)), context)
    for style in MOUTH_STYLES:
        doc.part(f"mouth_{style}", held_to_head(mouth_grid(style)), context)
    for style in HAIR_STYLES:
        doc.part(f"hair_{style}", hair_grid(style), context)
    if current().sex == "male":
        for style in BEARD_STYLES:
            doc.part(f"beard_{style}", beard_grid(style), context)
    doc.clips()
    return doc.w.bytes()


def gear_document(item: str) -> bytes:
    """An item: its meshes, skinned to the same armature as the body (and so to any character's skeleton)."""
    doc = Doc(item)
    context = gear_context()
    for name, grid in GEAR[item]().items():
        doc.part(name, grid, context)
    return doc.w.bytes()


def prop_document(name: str) -> bytes:
    """A prop: its mesh alone, not skinned."""
    doc = Doc(name, rigged=False)
    doc.part(name, PROPS[name](), None)
    return doc.w.bytes()


def whole(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "wb") as f:
        f.write(data)
    os.replace(path + ".tmp", path)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the character models.")
    ap.add_argument("items", nargs="*", help="only these items (the body is always built)")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--body", action="append", choices=list(BODIES), help="only this body (races.py); again for more")
    ap.add_argument("--no-gear", action="store_true", help="the bodies only")
    args = ap.parse_args()
    for i in args.items:
        if i not in GEAR:
            ap.error(f"no item {i!r}; there are: {', '.join(ITEM_IDS)}")
    items = [] if args.no_gear else [i for i in ITEM_IDS if not args.items or i in args.items]
    if not args.no_gear and not args.items:
        for name in PROPS:
            whole(os.path.join(args.out, "props", f"{name}.glb"), prop_document(name))
        print(f"Built {len(PROPS)} props into {os.path.join(args.out, 'props')}.")
    for name in args.body or list(BODIES):
        use(name)
        out = os.path.join(args.out, name)
        whole(os.path.join(out, "body.glb"), body_document())
        for i in items:
            whole(os.path.join(out, "gear", f"{i}.glb"), gear_document(i))
        print(f"Built {name} and {len(items)} items of gear into {out}.")


if __name__ == "__main__":
    main()

