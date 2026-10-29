#!/bin/bash
# tests/walls/props_break_gate.sh
# Гейт для #588 (сбиваемое) и #589 (уход пнутых предметов в фейд)
set -e

DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$DIR"

BUILD_DIR="build/tests/props_break"
mkdir -p "$BUILD_DIR"

# Поиск level.shr для L1 и L2
L1_SHR=""
for p in "build/level.shr" "build/ship_stage/level.shr" "$HOME/Downloads/shar-psp/build/ship_stage/level.shr" "$HOME/Downloads/shar-psp/build/level.shr"; do
  if [ -f "$p" ]; then L1_SHR="$p"; break; fi
done

L2_SHR=""
for p in "build/levels/l2/level.shr" "build/ship_stage/l2/level.shr" "$HOME/Downloads/shar-psp/build/ship_stage/l2/level.shr"; do
  if [ -f "$p" ]; then L2_SHR="$p"; break; fi
done

if [ -z "$L1_SHR" ] || [ -z "$L2_SHR" ]; then
  echo "ОШИБКА: не найдены level.shr для L1 ($L1_SHR) или L2 ($L2_SHR)"
  exit 1
fi

echo "--- Сборка и запуск: ЗЕЛЁНЫЙ ПРОГОН ---"
clang -std=c11 -O2 -DSKIN_HOST -I viewer \
  tests/walls/props_break_host.c \
  viewer/col.c viewer/props.c viewer/stateprops.c viewer/car.c viewer/coins.c \
  -lm -o "$BUILD_DIR/props_break_green"

"$BUILD_DIR/props_break_green" green "$L1_SHR" "$L2_SHR"

echo ""
echo "--- Сборка и запуск: КРАСНЫЙ КОНТРОЛЬ (-DHYDRANT_SMASH_OLD=1 -DFENCE_BREAK_OLD=1 -DPROP_GHOST_OLD=1 -DPROP_FADE_OLD=1) ---"
clang -std=c11 -O2 -DSKIN_HOST -I viewer \
  -DHYDRANT_SMASH_OLD=1 -DFENCE_BREAK_OLD=1 -DPROP_GHOST_OLD=1 -DPROP_FADE_OLD=1 \
  tests/walls/props_break_host.c \
  viewer/col.c viewer/props.c viewer/stateprops.c viewer/car.c viewer/coins.c \
  -lm -o "$BUILD_DIR/props_break_red"

set +e
"$BUILD_DIR/props_break_red" red "$L1_SHR" "$L2_SHR"
RED_RC=$?
set -e

if [ $RED_RC -eq 0 ]; then
  echo "ОШИБКА: красный контроль прошёл успешно, хотя должен был отловить баги!"
  exit 1
fi

echo "КРАСНЫЙ КОНТРОЛЬ: PASS (все сбои отловлены под флагами отката)"
echo ""
echo "ИТОГ: props_break_gate PASS (#588 и #589 полностью закрыты)"
