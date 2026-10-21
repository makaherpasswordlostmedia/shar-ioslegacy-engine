#!/bin/bash
# Гейт пакета «Объекты уровня и миссий» на Маке (три пункта Роба 28.09, правка 10):
#   1) AnimCollision/Anim диска: грузовик Duff у Kwik-E-Mart с подъёмником, ветка, платформы АЭС и др. — рисунок, объёмы COL1,
#      действия (tests/levelobj/expect.py — экспорт против диска, tests/levelobj/host.c — игра без экрана);
#   2) «вырезка со смешиванием» (лестница пожарной машины) — tests/levelobj/cutout_check.py + tools/blendmip_check.py;
#   3) предметы/маркеры миссий (msnart.shr MSA2) и персонажи скриптов — tests/levelobj/msnart_check.py.
#   tests/levelobj/host.sh [NEW.shr] [BASE.shr] [MSNART.shr]
#     NEW    — уровень пакета (tools/build_level.sh), по умолчанию build/level.shr
#     BASE   — тот же код как до пакета: SHR_NO_ANIMOBJ=1 SHR_CUT_BLEND=0 tools/build_level.sh build/objlvl/level_off.shr
#     MSNART — по умолчанию build/msnart.shr (tools/msnart_export.py)
# Сначала КРАСНЫЙ (обязан упасть): экспорт-проверка и проверка вырезок на BASE; host без aoStep (nolive), без △ (noact),
# живой ящик вне своей сетки (far); испорченная копия msnart (--plant). Потом ЗЕЛЁНЫЙ. Итог: build/objlvl/*.txt
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
NEW="${1:-build/level.shr}"; BASE="${2:-build/objlvl/level_off.shr}"; MSA="${3:-build/msnart.shr}"; OUT=build/objlvl; mkdir -p "$OUT"
[ -f "$NEW" ] && [ -f "$BASE" ] && [ -f "$MSA" ] || { echo "FAIL: нет $NEW, $BASE или $MSA (см. начало файла)"; exit 1; }
. .venv/bin/activate
V=viewer
cc -std=c11 -O2 -Wall -Wno-unused-function -I $V tests/levelobj/host.c $V/animobj.c $V/stateprops.c $V/col.c $V/props.c $V/coins.c $V/car.c -lm \
   -o "$OUT/host" 2> "$OUT/build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/build.txt"; exit 1; }
red=0; nred=6
red_run() {   # $1 имя, дальше команда: обязана упасть
  local n="$1"; shift
  "$@" > "$OUT/red_$n.txt" 2>&1
  if [ $? -ne 0 ]; then echo "красный ($n): упал, как должен — $(grep -m1 'FAIL' "$OUT/red_$n.txt" | cut -c1-120)"; red=$((red + 1))
  else echo "КРАСНЫЙ НЕ ПОЙМАН: $n прошёл гейт"; fi
}
red_run export_base python3 tests/levelobj/expect.py "$BASE" "$BASE"
red_run cutout_base python3 tests/levelobj/cutout_check.py "$BASE"
for p in nolive noact far; do red_run "host_$p" "$OUT/host" "$NEW" --plant "$p"; done
red_run msnart_plant python3 tests/levelobj/msnart_check.py "$MSA" --plant
rc=0
python3 tests/levelobj/expect.py "$NEW" "$BASE" > "$OUT/green_export.txt" 2>&1 || rc=1
"$OUT/host" "$NEW" > "$OUT/green_host.txt" 2>&1 || rc=1
python3 tests/levelobj/cutout_check.py "$NEW" --expect-family 16 > "$OUT/green_cutout.txt" 2>&1 || rc=1
python3 tools/blendmip_check.py "$NEW" > "$OUT/green_blendmip.txt" 2>&1 || rc=1
python3 tests/levelobj/msnart_check.py "$MSA" > "$OUT/green_msnart.txt" 2>&1 || rc=1
grep -h "^CHECK\|^RESULT\|^blendmip" "$OUT"/green_*.txt
if [ $red -eq $nred ] && [ $rc -eq 0 ]; then echo "PASS: красный $red/$nred пойман, зелёный: $(grep -h '^RESULT' "$OUT"/green_*.txt | tr '\n' ' ')"; exit 0; fi
echo "FAIL: красный $red/$nred, зелёный rc=$rc"; exit 1
