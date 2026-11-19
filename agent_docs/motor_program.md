# Motors, wiring and the motor program

## The motors you own

Speeds and torques are the nominal ratings; the simulator uses fitted values (`simulator.md`).

| part | motor | no-load speed | stall torque | notes |
|---|---|---|---|---|
| 58120c01 | M motor (×2) | 400 rpm | 0.15 N m | 2 × 6 anti-studs underneath (no studs on top) |
| 99499c01 | L motor (×2) | 390 rpm | 0.18 N m | studless: pin it on |
| 58121c01 | XL motor (×2) | 220 rpm | 0.40 N m | studless: pin it on |
| 99498c01 | servo (×2) | 125 rpm | 0.10 N m | position motor: ±90°; drives to its angle, then holds only by its gearbox friction |
| 12787c01 | pullback motor (×2) | 600 rpm | 0.05 N m | not electric: wound by hand before the run, released at t = 0; torque falls to 0 over 10 output turns |

- A motor follows its torque–speed line, scaled by the level: low levels lose torque more than speed, and a heavy drivetrain may not start at level 1.
- **The pullback motor** is a spring motor. The owner winds it by hand before the run, as far as your design asks (`"pullback": [{"motor": "<name>", "wind_turns": 0…10, "sense": 1 or -1}]`; default fully wound, turning the way that rolls the wheels forward), and its ratchet holds the spring until the start (t = 0), when it releases.
  - Its stored energy can power any mechanism you connect to its output, not only wheels.
  - It is not driven by the program: commands may not name it, and `"all"` skips it.
  - It needs no wiring.
  - It freewheels when turned faster than it drives.
- Gearing trades speed for force. For example, the ratio of an 8T pinion driving a 24T gear is 1 : 3.

## How the vehicle is driven

The real vehicle is driven **open loop** by timed commands, as from a IR remote. A laptop sends them through an IR transmitter, and nobody steers. The design's `"motor_program"` is the list of those commands. The simulator executes the same list.

```json
"motor_program": [
  {"t": 0.0, "motor": "all", "level": 7, "note": "drive forward, full speed"},
  {"t": 1.2, "motor": "arm_motor", "level": -4, "note": "lower the arm at 4/7 speed"},
  {"after": 1, "delay": 0.8, "motor": "arm_motor", "level": "brake", "note": "0.8 s later: hold the arm"},
  {"t": 2.5, "motor": "drive_motor", "level": 3},
  {"t": 6.0, "motor": "all", "level": "brake", "note": "stop in the goal and hold"}
]
```

**Each command has three parts:**
- **`"motor"`:** the name of a motor part in your design, or `"all"`.
- **`"level"`:**
  - **an integer from −7 to 7** sets the speed: level k drives the motor at level k of 7 (`simulator.md` gives the torque and speed it then has). For the motor that drives the wheels, + rolls the vehicle forward. For any other motor, + is the motor's own positive sense.
  - **`0`** cuts the power: the motor floats and coasts to a stop.
  - **`"brake"`** actively resists turning and holds against moderate loads.
  - **Servo:** level k is an angle, k/7 × 90° from centre (−90° … +90°); `0` and `"brake"` both send it to the centre. About 0.12 s after the command it starts to turn, at about 0.12 s per 90°, with up to 0.10 N·m. Once at its angle (or after 0.25 s blocked) it stops driving: only its gearbox friction (about 0.025 N·m) holds the angle, so a larger load turns it away until the next command.
- **When it fires** (exactly one of):
  - `"t": s`: s seconds after the start;
  - `"after": i`: when command number i (0-based) has fired, plus an optional `"delay": s`.
- **`"note"`** (optional): free text for yourself.

**Timing:**
- Commands are at least 0.1 s apart (the remote cannot send faster). Each one takes effect **35 ms** after it is sent (IR latency).
- At most 200 commands: drive, stop, reverse, raise an arm, shift a weight, drive again, as the level needs.
- With no program, every motor runs at +7 from the start (a servo goes to +90°; a pullback motor runs on its spring). With a program, motors start stopped until a command turns them on.
- To finish, stop in the goal (`"brake"` or `0` at the right time). Reaching the goal is what counts; for the next 5 s the vehicle must stay upright and in one piece while it is still in it (`rules.md`).

**Not available:** position, sensor or angle triggers and closed-loop control; everything is decided by time.

## Wiring (the validator works it out and checks it)

- **IR receivers:** two are owned (58123c01, 20.6 g, 4 × 4 anti-studs underneath), and at least one must be on board. Each has two outputs, A and B, on its own channel. Each motor whose level changes during the run needs its own output, so **one receiver sequences up to 2 motors, and two receivers up to 4**.
- **Sharing an output:** two motors may share one output (their plugs stack) only if they must turn the same way at the same speed for the whole run, seen from each motor's output face. A stacked plug cannot be turned round, so motors mounted mirror-image (for example a left and a right wheel motor) need two outputs.
- **Box-direct motors:** a motor that runs at a constant full ±7 from start to end can plug straight into a battery box instead of the receiver. A box has no speed control.
- **Battery boxes:**
  - 2 AAA boxes (87513c01, 109 g, studs on top, anti-studs underneath);
  - 2 AA boxes (59510c01, 191.5 g, studless: pin it on);
  - at most 3 motors per box.
- **Cables and plugs (checked by the validator):**
  - **Where each lead goes:**
    - every motor's lead plugs onto a receiver output (or, box-direct, onto a battery box's connector);
    - every receiver's lead plugs onto a battery box's connector.
  - **The connectors:** power plugs are 16 × 16 mm and stack, 6.4 mm per plug.
    - AAA box: its connector is the pad on top at box-local x = 8…24 mm, y = −8…8 mm. Its top has studs only along the two long edges and at the −x end; the middle strip holds the switch and the connector.
    - AA box: its connector is the pad on top at box-local x = 8…24 mm, y = −8…8 mm. The switch knob is on the same face, at x ≈ −8 mm.
    - Receiver: its outputs A and B are the two pads on its low front step.
  - **Room for the plugs:** each battery box connector must stay **uncovered**. Nothing may be built over it, and the stack of plugs on it needs a clear 16 × 16 mm column, plus room on one side for the plug's cable. In particular, do not put the receiver (or anything else) over the box's connector: put it beside it.
  - **Lead lengths** (no extension cables are owned): the lead runs from where it leaves its part (the back of a motor, the front of the receiver) to its plug. The straight distance + 20 mm for the bends must fit within the lead:
    - M motor: 224 mm;
    - L, XL motors and servo: 200 mm;
    - receiver: about 150 mm.

The simulation result lists the commands as they were executed (`motor_program_log`).
