#!/bin/sh
# Золотая запись m0 в собственной копии observer3 (DS4 Роба, копия его раскладки). Меню жмём сами, строго по PID
#   golden_session.sh go    — подтвердить заполненную запись ввода Power On и включить видео (игра стартует с нуля)
#   golden_session.sh stop  — остановить ввод и видео, положить видео в build/ps2ref/golden/m0.mp4
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
AX="$ROOT/build/ps2ref/ax"; G="$ROOT/build/ps2ref/golden"; V="$ROOT/build/ps2ref/profiles/observer3/data/videos"
[ -x "$AX" ] || swiftc -O "$ROOT/tools/ps2ref/ax.swift" -o "$AX"
PID=$(cd "$ROOT/tools/ps2ref" && python3 profile.py --index 3 pid)
case "${1:-}" in
go)
  "$AX" "$PID" set "New Input Recording" 1 "$G/m0.p2m2"
  "$AX" "$PID" press "New Input Recording" OK
  sleep 3
  "$AX" "$PID" menu System "Video Capture"
  sleep 1.5
  "$AX" "$PID" press "Video Capture" Save
  ;;
stop)
  "$AX" "$PID" menu Tools "Input Recording" Stop
  "$AX" "$PID" menu System "Video Capture"
  sleep 3
  f=$(ls -t "$V"/*.mp4 | head -1)
  mv -n "$f" "$G/m0.mp4"
  ls -l "$G"
  ;;
*) echo "usage: $0 go|stop"; exit 2 ;;
esac
