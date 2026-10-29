#!/bin/bash
# Гейт бонус-игры в безголовом эмуляторе (правка 420), ~3 мин: меню -> BONUS GAME -> выбор -> гонка 1 круг на b01 (машиной
# игрока ведёт водитель ИИ, flag bonusauto) -> вид сверху и за машиной -> итоги -> главное меню (tests/bonus/emu_scenario.txt).
#   tests/bonus/emu.sh [EBOOT]      (по умолчанию viewer/build/EBOOT.PBP; данные — build/, трассы — build/bonus/)
# ЗЕЛЁНЫЙ: tests/bonus/emu_check.py — menu, load, start, laps (4 машины), cams (обе), shots (не пустые и разные), back.
# КРАСНЫЙ: EBOOT с -DBONUS_OLD=1 (пункт серый, как было) на тех же данных обязан уронить проверку menu.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; OUT=build/gates/bonus; mkdir -p "$OUT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
EB="${1:-viewer/build/EBOOT.PBP}"
[ -f "$EB" ] && [ -f build/bonus/b01.shr ] && [ -f build/bonus/b01.bns ] && [ -f build/bonus/msncars-b.shr ] || { echo "FAIL: нет $EB или build/bonus/* (python tools/bonus/export.py --all)"; exit 2; }
echo "EBOOT $(shasum -a 256 "$EB" | cut -c1-8); b01.shr $(shasum -a 256 build/bonus/b01.shr | cut -c1-8); b01.bns $(shasum -a 256 build/bonus/b01.bns | cut -c1-8)"
psp-cmake -S viewer -B "$OUT/red_build" -DCMAKE_C_FLAGS="-DBONUS_OLD=1" > "$OUT/red_cmake.txt" 2>&1 &&
  cmake --build "$OUT/red_build" > "$OUT/red_build.txt" 2>&1 || { echo "FAIL: красная сборка не собралась ($OUT/red_build.txt)"; exit 2; }
run() {   # имя EBOOT -> папка прогона smoke
  local d="$OUT/emu_$1"; rm -rf "$d"; mkdir -p "$d"; cp "$2" "$d/EBOOT.PBP"
  local log; log=$(SMOKE_HEADLESS=1 SMOKE_SCN="$ROOT/tests/bonus/emu_scenario.txt" tools/smoke.sh "$d" 2>&1)
  echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
}
G=$(run green "$EB"); R=$(run red "$OUT/red_build/EBOOT.PBP")
[ -f "$G/smoke.txt" ] && [ -f "$R/smoke.txt" ] || { echo "FAIL: прогон не отработал ($G, $R)"; exit 2; }
"$PY" tests/bonus/emu_check.py "$G" > "$OUT/emu_green.txt" 2>&1; rg=$?
"$PY" tests/bonus/emu_check.py "$R" --expect-fail > "$OUT/emu_red.txt" 2>&1; rr=$?
echo "зелёный: $(head -1 "$OUT/emu_green.txt" | cut -c1-200)"; tail -n +2 "$OUT/emu_green.txt"
echo "красный (-DBONUS_OLD=1): $(head -1 "$OUT/emu_red.txt" | cut -c1-200)"
echo "снимки: ${G#$ROOT/} (зелёный), ${R#$ROOT/} (красный)"
if [ $rg -eq 0 ] && [ $rr -eq 0 ]; then echo "ИТОГ: PASS (бонус-игра: меню, трасса, гонка с соперниками, обе камеры, выход; красный пойман)"; exit 0; fi
echo "ИТОГ: FAIL (зелёный rc=$rg, красный пойман=$([ $rr -eq 0 ] && echo да || echo НЕТ))"; exit 1
