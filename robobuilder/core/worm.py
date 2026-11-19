"""Gear-mesh couplings and self-locking worm meshes (which shaft carries a mesh, which motors reach a worm), used by
the validator's drive statistics; and the pin-joint break force of the stud-clutch structure model."""
from __future__ import annotations

import os

import numpy as np

from .design import Design

PIN_BREAK_FORCE_N = float(os.environ.get("RB_PIN_BREAK_N", "50.0"))  # debug override (diagnostics)
"""Break force of a pin joint [N]. The joint breaks on the force magnitude; a pin is loaded mostly in shear
(a motor's reaction torque), which a pin does not fail in, so this is set well above the 25 N shear per pin of the
XL motor at stall with its two front pins 16 mm apart. Axial pull-out is not modelled separately."""


def gear_joint_specs(design: Design) -> list[dict]:
    """The declared gear meshes as couplings between the two gears' shafts (``--gears joint``): for each mesh, the
    axle each gear is cross-fitted on, that axle's bearing connection (its first hinge, or the motor output) and the
    speed ratio w_b / w_a = -z_a / z_b (spur meshes turn the shafts in opposite directions; the sign is relative to
    the gears' own axes, which the validator requires parallel, so it also holds for the axles). Gears on the same
    shaft need no coupling."""
    from .design import place  # noqa: PLC0415
    from .parts import bench_parts  # noqa: PLC0415

    from .gear_rules import joint_mesh  # noqa: PLC0415

    cat = bench_parts()
    P = place(design)
    parts = {p.name: p for p in design.parts}
    shaft = {c.child: c.parent for c in design.connections if c.kind == "cross"}
    # a free-turning bevel half (69761, round bore) idles on a bare axle (validator); in simulation it is
    # locked to that axle (idler_locks) and the two turn together in the axle's own bearing
    free = idler_bearings(design)
    shaft.update({g: axle for g, (axle, _) in free.items()})
    out = []
    for m in design.gear_meshes:
        sa, sb = shaft.get(m.gear_a), shaft.get(m.gear_b)
        if sa is None or sb is None or sa == sb:
            continue
        ba = free[m.gear_a][1] if m.gear_a in free else next(
            (c for c in design.connections if c.child == sa and c.kind in ("motor", "hinge")), None)
        bb = free[m.gear_b][1] if m.gear_b in free else next(
            (c for c in design.connections if c.child == sb and c.kind in ("motor", "hinge")), None)
        if ba is None or bb is None:
            continue
        za, zb = cat[parts[m.gear_a].part].teeth, cat[parts[m.gear_b].part].teeth
        ga, gb = P[m.gear_a].axis(), P[m.gear_b].axis()
        perpendicular = abs(float(np.dot(ga, gb))) < 1e-3
        k = (za / zb) if perpendicular else (-za / zb)  # about the gears' own axes (design._propagate)

        sa_sgn = 1.0 if float(np.dot(ga, P[sa].axis())) > 0 else -1.0  # gear axis vs its shaft's hinge axis
        sb_sgn = 1.0 if float(np.dot(gb, P[sb].axis())) > 0 else -1.0
        # joint: the mesh is always a gear joint (right angles; knob wheels / bevel halves, also parallel)
        out.append({"gears": (m.gear_a, m.gear_b), "shafts": (sa, sb), "bearings": (ba, bb),
                    "ratio": k * sa_sgn * sb_sgn, "right_angle": perpendicular,
                    "joint": perpendicular or joint_mesh(parts[m.gear_a].part, parts[m.gear_b].part)})  # fmt: skip
    return out


