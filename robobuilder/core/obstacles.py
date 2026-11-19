# Copyright (c) 2026, robobuilder project.
# SPDX-License-Identifier: BSD-3-Clause

"""Parametric obstacles with difficulty levels, vehicle placement and the success / failure judge (pure Python).

Env frame: x = direction of travel, z up, metres. Every course starts on a surface at z = 0 unless stated
(the rope hangs higher). Geometry is static boxes / cylinders / capsules; the seesaw plank and the ramp board are
dynamic bodies. Each obstacle has a start line, a goal region, failure conditions and a time limit:

* success   -- the reference points (all part origins for ``goal.ref == "rear"``, the front-most part origin for
               ``"front"``, the towed load for ``"load"``) are inside the goal region, the vehicle is intact;
* fell      -- the chassis origin drops below ``fail_z``;
* flipped   -- the vehicle's up axis tilts more than 75 deg for 0.5 s;
* left_lane -- the chassis leaves ``|y| <= lane_half_width`` (with a ``centreline``: its distance from the centreline);
* broke     -- a part moved more than 15 mm from its design place relative to the chassis (a joint broke);
* stuck     -- progress improved less than 5 mm in ``stuck_window_s``;
* timeout   -- ``time_limit_s`` of driving elapsed.

``generate(kind, level)`` builds one course (level 1, 2 or 3; ``FINAL_LEVELS`` lists the levels of each obstacle).

A curved course (the U-turn) sets ``Obstacle.centreline``: progress, the goal and the lane are then measured along it
(arc length, distance from it) instead of along x and |y|.
"""

from __future__ import annotations

import dataclasses
import math
import os
import random
from dataclasses import asdict, dataclass, field

import numpy as np

from .design import SURFACES, Design, place, quat_xyzw, rot_matrix  # noqa: F401  (SURFACES re-exported)

INF = 1.0e9
PAYLOAD_DROP_Z = 0.004  # a payload lower than this (m above z = 0) has fallen off the vehicle


@dataclass
class Shape:
    name: str
    kind: str  # box | cylinder | capsule
    size: tuple  # box: (sx, sy, sz); cylinder / capsule: (radius, length) along ``axis``
    pos: tuple[float, float, float]
    quat: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)  # xyzw
    axis: str = "X"
    surface: str = "laminate"
    color: tuple[float, float, float] = (0.55, 0.45, 0.34)
    dynamic: bool = False
    mass_kg: float = 0.0


@dataclass
class JointSpec:
    name: str
    kind: str  # revolute (to the world) | distance (tow line)
    body0: str  # "" = world, a shape name, or "vehicle:tow" (design chassis at its tow point)
    body1: str
    anchor: tuple[float, float, float]  # world anchor on body0 [m]
    anchor1: tuple[float, float, float] = (0.0, 0.0, 0.0)  # world anchor on body1 [m]
    axis: str = "Y"
    lower_deg: float = -INF
    upper_deg: float = INF
    max_dist: float = 0.0


@dataclass
class StartSpec:
    front_x: float | None = 0.0  # the vehicle's front-most extent is placed here ...
    rear_x: float | None = None  # ... or its rear-most extent here
    y: float = 0.0  # track centre (or rope wheel line) goes here
    surface_z: float = 0.0  # surface height at x = surface_x (the vehicle's wheels are set on this line)
    surface_x: float = 0.0
    pitch_deg: float = 0.0  # surface slope at the start (nose up > 0)
    align: str = "track"  # track | rope | rope_track (on the ground wheels, rope wheel line at y)


@dataclass
class GoalSpec:
    x_min: float
    x_max: float = INF
    y_half: float = 0.2
    z_min: float = -0.02
    z_max: float = 1.0
    ref: str = "rear"  # rear (all part origins) | front (front-most part origin) | load (the towed sled)
    #   | half (the midpoint of the part origins' x extent: half the vehicle past x_min; y / z checked on all parts)
    hold_s: float = 0.0  # > 0: the vehicle must stay inside the goal region, at rest (< 5 mm of travel), this long


@dataclass
class Obstacle:
    kind: str
    level: int
    params: dict
    description: str
    shapes: list[Shape]
    start: StartSpec
    goal: GoalSpec
    fail_z: float
    time_limit_s: float
    floor_z: float = 0.0
    floor_surface: str = "laminate"
    joints: list[JointSpec] = field(default_factory=list)
    lane_half_width: float = 0.2
    stuck_window_s: float = 4.0
    stuck_min_progress_m: float = 0.005
    tow_line_m: float = 0.0  # tow line length (unused on the benchmark's courses)
    sled_gap_m: float = 0.0
    constraints: dict = field(default_factory=dict)  # level constraints on the design (``check_constraints``)
    payload: dict = field(default_factory=dict)  # {mass_g, size_mm, surface}: a loose load carried on design.cargo_mm
    # optional course centreline, a polyline [(x, y), ...] [m]. When set, progress is the arc length along it (from its
    # first point) instead of x, ``lane_half_width`` bounds the chassis' distance from it instead of |y|, and the goal's
    # x_min / x_max are arc lengths and y_half a distance from it (see ``Judge``). Empty: the straight x-course.
    centreline: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------------------------------------------------------
# geometry helpers
# ----------------------------------------------------------------------------------------------------------------

GREY = (0.45, 0.46, 0.50)
WOOD = (0.62, 0.48, 0.30)
BLUE = (0.20, 0.35, 0.65)
RED = (0.70, 0.20, 0.15)
WAX = (0.85, 0.85, 0.92)
RUBBER = (0.12, 0.12, 0.12)
SURF_COLOR = {
    "laminate": (0.55, 0.45, 0.34),
    "wood": WOOD,
    "rubber_mat": RUBBER,
    "waxed": WAX,
    "cord": (0.9, 0.85, 0.6),
}


def pitch_quat(angle_deg: float) -> tuple[float, float, float, float]:
    """Rotation raising the +x end by ``angle_deg`` (rotation about y by -angle)."""
    h = -math.radians(angle_deg) / 2
    return (0.0, math.sin(h), 0.0, math.cos(h))


def box(name, x0, x1, y_half, z_top, z_bot, surface="laminate", color=None, y0=0.0) -> Shape:
    return Shape(
        name,
        "box",
        (x1 - x0, 2 * y_half, z_top - z_bot),
        (0.5 * (x0 + x1), y0, 0.5 * (z_top + z_bot)),
        surface=surface,
        color=color or SURF_COLOR.get(surface, GREY),
    )


def slab(name, a, b, y_half, t=0.02, surface="laminate", color=None) -> Shape:
    """A plank whose top face runs from point a = (x, z) to b = (x, z)."""
    (xa, za), (xb, zb) = a, b
    ang = math.atan2(zb - za, xb - xa)
    length = math.hypot(xb - xa, zb - za)
    nx, nz = -math.sin(ang), math.cos(ang)
    c = (0.5 * (xa + xb) - nx * t / 2, 0.0, 0.5 * (za + zb) - nz * t / 2)
    return Shape(
        name,
        "box",
        (length, 2 * y_half, t),
        c,
        pitch_quat(math.degrees(ang)),
        surface=surface,
        color=color or SURF_COLOR.get(surface, GREY),
    )


# ----------------------------------------------------------------------------------------------------------------
# obstacle generators
# ----------------------------------------------------------------------------------------------------------------

COURSE_HALF_WIDTH = 0.15


# ------------------------------------------------------------------------------------------------ rope (the cord)
ROPE_HEIGHT = 0.0  # the start deck top
ROPE_PLATFORM_LEN = 0.70  # start and goal platforms (solid)
ROPE_EDGE_TOP = 0.080  # rope top above the deck at the platform edges (it runs over a saddle post there)
ROPE_ANCHOR_BACK = 0.40  # the rope is anchored lying on the deck 0.40 m behind the start edge / beyond the goal edge
ROPE_START_FRONT_X = -0.41  # the vehicle's front starts just behind the start anchor
ROPE_CHASM = 0.40  # depth of the chasm under the rope (below the start deck)
ROPE_SADDLE_LEN = 0.010  # saddle posts under the rope at the edges: 10 mm long, as wide as the rope


def rope_profile(span, incline_deg, sag, n=None, z0=None):
    """Rope axis points (x, z) of the free span: straight incline minus a parabolic sag (max ``sag`` at mid-span),
    starting at height ``z0`` (default: a 4 mm rope over the start saddle)."""
    n = n or max(2, int(math.ceil(span / 0.025)))
    z0 = ROPE_HEIGHT + ROPE_EDGE_TOP - 0.002 if z0 is None else z0
    t = math.tan(math.radians(incline_deg))
    return [(span * i / n, z0 + span * i / n * t - 4 * sag * (i / n) * (1 - i / n)) for i in range(n + 1)]


def rope_path(level: int, spec) -> tuple[list[tuple[float, float]], int, int]:
    """Rope axis polyline (x, z): lying on the start deck from its anchor, rising to the start saddle, the free span,
    the goal saddle, down to its anchor lying on the goal deck. Returns (points, index of the start edge, index of the
    goal edge)."""
    span, inc, sag_mm, r_mm, _goal_len, goal_anchor = _rope_spec(spec)
    r = r_mm * 1e-3
    z_edge = ROPE_HEIGHT + ROPE_EDGE_TOP - r
    pts = [(-ROPE_ANCHOR_BACK, ROPE_HEIGHT + r)]
    i0 = len(pts)
    pts += rope_profile(span, inc, sag_mm * 1e-3, z0=z_edge)
    i1 = len(pts) - 1
    goal_top = pts[i1][1] + r - ROPE_EDGE_TOP
    pts.append((span + goal_anchor, goal_top + r))
    return pts, i0, i1


def rope(level: int, spec) -> Obstacle:
    """The cord over a chasm between two solid platforms (``final_rope`` builds the real course on it).

    A braided nylon cord (a chain of static capsules) is anchored lying on the start deck 0.40 m behind the edge,
    rises in a straight line to a saddle post at the edge, spans the chasm (incline and parabolic sag), runs over a
    saddle post at the goal edge and down to its anchor lying on the goal deck. ``spec``: span m, incline deg, sag mm,
    cord radius mm."""
    span, inc, sag_mm, r_mm, goal_len, _anchor = _rope_spec(spec)
    r = r_mm * 1e-3
    pts, i0, i1 = rope_path(level, spec)
    shapes = []
    for i in range(len(pts) - 1):
        (xa, za), (xb, zb) = pts[i], pts[i + 1]
        ang = math.degrees(math.atan2(zb - za, xb - xa))
        prefix = "rope_s" if i < i0 else "rope" if i < i1 else "rope_g"
        shapes.append(
            Shape(
                f"{prefix}{i}",
                "capsule",
                (r, math.hypot(xb - xa, zb - za)),
                (0.5 * (xa + xb), 0.0, 0.5 * (za + zb)),
                pitch_quat(ang),
                axis="X",
                surface="cord",
                color=SURF_COLOR["cord"],
            )
        )
    goal_top = pts[i1][1] + r - ROPE_EDGE_TOP
    L = ROPE_PLATFORM_LEN
    shapes += [
        box("platform_start", -L, 0.0, COURSE_HALF_WIDTH, 0.0, -ROPE_CHASM, "wood"),
        box("platform_goal", span, span + goal_len, COURSE_HALF_WIDTH, goal_top, -ROPE_CHASM, "wood"),
        # saddle posts under the rope at the edges (as wide as the rope)
        box("saddle_start", -ROPE_SADDLE_LEN, 0.0, r, ROPE_EDGE_TOP - 2 * r, 0.0, "wood", GREY),
        box("saddle_goal", span, span + ROPE_SADDLE_LEN, r, goal_top + ROPE_EDGE_TOP - 2 * r, goal_top, "wood", GREY),
    ]
    lowest = min(p[1] for p in pts[i0 : i1 + 1])
    params = {
        "span_m": span,
        "incline_deg": inc,
        "sag_mm": sag_mm,
        "rope_radius_mm": r_mm,
        "edge_rope_top_mm": ROPE_EDGE_TOP * 1000,
        "anchor_back_m": ROPE_ANCHOR_BACK,
        "goal_deck_z_m": round(goal_top, 4),
        "goal_platform_m": goal_len,
    }
    desc = (
        f"rope {span * 1000:.0f} mm span between two solid platforms, {inc} deg incline, {sag_mm} mm sag, "
        f"{2 * r_mm} mm diameter"
    )
    return Obstacle(
        "rope",
        level,
        params,
        desc,
        shapes,
        StartSpec(front_x=ROPE_START_FRONT_X, y=0.0, surface_z=ROPE_HEIGHT, align="rope_track"),
        GoalSpec(
            x_min=span + 0.005,
            x_max=span + goal_len,
            z_min=lowest - 0.15,
            ref="rear",
            y_half=0.1,
            hold_s=0.0,
            # keep the region's ceiling 0.5 m above the goal deck (1 m default below)
            z_max=max(1.0, goal_top + 0.5),
        ),
        fail_z=lowest - 0.15,
        time_limit_s=round(30.0 + 12.0 * span, 1),
        floor_z=-ROPE_CHASM,
        lane_half_width=0.1,
        constraints={},
    )


