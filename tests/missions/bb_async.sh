#!/bin/bash
# №bb-async (разбор железа TEST19, столб F2-7): после «BBOP npc+ … sync=1» стоит 29 из 42 кадров io ≥ 12 мс — запись ящика на карту в кадре (20–46 мс на PSP).
# Зелёный: после загрузки уровня НИ ОДНОГО «npc+/car+ … sync=1» из фонового чтения; красный -DBB_SYNC_ASYNC_OLD=1 обязан дать ≥ 1. Безоконный эмулятор, пакет RACE_PKG.   tests/missions/bb_async.sh
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; export TWINS_ROOT="$ROOT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"; OUT=build/bb_async; mkdir -p "$OUT"
count() { awk '/^SCENE B_card_race_L1/{r=1} r && /^BBOP (npc|car)\+ .* sync=1/{n++} END{print n+0}' "$1/smoke.txt"; }
for v in red green; do
  fl=""; [ $v = red ] && fl="-DCMAKE_C_FLAGS=-DBB_SYNC_ASYNC_OLD=1"
  psp-cmake -S viewer -B "$OUT/${v}_build" $fl > "$OUT/${v}_cmake.txt" 2>&1 && cmake --build "$OUT/${v}_build" -j4 > "$OUT/${v}_build.txt" 2>&1 || { echo "FAIL: сборка $v"; exit 2; }
  d=$("$ROOT/.venv/bin/python" tests/missions/bb_async.py "$OUT/${v}_build/EBOOT.PBP" $v | tail -1); eval "${v}_n=$(count "$d")"
  . tests/lib/drawn.sh; echo -n "  [$v] "; drawn_check "$d" || { echo "FAIL: куски drawPieceM не уходят в drawGeo (картинка), прогон $v"; exit 1; }
done
echo "npc+/car+ с sync=1 за миссию: красный (прежнее) $red_n, зелёный $green_n"
[ "$red_n" -ge 1 ] && [ "$green_n" -eq 0 ] && { echo PASS; exit 0; } || { echo FAIL; exit 1; }
