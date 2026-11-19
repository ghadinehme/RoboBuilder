# Copyright (c) 2026, robobuilder project.
# SPDX-License-Identifier: BSD-3-Clause

"""Part catalog: the real parts, their colours and catalogue masses.

Masses are catalogue weights; the battery boxes add their cells. Geometry is in ``data/parts/metadata.json`` and
:mod:`.parts`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")  # part metadata (data/parts/metadata.json)

AAA_CELL_MASS_G = 11.5
"""Typical alkaline AAA cell [g]."""


@dataclass(frozen=True)
class PartType:
    """One part type of the catalogue."""

    catalogue_id: str
    catalogue_colour: int  # colour id in the inventory
    mass_g: float  # measured (catalogue) [g]
    mass_source: str
    role: str


PART_TYPES: dict[str, PartType] = {
    p.catalogue_id: p
    for p in (
        PartType("3895", 11, 4.2, "catalogue", "chassis rail: beam brick 1x12 with holes"),
        PartType("3710", 11, 0.71, "catalogue", "spacer plate 1x4"),
        PartType("3701", 11, 1.46, "catalogue", "gear-frame: beam brick 1x4 with holes"),
        PartType("3032", 11, 3.3, "catalogue", "deck: plate 4x6"),
        PartType("44294", 86, 1.05, "catalogue", "wheel axle: axle 7"),
        PartType("3705", 11, 0.59, "catalogue", "jackshaft: axle 4"),
        PartType("94925", 86, 0.70, "catalogue", "gear 16 tooth"),
        PartType("3648", 85, 1.17, "catalogue", "gear 24 tooth"),
        PartType("10928", 85, 0.22, "catalogue", "motor pinion: gear 8 tooth"),
        PartType("32062", 5, 0.26, "catalogue", "motor shaft: axle 2 notched"),
        PartType("4185", 86, 0.97, "catalogue", "wheel: wedge belt wheel"),
        PartType("3713", 86, 0.14, "catalogue", "bush"),
        PartType("58120c01", 86, 33.5, "catalogue (incl. cable)", "M-motor"),
        PartType("87513c01", 86, 40.0 + 6 * AAA_CELL_MASS_G, "catalogue 40 g + 6 AAA", "AAA battery box"),
    )
}


# ----------------------------------------------------------------------------------------------------------------
# More parts (masses are catalogue weights; wheel + tyre pairs are one part: rim and rubber tyre)
# ----------------------------------------------------------------------------------------------------------------

EXTENDED_PART_TYPES: dict[str, PartType] = {
    p.catalogue_id: p
    for p in (
        PartType("3894", 11, 2.2, "catalogue", "frame: beam brick 1x6 with holes"),
        PartType("3702", 11, 2.85, "catalogue", "frame: beam brick 1x8 with holes"),
        PartType("3703", 11, 5.87, "catalogue", "long chassis rail: beam brick 1x16 with holes"),
        PartType("32073", 86, 0.66, "catalogue", "axle: axle 5"),
        PartType("3706", 11, 0.86, "catalogue", "axle: axle 6"),
        PartType("3707", 11, 1.18, "catalogue", "axle: axle 8"),
        PartType("3649", 86, 3.76, "catalogue", "gear 40 tooth"),
        PartType("32270", 86, 0.58, "catalogue", "gear 12 tooth double bevel"),
        PartType("32269", 2, 1.4, "catalogue", "gear 20 tooth double bevel"),
        PartType("32498", 11, 3.5, "catalogue", "gear 36 tooth double bevel"),
        PartType("2780", 11, 0.2, "catalogue", "pin with friction ridges"),
        PartType("32020c01", 86, 33.0, "catalogue", "wheel 62.4 x 20 mm with rubber tyre (32020 / 32019)"),
        PartType("99499c01", 86, 45.0, "catalogue (incl. cable)", "L-motor"),
        PartType("58121c01", 86, 72.0, "catalogue (incl. cable)", "XL-motor"),
    )
}
"""New part types (none of them replaces a :data:`PART_TYPES` entry); merged into :data:`PART_TYPES` below."""

PART_TYPES.update({k: v for k, v in EXTENDED_PART_TYPES.items() if k not in PART_TYPES})

TYRE_FRICTION: dict[str, dict] = {
    "32020c01": {"mu": 1.38, "surface": "plywood", "source": "public measurements: wheel grip test"},
}
"""Measured sliding friction of rubber-tyred wheels (public measurements: a driven 4-wheel car on a tilting plywood
board, wheels slipping, mu = tan(angle)). Hard ABS parts (every other part) keep the ABS material."""

MOTOR_LINES: dict[str, dict] = {
    "99499c01": {
        "no_load_rpm": 390.0,
        "stall_torque_nm": 0.18,
        "source": "public measurements, 9 V (L-motor); with a battery box: 375 rpm, 0.22 N m",
    },
    "58121c01": {
        "no_load_rpm": 220.0,
        "stall_torque_nm": 0.40,
        "source": "public measurements, 9 V (XL-motor); with a battery box: 220 rpm, 0.40 N m",
    },
}
"""Linear DC-motor lines (tau = tau_stall (1 - w / w0)) of the extra motors. The M-motor keeps the line in
:mod:`robobuilder.core.car_design` (public measurements: 400 rpm, 0.15 N m)."""

# ----------------------------------------------------------------------------------------------------------------
# Liftarms, long axles and the worm gear (masses are catalogue weights)
# ----------------------------------------------------------------------------------------------------------------

LIFTARM_PART_TYPES: dict[str, PartType] = {
    p.catalogue_id: p
    for p in (
        PartType("32524", 11, 1.74, "catalogue", "liftarm thick 1x7"),
        PartType("40490", 11, 2.59, "catalogue", "liftarm thick 1x9"),
        PartType("32278", 11, 4.0, "catalogue", "liftarm thick 1x15"),
        PartType("4716", 86, 0.6, "catalogue", "worm gear (2L, single start)"),
    )
}
"""More part types (none replaces an existing entry); merged into :data:`PART_TYPES` below."""

PART_TYPES.update({k: v for k, v in LIFTARM_PART_TYPES.items() if k not in PART_TYPES})

# ----------------------------------------------------------------------------------------------------------------
# The rest of the owned inventory. Masses are catalogue unit weights; colours are the inventory colour with the most
# pieces (``4185t`` is the wedge-belt wheel with its tyre, one simulated part). Bench geometry: :mod:`.parts`.
# ----------------------------------------------------------------------------------------------------------------
AA_CELL_MASS_G = 23.0
"""Typical alkaline AA cell [g]."""

INVENTORY_PART_TYPES: dict[str, PartType] = {
    p.catalogue_id: p
    for p in (
        # -- electrics --
        PartType("59510c01", 86, 53.5 + 6 * AA_CELL_MASS_G, "catalogue 53.5 g + 6 AA",
                 "AA battery box (4 x 11 x 7)"),
        PartType("58123c01", 86, 20.6, "catalogue (incl. cable)", "IR receiver"),
        # -- wheels --
        PartType("56145c01", 11, 15.1, "catalogue", "wheel 30.4 x 20 rim with 43.2 x 22 ZR tyre"),
        PartType("55982c01", 86, 8.37, "catalogue", "wheel 18 x 14 rim with 30.4 x 14 tyre"),
        PartType("55423c01", 11, 1.1, "catalogue", "RC train wheel with rubber friction band"),
        PartType("4185t", 3, 0.97 + 0.75, "catalogue 4185 + 2815",
                 "wedge-belt wheel 4185 with its rubber tyre 2815 (counts one of each)"),
        # -- beam bricks --
        PartType("2730", 85, 3.67, "catalogue", "beam brick 1x10 with holes"),
        PartType("32018", 86, 4.92, "catalogue", "beam brick 1x14 with holes"),
        PartType("3700", 86, 0.82, "catalogue", "beam brick 1x2 with hole"),
        PartType("32000", 86, 0.73, "catalogue", "beam brick 1x2 with 2 holes"),
        PartType("6541", 86, 0.38, "catalogue", "beam brick 1x1 with hole"),
        # -- liftarms --
        PartType("32523", 86, 0.7, "catalogue", "liftarm thick 1x3"),
        PartType("32316", 86, 1.25, "catalogue", "liftarm thick 1x5"),
        PartType("32525", 86, 2.8, "catalogue", "liftarm thick 1x11"),
        PartType("41239", 86, 3.3, "catalogue", "liftarm thick 1x13"),
        # -- pins --
        PartType("3673", 86, 0.16, "catalogue", "pin without friction (pivot)"),
        PartType("6558", 7, 0.37, "catalogue", "pin 3L with friction"),
        PartType("32054", 86, 0.33, "catalogue", "pin 3L with friction and stop bush"),
        PartType("43093", 7, 0.26, "catalogue", "axle-pin 1L+1L with friction"),
        PartType("65249", 86, 0.3, "catalogue", "axle-pin 1L pin (no friction) + 2L axle"),
        PartType("15100", 153, 0.4, "catalogue", "pin 1L with friction and perpendicular pin hole"),
        PartType("87082", 86, 0.5, "catalogue", "pin 3L with centre pin hole"),
        # -- axles --
        PartType("4519", 86, 0.43, "catalogue", "axle 3"),
        PartType("60485", 86, 1.3, "catalogue", "axle 9"),
        PartType("23948", 86, 1.65, "catalogue", "axle 11"),
        PartType("50451", 11, 2.37, "catalogue", "axle 16"),
        PartType("24316", 85, 0.45, "catalogue", "axle 3 with stop"),
        PartType("15462", 85, 0.73, "catalogue", "axle 5 with stop"),
        PartType("87083", 85, 0.59, "catalogue", "axle 4 with stop"),
        PartType("6587", 85, 0.48, "catalogue", "axle 3 with stud"),
        PartType("4265c", 1, 0.1, "catalogue", "bush 1/2 smooth"),
        # -- gears --
        PartType("6589", 86, 0.29, "catalogue", "gear 12 tooth bevel"),
        PartType("32198", 86, 0.75, "catalogue", "gear 20 tooth bevel"),
        PartType("69778", 86, 0.5, "catalogue", "gear 12 tooth (spur, narrow teeth)"),
        PartType("18946", 86, 0.84, "catalogue", "gear 16 tooth with clutch on both sides (round bore)"),
        PartType("6542b", 86, 0.7, "catalogue", "gear 16 tooth with clutch, smooth centre (round bore)"),
        PartType("4019", 9, 0.7, "catalogue", "gear 16 tooth (axle hole, open sides)"),
        # -- bent / shaped liftarms --
        PartType("32140", 86, 1.43, "catalogue", "liftarm L 2x4 thick"),
        PartType("32526", 86, 1.77, "catalogue", "liftarm L 3x5 thick"),
        PartType("32348", 86, 2.0, "catalogue", "liftarm bent 1x7 (4-4) thick"),
        PartType("32271", 86, 2.63, "catalogue", "liftarm bent 1x9 (7-3) thick"),
        PartType("6629", 86, 2.6, "catalogue", "liftarm bent 1x9 (6-4) thick"),
        PartType("60484", 86, 1.19, "catalogue", "liftarm T 3x3 thick"),
        PartType("32056", 86, 0.73, "catalogue", "liftarm L 3x3 thin"),
        PartType("32009", 86, 3.46, "catalogue", "liftarm double bent 1x11.5 thick"),
        # -- connectors --
        PartType("6536", 86, 0.39, "catalogue", "axle and pin connector perpendicular"),
        PartType("32184", 86, 0.64, "catalogue", "axle and pin connector perpendicular 3L"),
        PartType("42003", 86, 0.77, "catalogue", "axle and pin connector perpendicular 3L, 2 pin holes"),
        PartType("32013", 86, 0.46, "catalogue", "angle connector #1"),
        PartType("32015", 86, 0.69, "catalogue", "angle connector #5 (112.5 deg)"),
        PartType("32034", 86, 0.68, "catalogue", "angle connector #2 (180 deg)"),
        PartType("48989", 86, 1.22, "catalogue", "pin connector perpendicular 3L with 4 pins"),
        # -- plates and bricks --
        PartType("3001", 11, 2.32, "catalogue", "brick 2x4"),
        PartType("3020", 86, 1.2, "catalogue", "plate 2x4"),
        PartType("3021", 86, 0.93, "catalogue", "plate 2x3"),
        PartType("3022", 86, 0.64, "catalogue", "plate 2x2"),
        PartType("3023", 86, 0.36, "catalogue", "plate 1x2"),
        PartType("3623", 86, 0.53, "catalogue", "plate 1x3"),
        PartType("3795", 86, 1.74, "catalogue", "plate 2x6"),
        PartType("3034", 86, 2.27, "catalogue", "plate 2x8"),
        PartType("4477", 86, 1.61, "catalogue", "plate 1x10"),
        PartType("3028", 86, 9.47, "catalogue", "plate 6x12"),
        PartType("3030", 86, 5.55, "catalogue", "plate 4x10"),
        PartType("3031", 86, 2.22, "catalogue", "plate 4x4"),
        PartType("3033", 86, 7.95, "catalogue", "plate 6x10"),
        PartType("3035", 86, 4.7, "catalogue", "plate 4x8"),
        PartType("3036", 86, 6.4, "catalogue", "plate 6x8"),
        PartType("3958", 86, 4.71, "catalogue", "plate 6x6"),
        PartType("41539", 86, 9.4, "catalogue", "plate 8x8"),
        PartType("92438", 86, 17.0, "catalogue", "plate 8x16"),
        # -- servo --
        PartType("99498c01", 86, 44.0, "catalogue (incl. cable)", "servo motor"),
        # -- frames and the tread sprocket --
        PartType("64179", 86, 5.3, "catalogue", "liftarm frame thick 5x7 open centre"),
        PartType("64178", 86, 7.0, "catalogue", "liftarm frame thick 5x11 open centre"),
        PartType("57520", 66, 1.63, "catalogue", "tread sprocket wheel small (25.4)"),
        # -- gear racks (core.racks) --
        PartType("3743", 11, 0.79, "catalogue", "gear rack 1x4"),
        PartType("6630", 9, 2.0, "catalogue", "gear rack 1x8 with holes"),
        PartType("87761", 11, 1.8, "catalogue", "gear rack 1x7 with axle and pin holes"),
        # -- knob / bevel gears, sprocket, connectors, cam, catches, gearbox, steering arm (bench geometry:
        # core.parts / core.gear_rules) --
        PartType("57519", 3, 5.1, "catalogue", "tread sprocket wheel large (40.4)"),
        PartType("32072", 3, 0.87, "catalogue", "gear knob cog wheel (4 knobs, axle hole)"),
        PartType("69761", 3, 2.2, "catalogue", "gear 22 tooth bevel (half, pin hole)"),
        PartType("69762", 3, 1.2, "catalogue", "gear 14 tooth bevel thick (half)"),
        PartType("57585", 86, 0.65, "catalogue", "axle connector hub with 3 axles"),
        PartType("55615", 86, 1.9, "catalogue", "pin connector perpendicular 3x3 bent with 4 pins"),
        PartType("6575", 3, 0.7, "catalogue", "cam"),
        PartType("6641", 5, 0.5, "catalogue", "changeover catch"),
        PartType("35188", 4, 1.08, "catalogue", "changeover rotary catch"),
        PartType("6588", 9, 4.5, "catalogue", "gearbox 2x4x3 1/3 (worm gearbox housing)"),
        PartType("57515", 85, 1.52, "catalogue", "steering arm 6x2 with tow ball socket"),
        # -- shock absorbers (a cylinder and a rod body in the simulator), CV joint pair, differential and housing,
        # pullback motor, train motor (bench geometry: core.parts / core.mechanisms) --
        PartType("731c04", 3, 2.1, "catalogue",
                 "shock absorber 6.5L, hard spring (design part = the whole shock)"),
        PartType("2909c03", 11, 4.0, "catalogue",
                 "shock absorber 9.5L, soft spring (design part = the whole shock)"),
        PartType("32494", 86, 0.55, "catalogue", "steering CV joint ball (axle driver)"),
        PartType("92906", 85, 0.45, "catalogue", "steering CV joint cup with 2L axle"),
        PartType("62821b", 85, 2.8, "catalogue", "differential, one-piece, 28T bevel ring"),
        PartType("65414", 86, 2.31, "catalogue", "differential housing (new style, no ring gear)"),
        PartType("12787c01", 85, 31.0, "catalogue", "Pullback motor 6 x 5 x 3 (spring motor)"),
        PartType("87574c01", 11, 57.1, "catalogue (incl. cable)", "train motor"),
    )
}
"""Inventory additions (none replaces an existing entry); merged into :data:`PART_TYPES` below."""

PART_TYPES.update({k: v for k, v in INVENTORY_PART_TYPES.items() if k not in PART_TYPES})
INVENTORY_TYRE_FRICTION: dict[str, dict] = {
    "56145c01": {"mu": 1.19, "surface": "plywood", "source": "public measurements: wheel grip test"},
    "55982c01": {"mu": 1.0, "surface": "plywood",
                 "source": "estimate (no published test of this tyre): between the measured 24 mm (0.65) and "
                           "43 mm, 14 mm tread (1.15) tyres"},
    "4185t": {"mu": 0.37, "surface": "plywood",
              "source": "public measurements: traction test (wedge-belt wheel 4185 + tyre 2815, pulling force / weight, plywood)"},
}
"""Tyre friction of the inventory wheels (measured where published, else an estimate; same use as TYRE_FRICTION)."""

INVENTORY_MOTOR_LINES: dict[str, dict] = {
    "99498c01": {
        "no_load_rpm": 125.0,
        "stall_torque_nm": 0.13,
        "source": "public measurements: about 0.12 s per 90 deg of motion (~125 rpm), back-driven above ~12.8 N cm at "
                  "9 V (stall ~0.13 N m); 7 positions each side of neutral (+-90 deg)",
    },
    "87574c01": {
        "no_load_rpm": 1900.0,
        "stall_torque_nm": 0.036,
        "source": "public measurements at 9 V, at the wheel axles (both axles driven through internal gears): "
                  "1900 rpm no load, 3.6 N cm stall",
    },
    "12787c01": {
        "no_load_rpm": 600.0,
        "stall_torque_nm": 0.05,
        "stored_turns": 10.0,
        "source": "pullback (spring) motor 12787c01, estimates (no published test): 0.05 N m at full wind, falling "
                  "linearly to 0 over 10 output turns; no-load speed cap 600 rpm. Wound by hand before the run, "
                  "released at t = 0; not IR controlled (core.mechanisms)",
    },
}
"""Motor lines of the inventory additions (the servo and the train motor: public measurements; the pullback motor:
estimates, ``stored_turns``: output turns of a full wind)."""

MOTOR_LEAD_MM: dict[str, float] = {
    "58120c01": 224.0, "99499c01": 200.0, "58121c01": 200.0, "99498c01": 200.0,
    "87574c01": 224.0,  # the train motor's lead is the same cable as the M-motor's
}
"""Fixed motor lead length [mm] (motor body to the power plug; M-motor: cable path 224 mm; L / XL / servo:
~20 cm). No extension cables are in the inventory (``design.check_real_electrics``)."""
RECEIVER_LEAD_MM = 150.0
"""IR receiver lead to the battery box [mm] (estimate; the receiver usually sits on or next to the box)."""

BOM_COMPONENTS: dict[str, tuple[str, ...]] = {"4185t": ("4185", "2815")}
"""Simulated parts that are an assembly of several inventory items (counted per item in the bill of materials)."""
