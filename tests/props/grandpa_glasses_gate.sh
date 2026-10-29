#!/bin/bash
# grandpa_glasses_gate.sh — гейт проверки устранения розовых очков дедушки (№518)
# Проверяет зелёный тест (GRANDPA_GLASSES_OLD=0) и красный контроль (GRANDPA_GLASSES_OLD=1).
set -e

DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$DIR"

SRC="$DIR/tests/props/test_grandpa_glasses.c"
BIN="/tmp/test_grandpa_glasses_$$"
BIN_RED="/tmp/test_grandpa_glasses_red_$$"

cleanup() {
  rm -f "$BIN" "$BIN_RED"
}
trap cleanup EXIT

echo "=== 1. Зелёный тест: GRANDPA_GLASSES_OLD=0 (новое поведение) ==="
clang -std=c99 -O2 -I "$DIR" -DGRANDPA_GLASSES_OLD=0 "$SRC" -o "$BIN"
"$BIN"
GREEN_RES=$?

if [ $GREEN_RES -ne 0 ]; then
  echo "FAIL: Зелёный тест завершился с ошибкой $GREEN_RES"
  exit 1
fi

echo "=== 2. Красный контроль: GRANDPA_GLASSES_OLD=1 (старое поведение) ==="
clang -std=c99 -O2 -I "$DIR" -DGRANDPA_GLASSES_OLD=1 "$SRC" -o "$BIN_RED"
set +e
"$BIN_RED"
RED_RES=$?
set -e

if [ $RED_RES -eq 0 ]; then
  echo "FAIL: Красный контроль должен был упасть, но вернул 0!"
  exit 1
fi
echo "Красный контроль успешно подтвердил старый дефект (код $RED_RES), как и положено."

echo "=== ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ (ЗЕЛЁНЫЙ PASS, КРАСНЫЙ FAIL) ==="
exit 0
