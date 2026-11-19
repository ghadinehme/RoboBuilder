#!/bin/bash
# Linux: ./launch.sh opens the controller in Chrome, Chromium or Edge (Web Serial talks to the IR bridge over USB).
cd "$(dirname "$0")"
PORT=8765
URL="http://localhost:$PORT/index.html"
BROWSER=""
for b in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge microsoft-edge-stable brave-browser; do
  if command -v "$b" >/dev/null 2>&1; then BROWSER="$b"; break; fi
done
if [ -z "$BROWSER" ]; then
  echo "Web Serial needs Google Chrome, Chromium or Microsoft Edge. Install Chrome: https://www.google.com/chrome/"
  exit 1
fi
if ! id -nG "$USER" | grep -qwE "dialout|uucp"; then
  echo "Note: to reach the board, your user must be in the 'dialout' group (once, then log out and in):"
  echo "    sudo usermod -aG dialout $USER"
fi
if command -v python3 >/dev/null 2>&1; then
  python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
  SRV=$!
  trap 'kill $SRV 2>/dev/null' EXIT
  sleep 1
  "$BROWSER" "$URL" >/dev/null 2>&1 &
  echo "RoboBuilder controller: $URL (in $BROWSER)"
  echo "Leave this terminal open while you use it; close it (or press Ctrl-C) to stop."
  wait $SRV
else
  "$BROWSER" "$(pwd)/index.html" >/dev/null 2>&1 &
  echo "Opened index.html in $BROWSER."
fi
