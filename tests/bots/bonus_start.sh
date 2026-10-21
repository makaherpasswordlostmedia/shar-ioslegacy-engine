#!/bin/bash
# Старт бонус-миссии у бота как у игрока (разбор ночи 02.10 для приёмки L1, 03.10): игрок приезжает к персонажу бонус-миссии на
# своей машине; бот начинает с новой игры у дома Симпсонов. У bm1 This Old Shanty есть вступление (разговор с Клетусом), и старт
# машину не переносит (game_msn.h) — она оставалась у дома в 545 м, этап «сядь в машину» бот шёл пешком 96 с из общего времени.
# Правило стенда (missioner.c bonusCarToStart): до старта такой миссии машина — на её локаторе SetMissionResetPlayerInCar.
# Красный MISSIONER_BONUS_CAR_OLD=1: этап «сядь в машину» не кончается за 60 с; зелёный — кончается не позже 10 с после разговора.
#   tests/bots/bonus_start.sh   -> PASS/FAIL; рабочие файлы build/bots/gate_bonus_start/
cd "$(dirname "$0")/../.."
O=build/bots/gate_bonus_start; rm -rf "$O"; mkdir -p "$O"
BINS=missioner OUT_DIR=$O tools/bots/build.sh >/dev/null || { echo "FAIL: сборка миссионера"; exit 1; }
A="build/level.shr build/homer.shr build/sandbox/roads-l1.bin build/missions/level01.msn"
getin() {   # -> «начало этапа 1.0 конец (с)» этапа «сядь в машину» bm1 за первые 120 с игры; конец 999 — не кончился
  nice -n 10 $O/missioner $A --mission 12 --secs 120 -v > "$O/$1.log" 2>&1
  awk '/стадия 1\.0 t=/ { split($3, a, "="); s = a[2] + 0 } /стадия 1\.1 t=/ { split($3, a, "="); e = a[2] + 0 }
       END { if (s == "") s = -1; if (e == "") e = 999; printf "%.1f %.1f\n", s, e }' "$O/$1.log"
}
echo "== красный: MISSIONER_BONUS_CAR_OLD=1 (машина у дома Симпсонов)"
read RS RE <<< "$(MISSIONER_BONUS_CAR_OLD=1 getin red)"; echo "  «сядь в машину»: с $RS по $RE с"
echo "== зелёный"
read GS GE <<< "$(getin green)"; grep -m1 "бонус-миссия" "$O/green.log" | sed 's/^ */  /'; echo "  «сядь в машину»: с $GS по $GE с"
red=$(awk -v s="$RS" -v e="$RE" 'BEGIN { print (s >= 0 && e - s > 60) ? 1 : 0 }')
green=$(awk -v s="$GS" -v e="$GE" 'BEGIN { print (s >= 0 && e - s <= 10) ? 1 : 0 }')
[ "$red" = 1 ] && echo "  красный пойман" || echo "  КРАСНЫЙ НЕ ПОЙМАН"
[ "$red" = 1 ] && [ "$green" = 1 ] && echo "PASS" || { echo "FAIL"; exit 1; }