def _rope_spec(spec):
    return (*spec, ROPE_PLATFORM_LEN, ROPE_ANCHOR_BACK)


WALL_LANDING_M = 0.60  # floor beyond the wall where the vehicle must end


# ------------------------------------------------------------------------------------------------ the courses (brick)
# Each level is exactly what a simple real build produces: brick 10 in baseplates (32 x 32 studs, 256 mm), brick
# columns (2x2 bricks) and decks (two crossed plate layers + tiles) and very few 3D-printed parts. Heights are whole
# plates (3.2 mm) / bricks (9.6 mm), widths and positions are on the 8 mm stud grid. Floor benches (ramp, steps,
# bumps, seesaw, wall): baseplates at z = -3.2 mm, 3.2 mm brick floor tiles make z = 0. Raised benches (gap, bridge,
# gap_drop, u_turn): brick decks 99.2 mm (31 plates) above the baseplate sheet, which is the chasm floor. Printed
# parts (``real_world/course_parts.zip``): bridge plank segments, rope saddle posts, bump plates, the seesaw plank,
# the U-turn stand; their geometry is read from these generators.
BRICK_STUD = 0.008
BRICK_PLATE = 0.0032
BRICK_HEIGHT_M = 0.0096
BRICK_SURF = "abs"  # brick tiles / bricks and the printed (PLA) parts: ABS-like friction
BRICK_GREY = (0.62, 0.64, 0.68)
PRINT_COLOR = (0.95, 0.55, 0.15)
F_HALF = 0.152  # decks, steps, walls and plateaus: 38 studs (304 mm) across
F_DECK_H = 0.0992  # raised decks: top 31 plates above the baseplate sheet (the chasm floor)
BEAM_HOLE_Z = 0.0058  # a beam brick's hole axis above the brick's bottom


def _r6(v: float) -> float:
    return round(v, 6)


def _bisect(f, lo: float, hi: float, n: int = 100) -> float:
    """Root of f on [lo, hi] (f(lo), f(hi) of opposite signs)."""
    flo = f(lo)
    for _ in range(n):
        mid = 0.5 * (lo + hi)
        if (f(mid) > 0) == (flo > 0):
            lo, flo = mid, f(mid)
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---- ramp: one sharp brick slope panel (rubber mat) from the floor to a brick plateau
F_RAMP_PANEL_L = 0.460  # panel length along the slope (constant for every level; real build: MDF + rubber mat)
F_RAMP_PANEL_T = 0.0048  # a 3/16 in (4.8 mm) foam-core board, as built
F_RAMP_STOP_L = 0.016  # foot stop: a 2-stud row of plates + tiles, top 3.2 mm above the floor
F_RAMP_PLATEAU_L = 0.352  # 44 studs
F_RAMP_SEAT_DZ = (0.003, 0.0096)  # the seat touches the panel's underside 3-9.6 mm (vertical) below its upper end
F_RAMP_PANEL_KG = 0.15  # (the board swings) 460 x 304 x 4.8 mm foam-core board (~0.67 l at
# ~0.2 kg/l, paper faces included) with its surface: ~0.15 kg
F_RAMP_HINGED = True  # the board hangs from the plateau edge on a hinge along its top edge (tape on the real course);
# its foot just rests on the floor (board/floor friction), so a car pushing on its lower part can lift / swing it


def final_ramp_geometry(theta0: float) -> dict:
    """Real ramp build for a nominal slope ``theta0`` [deg]. The panel (256 mm along the slope, 8 mm thick) rests with its
    lower bottom edge on the floor (x = 0) against a 2-stud stop (plate + tile, 3.2 mm high: its top corner touches the
    panel's end face) and with its underside on the front edge of the plateau's seat strip (a brick height h_s just
    below the panel's upper end). Stop and seat sit on the stud grid, so h_s / tan(a) + 3.2 tan(a) is a whole number
    of studs: that fixes the actual angle a (the closest to theta0). The plateau deck behind the seat strip is the brick
    height nearest the panel's top corner (crest step <= 1.6 mm)."""
    P, T, pl, st = F_RAMP_PANEL_L, F_RAMP_PANEL_T, BRICK_PLATE, BRICK_STUD
    th0 = math.radians(theta0)
    best = None
    j_top = int(P * math.sin(th0) / pl)
    for j in range(j_top - 5, j_top + 1):
        hs = j * pl

        def f(th, hs=hs):
            return hs / math.tan(th) + pl * math.tan(th)

        k0 = round(f(th0) / st)
        for k in range(k0 - 4, k0 + 5):
            lo, hi = th0 - math.radians(8), th0 + math.radians(8)
            if not (f(hi) - k * st) < 0 < (f(lo) - k * st):
                continue
            th = _bisect(lambda a, k=k: f(a) - k * st, lo, hi)
            dz = P * math.sin(th) - hs
            if not F_RAMP_SEAT_DZ[0] <= dz <= F_RAMP_SEAT_DZ[1]:
                continue
            if best is None or abs(th - th0) < abs(best[0] - th0):
                best = (th, hs, k)
    th, hs, k = best
    s, c = math.sin(th), math.cos(th)
    xs = -pl * s / c  # the stop's front face
    xc = hs * c / s  # the seat strip's front edge (it touches the panel's underside)
    ex, ez = P * c, P * s  # panel: upper bottom corner
    ux, uz = ex - T * s, ez + T * c  # panel: upper top corner
    H = round(uz / pl) * pl  # plateau deck top (brick height nearest the panel's top corner)
    m = max(1, math.ceil((ex + 0.0005 - xc) / st - 1e-9))
    xd = xc + m * st  # plateau deck front face
    return {
        "slope_deg": round(math.degrees(th), 2), "slope_rad": th, "rise_m": _r6(H), "seat_m": _r6(hs),
        "stop_x_m": _r6(xs), "seat_x_m": _r6(xc), "plateau_x_m": _r6(xd), "stop_to_seat_studs": k,
        "seat_studs": m, "crest_step_mm": round((H - uz) * 1000, 2), "crest_notch_mm": round((xd - ux) * 1000, 1),
        "foot_lip_mm": round(T * c * 1000, 2), "panel_top_corner_m": (_r6(ux), _r6(uz)),
    }


def final_ramp(level: int, spec) -> Obstacle:
    """Climb a sharp rubber-mat brick slope panel to a brick plateau (``final_ramp_geometry``)."""
    theta0, surface = spec
    g = final_ramp_geometry(theta0)
    th, H, xs, xc, xd = g["slope_rad"], g["rise_m"], g["stop_x_m"], g["seat_x_m"], g["plateau_x_m"]
    P, T = F_RAMP_PANEL_L, F_RAMP_PANEL_T
    s, c = math.sin(th), math.cos(th)
    panel = Shape("ramp", "box", (P, 2 * F_HALF, T), (_r6(P / 2 * c - T / 2 * s), 0.0, _r6(P / 2 * s + T / 2 * c)),
                  pitch_quat(math.degrees(th)), surface=surface, color=SURF_COLOR.get(surface, GREY),
                  dynamic=F_RAMP_HINGED, mass_kg=F_RAMP_PANEL_KG if F_RAMP_HINGED else 0.0)
    shapes = [  # (no stop strip at the foot: the real board just rests on the floor)
        panel,
        box("seat", xc, xd, F_HALF, g["seat_m"], 0.0, BRICK_SURF, BRICK_GREY),
        box("plateau", xd, xd + F_RAMP_PLATEAU_L, F_HALF, H, 0.0, BRICK_SURF, BRICK_GREY),
    ]
    params = {k: v for k, v in g.items() if k != "slope_rad"}
    params.update(slope_nominal_deg=theta0, surface=surface, panel_mm=(P * 1000, 2 * F_HALF * 1000, T * 1000),
                  ramp_length_m=_r6(xd), slope_length_m=P)
    ob = Obstacle(
        "ramp",
        level,
        params,
        f"sharp ramp {g['slope_deg']} deg (a {P * 1000:.0f} mm foam-core board"
        + (" hinged at the plateau edge, its foot resting on the floor" if F_RAMP_HINGED else " resting on the floor")
        + ") up to a plateau "
        f"{H * 1000:.1f} mm high",
        shapes,
        StartSpec(front_x=_r6(xs - F_RAMP_STOP_L - 0.02)),
        GoalSpec(x_min=_r6(xd + 0.01), x_max=_r6(xd + F_RAMP_PLATEAU_L), z_min=_r6(H - 0.004)),
        fail_z=-0.05,
        time_limit_s=round(30.0 + 50.0 * max(0.0, H - 0.1), 1),
        floor_surface=BRICK_SURF,
        lane_half_width=F_HALF,
    )
    if F_RAMP_HINGED:  # hinge along the board's top edge (mid-thickness of its upper end), across the course
        params["panel_hinge_m"] = (_r6(P * c - T / 2 * s), _r6(P * s + T / 2 * c))
        params["panel_kg"] = F_RAMP_PANEL_KG
        hx, hz = params["panel_hinge_m"]
        ob.joints.append(JointSpec("panel_hinge", "revolute", "", "ramp", (hx, 0.0, hz), axis="Y"))
    return ob


# ---- gap: two brick decks
def final_gap(level: int, spec) -> Obstacle:
    """Cross a gap (a whole number of studs) between two brick decks 99.2 mm above the baseplate floor. Platforms
    max(0.45, 1.6 x gap + 0.15) m long rounded up to whole studs (the start one 6 studs longer)."""
    gmm = spec
    w = gmm * 1e-3
    plat = _r6(math.ceil(max(0.45, 1.6 * w + 0.15) / BRICK_STUD - 1e-9) * BRICK_STUD)
    shapes = [
        box("platform_start", -(plat + 0.048), 0.0, F_HALF, 0.0, -F_DECK_H, BRICK_SURF, BRICK_GREY),
        box("platform_goal", w, w + plat, F_HALF, 0.0, -F_DECK_H, BRICK_SURF, BRICK_GREY),
    ]
    return Obstacle(
        "gap",
        level,
        {"gap_mm": gmm, "gap_studs": round(gmm / 8), "drop_m": F_DECK_H, "platform_m": plat},
        f"gap {gmm} mm ({round(gmm / 8)} studs) between two brick decks, {F_DECK_H * 1000:.1f} mm deep",
        shapes,
        StartSpec(front_x=-0.03),
        GoalSpec(x_min=_r6(w + 0.005), x_max=_r6(w + plat), z_min=-0.004),
        fail_z=-0.02,
        time_limit_s=20.0 if gmm <= 160 else round(20.0 + 25.0 * w, 1),
        floor_z=-F_DECK_H,
        lane_half_width=F_HALF,
    )


# ---- bridge: printed plank segments on hidden brick columns
F_BRIDGE_L = 0.640  # 80 studs
F_BRIDGE_SEG = 0.160  # 4 identical printed segments per width
F_BRIDGE_T = 0.0096  # plank thickness (one brick): top flush with the decks
F_BRIDGE_START, F_BRIDGE_GOAL = 0.456, 0.400


def final_bridge_supports() -> list[tuple[float, float]]:
    """x ranges [m] of the hidden support columns under the plank: a 1-stud column at each end (one jumper plate, its
    stud in the end socket) and a 2-stud column at each joint (two 1x2 jumper plates: one stud per segment end)."""
    out = [(0.0, BRICK_STUD)]
    n = round(F_BRIDGE_L / F_BRIDGE_SEG)
    out += [(_r6(i * F_BRIDGE_SEG - BRICK_STUD), _r6(i * F_BRIDGE_SEG + BRICK_STUD)) for i in range(1, n)]
    out.append((_r6(F_BRIDGE_L - BRICK_STUD), F_BRIDGE_L))
    return out


