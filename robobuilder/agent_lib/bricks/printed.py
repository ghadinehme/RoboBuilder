"""Custom 3D-printed part (the Cross+Print task): a CadQuery solid plus its brick interfaces.

    import cadquery as cq
    from bricks.printed import PrintedPart, STUD, PLATE, BRICK

    def part():
        p = PrintedPart("hook", "a hook that grabs the rope")
        p.add(cq.Workplane("XY").box(32, 16, 9.6, centered=(True, True, False)).translate((0, 0, -9.6)))
        p.studs_top([(x, y) for x in (-12, -4, 4, 12) for y in (-4, 4)], z=0.0)     # studs on the top face z = 0
        p.sockets_bottom([(x, y) for x in (-12, 12) for y in (-4, 4)], z=-9.6)      # anti-studs in the bottom face
        p.pin_hole((-8, 0, -5.6), axis="y", length=16)                              # round pin hole(s)
        p.axle_hole((8, 0, -5.6), axis="y", length=16)                              # cross hole(s)
        return p

`brick-bench part <script.py>` runs the script's `part()`, exports the STL and registers the part. Frames are mm, z up;
the part's origin is wherever you model it (the design places that origin). Holes are 8 mm long segments: a longer
hole is declared as several 8 mm holes along its axis (as on a beam). Interfaces are cut / added only by the
helpers; anything else you model with CadQuery (`add`, `cut`).
"""
from __future__ import annotations

import json
import os

STUD = 8.0  # stud pitch [mm]
PLATE = 3.2  # plate height
BRICK = 9.6  # brick height
STUD_D, STUD_H = 4.8, 1.7  # a stud
SOCKET_D, SOCKET_DEPTH = 4.9, 2.0  # a printed anti-stud socket (a stud presses into it)
PIN_HOLE_D = 4.9  # round pin hole (a pin's 4.8 mm plus print clearance)
AXLE_CROSS, AXLE_ARM = 4.9, 1.9  # cross hole: 4.8 x 1.8 mm cross plus clearance
AXES = ("x", "y", "z")
if os.environ.get("RB_PRINT_FIT") == "real":  # sizes for a real print, tuned with a fit coupon on an FDM printer
    STUD_D, SOCKET_D, PIN_HOLE_D, AXLE_CROSS, AXLE_ARM = 5.0, 5.1, 5.0, 5.0, 2.0  # (the simulator is unchanged)


def _cq():
    import cadquery as cq  # noqa: PLC0415

    return cq


def _cyl(d: float, length: float, centre, axis: str, pad: float = 0.0):
    """a cylinder of diameter d and length (+2 pad) centred on ``centre`` along a global axis"""
    cq = _cq()
    L = length + 2 * pad
    s = cq.Workplane("XY").circle(d / 2).extrude(L).translate((0, 0, -L / 2))
    if axis == "x":
        s = s.rotate((0, 0, 0), (0, 1, 0), 90)
    elif axis == "y":
        s = s.rotate((0, 0, 0), (1, 0, 0), 90)
    return s.translate(tuple(float(v) for v in centre))


def _cross(length: float, centre, axis: str, pad: float = 0.0):
    cq = _cq()
    L = length + 2 * pad
    s = (cq.Workplane("XY").rect(AXLE_CROSS, AXLE_ARM).extrude(L)
         .union(cq.Workplane("XY").rect(AXLE_ARM, AXLE_CROSS).extrude(L)).translate((0, 0, -L / 2)))
    if axis == "x":
        s = s.rotate((0, 0, 0), (0, 1, 0), 90)
    elif axis == "y":
        s = s.rotate((0, 0, 0), (1, 0, 0), 90)
    return s.translate(tuple(float(v) for v in centre))


def _segments(centre, axis: str, length: float):
    """centres of the 8 mm hole segments of a hole of ``length`` (a multiple of 8) centred on ``centre``"""
    n = int(round(length / 8.0))
    if n < 1 or abs(n * 8.0 - length) > 0.01:
        raise ValueError(f"hole length {length} mm: use a multiple of 8 mm")
    k = AXES.index(axis)
    out = []
    for i in range(n):
        c = [float(v) for v in centre]
        c[k] += (i - (n - 1) / 2) * 8.0
        out.append(c)
    return out


