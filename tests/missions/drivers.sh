#!/bin/bash
# Аудит 09.10 п. 20 (В61): водители машин миссий в безголовом эмуляторе. Два EBOOT — новый и красный (-DMV_DRIVERS_OLD=1,
# водителей нет), один сценарий tests/missions/drivers_scenario.txt через tools/smoke.sh (SMOKE_HEADLESS=1): машина игрока
# в 6 м от машины миссии (sr2 Барт в honor_v, m7 Смитерс в smith_v, m6 Джаспер в cBone), снимки. Проверка
# tests/missions/drivers_check.py: у нового «MSN drivers-drawn» ≥ 1 в каждой из трёх миссий и в кадре на месте сиденья машины
# миссии есть пиксели водителя (разница с красным снимком), у красного — 0 водителей. Данные — DIR (по умолчанию build/race_w/stage:
# EBOOT заменяется, пакеты персонажей chars/*.chr — с клипом ndr_in_car_idle, tools/char_export.py)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
export PSPDEV=$ROOT/pspdev PATH=$ROOT/pspdev/bin:$PATH
SRC="${1:-build/race_w/stage}"; OUT=build/gates/drivers/$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
for v in new red; do
  F=""; [ $v = red ] && F="-DMV_DRIVERS_OLD=1"
  psp-cmake -S viewer -B "$OUT/build_$v" -DCMAKE_C_FLAGS="$F" > "$OUT/cmake_$v.txt" 2>&1 && cmake --build "$OUT/build_$v" > "$OUT/make_$v.txt" 2>&1 || { echo "FAIL: сборка $v"; tail -5 "$OUT/make_$v.txt"; exit 1; }
  S="$OUT/stage_$v"; mkdir -p "$S"; (cd "$SRC" && find . -type f) | while read -r f; do mkdir -p "$S/$(dirname "$f")"; cp -c "$SRC/$f" "$S/$f" 2>/dev/null || cp "$SRC/$f" "$S/$f"; done
  cp "$OUT/build_$v/EBOOT.PBP" "$S/EBOOT.PBP"
  SMOKE_HEADLESS=1 SHIP_LEVELS="2 3 4 5 6 7" SMOKE_SCN="$ROOT/tests/missions/drivers_scenario.txt" tools/smoke.sh "$S" > "$OUT/smoke_$v.txt" 2>&1
  D=$(grep -o 'build/smoke/[0-9-]*' "$OUT/smoke_$v.txt" | tail -1); [ -n "$D" ] || { echo "FAIL: смоук $v"; tail -3 "$OUT/smoke_$v.txt"; exit 1; }
  echo "$D" > "$OUT/run_$v.txt"; rm -rf "$S" "$OUT/build_$v"
done
N=$(cat "$OUT/run_new.txt"); R=$(cat "$OUT/run_red.txt")
if .venv/bin/python tests/missions/drivers_check.py "$R" "$R" > "$OUT/check_red.txt"; then echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0
else echo "красный: $(grep -m1 'CHECK.*FAIL' "$OUT/check_red.txt" | cut -c1-160)"; red=1; fi
echo "зелёный:"; .venv/bin/python tests/missions/drivers_check.py "$N" "$R" | tee "$OUT/check.txt"; green=${PIPESTATUS[0]}
[ $red = 1 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся; $OUT)" || { echo "FAIL ($OUT)"; exit 1; }