def final_bridge(level: int, spec) -> Obstacle:
    """Drive along a printed plank (``spec`` mm wide, 640 mm long, 9.6 mm thick, top flush with the decks) over a
    99.2 mm drop. Four 160 mm segments, each gripping one stud of the hidden brick support columns (16 mm wide, top
    9.6 mm below the plank top) at both ends."""
    wmm = spec
    w = wmm * 1e-3
    shapes = [
        box("platform_start", -F_BRIDGE_START, 0.0, F_HALF, 0.0, -F_DECK_H, BRICK_SURF, BRICK_GREY),
        box("plank", 0.0, F_BRIDGE_L, w / 2, 0.0, -F_BRIDGE_T, BRICK_SURF, PRINT_COLOR),
        box("platform_goal", F_BRIDGE_L, F_BRIDGE_L + F_BRIDGE_GOAL, F_HALF, 0.0, -F_DECK_H, BRICK_SURF, BRICK_GREY),
    ]
    for i, (x0, x1) in enumerate(final_bridge_supports()):
        shapes.append(box(f"support{i}", x0, x1, BRICK_STUD, -F_BRIDGE_T, -F_DECK_H, BRICK_SURF, BRICK_GREY))
    return Obstacle(
        "bridge",
        level,
        {"plank_width_mm": wmm, "plank_length_m": F_BRIDGE_L, "plank_thickness_mm": F_BRIDGE_T * 1000,
         "segments": round(F_BRIDGE_L / F_BRIDGE_SEG), "segment_mm": F_BRIDGE_SEG * 1000, "drop_m": F_DECK_H},
        f"printed plank {wmm} mm wide, {F_BRIDGE_L * 1000:.0f} mm long over a {F_DECK_H * 1000:.1f} mm drop",
        shapes,
        StartSpec(front_x=-0.03),
        GoalSpec(x_min=_r6(F_BRIDGE_L + 0.005), x_max=_r6(F_BRIDGE_L + F_BRIDGE_GOAL), z_min=-0.004),
        fail_z=-0.03,
        time_limit_s=max(30.0, round(15.0 + 25.0 * F_BRIDGE_L, 1)),
        floor_z=-F_DECK_H,
        lane_half_width=F_HALF,
    )


# ---- rope: brick decks, printed saddles (pressed onto the deck-edge studs) and table-clamped anchor posts
F_ROPE_TOWER = 0.192  # start deck top above the table (20 bricks); the goal tower is the same on a rigid riser
F_ROPE_PLATFORM = 0.704  # 88 studs
F_ROPE_SADDLE = (0.010, 0.008)  # printed saddle post: 10 mm along the cord, 8 mm across, top at the cord axis
# Two-table course (RB_ROPE_EDGE=0 gives a variant with the cord anchored on the decks): a fixed table
# and a standing desk, one printed edge device each (print/rope/ in real_world/course_parts.zip): the cord runs only between the two
# saddle posts; each device puts a low clamp arm on the deck edge. The car starts on the deck and climbs onto the
# cord over the post.
F_ROPE_EDGE = os.environ.get("RB_ROPE_EDGE", "1") == "1"
F_ROPE_DEVICE_ARM = (-0.032, 0.0185, 0.024, 0.008)  # x0, x1 (from the deck edge), width, height of the clamp's top arm
F_ROPE_DEVICE_POST = (-0.0025, 0.0175)  # the saddle post along the cord, over the clamp's spine (the cord goes down a
# hole in its top at x = 6 mm; on the gap side it lies in a groove over the post's rounded nose)
F_ROPE_DEVICE_POST_W = 0.010  # the saddle post across the cord (printed: on the clamp's bed side, cord in its middle)
F_ROPE_EDGE_START = -0.06  # car front 60 mm before the deck edge


F_ROPE_POST_NOSE_R = 0.006  # the printed saddle post's gap-side top edge is rounded (radius 6 mm, as printed)


def _rope_post(name, x0, x1, z_bot, z_top, gap_dir):
    """a printed saddle post: a box with its gap-side top edge rounded to F_ROPE_POST_NOSE_R (gap_dir +1: the gap is at
    x1, -1: at x0), as printed, so a wheel or pulley arriving from the gap rolls up over the nose"""
    r = F_ROPE_POST_NOSE_R
    w = F_ROPE_DEVICE_POST_W / 2
    if gap_dir > 0:
        xa, xb, xc = x0, x1 - r, x1 - r  # full-height block, nose strip, nose centre
        strip = box(name + "_nose_base", x1 - r, x1, w, z_top - r, z_bot, BRICK_SURF, PRINT_COLOR)
    else:
        xa, xb, xc = x0 + r, x1, x0 + r
        strip = box(name + "_nose_base", x0, x0 + r, w, z_top - r, z_bot, BRICK_SURF, PRINT_COLOR)
    return [box(name, xa, xb, w, z_top, z_bot, BRICK_SURF, PRINT_COLOR), strip,
            Shape(name + "_nose", "cylinder", (r, 2 * w), (xc, 0.0, z_top - r), axis="Y", surface=BRICK_SURF,
                  color=PRINT_COLOR)]


def final_rope_rise(span: float, incline_deg: float) -> float:
    """Goal deck height above the start deck [m]: span x tan(incline), rounded to whole plates."""
    return _r6(round(span * math.tan(math.radians(incline_deg)) / BRICK_PLATE) * BRICK_PLATE)


def final_rope(level: int, spec) -> Obstacle:
    """Rope over a chasm (``rope``) with the span fixed and the goal deck raised by a whole number of plates (the actual
    incline is atan(rise / span)). brick decks 704 mm long; saddle posts 10 x 8 mm up to the cord axis (the cord lies in
    a groove in their top); the cord ends go over the flush tops of two printed anchor posts 400 mm behind / beyond
    the saddles. The chasm floor is the table, 192 mm below the start deck."""
    span, inc0, sag_mm, r_mm = spec[:4]
    # optional (filmed calibration courses): spec[4] = goal device raised by this many mm (a brick under its clamp
    # arm: arm, post and cord end go up, the deck does not); spec[5] = the goal deck's measured rise in mm (instead of
    # span x tan(incline) rounded to whole plates). A plain 4-tuple builds exactly what it did before.
    raise_g = float(spec[4]) * 1e-3 if len(spec) > 4 and spec[4] else 0.0
    dz = _r6(float(spec[5]) * 1e-3) if len(spec) > 5 and spec[5] is not None else final_rope_rise(span, inc0)
    inc = math.degrees(math.atan2(dz + raise_g, span))  # the cord's incline, saddle to saddle
    ob = rope(level, spec=(span, inc, sag_mm, r_mm))
    r = r_mm * 1e-3
    top = ROPE_EDGE_TOP - r  # saddle top = cord axis
    sx, sy = F_ROPE_SADDLE
    if F_ROPE_EDGE:  # two tables, one printed edge device each: the cord ends at the saddle posts (no cord on the decks)
        caps = [sh for sh in ob.shapes if sh.kind == "capsule" and 0.0 < sh.pos[0] < span]
        a0, a1, aw, ah = F_ROPE_DEVICE_ARM
        p0, p1 = F_ROPE_DEVICE_POST
        ob.shapes = caps + [
            box("platform_start", -F_ROPE_PLATFORM, 0.0, F_HALF, 0.0, -F_ROPE_TOWER, BRICK_SURF, BRICK_GREY),
            box("platform_goal", span, span + F_ROPE_PLATFORM, F_HALF, dz, -F_ROPE_TOWER, BRICK_SURF, BRICK_GREY),
            box("device_arm_start", a0, a1, aw / 2, ah, 0.0, BRICK_SURF, PRINT_COLOR),
            box("device_arm_goal", span - a1, span - a0, aw / 2, dz + raise_g + ah, dz, BRICK_SURF, PRINT_COLOR),
        ] + _rope_post("saddle_start", p0, p1, 0.0, top, +1) + _rope_post("saddle_goal", span - p1, span - p0, dz,
                                                                           dz + raise_g + top, -1)
        ob.start.front_x = F_ROPE_EDGE_START
    else:
        ob.shapes = [sh for sh in ob.shapes if sh.kind == "capsule"] + [
            box("platform_start", -F_ROPE_PLATFORM, 0.0, F_HALF, 0.0, -F_ROPE_TOWER, BRICK_SURF, BRICK_GREY),
            box("platform_goal", span, span + F_ROPE_PLATFORM, F_HALF, dz, -F_ROPE_TOWER, BRICK_SURF, BRICK_GREY),
            box("saddle_start", -0.0001 - sx, -0.0001, sy / 2, top, 0.0, BRICK_SURF, PRINT_COLOR),
            box("saddle_goal", span + 0.0001, span + 0.0001 + sx, sy / 2, dz + top, dz, BRICK_SURF, PRINT_COLOR),
        ]
    if raise_g:
        ob.params["goal_device_raise_mm"] = round(raise_g * 1000, 2)
    ob.params.update(incline_deg=round(inc, 3), incline_nominal_deg=inc0, goal_deck_z_m=dz, goal_rise_mm=round(dz * 1000, 1),
                     goal_platform_m=F_ROPE_PLATFORM, start_platform_m=F_ROPE_PLATFORM, cord_d_mm=2 * r_mm,
                     start_tower_mm=F_ROPE_TOWER * 1000, saddle_mm=(sx * 1000, sy * 1000, round(top * 1000, 2)))
    ob.description = (f"rope {span * 1000:.0f} mm span between two brick decks, {inc:.2f} deg incline (goal deck "
                      f"{dz * 1000:.1f} mm higher), {sag_mm} mm sag, {2 * r_mm} mm cord")
    ob.goal.x_max = _r6(span + F_ROPE_PLATFORM)
    ob.floor_z = -F_ROPE_TOWER
    ob.lane_half_width = 0.1
    return ob


# ---- steps: three brick steps (bricks + tiles)
def final_steps(level: int, spec) -> Obstacle:
    """Climb ``count`` brick steps of ``riser`` mm (whole plates), treads 2.4 x riser rounded to whole studs."""
    h_mm, n = spec
    h = h_mm * 1e-3
    tread = _r6(round(2.4 * h / BRICK_STUD) * BRICK_STUD)
    shapes = []
    for i in range(n):
        x0 = i * tread
        x1 = x0 + tread if i < n - 1 else x0 + 0.352
        shapes.append(box(f"step{i}", _r6(x0), _r6(x1), F_HALF, _r6((i + 1) * h), 0.0, BRICK_SURF, BRICK_GREY))
    top = n * h
    x_goal = _r6((n - 1) * tread + 0.01)
    return Obstacle(
        "steps",
        level,
        {"step_mm": h_mm, "count": n, "tread_m": tread, "riser_plates": round(h / BRICK_PLATE)},
        f"{n} brick steps of {h_mm} mm, {tread * 1000:.0f} mm treads",
        shapes,
        StartSpec(front_x=-0.03),
        GoalSpec(x_min=x_goal, x_max=_r6(x_goal + 0.34), z_min=_r6(top - 0.003)),
        fail_z=-0.05,
        time_limit_s=round(30.0 + 10.0 * n + 150.0 * h, 1),
        floor_surface=BRICK_SURF,
        lane_half_width=F_HALF,
    )


# ---- bumps: rods printed on two bump plates (32 x 32 studs, one per 10 in baseplate) that press onto the baseplates
F_BUMP_PITCH = 0.256  # one 10 in baseplate (32 studs); the printed outline is 32 x 8 - 0.2 = 255.8 mm
F_BUMP_N = 2  # plates per level: the field is 512 mm long
F_BUMP_PLATES = tuple((_r6(k * F_BUMP_PITCH), _r6((k + 1) * F_BUMP_PITCH)) for k in range(F_BUMP_N))  # x ranges [m]
F_BUMP_FIELD = F_BUMP_PLATES[-1][1]
F_BUMP_PART_MARGIN = 0.02  # part origins may step this far outside the plates
F_BUMP_WHEEL_TOL = 0.005  # a wheel's origin over the bump field stays within the rods' y span +- this [m]: a
# wide car may not put its wheels in the rod-free strips along the plate edges (Judge: "a wheel went around the rods")
F_BUMP_PLATE_Y = 0.128  # y -0.128 .. 0.128 (32 studs, the central 256 mm of the 304 mm lane; 24 mm tile strips beside)
F_BUMP_MARGIN = 0.0021  # every rod stays 2 mm inside its plate's printed outline (outline 0.1 mm inside the pitch)


F_BUMP_AS_PRINTED = True
"""Rods as on the printed plates (print/bumps/L*/bump_plate_{1,2}.stl in real_world/course_parts.zip): 40-220 mm long,
off-centre in y; False gives a full-span variant."""


