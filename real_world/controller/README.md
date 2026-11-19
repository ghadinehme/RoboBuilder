# RoboBuilder controller

A browser page for the real-world tests: it plays each design's timed motor program through the USB IR bridge
(`../firmware/ir_bridge`) to the robot's IR receivers, films every try, and keeps a log of the results. It sends the
same commands as `python -m robobuilder.real` (a 3-2-1 countdown, the commands at their simulated times, a refresh
every 0.3 s, every output floated at the end of the run window). It needs Chrome or Edge (Web Serial) and no install.

```
index.html               the controller (one page, no dependencies)
experiments/             the designs it lists: index.js names the files; reference-L1.js is an example
launch.command / launch.sh / launch.bat         open the page (macOS / Linux / Windows)
flash_uno.command / flash_uno.sh / flash_uno.bat flash the IR bridge firmware onto an Arduino Uno
```

## Start

1. **Wire and plug in the IR bridge** (an Arduino Uno with the IR emitter on pin 3; `../README.md`, *IR emitter*).
2. **Open the controller.** Run the launcher for your system: it serves the folder on `localhost:8765` and opens it in
   Chrome or Edge. Opening `index.html` directly in Chrome or Edge also works. On macOS, the first time, right-click
   `launch.command` and choose **Open**; on Linux your user must be in the `dialout` group.
3. **Connect.** Click **Connect IR bridge** and pick the board's port (`ttyACM…`, `usbmodem…`, `COM…`). The dot turns
   green when the bridge answers.

## Load designs

The page lists the experiment files in `experiments/` (one experiment = a set of designs). Export them with
`scripts/export_controller.py`, which builds each schedule with `robobuilder.real`:

```bash
python scripts/export_controller.py reference --levels 1          # the reference agents' passing L1 designs + All-in-one robots
python scripts/export_controller.py run runs/my-model --levels 1,2,3   # the passing designs of your own run
python scripts/export_controller.py design my_design.json ramp 1  # one design (bench "all": an All-in-one design)
```

Each call writes `experiments/<name>.js` and adds it to `experiments/index.js`; reload the page. **Add an experiment
file** (top right of the Run tab) adds a single file in this browser only.

## Run a design

1. **Pick** an experiment, an agent and a level. A cell shows the simulated time to the goal; the squares under it are
   the real tries logged so far (green pass, red fail, amber partial). All-in-one robots have one cell per course;
   a dashed cell did not pass in simulation (it can still be run).
2. **Set up the robot** from the run card: where its front goes relative to the obstacle's start line, the wiring
   table (which motor plugs into which receiver channel and output, A red, B blue; set each receiver's channel switch
   as listed; a motor marked "battery box directly" is switched on at GO), the timed IR program and the agent's notes.
3. **Play.** **▶ Play** counts down 3-2-1 and runs the program. **■ Stop**, **STOP ALL** or the space bar stops at once.
   Keep the tab in front while a design runs (browsers slow down timers in background tabs).
   - **Speed scale**: real motor speed divided by the simulated one (1.00 by default); every command time is divided
     by it, e.g. 0.9 with weak batteries.
   - **Flip 1A**, ...: reverses an output whose motor turns the wrong way in a first test (remembered).
4. **Log the try.** Choose **Pass**, **Fail** or **Partial**, check the time to the goal (pre-filled from the run
   clock), the failure kind, the video and notes, then **Save try**. Up to 3 tries per design; reset the robot and the
   course between tries and change nothing on the robot or its program.

**Manual control** drives single receiver outputs by hand, for checking the wiring.

## Camera

The camera box (bottom right) shows the live picture on every tab.

1. Pick the camera in its list (Chrome asks once for permission), the **Quality** (720p to 4K) and, if wanted,
   **Record sound**.
2. Choose the **Video folder** once (Chrome asks for write permission once per session).
3. **Record every run** (on by default) records each run from the last second of the countdown to 1.5 s after the
   commands stop; **● Record** records by hand. After each recording the clip plays back: **Y** keeps it, **N**
   deletes it. Kept videos are saved as `<folder>/<experiment>/<course>/L<level>/<agent>_try_<k>.mp4` (All-in-one:
   `<experiment>/all_L1/<course>/...`) and the path goes into the next logged try.
4. **Place the camera** as the simulator's overview camera: fixed, beside the course, seeing the start, the obstacle
   and the goal. To line it up, click **picture…** and load a frame of the design's simulated overview video
   (`robobuilder simulate <design> <course> <level> --video`), tick **Overlay**, set its opacity, and move the camera
   until the course edges match; **Preview zoom** enlarges the live picture (the recording stays full frame) and ⤢
   enlarges the box.

## Results

The **Trial results** tab lists every try of an experiment, with a summary per agent. **Export JSON** (or CSV) after
each session and keep the file with the videos; **Import results** merges a file back in (the same try is never
counted twice). The log lives in this browser's storage, so export regularly.

## Flash the firmware

If the bridge does not answer, run `flash_uno.command` (macOS, Homebrew), `flash_uno.sh` (Linux) or `flash_uno.bat`
(Windows): they install `arduino-cli`, the Uno core and the IRremote library and flash `../firmware/ir_bridge`. Or open
`../firmware/ir_bridge/ir_bridge.ino` in the Arduino IDE, install "IRremote" (v4, by Armin Joachimsmeyer), choose
the board and **Upload**.

Serial protocol (115200 baud, one line per command; the bridge answers `OK ...` or `ERR ...`):

| Command | Meaning |
|---|---|
| `?` | ping (answer `OK ir-bridge 1`) |
| `P <ch> <A\|B> <-7..7\|brake>` | set one output (latched) |
| `C <ch> <a> <b>` | set both outputs of a channel; times out after about 1 s unless repeated |
| `N <1-10>` | number of IR repeats per message |
