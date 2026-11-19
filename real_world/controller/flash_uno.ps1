# Installs arduino-cli (into tools\ next to this script), the Uno core and the IRremote library, then flashes
# ..\firmware\ir_bridge to an Arduino Uno.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$fw = Join-Path $PSScriptRoot "..\firmware\ir_bridge"
$tools = Join-Path $PSScriptRoot "tools"
$cli = Join-Path $tools "arduino-cli.exe"
if (-not (Test-Path $cli)) {
  Write-Host "Downloading arduino-cli ..."
  New-Item -ItemType Directory -Force -Path $tools | Out-Null
  $zip = Join-Path $tools "arduino-cli.zip"
  Invoke-WebRequest -Uri "https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_Windows_64bit.zip" -OutFile $zip
  Expand-Archive -Path $zip -DestinationPath $tools -Force
  Remove-Item $zip
}
& $cli core update-index
& $cli core install arduino:avr
& $cli lib install "IRremote@4.7.1"
if ($LASTEXITCODE -ne 0) { & $cli lib install IRremote }
$boards = & $cli board list --format json | ConvertFrom-Json
$ports = @()
if ($boards.detected_ports) { $ports = $boards.detected_ports } else { $ports = $boards }
$port = ($ports | Where-Object { $_.port.address -like "COM*" -and ($_.matching_boards -or $_.port.protocol -eq "serial") } |
  Select-Object -First 1).port.address
if (-not $port) { Write-Host "No board found on a COM port. Plug it in (and install its USB driver if needed) and retry."; exit 1 }
Write-Host "Flashing $port ..."
& $cli compile --fqbn arduino:avr:uno $fw
& $cli upload -p $port --fqbn arduino:avr:uno $fw
Write-Host "Done. Now double-click launch.bat."