def final_bump_rods(level: int, hmm: float, n_rods: int, seed: int = 7) -> list[dict]:
    """Seeded rod layout: rod radius 0.6 x the max height, heights 0.6-1 x the max, 40-220 mm long and off-centre
    (2 mm inside the plate's 255.8 mm outline); each rod lies on one plate (its whole circle within the plate's x
    range)."""
    rng = random.Random(seed * 100 + (2 * level - 1) + 4000)  # level 1 / 2 / 3: the published rod layouts
    hmax = hmm * 1e-3
    R = 0.6 * hmax
    rods = []
    while len(rods) < n_rods:
        x = rng.uniform(0.0, F_BUMP_FIELD)
        k = min(int(x / F_BUMP_PITCH), F_BUMP_N - 1)
        x0, x1 = F_BUMP_PLATES[k]
        if not x0 + R + F_BUMP_MARGIN <= x <= x1 - R - F_BUMP_MARGIN:
            continue
        hgt = hmax * rng.uniform(0.6, 1.0)
        length = rng.uniform(0.04, 0.22)
        ylim = min(0.08, F_BUMP_PLATE_Y - F_BUMP_MARGIN - length / 2)
        y = rng.uniform(-ylim, ylim)
        if not F_BUMP_AS_PRINTED:  # full-span variant (not printed)
            length, y = 2 * (F_BUMP_PLATE_Y - F_BUMP_MARGIN), 0.0
        rods.append({"x": round(x, 5), "y": round(y, 5), "top": round(hgt, 5), "len": round(length, 5), "plate": k})
    rods.sort(key=lambda d: d["x"])
    return rods


def final_bumps(level: int, spec, seed: int = 7) -> Obstacle:
    """Rough terrain on two printed bump plates (32 x 32 studs = one 10 in baseplate each, 255.8 x 255.8 x 3.2 mm, top
    flush with the floor tiles): ``n`` rods (radius 0.6 x the max height, axis along y, partly sunk into the plate) over
    0.512 m, each entirely on one plate."""
    hmm, n_rods = spec
    R = 0.6 * hmm * 1e-3
    rods = final_bump_rods(level, hmm, n_rods, seed)
    shapes = [Shape(f"bump{i}", "cylinder", (_r6(R), d["len"]), (d["x"], d["y"], _r6(d["top"] - R)), axis="Y",
                    surface=BRICK_SURF, color=PRINT_COLOR) for i, d in enumerate(rods)]
    return Obstacle(
        "bumps",
        level,
        {"max_bump_mm": hmm, "rods": len(rods), "seed": seed, "rod_radius_mm": round(R * 1000, 2),
         "plates_mm": [[round(x0 * 1000, 3), round(x1 * 1000, 3), -F_BUMP_PLATE_Y * 1000, F_BUMP_PLATE_Y * 1000]
                       for x0, x1 in F_BUMP_PLATES],
         "field_m": F_BUMP_FIELD, "rod_plate": [d["plate"] for d in rods],
         # the rods' lateral span [m]: wheels over the field stay within it (+ F_BUMP_WHEEL_TOL; Judge)
         "rods_y_span_m": [round(min(d["y"] - d["len"] / 2 for d in rods), 5),
                           round(max(d["y"] + d["len"] / 2 for d in rods), 5)]},
        f"rough terrain: {len(rods)} rods up to {hmm} mm high over {F_BUMP_FIELD:g} m on {F_BUMP_N} printed bump plates "
        f"(32 x 32 studs)",
        shapes,
        StartSpec(front_x=-0.01),
        # crossed when half the car is past the end of the bump line
        # no lateral bound past the field either (a car driving on and veering during the 5 s hold stays in the goal)
        GoalSpec(x_min=_r6(F_BUMP_FIELD), x_max=INF, y_half=INF, z_min=-0.004, ref="half"),  # driving on past the field is fine
        fail_z=-0.05,
        time_limit_s=30.0,
        floor_surface=BRICK_SURF,
        lane_half_width=F_BUMP_PLATE_Y,  # the plates' width: with FINAL_OVER_KINDS every part must stay on them
    )


# ---- seesaw: a printed plank on a brick axle through beam bricks on brick columns
F_SEESAW_L, F_SEESAW_W = 0.240, 0.064  # plank (8 studs wide)
F_SEESAW_T = 0.008  # plank top to the rib bottoms (1.6 mm skin + ribs)
F_SEESAW_AXLE_D = 0.010  # cross-axle hole centre below the plank top
F_SEESAW_GAP = 0.256  # constant gap between the platforms (32 studs); the axle is at its centre (a stud-grid line)
F_SEESAW_H = 0.0288  # platform tops above the floor (3 bricks + 1 tile above the baseplate)
F_SEESAW_LEDGE = F_SEESAW_H - 2 * BRICK_PLATE  # end ledges: 2 plates lower than the platforms
F_SEESAW_PLANK_G = 54.0  # print/seesaw/seesaw_plank.stl (51.8 g at 20 % infill) + axle 12 + 2 bushes (~2 g)
F_SEESAW_PLAT_L = 0.400


def final_seesaw_geometry(tilt0: float) -> dict:
    """Axle column height (whole plates under a beam brick: axle at c + 2.6 mm above the floor) and the actual tilt:
    in the start pose the near end's rib bottoms rest on the near ledge (2 plates below the platform tops); choose the
    column giving the tilt closest to ``tilt0``."""
    half, zr = F_SEESAW_L / 2, F_SEESAW_AXLE_D - F_SEESAW_T  # rib bottoms 2 mm above the axle
    best = None
    for j in range(4, 80):
        za = j * BRICK_PLATE - BRICK_PLATE + BEAM_HOLE_Z
        dz = za - F_SEESAW_LEDGE
        if not 0 < dz < half * 0.95:
            continue
        th = _bisect(lambda a, dz=dz: half * math.sin(a) - zr * math.cos(a) - dz, 0.0, math.radians(80))
        if best is None or abs(th - math.radians(tilt0)) < abs(best[0] - math.radians(tilt0)):
            best = (th, j, za)
    th, j, za = best
    s, c = math.sin(th), math.cos(th)
    xp = F_SEESAW_GAP / 2
    top_near = za - half * s + F_SEESAW_AXLE_D * c
    x_contact = xp - half * c - zr * s
    a = round((x_contact - BRICK_STUD) / BRICK_STUD)
    return {"tilt_deg": round(math.degrees(th), 2), "tilt_rad": th, "axle_column_plates": j, "axle_z_m": _r6(za),
            "axle_x_m": xp, "ledge_x_m": (_r6(a * BRICK_STUD), _r6(a * BRICK_STUD + 2 * BRICK_STUD)),
            "end_step_mm": round((top_near - F_SEESAW_H) * 1000, 2),
            "end_gap_mm": round((xp - half * c - F_SEESAW_AXLE_D * s) * 1000, 1)}


def final_seesaw(level: int, spec) -> Obstacle:
    """Drive over a printed seesaw plank (240 x 64 mm, ribbed, ``F_SEESAW_PLANK_G`` g) on a brick cross axle through
    beam bricks on 2x2 brick columns beside it, between two brick platforms 28.8 mm high and 256 mm apart. It starts
    tilted with its near end on a brick ledge (top flush with the platform within ``end_step_mm``), tips when the car
    passes the axle and lands on the far ledge."""
    # spec < 0 (a variant): the same seesaw tipped the other way: it starts with its far end down on the far
    # ledge and its near end raised above the start platform (the plank mirrored about the axle)
    flip = spec < 0
    g = final_seesaw_geometry(abs(spec))
    th, za, xp = g["tilt_rad"], g["axle_z_m"], g["axle_x_m"]
    s, c = math.sin(th), math.cos(th)
    off = F_SEESAW_AXLE_D - F_SEESAW_T / 2  # plank box centre above the axle (plank frame)
    centre = (_r6(xp + off * s if flip else xp - off * s), 0.0, _r6(za + off * c))
    plank = Shape("plank", "box", (F_SEESAW_L, F_SEESAW_W, F_SEESAW_T), centre,
                  pitch_quat(-math.degrees(th) if flip else math.degrees(th)),
                  surface=BRICK_SURF, color=PRINT_COLOR, dynamic=True, mass_kg=F_SEESAW_PLANK_G * 1e-3)
    near_top = za + (F_SEESAW_L / 2) * s + F_SEESAW_AXLE_D * c  # the raised near end's top edge (flipped)
    l0, l1 = g["ledge_x_m"]
    hw = F_SEESAW_W / 2
    col_top = _r6(za + BRICK_HEIGHT_M - BEAM_HOLE_Z)  # beam brick top (its studs 1.7 mm higher)
    shapes = [
        box("platform_start", -F_SEESAW_PLAT_L, 0.0, F_HALF, F_SEESAW_H, 0.0, BRICK_SURF, BRICK_GREY),
        box("platform_goal", F_SEESAW_GAP, F_SEESAW_GAP + F_SEESAW_PLAT_L, F_HALF, F_SEESAW_H, 0.0, BRICK_SURF, BRICK_GREY),
        box("ledge_near", l0, l1, hw, F_SEESAW_LEDGE, 0.0, BRICK_SURF, BRICK_GREY),
        box("ledge_far", _r6(F_SEESAW_GAP - l1), _r6(F_SEESAW_GAP - l0), hw, F_SEESAW_LEDGE, 0.0, BRICK_SURF, BRICK_GREY),
        box("pivot_left", xp - BRICK_STUD, xp + BRICK_STUD, BRICK_STUD, col_top, 0.0, BRICK_SURF, BRICK_GREY, y0=0.048),
        box("pivot_right", xp - BRICK_STUD, xp + BRICK_STUD, BRICK_STUD, col_top, 0.0, BRICK_SURF, BRICK_GREY, y0=-0.048),
        plank,
    ]
    ob = Obstacle(
        "seesaw",
        level,
        {"tilt_deg": g["tilt_deg"], "tilt_nominal_deg": spec, "plank_width_mm": F_SEESAW_W * 1000,
         "plank_length_m": F_SEESAW_L, "plank_g": F_SEESAW_PLANK_G, "platform_gap_mm": F_SEESAW_GAP * 1000,
         "platform_mm": F_SEESAW_H * 1000, "axle_column_plates": g["axle_column_plates"],
         "axle_z_mm": round(za * 1000, 2), "ledge_mm": round(F_SEESAW_LEDGE * 1000, 1),
         "ledge_x_mm": (round(l0 * 1000, 1), round(l1 * 1000, 1)), "end_step_mm": g["end_step_mm"],
         "end_gap_mm": g["end_gap_mm"],
         **({"start_pose": "far end down on the far ledge, near end raised",
             "near_end_top_mm": round(near_top * 1000, 1),
             "near_end_above_platform_mm": round((near_top - F_SEESAW_H) * 1000, 1)} if flip else
            {"start_pose": "near end down on the near ledge"})},
        (f"printed seesaw plank 64 x 240 mm on a brick axle {za * 1000:.1f} mm above the floor, tilted {g['tilt_deg']} "
         f"deg with its far end down: its near end is raised {(near_top - F_SEESAW_H) * 1000:.0f} mm above the start "
         "platform" if flip else
         f"printed seesaw plank 64 x 240 mm tilted {g['tilt_deg']} deg on a brick axle {za * 1000:.1f} mm above the floor"),
        shapes,
        StartSpec(front_x=-0.005, surface_z=F_SEESAW_H),
        GoalSpec(x_min=_r6(F_SEESAW_GAP + 0.01), x_max=_r6(F_SEESAW_GAP + F_SEESAW_PLAT_L), z_min=_r6(F_SEESAW_H - 0.004)),
        fail_z=-0.02,
        time_limit_s=30.0,
        floor_surface=BRICK_SURF,
        lane_half_width=F_HALF,
    )
    ob.joints.append(JointSpec("pivot", "revolute", "", "plank", (xp, 0.0, _r6(za)), axis="Y"))
    return ob


# ---- gapdrop: brick decks
F_GAPDROP_GAP = 0.152  # 19 studs
F_GAPDROP_LANDING = 0.504