def idler_bearings(design: Design) -> dict[str, tuple]:
    """{free-turning bevel half (69761) in a gear mesh: (its axle, the axle's hinge in a hole)}. The validator
    makes it idle on a bare axle (nothing else turns with that axle), so the simulator locks the gear to its axle
    (:func:`idler_locks`) and the pair turns in the axle's hinge, which is the gear joint's bearing: the gear's own
    speed is then the mesh speed (with the gear on a revolute of its own, a gear joint on that revolute only fixes the
    gear's speed relative to its free axle, and the two shared the motion)."""
    from .parts import bench_parts  # noqa: PLC0415

    cat = bench_parts()
    meshed = {g for m in design.gear_meshes for g in (m.gear_a, m.gear_b)}
    out = {}
    for p in design.parts:
        if p.name not in meshed or p.part not in cat or not (cat[p.part].free_bore and cat[p.part].bevel_only):
            continue
        run = next((c for c in design.connections if c.parent == p.name and c.kind == "hinge"), None)
        brg = run and next((c for c in design.connections if c.child == run.child and c.kind == "hinge"
                            and c.parent != p.name), None)
        if brg is not None:
            out[p.name] = (run.child, brg)
    return out


def worm_lock_specs(design: Design) -> list[dict]:
    """Self-locking worm meshes. A single-start brick worm (4716) has a lead angle of ~4.5 deg, below the friction
    angle of ABS on ABS (atan 0.35-0.40 = 19-22 deg): the gear cannot turn the worm, whatever the load (only the worm
    can drive the gear). The gear joint couples the two shafts both ways, so the harness adds the missing
    one-way part as a brake on the worm's shaft: while every motor that drives the worm shaft is commanded 0 (IR
    level 0, brake or float alike: the worm holds by friction, not by the motor), the worm shaft's bearing joint (the
    motor joint itself when the worm sits on the motor output, else its hinge) gets a velocity drive to rest, capped at
    ``WORM_HOLD_TORQUE_NM / z``. When a driving motor is on, the bearing is the plain motor / hinge joint again: the
    worm then turns the gear at 1 : z at the motor line's speed (a gear-side load reaches the motor divided by z).

    Returns one dict per worm mesh: ``worm_shaft``, ``bearing`` (the bearing connection), ``teeth`` (the gear's z),
    ``motors`` (the motors whose train reaches the worm shaft without passing through any worm mesh from its gear
    side: a gear cannot drive a worm)."""
    from .design import shafts  # noqa: PLC0415
    from .parts import bench_parts  # noqa: PLC0415

    cat = bench_parts()
    parts = {p.name: p for p in design.parts}
    sh = shafts(design)
    teeth = {n: cat[p.part].teeth for n, p in parts.items() if p.part in cat}
    edges: dict[str, set[str]] = {}
    for m in design.gear_meshes:
        a, b = m.gear_a, m.gear_b
        if a not in sh or b not in sh or sh[a] == sh[b]:
            continue
        for x, y in ((a, b), (b, a)):
            if teeth.get(y) == 1 and teeth.get(x) != 1:  # gear -> worm: no power flow
                continue
            edges.setdefault(sh[x], set()).add(sh[y])
    reach: dict[str, set[str]] = {}  # shaft -> motors driving it
    for c in design.connections:
        if c.kind != "motor":
            continue
        todo, seen = [sh.get(c.child, c.child)], set()
        while todo:
            s = todo.pop()
            if s in seen:
                continue
            seen.add(s)
            reach.setdefault(s, set()).add(c.parent)
            todo.extend(edges.get(s, ()))
    out = []
    specs = {tuple(g["gears"]): g for g in gear_joint_specs(design)}
    for m in design.gear_meshes:
        g = specs.get((m.gear_a, m.gear_b))
        if g is None:
            continue
        for k, (w, other) in enumerate(((m.gear_a, m.gear_b), (m.gear_b, m.gear_a))):
            if teeth.get(w) == 1 and teeth.get(other) != 1:
                out.append({"worm": w, "gear": other, "worm_shaft": g["shafts"][k], "bearing": g["bearings"][k],
                            "teeth": int(teeth[other]), "motors": sorted(reach.get(g["shafts"][k], ()))})  # fmt: skip
    return out
