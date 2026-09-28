# Build and flash the Nova-Band firmware + screen assets to a T-Display-S3 Touch.
#
#   powershell -ExecutionPolicy Bypass -File firmware\flash.ps1 -Prebuilt        # flash firmware\prebuilt (no build tools needed)
#   powershell -ExecutionPolicy Bypass -File firmware\flash.ps1                  # rebuild assets + firmware, then flash
#   powershell -ExecutionPolicy Bypass -File firmware\flash.ps1 -SkipBuild -AppOnly
#   ... [-Port COM11]
#
# Needs arduino-cli with the esp32 core 3.x (for esptool) — building also needs
# the ArduinoJson library and, for the assets, the Blender renders in build/.
# Restore the original factory firmware (kept locally, not in git) with:
#   esptool --port COM11 write-flash 0 build\firmware-backup\original_16MB.bin
param(
  [string]$Port = "",
  [switch]$Prebuilt,
  [switch]$SkipBuild,
  [switch]$AppOnly
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$fqbn = "esp32:esp32:esp32s3:CDCOnBoot=cdc,FlashSize=16M,PSRAM=opi,PartitionScheme=custom,UploadSpeed=921600"
$esptool = Get-ChildItem "$env:LOCALAPPDATA\Arduino15\packages\esp32\tools\esptool_py\*\esptool.exe" | Select-Object -Last 1
if (-not $esptool) { throw "esptool not found: arduino-cli core install esp32:esp32" }

if (-not $Port) {
  $line = arduino-cli board list | Select-String "ESP32" | Select-Object -First 1
  if (-not $line) { throw "No ESP32 board found - plug in the T-Display-S3" }
  $Port = $line.ToString().Split(" ")[0]
}
Write-Host "Board on $Port"

if ($Prebuilt) {
  $d = Join-Path $root "firmware\prebuilt"
  $boot = "$d\bootloader.bin"; $part = "$d\partitions.bin"; $appBin = "$d\novaband_display.bin"; $assets = "$d\assets.bin"
} else {
  $out = Join-Path $root "build\fw\app"
  if (-not $SkipBuild) {
    python "$root\tools\fw_assets.py"
    arduino-cli compile -b $fqbn --output-dir $out "$root\firmware\novaband_display"
    if ($LASTEXITCODE) { throw "compile failed" }
  }
  $boot = "$out\novaband_display.ino.bootloader.bin"; $part = "$out\novaband_display.ino.partitions.bin"
  $appBin = "$out\novaband_display.ino.bin"; $assets = "$root\build\fw\assets.bin"
}

$flash = @("0x0", $boot, "0x8000", $part, "0x10000", $appBin)
if (-not $AppOnly) { $flash += @("0x310000", $assets) }
& $esptool.FullName --chip esp32s3 --port $Port --baud 921600 write-flash --flash-size 16MB @flash
if ($LASTEXITCODE) { throw "flash failed" }
Write-Host "Done. Serial log: arduino-cli monitor -p $Port -c baudrate=115200"