def final_gapdrop(level: int, spec) -> Obstacle:
    """Cross a 152 mm (19-stud) gap to a brick landing deck ``spec`` mm (whole plates) lower; the landing deck is 99.2 mm
    above the baseplate floor."""
    # spec: drop mm, or (drop mm, gap mm) for a measured course ; a plain number is unchanged
    dmm, gmm = (spec[0], spec[1]) if isinstance(spec, (tuple, list)) else (spec, None)
    drop, w = dmm * 1e-3, (gmm * 1e-3 if gmm is not None else F_GAPDROP_GAP)
    floor = _r6(-(drop + F_DECK_H))
    shapes = [
        box("platform_start", -0.60, 0.0, F_HALF, 0.0, floor, BRICK_SURF, BRICK_GREY),
        box("platform_landing", w, w + F_GAPDROP_LANDING, F_HALF, -drop, floor, BRICK_SURF, BRICK_GREY),
    ]
    return Obstacle(
        "gap_drop",
        level,
        {"drop_mm": dmm, "gap_mm": round(w * 1000, 1), "drop_plates": round(drop / BRICK_PLATE),
         "chasm_m": F_DECK_H},
        f"gap {w * 1000:.0f} mm to a brick landing deck {dmm} mm lower",
        shapes,
        StartSpec(front_x=-0.03),
        GoalSpec(x_min=_r6(w + 0.005), x_max=_r6(w + F_GAPDROP_LANDING), z_min=_r6(-drop - 0.004), z_max=0.5),
        fail_z=_r6(-drop - 0.05),
        time_limit_s=30.0,
        floor_z=floor,
        lane_half_width=F_HALF,
    )


# ---- wall: brick bricks (+ a tile layer that makes the top smooth and lifts it by the floor tiles' 3.2 mm)
F_WALL_THICK = 2 * BRICK_STUD  # one layer of 2x4 bricks laid along the wall: 2 studs (16 mm) thick
F_WALL_HALF = 0.128  # 8 bricks of 2x4 end to end: 32 studs (256 mm, one 10 in baseplate) across; the lane is as wide


def final_wall(level: int, spec) -> Obstacle:
    """Climb over a brick wall ``spec`` bricks high above the floor: one layer of 2x4 bricks (2 studs = 16 mm thick),
    8 bricks (32 studs = 256 mm) across, the lane exactly as wide, and come down on the floor beyond."""
    n = spec
    h = _r6(n * BRICK_HEIGHT_M)
    t = F_WALL_THICK
    return Obstacle(
        "wall",
        level,
        {"bricks": n, "height_mm": round(n * 9.6, 1), "thickness_mm": round(t * 1000, 1), "width_mm": round(2 * F_WALL_HALF * 1000, 1),
         "landing_m": WALL_LANDING_M},
        f"climb over a brick wall {n} bricks = {n * 9.6:.1f} mm high, one 2x4 brick ({t * 1000:.0f} mm) thick, "
        f"{2 * F_WALL_HALF * 1000:.0f} mm wide",
        [box("wall", 0.0, t, F_WALL_HALF, h, 0.0, BRICK_SURF, BRICK_GREY)],
        StartSpec(front_x=-0.03),
        GoalSpec(x_min=round(t + 0.01, 4), x_max=round(t + WALL_LANDING_M, 4), z_min=-0.004),
        fail_z=-0.05,
        time_limit_s=round(30.0 + 100.0 * h),
        floor_surface=BRICK_SURF,
        lane_half_width=F_WALL_HALF,
    )


# ---- uturn: brick lanes, a tilted plate of four 10 in baseplates + tiles on printed wedge adapters
F_UTURN_LANE_LEN = 0.552  # lane length from the start line (car front) to the plate's hinge
# lane length behind the start line: 0.200 (lanes 752 mm = 94 studs); RB_UTURN_BACK sets another length
F_UTURN_BACK = float(os.environ.get("RB_UTURN_BACK", "0.200"))
F_UTURN_PLATE = 0.512  # 2 x 2 baseplates (64 x 64 studs)
F_UTURN_PLATE_T = 0.0047  # baseplate sheet 1.5 mm + tiles 3.2 mm
F_UTURN_LIP_MIN = 0.0016  # wedge lip thickness along the face (per angle: the plate's top edge clears the lane end)
F_UTURN_LIP_H = 0.003  # lip height above the wedge face (below the plate top)
F_UTURN_WEDGE_H = (0.004, 0.0072)  # wedge face height above the column top at the lip foot (chosen per angle)
F_UTURN_SUPPORT_Y = (-0.096, 0.0, 0.096, 0.192, 0.288, 0.384)  # wedge / column centres across the plate (y, m)


def final_uturn_geometry(tilt: float) -> dict:
    """Plate pose and supports. Row 1: printed wedges (2x2 brick socket underside, face at ``tilt``, lip at the downhill
    end) on 2x2 columns right at the lane ends; the plate's lower edge rests against the lips. The wedge face height
    at the lip foot is chosen per angle so that the plate's top lower corner is level with the lane tops (z = 0); the
    plate starts a hinge gap (< 8 mm) beyond the lane ends. Rows 2-3: plain 2x2 brick columns with a 2x2 tile whose
    downhill top edge touches the plate's underside, placed at the grid position / plate count with the smallest
    height residual near 1/2 and near the top of the plate."""
    th = math.radians(tilt)
    s, c = math.sin(th), math.cos(th)
    t, L = F_UTURN_PLATE_T, F_UTURN_LANE_LEN
    lip = max(F_UTURN_LIP_MIN, (0.0004 + t * s) / c)  # the plate's top lower corner ends up ~0.5 mm past the lanes
    xd = L + 0.0001  # wedge downhill end (wedges on 2x2 columns right at the lane ends)
    bx = xd + lip * c  # plate's lower bottom corner (against the lip)
    tx = bx - t * s  # plate's lower top corner
    bz = -t * c
    j = math.floor((bz + F_DECK_H - F_UTURN_WEDGE_H[0]) / BRICK_PLATE)
    zc = -F_DECK_H + j * BRICK_PLATE  # wedge column top
    h_lip = bz - zc
    rows = [{"kind": "wedge", "x0": _r6(xd), "top_m": _r6(zc), "plates": j, "residual_mm": 0.0}]
    for s_target in (0.5 * F_UTURN_PLATE, F_UTURN_PLATE - 0.040):
        xt = bx + s_target * c
        best = None
        for m in range(-10, 11):
            x0 = L + 0.0001 + (round((xt - L) / BRICK_STUD) + m) * BRICK_STUD
            if x0 + 2 * BRICK_STUD > bx + (F_UTURN_PLATE - 0.004) * c or x0 < bx + 0.03:
                continue
            zu = bz + (x0 - bx) * s / c  # plate underside above the column's downhill top edge
            jj = round((zu + F_DECK_H) / BRICK_PLATE)
            res = -F_DECK_H + jj * BRICK_PLATE - zu
            if best is None or abs(res) < abs(best[2]):
                best = (x0, jj, res)
        x0, jj, res = best
        rows.append({"kind": "column", "x0": _r6(x0), "top_m": _r6(-F_DECK_H + jj * BRICK_PLATE), "plates": jj,
                     "residual_mm": round(res * 1000, 2)})
    return {"tilt_rad": th, "hinge_x_m": _r6(tx), "hinge_gap_mm": round((tx - L) * 1000, 2),
            "plate_bottom_corner_m": (_r6(bx), _r6(bz)), "wedge_h_lip_mm": round(h_lip * 1000, 3),
            "wedge_x0_m": _r6(xd), "wedge_lip_mm": round(lip * 1000, 3), "rows": rows}


def final_uturn_plate_dy(lane_mm: float) -> float:
    """Sideways offset of the U-turn plate's centre line from the turn centre y = R (m). The printed stand pins the
    plate's underside hole grid to the floor's stud grid. The plate is 64 studs wide, so its holes lie 4 mm off its
    centre line; the floor's studs lie on y = 0 mod 8 mm for an odd-stud lane (25 / 19 studs: levels 1 and 3) and on
    4 mod 8 mm for an even one. Odd lanes therefore shift the plate by half a stud, +4 mm (centre y = 156 mm), the
    same way as the support columns (``yc + BRICK_STUD / 2`` below): the plate's seam joiners then stay centred in the
    80 mm gaps between the columns (plate y = -200, -104, +88, +184 mm from its centre line). Even lanes (22 studs, level 2): no shift."""
    return BRICK_STUD / 2 if round(lane_mm / 8) % 2 else 0.0


def final_uturn(level: int, spec) -> Obstacle:
    """U-turn (``uturn``) on brick: lanes are brick decks 99.2 mm above the baseplate floor, the connector plate is four
    10 in baseplates with tiles (512 x 512 x 4.7 mm) resting on printed wedge adapters (``final_uturn_geometry``)."""
    tilt, lane_mm, gap_mm = spec
    g = final_uturn_geometry(tilt)
    th = g["tilt_rad"]
    hw, gap, L, back = lane_mm * 1e-3 / 2, gap_mm * 1e-3, F_UTURN_LANE_LEN, F_UTURN_BACK
    R = hw + gap / 2
    P = F_UTURN_PLATE
    tx = g["hinge_x_m"]
    high = P * math.sin(th)
    fail = -0.05
    floor = -F_DECK_H
    yb = 2 * R
    shapes = [
        box("lane_a", -back, L, hw, 0.0, floor, BRICK_SURF, BRICK_GREY),
        box("lane_b", -back, L, hw, 0.0, floor, BRICK_SURF, BRICK_GREY, y0=yb),
    ]
    pl = slab("plate", (tx, 0.0), (tx + P * math.cos(th), high), P / 2, F_UTURN_PLATE_T, BRICK_SURF)
    plate_dy = final_uturn_plate_dy(lane_mm)
    pl.pos = (pl.pos[0], _r6(R + plate_dy), pl.pos[2])
    pl.color = BLUE
    shapes.append(pl)
    bx, bz = g["plate_bottom_corner_m"]
    for r_i, row in enumerate(g["rows"]):
        x0 = row["x0"]
        if row["kind"] == "wedge":  # the wedge as a box up to its face height at the downhill end (under the plate)
            ztop = row["top_m"] + (g["wedge_h_lip_mm"] - g["wedge_lip_mm"] * math.sin(th)) * 1e-3
        else:
            ztop = row["top_m"]
        for k, yc in enumerate(F_UTURN_SUPPORT_Y):
            yc = _r6(yc + (BRICK_STUD / 2 if round(lane_mm / 8) % 2 else 0.0))  # 2x2 columns centred on grid lines
            shapes.append(box(f"support{r_i}_{k}", x0, _r6(x0 + 2 * BRICK_STUD - 0.0002), BRICK_STUD - 0.0001,
                              _r6(ztop), floor, BRICK_SURF, PRINT_COLOR if row["kind"] == "wedge" else BRICK_GREY, y0=yc))
    pts = [(-back, 0.0)]
    k = 60
    for j in range(k + 1):
        a = math.pi * j / k
        pts.append((round(L + R * math.sin(a), 6), round(R - R * math.cos(a), 6)))
    pts.append((-back, yb))
    seg = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts[:-1], pts[1:], strict=True)]
    s_arc_end = sum(seg[:-1])
    goal_s0 = s_arc_end + (L - 0.10)
    s_total = sum(seg)
    path = goal_s0 - back
    return Obstacle(
        "u_turn",
        level,
        {"tilt_deg": tilt, "lane_width_mm": round(2 * hw * 1000), "gap_mm": round(gap * 1000), "lane_m": L,
         "turn_radius_mm": round(R * 1000), "plate_m": P, "plate_mm": (P * 1000, P * 1000, F_UTURN_PLATE_T * 1000),
         "plate_rise_mm": round(high * 1000, 1), "path_m": round(path, 4), "hinge_gap_mm": g["hinge_gap_mm"],
         "wedge_h_lip_mm": g["wedge_h_lip_mm"], "wedge_lip_mm": g["wedge_lip_mm"], "turn_margin_mm": round((P * math.cos(th) + tx - L - R) * 1000),
         "plate_y_mm": round((R + plate_dy) * 1000, 1),
         "supports": [{k: v for k, v in r.items()} for r in g["rows"]]},
        f"U-turn on a brick plate (4 baseplates) tilted {tilt} deg up (turn radius {R * 1000:.0f} mm) between two "
        f"{2 * hw * 1000:.0f} mm brick lanes {gap * 1000:.0f} mm apart",
        shapes,
        StartSpec(front_x=0.0),
        GoalSpec(x_min=round(s_arc_end, 6),  # anywhere on the second lane
        x_max=round(s_total, 6), y_half=hw + 0.02, z_min=-0.004),
        fail_z=round(fail, 5),
        time_limit_s=round(30.0 + 25.0 * path),
        floor_z=round(floor, 5),
        lane_half_width=R,
        stuck_window_s=6.0,
        centreline=pts,
    )


