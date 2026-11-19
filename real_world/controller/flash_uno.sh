#!/bin/bash
# Linux: run if the board does not answer in the controller ("no IR bridge answer"): installs arduino-cli (into
# ~/.local/bin), the Uno core and the IRremote library, then flashes ../firmware/ir_bridge to an Arduino Uno.
set -e
cd "$(dirname "$0")"
FW=../firmware/ir_bridge
export PATH="$HOME/.local/bin:$PATH"
if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "Installing arduino-cli into ~/.local/bin ..."
  mkdir -p "$HOME/.local/bin"
  curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | BINDIR="$HOME/.local/bin" sh
fi
arduino-cli core update-index
arduino-cli core install arduino:avr
arduino-cli lib install "IRremote@4.7.1" || arduino-cli lib install IRremote
PORT_DEV=$(ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null | head -1)
if [ -z "$PORT_DEV" ]; then echo "No board found on USB (/dev/ttyACM* / ttyUSB*). Plug it in and retry."; exit 1; fi
echo "Flashing $PORT_DEV ..."
arduino-cli compile --fqbn arduino:avr:uno "$FW"
arduino-cli upload -p "$PORT_DEV" --fqbn arduino:avr:uno "$FW"
echo "Done. Now run ./launch.sh"
