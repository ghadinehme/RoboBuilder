"""RoboBuilder: a benchmark in which coding agents co-design a robot's hardware and program from standard parts, a
learned simulator, and real courses."""
import os

__version__ = "1.0.0"

BENCHMARK_ENV = {
    "RB_POWERED": "any",  # a motor must drive something (wheels are not required)
    "RB_MAX_DRIVE_MOTORS": "none",  # any number of motors may move the robot
    "RB_CRANK_RIDERS": "1",  # parts pinned to a crank ride on it (gear-torque model)
    "RB_MAX_CHAINS": "2",  # at most two chain loops per design (chain drives and chain tracks together)
    "RB_START_BOARD_MM": '{"*": 500, "gap": 1000}',  # start boards: 500 mm on every course, 1000 mm on the gap
}
"""The benchmark's fixed rule and simulator configuration (set for this process and every simulator subprocess)."""
for _k, _v in BENCHMARK_ENV.items():
    os.environ.setdefault(_k, _v)
os.environ.setdefault("MUJOCO_GL", "egl")