FINAL_LEVELS: dict[str, list] = {
    "ramp": [(a, "rubber_mat") for a in (30, 46, 62)],  # nominal slope deg (actual: final_ramp_geometry)
    "gap": [152, 336, 752],  # gap mm (19, 42, 94 studs)
    "bridge": [40, 24, 8],  # printed plank width mm (5, 3, 1 studs), 640 mm long
    # span m, nominal incline deg, sag mm, cord radius mm: the goal deck rises a whole number of plates (the nearest
    # to 600 mm x tan(incline)) and the span is that rise / tan(incline), so the tables stand 585-600 mm apart
    "rope": [(0.6, 0.0, 12.5, 1.5), (0.5989, 10.0, 12.5, 1.5), (0.5979, 20.0, 12.5, 1.5)],
    "steps": [(28.8, 3), (57.6, 3), (105.6, 3)],  # riser mm (3, 6, 11 bricks), count
    "bumps": [(35.0, 10), (55.0, 14), (80.0, 18)],  # max rod mm, rod count
    # nominal tilt deg (actual: final_seesaw_geometry); negative: tipped with the far end down, near end raised
    "seesaw": [-15.0, -30.0, -46.0],
    "gap_drop": [48.0, 128.0, 336.0],  # drop mm (15, 40, 105 plates) over a 152 mm gap
    "wall": [4, 16, 64],  # bricks (32 mm thick brick wall: climb over, land beyond)
    "u_turn": [(32.45, 200, 104), (35.46, 176, 128), (37.97, 152, 152)],  # tilt deg, lane mm, gap mm
}
"""The benchmark's courses: 10 obstacles x 3 levels, each level exactly what its simple real build produces (brick
baseplates, columns and decks; printed only: bridge plank segments, rope saddle posts, bump plates, the seesaw plank,
the U-turn wedges)."""

FINAL_GENERATORS = {"ramp": final_ramp, "gap": final_gap, "bridge": final_bridge, "rope": final_rope,
                    "steps": final_steps, "bumps": final_bumps, "seesaw": final_seesaw, "gap_drop": final_gapdrop,
                    "wall": final_wall, "u_turn": final_uturn}

FINAL_CHASM_KINDS = ("gap", "bridge", "rope", "gap_drop", "u_turn", "seesaw")
"""Benches whose travel surface is raised over a chasm (the ground plane at ``floor_z`` is the chasm floor: the
baseplate sheet under the decks, the table under the rope; on the seesaw the floor under the plank). Any part of the
design touching it fails the run ("touched chasm floor (<part>)"); ``generate`` marks these levels with
``params["chasm_floor_z"]``."""
FINAL_OVER_KINDS = ("wall", "bumps")
"""Benches that must be crossed over the top: a run fails ``left_lane`` as soon as any part's origin leaves the
lane (the wall spans the whole lane, so the only way past it is over; on the bumps the car may not skirt the plates)."""


def n_levels(kind: str) -> int:
    return len(FINAL_LEVELS.get(kind, ()))


def generate(kind: str, level: int, spec=None) -> Obstacle:
    """One course: ``kind`` at ``level`` (1..3). ``spec`` (optional): build the level from this spec instead of
    ``FINAL_LEVELS`` (a measured real course, e.g. a filmed run); the level number is kept as a label."""
    if kind not in FINAL_GENERATORS:
        raise KeyError(f"unknown obstacle '{kind}' ({', '.join(FINAL_GENERATORS)})")
    n = n_levels(kind)
    if not 1 <= level <= n:
        raise ValueError(f"{kind}: level must be 1..{n}")
    ob = FINAL_GENERATORS[kind](level, FINAL_LEVELS[kind][level - 1] if spec is None
                                else (tuple(spec) if isinstance(spec, list) else spec))
    if spec is not None:
        ob.params["custom_spec"] = list(spec) if isinstance(spec, (list, tuple)) else spec
    if kind in FINAL_CHASM_KINDS:  # any part touching the chasm floor fails (judge: "touched chasm floor")
        ob.params["chasm_floor_z"] = ob.floor_z
    if not ob.centreline:  # the goal is anywhere past the obstacle: no far end, no side limit
        ob.goal = dataclasses.replace(ob.goal, x_max=INF, y_half=INF)
    if kind in FINAL_OVER_KINDS:  # over, not around: every part origin stays in the lane
        # on the bumps a part may step slightly outside the plates (a wheel's width, 20 mm)
        ob.params["lane_parts_half_width_m"] = ob.lane_half_width + (F_BUMP_PART_MARGIN if kind == "bumps" else 0.0)
    board = start_board_mm(kind)
    if board is not None:
        ob = extend_start_board(ob, board)
    return ob


# ----------------------------------------------------------------------------------------------------------------
# placement
# ----------------------------------------------------------------------------------------------------------------


@dataclass
class VehiclePose:
    origin: tuple[float, float, float]  # world position of the design origin [m]
    quat: tuple[float, float, float, float]  # world orientation of the design frame (xyzw)
    parts: dict[str, tuple[tuple[float, float, float], tuple[float, float, float, float]]]  # name -> (pos, quat)
    rear_x: float
    front_x: float


def _q_pitch_design(pitch_deg: float):
    return pitch_quat(pitch_deg)


def _rot_pitch(pitch_deg: float) -> np.ndarray:
    return rot_matrix(0.0, -pitch_deg)


def place_vehicle(ob: Obstacle, design: Design, stats: dict, lift: float = 0.0005) -> VehiclePose:
    """World poses of all parts at the start line (design frame -> env frame)."""
    from .design import qmul

    P = place(design)
    ob = with_start_gap(ob, design)
    R = _rot_pitch(ob.start.pitch_deg)
    corners = []
    boxes = [pl.aabb() for pl in P.values()]
    if getattr(design, "treads", None):  # a tread's envelope reaches past its sprockets
        from .treads import tread_geoms  # noqa: PLC0415

        boxes += [g.bbox() for g in tread_geoms(design, P)]
    for lo, hi in boxes:
        corners += [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    c = (R @ (np.array(corners) * 1e-3).T).T
    if ob.start.align in ("rope", "rope_track"):
        y_ref = stats.get("rope_line_y_mm", stats["capability"].get("rope_wheel_line_y_mm", stats["track_center_y_mm"]))
    else:
        y_ref = stats["track_center_y_mm"]
    # wheel contact reference: the rear-most ground wheel bottom
    wheels = [P[n] for n in stats["wheels"]] if stats["wheels"] else list(P.values())
    rw = min(wheels, key=lambda w: w.p[0])
    contact = R @ (np.array([rw.p[0], y_ref, stats["ground_z_mm"]]) * 1e-3)
    ox = (ob.start.front_x - c[:, 0].max()) if ob.start.front_x is not None else (ob.start.rear_x - c[:, 0].min())
    cx = ox + contact[0]
    surf = ob.start.surface_z + (cx - ob.start.surface_x) * math.tan(math.radians(ob.start.pitch_deg))
    oz = surf + lift - contact[2]
    oy = ob.start.y - contact[1]
    origin = np.array([ox, oy, oz])
    q0 = _q_pitch_design(ob.start.pitch_deg)
    parts = {}
    for name, pl in P.items():
        pos = origin + R @ (pl.p * 1e-3)
        parts[name] = (tuple(float(v) for v in pos), qmul(q0, quat_xyzw(pl.inst.yaw_deg, pl.inst.spin_deg)))
    return VehiclePose(tuple(float(v) for v in origin), q0, parts, float(ox + c[:, 0].min()), float(ox + c[:, 0].max()))


APPROACH_BOARD_MM = 500.0
"""Flat board before every obstacle on the real benches (about 50 cm everywhere): the whole vehicle
must start on it."""


def with_start_gap(ob: Obstacle, design: Design) -> Obstacle:
    """the obstacle with its start line moved to the design's start_gap_mm (front of the vehicle at x = -gap)"""
    gap = getattr(design, "start_gap_mm", None)
    if gap is None or ob.start.front_x is None:
        return ob
    return dataclasses.replace(ob, start=dataclasses.replace(ob.start, front_x=-float(gap) * 1e-3))


START_BOARD_ENV = "RB_START_BOARD_MM"
"""optional start-board length per bench, e.g. '{"*": 500, "gap": 1000}' (the benchmark's setting,
robobuilder.BENCHMARK_ENV): the raised start (platform_start / the U-turn's start lane) is lengthened backwards to it
(its front edge stays at the start line) and the vehicle must fit on that board. Empty: the courses as built (bridge
456 mm, seesaw 400 mm, U-turn 200 mm)."""


def start_board_mm(kind: str) -> float | None:
    from . import rules  # noqa: PLC0415

    raw = rules.get("start_board_raw")  # a per-thread override (robobuilder.courses.rules)
    raw = (os.environ.get(START_BOARD_ENV, "") if raw is None else raw).strip()
    if not raw:
        return None
    import json  # noqa: PLC0415

    v = json.loads(raw)
    v = v if isinstance(v, dict) else {"*": v}
    x = v.get(kind, v.get("*"))
    return None if x is None else float(x)


def extend_start_board(ob: Obstacle, board_mm: float) -> Obstacle:
    """the start surface lengthened backwards to ``board_mm`` behind the start line (never shortened)"""
    L = board_mm / 1000.0
    shapes = []
    for sh in ob.shapes:
        if sh.kind == "box" and (sh.name == "platform_start" or (ob.kind == "u_turn" and sh.name == "lane_a")):
            x1 = sh.pos[0] + sh.size[0] / 2
            x0 = min(sh.pos[0] - sh.size[0] / 2, x1 - L) if x1 <= 1e-6 else min(sh.pos[0] - sh.size[0] / 2, -L)
            sh = dataclasses.replace(sh, size=(x1 - x0, *sh.size[1:]), pos=((x0 + x1) / 2, *sh.pos[1:]))
        shapes.append(sh)
    ob = dataclasses.replace(ob, shapes=shapes)
    ob.params["start_board_mm"] = float(board_mm)
    return ob


def approach_mm(ob: Obstacle) -> float:
    """length of flat start surface before the obstacle's start line (x = 0): the 500 mm board, or a shorter start
    table (bridge 456 mm, seesaw 400 mm); a start board set by RB_START_BOARD_MM (start_board_mm) wins"""
    if ob.params.get("start_board_mm") is not None:
        return float(ob.params["start_board_mm"])
    for sh in ob.shapes:
        if sh.name == "lane_a" and sh.kind == "box" and ob.kind == "u_turn":  # the raised start lane
            return min(APPROACH_BOARD_MM, round((sh.size[0] / 2 - sh.pos[0]) * 1000.0, 1))
        if sh.name == "platform_start" and sh.kind == "box":
            return min(APPROACH_BOARD_MM, round((sh.size[0] / 2 - sh.pos[0]) * 1000.0, 1))
    return APPROACH_BOARD_MM


def start_gap_issue(ob: Obstacle, design: Design, length_mm: float) -> str | None:
    """A chosen start gap (front of the vehicle to the obstacle's start line, x = 0) must leave the whole vehicle on
    the approach board: 0 <= gap and gap + length <= approach_mm(ob)."""
    gap = getattr(design, "start_gap_mm", None)
    if gap is None:
        # no start gap chosen: the level's default start. On a raised start (a start table / platform over a
        # chasm: gap, bridge, seesaw, rope, gapdrop, ...) the whole vehicle must still fit on it
        if ob.start.front_x is None or not any(sh.name == "platform_start" for sh in ob.shapes):
            return None
        g0 = max(0.0, -float(ob.start.front_x) * 1000.0)
        room = approach_mm(ob)
        if g0 + length_mm > room:
            return (f"with the default start (front {g0:.0f} mm from the start line) the vehicle's length {length_mm:.0f} mm "
                    f"does not fit on the {room:.0f} mm start board: it is {length_mm + g0 - room:.0f} mm too long")
        return None
    if ob.start.front_x is None:
        return f"start_gap_mm is not available on the {ob.kind} bench"
    if gap < 0:
        return f"start_gap_mm {gap:g} < 0: the vehicle would start on the obstacle"
    room = approach_mm(ob)
    if gap + length_mm > room:
        return (f"start_gap_mm {gap:g} + vehicle length {length_mm:.0f} mm > the {room:.0f} mm approach board: the "
                f"vehicle would not fit on it")
    return None


CONSTRAINT_KEYS = ("max_length_mm", "max_mass_g", "max_drive_motors", "max_wheel_diameter_mm", "sensors_only",
                   "payload", "max_parts")  # fmt: skip


def task_constraints(max_parts: int | None = None) -> dict:
    """Constraints of every task, on top of every level's own: an optional cap on the number of motors that drive
    wheels (motors that only turn legs, arms, masses or tails are free, as ``wheel_motors`` counts them) and an
    optional cap on the total number of pieces (every ``parts`` entry: pins, axles and bushes included)."""
    # RB_MAX_DRIVE_MOTORS: "none" (the benchmark) lifts the drive-motor cap, a number sets it
    lim = os.environ.get("RB_MAX_DRIVE_MOTORS", "1")
    out = {} if lim.lower() == "none" else {"max_drive_motors": int(lim)}
    if max_parts is not None:
        out["max_parts"] = int(max_parts)
    return out


def check_constraints(ob: Obstacle, design: Design, stats: dict, extra: dict | None = None) -> list[str]:
    """Violations of a level's constraints (checked before the run; a violating design is not simulated). ``extra``:
    task constraints merged in (the stricter value wins for the numeric caps), e.g. :func:`task_constraints`."""
    from .design import wheel_motors  # noqa: PLC0415
    from .parts import bench_parts  # noqa: PLC0415

    c, errs = dict(ob.constraints), []
    for k, v in (extra or {}).items():
        c[k] = min(c[k], v) if (k in c and isinstance(v, (int, float)) and not isinstance(v, bool)) else v
    if "max_parts" in c and stats["n_parts"] > c["max_parts"]:
        errs.append(f"constraint: {stats['n_parts']} pieces > {c['max_parts']}")
    if "max_length_mm" in c and stats["length_mm"] > c["max_length_mm"] + 1e-6:
        errs.append(f"constraint: {stats['length_mm']} mm long at the start > {c['max_length_mm']} mm")
    if "max_mass_g" in c and stats["mass_g"] > c["max_mass_g"] + 1e-6:
        errs.append(f"constraint: mass {stats['mass_g']} g > {c['max_mass_g']} g")
    if "max_drive_motors" in c and len(wheel_motors(design)) > c["max_drive_motors"]:
        errs.append(f"constraint: {len(wheel_motors(design))} drive motors > {c['max_drive_motors']}")
    if "max_wheel_diameter_mm" in c:
        cat = bench_parts()
        tr_r = {}
        if getattr(design, "treads", None):  # a tread's sprocket counts with the tread round it
            from .treads import tread_wheel_radii  # noqa: PLC0415

            tr_r = {n: v[0] for n, v in tread_wheel_radii(design, place(design)).items()}
        for p in design.parts:
            bp = cat.get(p.part)
            r = tr_r.get(p.name, bp.wheel_radius if bp is not None else 0.0)
            if bp is not None and (bp.kind == "wheel" or p.name in tr_r) and 2 * r > c["max_wheel_diameter_mm"] + 1e-6:
                errs.append(f"constraint: wheel '{p.name}' is {2 * r:.1f} mm > {c['max_wheel_diameter_mm']} mm")
    if c.get("sensors_only") and any("x" in cmd for cmd in design.motor_program):
        errs.append("constraint: no position ('x') triggers: the program must use sensors or time")
    if c.get("payload") and design.cargo_mm is None:
        errs.append("constraint: the design must declare a cargo point (cargo_mm) for the payload")
    return errs


def finalize(ob: Obstacle, design: Design, stats: dict, pose: VehiclePose) -> Obstacle:
    """Resolve vehicle-dependent geometry (none on the benchmark's courses: the course is returned as is)."""
    return ob


# ----------------------------------------------------------------------------------------------------------------
# judge
# ----------------------------------------------------------------------------------------------------------------


def _qrot(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty), vy + w * ty + (z * tx - x * tz), vz + w * tz + (x * ty - y * tx))


