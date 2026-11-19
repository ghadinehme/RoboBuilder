#!/bin/bash
# macOS: double-click to open the controller in Chrome or Edge (Web Serial talks to the IR bridge over USB).
cd "$(dirname "$0")"
PORT=8765
URL="http://localhost:$PORT/index.html"
pick_browser() {
  for app in "Google Chrome" "Microsoft Edge" "Chromium" "Brave Browser"; do
    if open -Ra "$app" 2>/dev/null; then echo "$app"; return; fi
  done
}
APP="$(pick_browser)"
if [ -z "$APP" ]; then
  echo "Web Serial needs Google Chrome or Microsoft Edge. Install Chrome: https://www.google.com/chrome/"
  exit 1
fi
if command -v python3 >/dev/null 2>&1; then
  python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
  SRV=$!
  trap 'kill $SRV 2>/dev/null' EXIT
  sleep 1
  open -a "$APP" "$URL"
  echo "RoboBuilder controller: $URL (in $APP)"
  echo "Leave this window open while you use it; close it (or press Ctrl-C) to stop."
  wait $SRV
else
  open -a "$APP" "$(pwd)/index.html"   # Chrome also allows Web Serial on a local file
  echo "Opened index.html in $APP."
fi
