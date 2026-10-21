#!/bin/bash
# Гейт №405 (пульс «Press START button» по записи PS2) и №409 (свечение логотипа без ступеней и сетки 4x4) — Мак, безголовый
# эмулятор (программный рендер рисует дизеринг GE, как железо), ~2 мин.
#   tests/title/title.sh [EBOOT]   (по умолчанию viewer/build/EBOOT.PBP; BOOT=boot.shr нового экспорта, по умолчанию собирается)
# ЗЕЛЁНЫЙ: EBOOT + boot.shr (страница логотипа рассеяна в 5650) — tests/title/title_check.py.
# КРАСНЫЙ: EBOOT -DTITLE_PULSE_OLD=1 -DTITLE_DITHER_OLD=1 + boot.shr с UI_LOGO_FS_OLD=1 (прежнее) обязан упасть (сетка 4x4);
# КРАСНЫЙ-2: новый EBOOT (без дизеринга) + прежний boot.shr — ступени 5650 (ровные полосы) обязаны быть пойманы.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; OUT=build/gates/405; mkdir -p "$OUT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
EB="${1:-viewer/build/EBOOT.PBP}"
[ -f "$EB" ] || { echo "FAIL: нет $EB"; exit 2; }
if [ -z "${BOOT:-}" ]; then BOOT="$OUT/boot_new.shr"; "$PY" tools/load_export.py --pack boot --out "$BOOT" > "$OUT/boot_new.txt" 2>&1 || { echo "FAIL: экспорт boot"; exit 2; }; fi
UI_LOGO_FS_OLD=1 "$PY" tools/load_export.py --pack boot --out "$OUT/boot_old.shr" > "$OUT/boot_old.txt" 2>&1 || { echo "FAIL: экспорт boot (прежний)"; exit 2; }
psp-cmake -S viewer -B "$OUT/red_build" -DCMAKE_C_FLAGS="-DTITLE_PULSE_OLD=1 -DTITLE_DITHER_OLD=1" > "$OUT/red_cmake.txt" 2>&1 &&
  cmake --build "$OUT/red_build" > "$OUT/red_build.txt" 2>&1 || { echo "FAIL: красная сборка не собралась ($OUT/red_build.txt)"; exit 2; }
echo "EBOOT $(shasum -a 256 "$EB" | cut -c1-8); boot.shr $(shasum -a 256 "$BOOT" | cut -c1-8) (прежний $(shasum -a 256 "$OUT/boot_old.shr" | cut -c1-8))"
run() {   # имя EBOOT boot.shr -> папка прогона
  local d="$OUT/$1"; rm -rf "$d"; mkdir -p "$d"; cp "$2" "$d/EBOOT.PBP"; cp "$3" "$d/boot.shr"
  local log; log=$(SMOKE_HEADLESS=1 SMOKE_SCN="$ROOT/tests/title/title_scenario.txt" tools/smoke.sh "$d" 2>&1)
  echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
}
G=$(run green "$EB" "$BOOT"); R=$(run red "$OUT/red_build/EBOOT.PBP" "$OUT/boot_old.shr"); R2=$(run red2 "$EB" "$OUT/boot_old.shr")
"$PY" tests/title/title_check.py "$G" > "$OUT/green.txt" 2>&1; rg=$?
"$PY" tests/title/title_check.py "$R" --expect-fail > "$OUT/red.txt" 2>&1; rr=$?
"$PY" tests/title/title_check.py "$R2" --expect-fail > "$OUT/red2.txt" 2>&1; rr2=$?
grep -q "ступени" "$OUT/red2.txt" || rr2=1
echo "зелёный: $(head -1 "$OUT/green.txt")"; tail -n +2 "$OUT/green.txt"
echo "красный (прежнее): $(head -1 "$OUT/red.txt")"; tail -n +2 "$OUT/red.txt" | grep -E "пульс|кадр title"
echo "красный-2 (без дизеринга, прежняя страница): $(head -1 "$OUT/red2.txt")"; tail -n +2 "$OUT/red2.txt" | grep -E "кадр title"
echo "снимки: ${G#$ROOT/}/title.png (зелёный), ${R#$ROOT/}/title.png (красный), ${R2#$ROOT/}/title.png (красный-2)"
if [ $rg -eq 0 ] && [ $rr -eq 0 ] && [ $rr2 -eq 0 ]; then echo "ИТОГ: PASS (пульс как PS2; свечение без ступеней и сетки; красный пойман)"; exit 0; fi
echo "ИТОГ: FAIL (зелёный rc=$rg, красный пойман=$([ $rr -eq 0 ] && echo да || echo НЕТ), красный-2 пойман=$([ $rr2 -eq 0 ] && echo да || echo НЕТ))"; exit 1