def _qconj(q):
    return (-q[0], -q[1], -q[2], q[3])


def mechanism_groups(design: Design) -> list[tuple[str, set[str]]]:
    """Rigid (stud / pin) clusters built on a beam brick with axle hole (32064) that turns with an axle: arms,
    booms, legs, as (anchor 32064, members). They move relative to the chassis by design, but not relative to their
    own anchor: a member that leaves its anchor has come off. Inventory designs: clusters on a pivot pin, liftarms
    locked on a turning axle, and clusters joined to the rest only through a hinge (their hole turning on an axle,
    :func:`_hinge_anchors`) are mechanisms too."""
    from .design import RIGID_KINDS, _components  # noqa: PLC0415
    from .parts import bench_parts  # noqa: PLC0415

    cat = bench_parts()
    names = [p.name for p in design.parts]
    kinds = {p.name: cat[p.part].kind for p in design.parts if p.part in cat}
    out = []
    inventory = any(cat[p.part].inventory for p in design.parts if p.part in cat)
    if inventory:  # inventory parts: liftarms / connectors locked on an axle (cross) and pivot-pin linkages move too
        from .design import pivot_connections, rigid_edges  # noqa: PLC0415

        piv = pivot_connections(design)
        movers = {c.child for c in design.connections if c.kind == "cross" and kinds.get(c.child) != "axle"}
        movers |= {design.connections[i].parent for i in piv} | {design.connections[i].child for i in piv}
        edges = rigid_edges(design)
    else:
        movers, edges = set(), [(c.child, c.parent) for c in design.connections if c.kind in RIGID_KINDS]
    comps = _components(names, edges)
    anchored: set[str] = set()  # inventory: clusters that are mechanisms of their own (a link on a pivot pin)
    if inventory:
        for comp in comps:
            if design.chassis not in comp and any(
                    kinds.get(n) == "axle_brick" or (n in movers and kinds.get(n) not in ("gear", "wheel", "bush"))
                    for n in comp):
                anchored |= set(comp)
    hinged = _hinge_anchors(design, comps, kinds) if inventory else {}
    for comp in comps:
        if design.chassis not in comp and frozenset(comp) in hinged and not (set(comp) & anchored):
            anchored |= set(comp)
    for comp in comps:
        anchors = sorted(n for n in comp if kinds.get(n) == "axle_brick")
        if inventory and not anchors:
            anchors = sorted(n for n in comp if n in movers and kinds.get(n) not in ("gear", "wheel", "bush"))
        if inventory and not anchors and design.chassis not in comp:
            anchors = hinged.get(frozenset(comp), [])
        if design.chassis not in comp and anchors:
            # parts that hang on the cluster alone (a free wheel on an axle in the arm's tip hole) move with it
            rest = [n for n in names if n not in comp and n not in anchored]
            for sub in _components(rest, [(c.child, c.parent) for c in design.connections
                                          if c.child not in comp and c.parent not in comp]):  # fmt: skip
                touches = any((c.child in sub and c.parent in comp) or (c.parent in sub and c.child in comp)
                               for c in design.connections)  # fmt: skip
                if touches and design.chassis not in sub:
                    comp = set(comp) | set(sub)
            out.append((anchors[0], set(comp)))
    for d in getattr(design, "differentials", None) or []:  # the satellites turn with the case
        if d.case in names:
            out.append((d.case, {d.case, *(s for s in d.satellites if s in names)}))
    if getattr(design, "racks", None):  # rack slides (core.racks): the side without the chassis slides
        from .racks import moving_groups  # noqa: PLC0415

        have = set().union(*[m for _, m in out]) if out else set()
        for anchor, members in moving_groups(design):
            rest = (set(members) - have) | {anchor}
            out.append((anchor, rest))
            have |= rest
    return out


NOT_HINGE_ANCHOR = ("gear", "wheel", "bush")  # free-turning gears / wheels / bushes on an axle stay chassis-checked


def _hinge_anchors(design: Design, comps, kinds) -> dict[frozenset, list[str]]:
    """Inventory designs: rigid clusters (without the chassis) joined to another cluster through a 'hinge' connection
    (an axle turning in a round hole of the cluster) swing by design: {cluster: [its hinge-hole members, sorted]}.
    Free gears / wheels / bushes spinning on an axle are left out (they turn in place)."""
    of = {n: frozenset(c) for c in comps for n in c}
    out: dict[frozenset, set[str]] = {}
    for c in design.connections:
        if c.kind != "hinge" or c.child not in of or c.parent not in of or of[c.child] == of[c.parent]:
            continue
        n = c.parent  # the part with the hole (an axle's own cluster: cross-locked liftarms are movers already)
        if design.chassis not in of[n] and kinds.get(n) not in NOT_HINGE_ANCHOR:
            out.setdefault(of[n], set()).add(n)
    return {k: sorted(v) for k, v in out.items()}


def hinge_links(design: Design) -> list[tuple[str, str]]:
    """(anchor, partner) of every hinge-joined mechanism anchor and the part across its hinge: an axle turning in a
    hole keeps its distance to the hole's part (the axle origin is on the turning axis), so a change of that distance
    beyond the break limit means the hinge came apart."""
    anchors = {a for a, _ in mechanism_groups(design)}
    out = []
    for c in design.connections:
        if c.kind == "hinge":
            if c.child in anchors:
                out.append((c.child, c.parent))
            elif c.parent in anchors:
                out.append((c.parent, c.child))
    return out


def mechanism_parts(design: Design) -> set[str]:
    """All parts of :func:`mechanism_groups` clusters."""
    return set().union(*[m for _, m in mechanism_groups(design)]) if mechanism_groups(design) else set()


FINAL_SETTLE_S = 5.0  # seconds the vehicle must stay in the goal, upright, after reaching it