class PrintedPart:
    """One printed part type: CadQuery solids (add / cut) plus declared brick interfaces."""

    def __init__(self, name: str = "printed_part", title: str = ""):
        self.name, self.title = name, title or name
        self._add, self._cut = [], []
        self.top: dict | None = None
        self.bottom: dict | None = None
        self.pins: list = []
        self.axles: list = []

    # -- free geometry -------------------------------------------------------------------------------------------
    def add(self, solid):
        """union a CadQuery Workplane / Shape into the part"""
        self._add.append(solid)
        return self

    def cut(self, solid):
        """subtract a CadQuery Workplane / Shape (applied before the interface holes are cut)"""
        self._cut.append(solid)
        return self

    # -- interfaces (the fixed menu) -----------------------------------------------------------------------------
    def studs_top(self, xy, z: float):
        """studs (4.8 x 1.7 mm) standing on the top face at height z; positions on the 8 mm grid. One top face."""
        if self.top is not None:
            raise ValueError("one stud face on top per part (one height)")
        self.top = {"z": float(z), "xy": [[float(x), float(y)] for x, y in xy]}
        return self

    def sockets_bottom(self, xy, z: float):
        """anti-stud sockets (4.9 mm, 2 mm deep) in the bottom face at height z: studs of the part below press in.
        One bottom face; positions on the 8 mm grid; (top z - bottom z) a multiple of the plate height 3.2 mm."""
        if self.bottom is not None:
            raise ValueError("one anti-stud face underneath per part (one height)")
        self.bottom = {"z": float(z), "xy": [[float(x), float(y)] for x, y in xy]}
        return self

    def pin_hole(self, centre, axis: str = "y", length: float = 8.0):
        """a round pin hole (pins, and axles that turn in it) along a part axis; length a multiple of 8 mm"""
        if axis not in AXES:
            raise ValueError("axis is 'x', 'y' or 'z'")
        self.pins += [[*c, axis] for c in _segments(centre, axis, length)]
        return self

    def axle_hole(self, centre, axis: str = "y", length: float = 8.0):
        """a cross hole (an axle through it turns the part with it) along a part axis; length a multiple of 8 mm"""
        if axis not in AXES:
            raise ValueError("axis is 'x', 'y' or 'z'")
        self.axles += [[*c, axis] for c in _segments(centre, axis, length)]
        return self

    # -- output ----------------------------------------------------------------------------------------------------
    def interfaces(self) -> dict:
        return {"name": self.name, "title": self.title, "studs_top": self.top, "studs_bottom": self.bottom,
                "pin_holes": self.pins, "axle_holes": self.axles}

    def build(self):
        """-> the finished CadQuery Workplane (solids, studs added, cuts, sockets and holes cut)"""
        if not self._add:
            raise ValueError("the part has no solid: add() at least one")
        body = self._add[0]
        for s in self._add[1:]:
            body = body.union(s)
        for s in self._cut:
            body = body.cut(s)
        if self.top:
            for x, y in self.top["xy"]:
                body = body.union(_cyl(STUD_D, STUD_H, (x, y, self.top["z"] + STUD_H / 2), "z", pad=0.0)
                                  .translate((0, 0, 0)))
        if self.bottom:
            for x, y in self.bottom["xy"]:
                body = body.cut(_cyl(SOCKET_D, SOCKET_DEPTH, (x, y, self.bottom["z"] + SOCKET_DEPTH / 2), "z", pad=0.01))
        for x, y, z, a in self.pins:
            body = body.cut(_cyl(PIN_HOLE_D, 8.0, (x, y, z), a, pad=0.01))
        for x, y, z, a in self.axles:
            body = body.cut(_cross(8.0, (x, y, z), a, pad=0.01))
        return body


def export(obj, interfaces: dict | None, out_dir: str) -> dict:
    """write part.stl and interfaces.json for a PrintedPart, a (solid, interfaces) tuple or a solid + interfaces"""
    os.makedirs(out_dir, exist_ok=True)
    if isinstance(obj, tuple):
        obj, interfaces = obj
    if isinstance(obj, PrintedPart):
        interfaces = obj.interfaces()
        obj = obj.build()
    if interfaces is None:
        raise ValueError("no interfaces: return a PrintedPart, or (solid, INTERFACES), or define INTERFACES")
    stl = os.path.join(out_dir, "part.stl")
    if hasattr(obj, "export") and not hasattr(obj, "val"):  # trimesh
        obj.export(stl)
    else:
        cq = _cq()
        cq.exporters.export(obj, stl, tolerance=0.02, angularTolerance=0.1)
    json.dump(interfaces, open(os.path.join(out_dir, "interfaces.json"), "w"), indent=1)
    return {"stl": stl, "interfaces": interfaces}


def load_part(spec_json: str) -> str:
    """make a registered printed part known to this Python's design library (bench_parts(), the inventory part set),
    so that bricks.design.validate / place / stats see it: load_part("/work/printed_parts/<id>.json") -> the part id"""
    from robobuilder.core.parts import BenchPart, Boxes, bench_parts, inventory_part_set  # noqa: PLC0415

    spec = json.load(open(spec_json))
    bx = tuple((tuple(float(v) for v in lo), tuple(float(v) for v in hi)) for lo, hi in spec["boxes"])
    lo = tuple(min(b[0][i] for b in bx) for i in range(3))
    hi = tuple(max(b[1][i] for b in bx) for i in range(3))
    bp = BenchPart(
        part_id=spec["part_id"], kind="connector", title=spec["title"], mass_g=float(spec["mass_g"]),
        com_mm=tuple(float(v) for v in spec["com_mm"]), shape=Boxes(lo, hi, bx),
        studs_top=tuple(tuple(float(v) for v in p) for p in spec["studs_top"]), top_z=float(spec["top_z"]),
        studs_bottom=tuple(tuple(float(v) for v in p) for p in spec["studs_bottom"]), bottom_z=float(spec["bottom_z"]),
        pin_holes=tuple((float(x), float(y), float(z), a) for x, y, z, a in spec["pin_holes"]),
        axle_holes=tuple((float(x), float(y), float(z), a) for x, y, z, a in spec["axle_holes"]),
        inventory=True, notes="custom 3D-printed PLA part")
    bench_parts()[spec["part_id"]] = bp
    inventory_part_set()[spec["part_id"]] = int(spec.get("copies", 4))
    return spec["part_id"]
