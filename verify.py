"""
Compares built character models with reference ones, part by part: every primitive's vertices
(positions, normals, colours, joints, weights), its triangles and material, the armature and its
bind matrices, and every clip's keys. The values are compared as stored, so any difference at all
shows.

  python tools/characters/verify.py REFERENCE [BUILT]

Both hold a folder for each body (`<race>_<sex>/body.glb` and `gear/<item>.glb`, as build.py
writes them) and the props (`props/<prop>.glb`); every body and prop in REFERENCE is compared. BUILT defaults to `models/` beside this file,
where build.py puts them. A folder laid out as bellweather-v2's library (`body/model.glb`,
`gear/<item>/model.glb`) or holding one body's files directly is compared as one body.
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build import OUT  # noqa: E402
from defs import ITEM_IDS  # noqa: E402
from gltf import Glb  # noqa: E402
from props import PROPS  # noqa: E402


def find(root: str, name: str) -> str:
    for p in (os.path.join(root, *name.split("/")) + ".glb", os.path.join(root, *name.split("/"), "model.glb")):
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"{name} in {root}")


def summary(g: Glb) -> dict:
    """Everything that makes the model what it is, keyed so files laid out differently compare."""
    j = g.json
    nodes = j["nodes"]
    out = {}
    for n in nodes:
        name = n.get("name")
        out[f"node {name} translation"] = [round(v, 9) for v in n.get("translation", [0, 0, 0])]
        out[f"node {name} children"] = sorted(nodes[c]["name"] for c in n.get("children", []))
        if "extras" in n:
            out[f"node {name} extras"] = n["extras"]
        if "mesh" in n:
            for i, p in enumerate(j["meshes"][n["mesh"]]["primitives"]):
                key = f"part {name} primitive {i}"
                out[f"{key} material"] = j["materials"][p["material"]]["name"]
                for attr, acc in sorted(p["attributes"].items()):
                    out[f"{key} {attr}"] = g.accessor(acc)
                out[f"{key} indices"] = g.accessor(p["indices"])
    for s in j.get("skins", []):
        out[f"skin {s.get('name')} joints"] = [nodes[i]["name"] for i in s["joints"]]
        out[f"skin {s.get('name')} skeleton"] = nodes[s["skeleton"]]["name"] if "skeleton" in s else None
        out[f"skin {s.get('name')} inverse"] = g.accessor(s["inverseBindMatrices"])
    used = {v for k, v in out.items() if k.endswith(" material")}
    for m in j.get("materials", []):
        if m["name"] in used:
            # Defaults filled in, and as float32 (what any engine keeps), since writers differ in both.
            pbr = m.get("pbrMetallicRoughness", {})
            f32 = lambda v: struct.unpack("<f", struct.pack("<f", v))[0]  # noqa: E731
            out[f"material {m['name']}"] = [
                [f32(v) for v in pbr.get("baseColorFactor", [1, 1, 1, 1])],
                f32(pbr.get("metallicFactor", 1)),
                f32(pbr.get("roughnessFactor", 1)),
            ]
    for a in j.get("animations", []):
        for c in a["channels"]:
            s = a["samplers"][c["sampler"]]
            key = f"clip {a['name']} {nodes[c['target']['node']]['name']} {c['target']['path']}"
            out[f"{key} times"] = g.accessor(s["input"])
            out[f"{key} values"] = g.accessor(s["output"])
            out[f"{key} interpolation"] = s.get("interpolation", "LINEAR")
    return out


def compare(ref: str, built: str) -> list[str]:
    a = summary(Glb(ref))
    b = summary(Glb(built))
    problems = []
    for k in sorted(set(a) | set(b)):
        if k not in b:
            problems.append(f"missing: {k}")
        elif k not in a:
            problems.append(f"extra: {k}")
        elif a[k] != b[k]:
            x, y = a[k], b[k]
            if isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
                diff = [i for i in range(len(x)) if x[i] != y[i]]
                problems.append(f"differs: {k} ({len(diff)} of {len(x)} values, first at {diff[0]}: {x[diff[0]]} vs {y[diff[0]]})")
            else:
                lx = len(x) if isinstance(x, list) else "-"
                ly = len(y) if isinstance(y, list) else "-"
                problems.append(f"differs: {k} (reference {str(x)[:80]} [{lx}], built {str(y)[:80]} [{ly}])")
    return problems


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    ref = sys.argv[1]
    built = sys.argv[2] if len(sys.argv) > 2 else OUT
    try:
        find(ref, "body")
        pairs = [(ref, built, "")]
    except FileNotFoundError:
        bodies = sorted(d for d in os.listdir(ref) if os.path.isdir(os.path.join(ref, d)) and d != "props")
        pairs = [(os.path.join(ref, b), os.path.join(built, b), b + "/") for b in bodies]
    bad = 0
    for ref_dir, built_dir, label in pairs:
        bad += compare_body(ref_dir, built_dir, label)
    if os.path.isdir(os.path.join(ref, "props")):
        bad += compare_all(os.path.join(ref, "props"), os.path.join(built, "props"), "props/", list(PROPS))
    print("All the same." if not bad else f"{bad} models differ.")
    return 1 if bad else 0


def compare_body(ref: str, built: str, label: str) -> int:
    return compare_all(ref, built, label, ["body"] + [f"gear/{i}" for i in ITEM_IDS])


def compare_all(ref: str, built: str, label: str, names: list) -> int:
    bad = 0
    for name in names:
        try:
            problems = compare(find(ref, name), find(built, name))
        except FileNotFoundError as e:
            problems = [f"missing: {e}"]
        print(f"{'ok  ' if not problems else 'DIFF'} {label}{name}")
        for p in problems[:12]:
            print("     ", p)
        if len(problems) > 12:
            print(f"      … and {len(problems) - 12} more")
        bad += bool(problems)
    return bad


if __name__ == "__main__":
    sys.exit(main())
