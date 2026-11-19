#!/bin/bash
# macOS: double-click if the board does not answer in the controller ("no IR bridge answer"): installs arduino-cli
# (via Homebrew), the Uno core and the IRremote library, then flashes ../firmware/ir_bridge to an Arduino Uno.
set -e
cd "$(dirname "$0")"
FW=../firmware/ir_bridge
if ! command -v arduino-cli >/dev/null 2>&1; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "Needs Homebrew (https://brew.sh) or the Arduino IDE (open $FW/ir_bridge.ino, install the 'IRremote'"
    echo "library by Armin Joachimsmeyer, board 'Arduino Uno', Upload)."
    exit 1
  fi
  brew install arduino-cli
fi
arduino-cli core update-index
arduino-cli core install arduino:avr
arduino-cli lib install "IRremote@4.7.1" || arduino-cli lib install IRremote
PORT_DEV=$(ls /dev/cu.usbmodem* /dev/cu.usbserial* /dev/cu.wchusbserial* 2>/dev/null | head -1)
if [ -z "$PORT_DEV" ]; then echo "No board found on USB (/dev/cu.usbmodem* / usbserial*). Plug it in and retry."; exit 1; fi
echo "Flashing $PORT_DEV ..."
arduino-cli compile --fqbn arduino:avr:uno "$FW"
arduino-cli upload -p "$PORT_DEV" --fqbn arduino:avr:uno "$FW"
echo "Done. Now open the controller (launch.command)."
