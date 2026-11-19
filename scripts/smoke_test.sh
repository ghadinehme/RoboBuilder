#!/usr/bin/env bash
# Fresh-install smoke test: a new virtual environment, `pip install -e .`, then the validator and one simulation.
#   scripts/smoke_test.sh [python3.12]
set -e
cd "$(dirname "$0")/.."
PY=${1:-python3.12}
D=$(mktemp -d)
$PY -m venv "$D/venv"
"$D/venv/bin/pip" install -q --upgrade pip
"$D/venv/bin/pip" install -q -e ".[test]"
echo "== validate the example design (ramp L1)"
"$D/venv/bin/robobuilder" validate agent_docs/example_design.json ramp 1 | head -20
echo "== simulate a reference design (opus-5.5, ramp L1, Cross)"
"$D/venv/bin/robobuilder" simulate reference_results/designs/opus-5.5/ramp_L1/cross.json ramp 1 --out "$D/sim"
echo "== the leaderboard of the reference entrants"
"$D/venv/bin/robobuilder" score
echo "== fast tests"
"$D/venv/bin/python" -m pytest -q tests/test_basic.py
rm -rf "$D"