class Judge:
    """Decides success / failure from part poses (call :meth:`update` every few milliseconds while driving)."""

    FLIP_DEG = 75.0
    FLIP_HOLD_S = 0.5
    BREAK_MM = 15.0
    # after the vehicle first reaches the goal it must stay there, upright (chassis within UPRIGHT_DEG
    # of its start attitude, a longer tilt than UPRIGHT_HOLD_S fails) and unbroken, for settle_s seconds; the run's
    # time is the moment it reached the goal (the settle is not counted). RB_SETTLE_S overrides (0 = off).
    UPRIGHT_DEG = 30.0
    UPRIGHT_HOLD_S = 0.3

    def __init__(self, ob: Obstacle, design: Design, pose: VehiclePose):
        self.ob = ob
        self.chassis = design.chassis
        from .design import qmul

        self._qmul = qmul
        c_pos, c_q = pose.parts[self.chassis]
        self.q_chassis0_inv = _qconj(c_q)
        self.q_vehicle0 = pose.quat
        # every part's start offset in the chassis frame (break detection); parts of a moving mechanism (a rigid
        # cluster built on a beam brick with axle hole: arms, booms, legs) are exempt: they move by design
        self.rel0 = {n: np.array(_qrot(_qconj(c_q), np.subtract(p, c_pos))) for n, (p, _) in pose.parts.items()}
        self.mechanism = mechanism_parts(design)
        self.mech_rel0 = {}  # member -> (anchor, start offset in the anchor frame)
        for a, members in mechanism_groups(design):
            a_pos, a_q = pose.parts[a]
            for n in members:
                if n != a and n in pose.parts:
                    self.mech_rel0[n] = (a, np.array(_qrot(_qconj(a_q), np.subtract(pose.parts[n][0], a_pos))))
        self.hinge0 = [(a, b, float(np.linalg.norm(np.subtract(pose.parts[a][0], pose.parts[b][0]))))
                       for a, b in hinge_links(design) if a in pose.parts and b in pose.parts]
        self.cl = None  # curved course: (segment starts, segment vectors), their lengths and start arc lengths
        if ob.centreline:
            P = np.asarray(ob.centreline, dtype=float)
            self.cl = (P[:-1], P[1:] - P[:-1])
            self.cl_len = np.linalg.norm(self.cl[1], axis=1)
            self.cl_s = np.concatenate([[0.0], np.cumsum(self.cl_len)[:-1]])
            self.s_chassis = float(self._project([c_pos])[0][0])
        self.start_ref = self._ref(pose.parts, None, init=True)
        self.goal_dist = max(ob.goal.x_min - self.start_ref, 1e-6)
        self.best = self.start_ref
        self.anchor, self.anchor_t = self.start_ref, 0.0  # stuck detection: last 5 mm progress mark
        self.flip_since = None
        self.t = 0.0
        self.result = None
        self.hold_hist: list = []
        self.chasm_touch = None  # raised benches: name of the first part that touched the chasm floor
        env_settle = os.environ.get("RB_SETTLE_S")
        self.settle_s = float(env_settle) if env_settle not in (None, "") else FINAL_SETTLE_S
        self.cross_t = None  # when the vehicle first reached the goal (settle phase running)
        self.tilt_since = None
        # set by the simulator: "<upper>/<lower>" of the first stud joint released while driving -> "broke"
        self.joint_released = None
        # set by the simulator: a mechanism that came apart while driving (a rack ran off its pinion) -> "broke"
        self.mech_broke = None
        # bumps: the wheels (tyres, tread sprockets), whose origins over the field must stay within the rods' span
        self.wheels = set()
        if ob.kind == "bumps" and ob.params.get("rods_y_span_m") is not None:
            from .parts import bench_parts  # noqa: PLC0415

            cat = bench_parts()
            self.wheels = {p.name for p in design.parts if p.part in cat and cat[p.part].kind == "wheel"}
            self.wheels |= {s_ for t_ in (getattr(design, "treads", None) or []) for s_ in t_.sprockets}
            self.wheels &= set(pose.parts)

    # windows of the centreline searched around the chassis' last arc length: the chassis itself (it moves < 30 mm per
    # check) and the other parts (a vehicle is < 0.6 m long). A part that climbed over a divider into the next lane
    # is then far from the local centreline (left_lane), not progress along the next lane.
    CL_CHASSIS_WIN = 0.15
    CL_PARTS_WIN = 0.6

    def _project(self, pts, lo: float = -INF, hi: float = INF) -> tuple[np.ndarray, np.ndarray]:
        """Arc length along the centreline and horizontal distance from it of points (x, y, ...), searching the
        segments that overlap the arc-length window [lo, hi]."""
        A, D = self.cl
        sel = np.nonzero((self.cl_s + self.cl_len >= lo) & (self.cl_s <= hi))[0]
        if not len(sel):
            sel = np.arange(len(A))
        p = np.asarray([q[:2] for q in pts], dtype=float)[:, None, :]  # (k, 1, 2)
        a, dv, ln = A[sel][None], D[sel][None], self.cl_len[sel][None]
        u = np.clip(np.sum((p - a) * dv, axis=2) / np.maximum(ln**2, 1e-12), 0.0, 1.0)  # (k, m)
        dist = np.linalg.norm(p - (a + u[..., None] * dv), axis=2)
        i = np.argmin(dist, axis=1)
        k = np.arange(len(p))
        return self.cl_s[sel][i] + u[k, i] * self.cl_len[sel][i], dist[k, i]

    def _ref(self, parts, load_pos, init=False) -> float:
        g = self.ob.goal
        if self.cl is not None:
            if g.ref not in ("rear", "front"):
                raise ValueError("a centreline course supports goal.ref 'rear' / 'front' only")
            s, _ = self._project([p for p, _ in parts.values()], self.s_chassis - self.CL_PARTS_WIN,
                                 self.s_chassis + self.CL_PARTS_WIN)  # fmt: skip
            return float(s.min() if g.ref == "rear" else s.max())
        if g.ref == "load":
            if load_pos is None:
                return next(s.pos[0] for s in self.ob.shapes if s.name == "sled")
            return float(load_pos[0])
        xs = [p[0] for p, _ in parts.values()]
        if g.ref == "half":
            return 0.5 * (min(xs) + max(xs))
        return min(xs) if g.ref == "rear" else max(xs)

    def progress(self) -> float:
        return (self.best - self.start_ref) / self.goal_dist

    def update(self, t: float, parts: dict, load_pos=None) -> dict | None:
        """``parts``: name -> (pos xyz, quat xyzw) in the env frame; ``load_pos``: towed sled position."""
        if self.result is not None:
            return self.result
        self.t = t
        ob, g = self.ob, self.ob.goal
        c_pos, c_q = parts[self.chassis]
        lateral = abs(c_pos[1])
        if self.cl is not None:
            s_c, d_c = self._project([c_pos], self.s_chassis - self.CL_CHASSIS_WIN, self.s_chassis + self.CL_CHASSIS_WIN)
            self.s_chassis, lateral = float(s_c[0]), float(d_c[0])
        ref = self._ref(parts, load_pos)
        self.best = max(self.best, ref)
        if ref > self.anchor + ob.stuck_min_progress_m:
            self.anchor, self.anchor_t = ref, t
        # vehicle up axis: rotation relative to the start pose applied to the start up axis
        q_rel = self._qmul(c_q, self.q_chassis0_inv)
        up = _qrot(self._qmul(q_rel, self.q_vehicle0), (0.0, 0.0, 1.0))
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, up[2]))))
        if tilt > self.FLIP_DEG:
            self.flip_since = t if self.flip_since is None else self.flip_since
        else:
            self.flip_since = None
        self.tilt_now = tilt
        broken = []
        for n, (p, _) in parts.items():
            if n in self.mechanism:
                continue
            d = np.array(_qrot(_qconj(c_q), np.subtract(p, c_pos)))
            if np.linalg.norm(d - self.rel0[n]) * 1e3 > self.BREAK_MM:
                broken.append(n)
        for n, (a, r0) in self.mech_rel0.items():  # a leg / arm member that came off its 32064
            a_pos, a_q = parts[a]
            d = np.array(_qrot(_qconj(a_q), np.subtract(parts[n][0], a_pos)))
            if np.linalg.norm(d - r0) * 1e3 > self.BREAK_MM:
                broken.append(n)
        for a, b, d0 in self.hinge0:  # a hinge-joined mechanism that came off its axle / hole
            if abs(float(np.linalg.norm(np.subtract(parts[a][0], parts[b][0]))) - d0) * 1e3 > self.BREAK_MM:
                broken.append(a)
        reason = None
        if c_pos[2] < ob.fail_z:
            reason = "fell"
        elif self.chasm_touch is not None and ob.params.get("chasm_floor_z") is not None:
            reason = f"touched chasm floor ({self.chasm_touch})"
        elif self.flip_since is not None and t - self.flip_since >= self.FLIP_HOLD_S:
            reason = "flipped"
        elif self.joint_released is not None:
            reason = f"broke (stud joint released: {self.joint_released})"
        elif getattr(self, "mech_broke", None) is not None:
            reason = f"broke ({self.mech_broke})"
        elif broken:
            reason = f"broke ({', '.join(sorted(broken)[:4])})"
        elif lateral > ob.lane_half_width and (ob.kind != "bumps" or (self.cross_t is None and c_pos[0] <= ob.params.get(
                "field_m", INF))):  # bumps: the chassis over the plates until it crossed / is past the field
            reason = "left_lane"
        elif (self.cl is None and ob.params.get("lane_parts_half_width_m") is not None
              and max((abs(p[1]) for p, _ in self._lane_parts(parts)), default=0.0) > ob.params["lane_parts_half_width_m"]):
            reason = "left_lane (a part went around the obstacle)"
        elif self._wheel_outside(parts):
            reason = "left_lane (a wheel went around the rods)"
        elif self.cl is not None:  # curved course: the goal region in arc length / distance from the centreline
            pl = [p for p, _ in parts.values()]
            s, d = self._project(pl, self.s_chassis - self.CL_PARTS_WIN, self.s_chassis + self.CL_PARTS_WIN)
            part_hw = ob.params.get("lane_parts_half_width_m")  # painted lanes: every part origin must stay inside
            if part_hw is not None and float(np.max(d)) > part_hw:
                return self._finish(False, "left_lane")
            if g.ref == "front":
                i = int(np.argmax(s))
                pl, s, d = [pl[i]], s[i : i + 1], d[i : i + 1]
            inside = all(g.x_min <= si <= g.x_max and di <= g.y_half and g.z_min <= p[2] <= g.z_max
                         for p, si, di in zip(pl, s, d, strict=True))  # fmt: skip
            if inside:
                return self._reached(t)
            if self.cross_t is not None:
                # reaching the goal is the pass, even if the vehicle leaves the goal area afterwards
                return self._finish(True, "crossed (left the goal area afterwards)", self.cross_t)
            if t - self.anchor_t > float(os.environ.get("RB_STUCK_S") or ob.stuck_window_s):  # env: diagnostics
                reason = "stuck"
            elif t >= ob.time_limit_s and self.cross_t is None:
                reason = "timeout"
        else:
            pts = (
                [p for p, _ in parts.values()]
                if g.ref == "rear"
                else ([max((p for p, _ in parts.values()), key=lambda q: q[0])] if g.ref == "front" else [load_pos])
            )
            if g.ref == "half":  # half the vehicle (the midpoint of its x extent) past x_min, every part in y / z
                pts = [p for p, _ in parts.values()]
                xm = 0.5 * (min(p[0] for p in pts) + max(p[0] for p in pts))
                inside = g.x_min <= xm <= g.x_max and all(abs(p[1]) <= g.y_half and g.z_min <= p[2] <= g.z_max for p in pts)
            else:
                inside = all(
                    p is not None and g.x_min <= p[0] <= g.x_max and abs(p[1]) <= g.y_half and g.z_min <= p[2] <= g.z_max
                    for p in pts
                )
            if ob.payload:
                pl = load_pos
                if pl is None or pl[2] < PAYLOAD_DROP_Z or pl[0] < min(p[0] for p, _ in parts.values()) - 0.05:
                    return self._finish(False, "dropped payload")
                inside = inside and g.x_min <= pl[0] <= g.x_max
            if inside and g.hold_s > 0:
                self.hold_hist.append((t, float(c_pos[0])))
                self.hold_hist = [h for h in self.hold_hist if t - h[0] <= g.hold_s + 1e-9]
                xs_h = [h[1] for h in self.hold_hist]
                if t - self.hold_hist[0][0] >= g.hold_s - 1e-9 and max(xs_h) - min(xs_h) < 0.005:
                    return self._finish(True, "stopped in the goal")
                inside = False
                self.anchor_t = t  # waiting in the goal is not "stuck"
            elif g.hold_s > 0:
                self.hold_hist = []
            if inside:
                return self._reached(t)
            if self.cross_t is not None:
                # reaching the goal is the pass, even if the vehicle leaves the goal area afterwards
                return self._finish(True, "crossed (left the goal area afterwards)", self.cross_t)
            if t - self.anchor_t > float(os.environ.get("RB_STUCK_S") or ob.stuck_window_s):  # env: diagnostics
                reason = "stuck"
            elif t >= ob.time_limit_s and self.cross_t is None:
                reason = "timeout"
        if reason:
            return self._finish(False, reason if self.cross_t is None else f"{reason} after crossing", self.cross_t)
        return None

    def _lane_parts(self, parts: dict):
        """the parts the per-part lane rule applies to: all on the wall; on the bumps only parts not yet past
        the end of the bump field, and none once the vehicle has reached the goal (driving on past the field is fine)"""
        if self.ob.kind != "bumps":
            return list(parts.values())
        if self.cross_t is not None:
            return []
        x_end = self.ob.params.get("field_m", INF)
        return [(p, q) for p, q in parts.values() if p[0] <= x_end]

    def _wheel_outside(self, parts: dict) -> bool:
        """bumps: a wheel origin over the bump field outside the rods' y span (+ F_BUMP_WHEEL_TOL), before the
        vehicle reached the goal"""
        span = self.ob.params.get("rods_y_span_m")
        if not self.wheels or span is None or self.cross_t is not None:
            return False
        x_end = self.ob.params.get("field_m", INF)
        for n in self.wheels:
            p = parts.get(n)
            if p is not None and 0.0 <= p[0][0] <= x_end and not (
                    span[0] - F_BUMP_WHEEL_TOL <= p[0][1] <= span[1] + F_BUMP_WHEEL_TOL):
                return True
        return False

    def _reached(self, t: float) -> dict | None:
        """inside the goal: success after settle_s seconds there, upright (at once with RB_SETTLE_S=0)"""
        if self.settle_s <= 0:
            return self._finish(True, "crossed")
        if self.cross_t is None:
            self.cross_t = t
        self.anchor_t = t  # resting in the goal is not "stuck"
        if self.tilt_now > self.UPRIGHT_DEG:
            self.tilt_since = t if self.tilt_since is None else self.tilt_since
            if t - self.tilt_since >= self.UPRIGHT_HOLD_S:
                return self._finish(False, f"tipped over after crossing ({self.tilt_now:.0f} deg)", self.cross_t)
        else:
            self.tilt_since = None
        if t - self.cross_t >= self.settle_s - 1e-9:
            return self._finish(True, f"crossed and stayed upright {self.settle_s:g} s", self.cross_t)
        return None

    def _finish(self, ok: bool, reason: str, t_report: float | None = None) -> dict:
        self.result = {
            "obstacle": self.ob.kind,
            "level": self.ob.level,
            "crossed": ok,
            "time_s": round(self.t if t_report is None else t_report, 3),
            "reached_goal_s": None if self.cross_t is None else round(self.cross_t, 3),
            "settle_s": self.settle_s,
            "max_progress": round(min(max(self.progress(), 0.0), 1.0), 4),
            "max_progress_m": round(self.best - self.start_ref, 4),
            "failure": None if ok else reason,
            "params": self.ob.params,
        }
        return self.result

    def timeout_result(self) -> dict:
        return self._finish(False, "timeout")
