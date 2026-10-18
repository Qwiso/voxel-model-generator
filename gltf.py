"""
A small glTF 2.0 binary (.glb) writer and reader: enough for skinned voxel meshes, an armature and
sampled clips. Stdlib only, so it runs under any Python, Blender's included.
"""

import json
import struct

FLOAT = 5126
UBYTE = 5121
USHORT = 5123
UINT = 5125

ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963

_FMT = {FLOAT: "f", UBYTE: "B", USHORT: "H", UINT: "I"}
_SIZE = {FLOAT: 4, UBYTE: 1, USHORT: 2, UINT: 4}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


class GlbWriter:
    def __init__(self, generator: str):
        self.json = {
            "asset": {"version": "2.0", "generator": generator},
            "scene": 0,
            "scenes": [],
            "nodes": [],
            "meshes": [],
            "materials": [],
            "skins": [],
            "accessors": [],
            "bufferViews": [],
            "buffers": [],
            "animations": [],
        }
        self.bin = bytearray()

    def accessor(self, values, component: int, type_: str, *, normalized=False, target=None, bounds=False, name=None) -> int:
        """Packs `values` into the buffer as an accessor of its own, returning its index."""
        while len(self.bin) % 4:
            self.bin.append(0)
        data = struct.pack(f"<{len(values)}{_FMT[component]}", *values)
        view = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            view["target"] = target
        self.bin += data
        self.json["bufferViews"].append(view)
        w = WIDTH[type_]
        acc = {
            "bufferView": len(self.json["bufferViews"]) - 1,
            "componentType": component,
            "count": len(values) // w,
            "type": type_,
        }
        if name:
            acc["name"] = name
        if normalized:
            acc["normalized"] = True
        if bounds:
            # As stored: float32 for floats.
            stored = struct.unpack(f"<{len(values)}{_FMT[component]}", data)
            acc["min"] = [min(stored[i::w]) for i in range(w)]
            acc["max"] = [max(stored[i::w]) for i in range(w)]
        self.json["accessors"].append(acc)
        return len(self.json["accessors"]) - 1

    def add(self, kind: str, item: dict) -> int:
        self.json[kind].append(item)
        return len(self.json[kind]) - 1

    def bytes(self) -> bytes:
        while len(self.bin) % 4:
            self.bin.append(0)
        self.json["buffers"] = [{"byteLength": len(self.bin)}]
        doc = {k: v for k, v in self.json.items() if v != []}
        js = json.dumps(doc, separators=(",", ":")).encode()
        js += b" " * (-len(js) % 4)
        total = 12 + 8 + len(js) + 8 + len(self.bin)
        return (
            struct.pack("<4sII", b"glTF", 2, total)
            + struct.pack("<I4s", len(js), b"JSON")
            + js
            + struct.pack("<I4s", len(self.bin), b"BIN\0")
            + bytes(self.bin)
        )


class Glb:
    """A .glb read back: its JSON, and its accessors' values (as stored, not denormalized)."""

    def __init__(self, path: str):
        with open(path, "rb") as f:
            data = f.read()
        magic, _version, _total = struct.unpack_from("<4sII", data, 0)
        assert magic == b"glTF", path
        at = 12
        self.json = None
        self.bin = b""
        while at < len(data):
            length, kind = struct.unpack_from("<I4s", data, at)
            chunk = data[at + 8 : at + 8 + length]
            if kind == b"JSON":
                self.json = json.loads(chunk)
            elif kind == b"BIN\0":
                self.bin = chunk
            at += 8 + length

    def accessor(self, i: int) -> list:
        a = self.json["accessors"][i]
        v = self.json["bufferViews"][a["bufferView"]]
        comp = a["componentType"]
        w = WIDTH[a["type"]]
        size = _SIZE[comp]
        stride = v.get("byteStride", size * w)
        base = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        out = []
        for n in range(a["count"]):
            out += struct.unpack_from(f"<{w}{_FMT[comp]}", self.bin, base + n * stride)
        return out
