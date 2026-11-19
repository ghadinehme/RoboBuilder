# Real-world tests

The benchmark score is computed in the simulator. This folder is for building a design and running it on a real
course, as in the paper: every design that passed in simulation was built by hand from the owned parts and run, with
its program unchanged, on a physical replica of its course, filmed in up to three tries; it passes for real if one try
reaches the goal and stays there upright for 5 s.

```
course_parts.zip          STLs of the printed course parts (bridge planks, rope edge devices, bump plates, seesaw
                          plank, U-turn plate stand and joiners) and two fit coupons
firmware/ir_bridge/       the USB-serial IR bridge (Arduino Uno / Nano / ESP32) that drives the robots' IR receivers
controller/               a browser controller (Chrome / Edge): runs designs through the bridge, films and logs each try
inventory.md              every part with its catalogue number and the pieces owned, to buy the parts
```

and in the package: `python -m robobuilder.real` (parts list, wiring and the timed IR program of a design, and the
player), `scripts/export_printed_part.py` (an agent's printed part as a real print), `scripts/export_controller.py`
(designs for the controller).

## 1. Build the courses

Every course is a simulated twin of a simple real build: 10 in baseplates (32 x 32 studs, 256 mm), 2x2-brick columns,
decks of two crossed plate layers topped with tiles, 3.2 mm floor tiles, and a few printed parts. Heights are whole
plates (3.2 mm) or bricks (9.6 mm); widths and positions are on the 8 mm stud grid; lanes are 304 mm (38 studs) wide.
The exact geometry of each level, in metres, is in its task file:

```bash
robobuilder task bumps 2 > bumps_L2.json     # shapes (boxes and capsules with pose and size), start, goal, time limit
```

`agent_docs/benches.md` lists every level's dimensions. Floor courses (ramp, steps, bumps, seesaw, wall) have the
baseplates 3.2 mm below the floor surface (floor tiles on top). Raised courses (gap, bridge, gap-drop, U-turn) have
decks 99.2 mm (31 plates) above the baseplate sheet, which is the chasm floor: touching it fails. Every course starts
with a flat start board, 500 mm long (1000 mm on the gap).

The filmed courses replace the brick decks and floor tiles with boards of the same top height: 1/4 in MDF
plus 1/8 in hardboard or foam board (9.55 mm, against 9.6 mm in simulation), on printed or brick columns. The
ramp's board rests on a lab jack set to the level's height. Check heights against the task file either way.

| obstacle | build | printed parts (course_parts.zip, under print/) |
|---|---|---|
| ramp | a 460 x 304 mm foam-core board (4.8 mm), hinged with tape along its top edge to the edge of a brick plateau, its foot resting on the floor behind a 2-stud stop | none |
| gap | two brick decks, the gap a whole number of studs | none |
| bridge | a 640 mm plank of four 160 mm segments over a 99.2 mm drop between two decks; each segment end presses onto the stud of a 1x2 jumper plate on a hidden column (2x2 column of 9 bricks with two jumpers at x = 160, 320, 480 mm; a 1x2 column with one jumper at each deck edge); plank top flush with the decks | `bridge/bridge_plank_L<k>_w<width>.stl`, 4 per level |
| rope | two tables facing each other across the gap (a fixed table and a standing desk, whose height sets the level); one printed edge device clamped on each table edge carries the 3 mm cord on its saddle post; the cord is tensioned with the winch on the fixed table and knotted under the tie device on the desk | `rope/` (one winch body, drum, knob, crank, one tie device, two clamp screws) |
| steps | one step unit per level: two printed side frames of straight bars (rail, posts behind each riser, beams under each tread; bars plug together by the 3-digit code on their top face), 1/2 in foam-board treads and 3/16 in foam-board risers taped on, all 304 mm wide; the unit's shoes slide sideways onto four printed base rails taped to the floor at x = 20 and 180 mm (left rails with the end stops), so a level swap is one slide | `steps/L<k>/{left,right}/` (one frame per side; 9 / 11 / 16 bars per side at L1 / L2 / L3), `steps/base_rail_{left,right}.stl` (2 each, shared by all levels) |
| bumps | two printed bump plates (32 x 32 studs, 255.8 mm, one per baseplate), top flush with the floor; the rods are printed in place at their simulated positions. The filmed courses use the tiled version, each plate printed as four 128 mm tiles that fit a standard bed; the whole plates need a 256 mm bed | `bumps_tiles/L<k>/bump_plate_{1,2}_{near,far}_{left,right}.stl` (filmed), or `bumps/L<k>/bump_plate_{1,2}.stl` (whole plates) |
| seesaw | the printed plank on an axle 12 through its cross hole, two bushes beside it, the axle in the round holes of two beam bricks 1x2 on 2x2 columns 8 mm outside the plank's sides; platforms 28.8 mm high and 256 mm apart, ledges 22.4 mm high | `seesaw/seesaw_plank.stl` |
| gap-drop | a 152 mm gap from the start deck to a landing deck lower by a whole number of plates | none |
| wall | one layer of 2x4 bricks (16 mm thick), 256 mm across, n bricks high | none |
| U-turn | two board lanes 99.2 mm high on 24 printed columns and a tilted plate of four baseplates with tiles (512 x 512 mm) held by the printed stand: a hinge bar under its lower edge, three props on foot rails | `u_turn/` (24 lane columns, or all 24 on one plate; hinge bar end L, middle, end R; hinge posts L, R; 3 prop heads, legs, rails; 7 seam joiners 4x8 and one cap 4x4 join the four baseplates) |

Level-specific settings of the printed stands: the U-turn props go in rail hole 1 (L1), 3 (L2) or 5 (L3); the seesaw
axle column has 15 (L1), 24 (L2) or 33 (L3) plates under the beam brick. Check every course against its task file:
heights, the gap width and the tilt (a phone inclinometer on the plate or board, +-0.5 deg).

## 2. Print

PLA, 0.2 mm layers. Print each STL in the orientation it is saved in, without supports. The bump plates are 255.8 mm
square: they need a 256 mm bed, no brim and no skirt. Infill: bridge planks 15 %, bump plates 5 % (gyroid), seesaw
plank 20 %, step bars 30 %, rope devices and U-turn stand and columns 30 % with 3 to 4 walls (they carry load).

Fit coupons first: `fit_coupons/stud_fit_coupon.stl` (studs and sockets that press onto standard parts) and
`fit_coupons/baseplate_pin_coupon.stl` (pins into the underside holes of the baseplates, for the U-turn stand and
joiners). Printed studs come out about 0.2 mm small and holes about 0.1 mm small on a typical FDM printer.

**An agent's printed part** (Cross+Print designs, All-in-one robots): its CadQuery script and spec are in
`reference_results/printed_parts/<id>/` (or `printed/<id>/` of a task in your run). Export it for printing with the
interface sizes tuned on our printer (studs 5.0 mm, pin holes 5.0 mm, cross holes 5.0 x 2.0 mm, stud sockets
5.1 mm):

```bash
python scripts/export_printed_part.py reference_results/printed_parts/p3d_fea6c3a85a/cad_script.py prints/
```

The simulated part keeps the nominal sizes; only the clearances of the printed interfaces change.

## 3. Build the robot and wire it

```bash
python -m robobuilder.real reference_results/designs/opus-5.5/ramp_L1/cross.json ramp 1 --dry-run
```

prints the parts list (part ids and neutral names; the inventory is `robobuilder/core/data/inventory.json`), the
start gap, which motor plugs into which IR receiver channel and output (A red, B blue; motors that always run together
stack their plugs on one output; a motor at full power for the whole run may plug straight into a battery box,
switched on at GO), and the timed IR commands. Build from the design file: every part's pose is `pos_mm`, `yaw_deg`,
`spin_deg` in the design frame (x forward, y left, z up). Set each IR receiver's channel switch as printed. Place the
robot with its front `start_gap_mm` before the obstacle's start line (x = 0 in the task file), centred and pointing
along the course.

## 4. Run it

### IR emitter

One IR emitter controls every receiver: each command carries its channel, so set each receiver's channel switch as the
wiring table says and the bridge reaches all of them through the same LED. Parts: an Arduino Uno or Nano, one or two
940 nm IR LEDs, an NPN transistor (2N2222, PN2222 or BC337), a 1 kΩ resistor and a 47 Ω resistor per LED, a USB cable.

```
Arduino pin 3 ──[1 kΩ]──► base    NPN transistor (2N2222 / PN2222 / BC337)
                                  emitter ──► GND
5 V ──[47 Ω]──►|── IR LED 1 ──┐
5 V ──[47 Ω]──►|── IR LED 2 ──┴──► collector
        (anode → cathode; the cathode is the short leg / flat side)
```

- **Pin.** Pin 3 on the Uno and Nano (fixed by the timer the IRremote library uses); pin 4 on an ESP32.
- **Resistors.** Each LED has its own 47 Ω resistor: about 70 mA in short 38 kHz bursts, within a typical IR LED's
  pulse rating.
- **Second LED (optional).** Only for coverage: a receiver hears the LED only when its dark front window can see it.
  Put one LED behind the start and one above or past the goal pointing back along the course, for robots that turn
  or climb (U-turn, wall, seesaw, rope) or whose two receivers face different ways. It can sit up to about 2 m away
  on twisted pair. Both LEDs flash together; the firmware is unchanged.
- **Without a transistor**, one or two LEDs straight from pin 3 to GND through 220 Ω each also work (about 15 mA each,
  shorter range).
- **Check an LED** through a phone camera: it flickers purple while a command is sent.

### Play the program

Flash `firmware/ir_bridge/ir_bridge.ino` onto the board (Arduino IDE, the "IRremote" library v4 by Armin
Joachimsmeyer; or `controller/flash_uno.*`), point the IR LED at the course, and play the program from the command
line:

```bash
pip install pyserial
python -m robobuilder.real <design.json> <bench> <level> --port /dev/ttyACM0
```

After a 3-2-1 countdown it sends the same timed commands as in the simulation, refreshes them every 0.3 s, and floats
every output at the end of the run window. `--speed-scale 0.9` stretches every command time when the motors run slow
(weak batteries); `--flip 1A` reverses an output whose motor turns the wrong way in a first test. Use fresh batteries.

Or use the **controller** (`controller/`, see its README): a page for Chrome or Edge that plays the same schedules
over Web Serial, with the run card of each design (placement, wiring, program, agent's notes), camera recording with a
reference overlay, and a log of every try with JSON export. Export designs for it with
`python scripts/export_controller.py reference|run|design ...`.

## 5. Film and report

Film each try from one fixed camera beside the course that sees the start, the obstacle and the goal (as the
simulator's overview camera), 4K or 1080p at 30 fps, from just before the robot moves until it stops or crosses, with
no person or hand in frame during the run. Up to three tries per design; reset the robot and the course between tries
and change nothing on the robot or its program. A try **crosses** if the robot reaches the goal zone within the time
limit and stays there upright and in one piece for 5 s; the design passes for real if one try crosses.

Report one record per try, for example:

```json
{"design": "reference_results/designs/opus-5.5/ramp_L1/cross.json", "bench": "ramp", "level": 1, "try": 1,
 "video": "ramp_L1_try1.mp4", "crossed": true, "time_to_goal_s": 2.6,
 "notes": "anything changed or unusual: build fixes, speed scale, resets, parts that came loose"}
```
