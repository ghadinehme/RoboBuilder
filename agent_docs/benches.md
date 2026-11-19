# The 10 benches

The benchmark has 10 obstacle benches with 3 levels each, from easy (L1) to hard (L3). Your task is one level; its exact geometry, start, goal, lane and time limit are in `task.json` (lengths in metres there). Every course is built from real bricks and a few printed parts, at the dimensions below.

## ramp

Drive up a sharp ramp (a 460 mm foam-core board, the same board as the floor) onto a raised brick plateau. The board hangs from the plateau edge on a hinge along its top edge and its foot only rests on the floor, so it can lift and swing.

| level | course | lane width | time limit |
|---|---|---|---|
| L1 | sharp ramp 30.02 deg (a 460 mm foam-core board) up to a brick plateau 233.6 mm high | 304 mm | 36.7 s |
| L2 | sharp ramp 45.86 deg (a 460 mm foam-core board) up to a brick plateau 332.8 mm high | 304 mm | 41.6 s |
| L3 | sharp ramp 62.31 deg (a 460 mm foam-core board) up to a brick plateau 409.6 mm high | 304 mm | 45.5 s |

## gap

Cross a gap between two raised brick decks (99.2 mm deep). Touching the floor of the gap fails.

| level | course | lane width | time limit |
|---|---|---|---|
| L1 | gap 152 mm (19 studs) between two brick decks, 99.2 mm deep | 304 mm | 20 s |
| L2 | gap 336 mm (42 studs) between two brick decks, 99.2 mm deep | 304 mm | 28.4 s |
| L3 | gap 752 mm (94 studs) between two brick decks, 99.2 mm deep | 304 mm | 38.8 s |

## bridge

Drive along a narrow printed plank, 640 mm long, over a 99.2 mm drop. Touching the floor below fails.

| level | course | lane width | time limit |
|---|---|---|---|
| L1 | printed plank 40 mm wide, 640 mm long over a 99.2 mm drop | 304 mm | 31 s |
| L2 | printed plank 24 mm wide, 640 mm long over a 99.2 mm drop | 304 mm | 31 s |
| L3 | printed plank 8 mm wide, 640 mm long over a 99.2 mm drop | 304 mm | 31 s |

## rope

Travel along a 3 mm cord from one deck to another, higher deck. Touching the table below fails.

| level | course | lane width | time limit |
|---|---|---|---|
| L1 | rope 600 mm span between two brick decks, 0.00 deg incline (goal deck 0.0 mm higher), 12.5 mm sag, 3.0 mm cord | 200 mm | 37.2 s |
| L2 | rope 599 mm span between two brick decks, 10.00 deg incline (goal deck 105.6 mm higher), 12.5 mm sag, 3.0 mm cord | 200 mm | 37.2 s |
| L3 | rope 598 mm span between two brick decks, 20.00 deg incline (goal deck 217.6 mm higher), 12.5 mm sag, 3.0 mm cord | 200 mm | 37.2 s |

## steps

Climb three brick steps.

| level | course | lane width | time limit |
|---|---|---|---|
| L1 | 3 brick steps of 28.8 mm, 72 mm treads | 304 mm | 64.3 s |
| L2 | 3 brick steps of 57.6 mm, 136 mm treads | 304 mm | 68.6 s |
| L3 | 3 brick steps of 105.6 mm, 256 mm treads | 304 mm | 75.8 s |

## bumps

Cross a field of rods on two printed bump plates. The rods are 40–220 mm long and lie at different places across the lane, as printed (`task.json` gives each one); some sit side by side or overlap. Cross over them, not around (the wheels stay within the span of the rods, ±5 mm, while over the field; another part may step up to 20 mm outside the plates; the chassis stays over them). Crossed when half the vehicle is past the end of the bump line (`rules.md`).

| level | course | lane width | time limit |
|---|---|---|---|
| L1 | rough terrain: 10 rods up to 35.0 mm high over 0.512 m on 2 printed bump plates (32 x 32 studs) | 256 mm | 30 s |
| L2 | rough terrain: 14 rods up to 55.0 mm high over 0.512 m on 2 printed bump plates (32 x 32 studs) | 256 mm | 30 s |
| L3 | rough terrain: 18 rods up to 80.0 mm high over 0.512 m on 2 printed bump plates (32 x 32 studs) | 256 mm | 30 s |

## seesaw

Cross from the start platform to the goal platform over a printed seesaw plank. The plank turns freely on its axle; at the start it rests tipped with its far end down on the far ledge and its near end raised above the start platform. No part of the vehicle may touch the floor between the platforms: it must cross on the plank.

| level | course | lane width | time limit |
|---|---|---|---|
| L1 | printed seesaw plank 64 x 240 mm on a brick axle 50.6 mm above the floor, tilted 14.54 deg with its far end down: its near end is raised 62 mm above the start platform | 304 mm | 30 s |
| L2 | printed seesaw plank 64 x 240 mm on a brick axle 79.4 mm above the floor, tilted 29.31 deg with its far end down: its near end is raised 118 mm above the start platform | 304 mm | 30 s |
| L3 | printed seesaw plank 64 x 240 mm on a brick axle 108.2 mm above the floor, tilted 46.59 deg with its far end down: its near end is raised 173 mm above the start platform | 304 mm | 30 s |

## gap-drop

Cross a 152 mm gap onto a lower landing deck. Touching the floor of the gap fails.

| level | course | lane width | time limit |
|---|---|---|---|
| L1 | gap 152 mm to a brick landing deck 48.0 mm lower | 304 mm | 30 s |
| L2 | gap 152 mm to a brick landing deck 128.0 mm lower | 304 mm | 30 s |
| L3 | gap 152 mm to a brick landing deck 336.0 mm lower | 304 mm | 30 s |

## wall

Get over a brick wall, one 2x4 brick thick. Cross over the top: any part leaving the lane fails.

| level | course | lane width | time limit |
|---|---|---|---|
| L1 | climb over a brick wall 4 bricks = 38.4 mm high, one 2x4 brick (16 mm) thick, 256 mm wide | 256 mm | 34 s |
| L2 | climb over a brick wall 16 bricks = 153.6 mm high, one 2x4 brick (16 mm) thick, 256 mm wide | 256 mm | 45 s |
| L3 | climb over a brick wall 64 bricks = 614.4 mm high, one 2x4 brick (16 mm) thick, 256 mm wide | 256 mm | 91 s |

## U-turn

Drive off the end of one raised lane onto a plate tilted upward, turn around on it, and come back along the second, parallel lane. It is crossed once the whole vehicle is on the second lane, anywhere along it. Touching the floor between or beside the lanes fails.

| level | course | lane width | time limit |
|---|---|---|---|
| L1 | U-turn on a brick plate (4 baseplates) tilted 32.45 deg up (turn radius 152 mm) between two 200 mm brick lanes 104 mm apart | 304 mm | 67 s |
| L2 | U-turn on a brick plate (4 baseplates) tilted 35.46 deg up (turn radius 152 mm) between two 176 mm brick lanes 128 mm apart | 304 mm | 67 s |
| L3 | U-turn on a brick plate (4 baseplates) tilted 37.97 deg up (turn radius 152 mm) between two 152 mm brick lanes 152 mm apart | 304 mm | 67 s |
