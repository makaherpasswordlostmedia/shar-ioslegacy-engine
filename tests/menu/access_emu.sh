#!/bin/bash
# Гейт пункта ДОБИВКИ 26 в безголовом эмуляторе (~3 мин): повтор записей PS2 ps2_access_pause / _options_unlock / _settings_unlock
# сценарием tests/menu/access_scenario.txt, сверка tests/menu/access_check.py.
#   tests/menu/access_emu.sh [EBOOT]   (по умолчанию viewer/build/EBOOT.PBP; данные — build/ как у tools/smoke.sh)
# ЗЕЛЁНЫЙ — EBOOT; КРАСНЫЕ — тот же код с -DPAUSE_MS_DIM_OLD=1 (MISSION SELECT белый, ↓↓↓ попадает на VIEW CARDS) и с
# -DPAUSE_SUB_START_OLD=1 (START на SETTINGS ничего не делает): каждый обязан уронить свою проверку. Красный самого гейта паузы по
# пикселям (группа rows, кадр PS2 shot_120): зелёный EBOOT, сценарий без «flag saves» — SAVE GAME серый, проверка обязана упасть.
# Будка (запись PS2 ps2_v105_booth_access): сценарий tests/shop/booth_scenario.txt, сверка tests/menu/access_booth_check.py —
# зелёный EBOOT, красный -DBOOTH_ACCESS_OLD=1 (те же данные, build/phone.shr с меткой Accept). Логика всех трёх — хост tests/menu/access.sh
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; OUT=build/gates/access; mkdir -p "$OUT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
EB="${1:-viewer/build/EBOOT.PBP}"; [ -f "$EB" ] || { echo "FAIL: нет $EB"; exit 2; }
echo "EBOOT $(shasum -a 256 "$EB" | cut -c1-8)"
for f in PAUSE_MS_DIM_OLD PAUSE_SUB_START_OLD BOOTH_ACCESS_OLD; do
  psp-cmake -S viewer -B "$OUT/red_$f" -DCMAKE_C_FLAGS="-D$f=1" > "$OUT/red_$f.cmake.txt" 2>&1 &&
    cmake --build "$OUT/red_$f" > "$OUT/red_$f.build.txt" 2>&1 || { echo "FAIL: красная сборка $f ($OUT/red_$f.build.txt)"; exit 2; }
done
run() {   # имя EBOOT [сценарий] -> папка прогона smoke
  local d="$OUT/$1"; rm -rf "$d"; mkdir -p "$d"; cp "$2" "$d/EBOOT.PBP"
  local log; log=$(SHIP_LEVELS="" SMOKE_HEADLESS=1 SMOKE_SCN="${3:-$ROOT/tests/menu/access_scenario.txt}" tools/smoke.sh "$d" 2>&1)
  echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
}
NS="$OUT/scenario_nosaves.txt"; grep -v '^flag saves' tests/menu/access_scenario.txt > "$NS"
G=$(run green "$EB"); R0=$(run red_rows "$EB" "$ROOT/$NS"); R1=$(run red_ms "$OUT/red_PAUSE_MS_DIM_OLD/EBOOT.PBP"); R2=$(run red_start "$OUT/red_PAUSE_SUB_START_OLD/EBOOT.PBP")
BS="$ROOT/tests/shop/booth_scenario.txt"
BG=$(run booth_green "$EB" "$BS"); BR=$(run booth_red "$OUT/red_BOOTH_ACCESS_OLD/EBOOT.PBP" "$BS")
"$PY" tests/menu/access_check.py "$G" > "$OUT/green.txt" 2>&1; rg=$?
"$PY" tests/menu/access_check.py "$R0" --expect-fail rows > "$OUT/red_rows.txt" 2>&1; r0=$?
"$PY" tests/menu/access_check.py "$R1" --expect-fail ms > "$OUT/red_ms.txt" 2>&1; r1=$?
"$PY" tests/menu/access_check.py "$R2" --expect-fail start > "$OUT/red_start.txt" 2>&1; r2=$?
"$PY" tests/menu/access_booth_check.py "$BG" > "$OUT/booth_green.txt" 2>&1; bg=$?
"$PY" tests/menu/access_booth_check.py "$BR" --expect-fail > "$OUT/booth_red.txt" 2>&1; br=$?
echo "зелёный: $(head -1 "$OUT/green.txt")"; tail -n +2 "$OUT/green.txt"
echo "красный сценарий без flag saves (SAVE GAME серый): $(head -1 "$OUT/red_rows.txt")"
echo "красный -DPAUSE_MS_DIM_OLD=1: $(head -1 "$OUT/red_ms.txt")"
echo "красный -DPAUSE_SUB_START_OLD=1: $(head -1 "$OUT/red_start.txt")"
echo "будка зелёный: $(head -1 "$OUT/booth_green.txt")"
echo "будка красный -DBOOTH_ACCESS_OLD=1: $(head -1 "$OUT/booth_red.txt")"
echo "снимки: ${G#$ROOT/} (зелёный), ${R0#$ROOT/}, ${R1#$ROOT/}, ${R2#$ROOT/} (красные); будка ${BG#$ROOT/}, ${BR#$ROOT/}"
if [ $rg -eq 0 ] && [ $r0 -eq 0 ] && [ $r1 -eq 0 ] && [ $r2 -eq 0 ] && [ $bg -eq 0 ] && [ $br -eq 0 ]; then
  echo "ИТОГ: PASS (пауза L1 m0sd как PS2: по пикселям как shot_120, MISSION SELECT серый и обойдён, START из SETTINGS — в игру; будка — 6 строк PS2, у закрытой звёзды без Accept; красные пойманы)"; exit 0; fi
echo "ИТОГ: FAIL (зелёный rc=$rg, красный rows=$r0, красный ms=$r1, красный start=$r2, будка зелёный=$bg, будка красный=$br)"; exit 1
