"""Budgets and fixed settings of the benchmark tasks (as in the paper)."""
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS = os.environ.get("RB_DOCS_DIR") or os.path.join(REPO, "agent_docs")
"""the documents the agents receive (agent_docs/)"""

PHASES = {
    "cross": {"sims": 30, "hours": 24.0},  # Cross: pass the level
    "print": {"sims": 30, "hours": 24.0},  # Cross+Print: if Cross failed, 30 more simulations and one printed part type
    "light": {"sims": 50, "hours": 24.0},  # Light: the lightest passing design (a fresh session)
    "fast": {"sims": 50, "hours": 24.0},  # Fast: the fastest passing design (a fresh session)
}
LIGHT_FAST_HOURS = {1: 24.0, 2: 48.0, 3: 72.0}
"""wall-time budget of a Light / Fast session by level (50 simulations at every level)"""
ALL_IN_ONE = {"sims": 300, "hours": 72.0, "min_sims": 300, "max_mm": 250.0, "copies": 8}
"""All-in-one: 300 simulations; the hand-in is accepted once the robot passes all ten courses or the simulations are
used up; printed structure (any number of part types, 8 copies each, 250 mm per side)"""
BANNED_ALL_IN_ONE = ("plate", "beam_brick")
"""part kinds the All-in-one robot may not use (its structure is printed): together they are every part of the
parts.md sections "beam bricks, liftarms and frames" (beam bricks, liftarms, frames, the gearbox, the steering arm) and
"Bricks and plates" (tests/test_basic.py checks this)"""
PRINT_COPIES = 4
PRINT_MAX_MM = 256.0
PRINT_MIN_WALL_MM = 1.2
WRAPUP_MIN = 20.0  # the closing lessons.md turn [min]
MAX_NUDGES = 30  # reminders when an agent stops early (budget left)
BEST_ATTEMPT_MIN_H = 0.5  # a best attempt is refused while simulations and more than this many hours are left
FRESH_MIN_H = 0.5  # a Light / Fast session is not reminded once less than this is left
TURNS = 1000
PYTHON_TIMEOUT_S = 300
OUTPUT_CHARS = 20000
