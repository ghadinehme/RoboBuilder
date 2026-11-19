#!/usr/bin/env bash
# The four reference entrants as run for the paper (medium reasoning effort), one after the other, then the
# leaderboard with them. Each run is about 4,000 simulations; the CLIs must be installed and logged in.
#   scripts/run_reference_agents.sh [runs dir, default runs]
set -e
cd "$(dirname "$0")/.."
D=${1:-runs}
robobuilder run --agent claude-code --model claude-opus-5-5 --effort medium --run-dir "$D/opus-5.5"
robobuilder run --agent claude-code --model claude-sonnet-5-5 --effort medium --run-dir "$D/sonnet-5.5"
robobuilder run --agent codex --model gpt-6-astra --effort medium --run-dir "$D/gpt-6-astra"
robobuilder run --agent codex --model gpt-6.1-sol --effort medium --run-dir "$D/gpt-6.1-sol"
robobuilder score --no-reference "$D/opus-5.5" "$D/sonnet-5.5" "$D/gpt-6-astra" "$D/gpt-6.1-sol"
