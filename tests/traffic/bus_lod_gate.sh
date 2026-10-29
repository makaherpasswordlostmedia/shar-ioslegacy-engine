#!/bin/bash
# bus_lod_gate.sh — гейт проверки дистанции переключения LOD машин трафика (№558)
# Проверяет зелёный прогон (TRF_LOD_DIST_OLD=0) и красный контроль (TRF_LOD_DIST_OLD=1).
set -e

DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$DIR"

SRC="$DIR/tests/traffic/test_bus_lod.c"
BIN="/tmp/test_bus_lod_$$"
BIN_RED="/tmp/test_bus_lod_red_$$"

cleanup() {
  rm -f "$BIN" "$BIN_RED"
}
trap cleanup EXIT

TRAFFIC_SHR=""
for p in $HOME/Downloads/shar-psp-sonnet-runs-w/build/final-20261011-1721/traffic.shr $HOME/Downloads/shar-psp/build/traffic.shr "$DIR/build/traffic.shr"; do
  if [ -f "$p" ]; then TRAFFIC_SHR="$p"; break; fi
done
if [ -z "$TRAFFIC_SHR" ]; then
  echo "Error: traffic.shr not found"
  exit 1
fi
echo "Using traffic.shr: $TRAFFIC_SHR"

echo "=== 1. Зелёный тест: TRF_LOD_DIST_OLD=0 (новое поведение) ==="
clang -std=c99 -O2 -I "$DIR" -DSKIN_HOST -DTRF_LOD_DIST_OLD=0 "$SRC" -lm -o "$BIN"
"$BIN" "$TRAFFIC_SHR"
GREEN_RES=$?

if [ $GREEN_RES -ne 0 ]; then
  echo "FAIL: Зелёный тест завершился с ошибкой $GREEN_RES"
  exit 1
fi

echo "=== 2. Красный контроль: TRF_LOD_DIST_OLD=1 (старое поведение) ==="
clang -std=c99 -O2 -I "$DIR" -DSKIN_HOST -DTRF_LOD_DIST_OLD=1 "$SRC" -lm -o "$BIN_RED"
set +e
"$BIN_RED" "$TRAFFIC_SHR"
RED_RES=$?
set -e

if [ $RED_RES -eq 0 ]; then
  echo "FAIL: Красный контроль должен был упасть, но вернул 0!"
  exit 1
fi
echo "Красный контроль успешно упал (код $RED_RES), как и положено."

echo "=== ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ (ЗЕЛЁНЫЙ PASS, КРАСНЫЙ FAIL) ==="
exit 0
