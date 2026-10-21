#!/bin/bash
# Гейт замеров чёрного ящика (исследование 03.10 П1–П3, docs/ИССЛЕДОВАНИЕ_ПАМЯТЬ_ME_ПОДГРУЗКА_2026-10-03.md): короткая езда
# в безголовом эмуляторе (~/.claude/skills/shar-level-polish/scripts/scen.py), затем в blackbox.txt и smoke.txt:
#   (1) шапка «vol <код> <КБ>K» — проба volatile выполнена (код не 1 — значение «не пробовали»);
#   (2) smoke.txt «BBCPU ok=1f» — найдены все пять потоков (user_main, loader, audio_mix, audio_io, bbw); доли процессора
#       эмулятор не считает (runClocks 0) — числа проверяются только на PSP;
#   (3) строки ящика несут поля «cpu a/b/c/d/e» и «cell N Mms >100:K miss F», клеток за прогон больше нуля.
# Красный: сборка с -DBB_PROBES_OFF (замеры выключены) обязана упасть по (1) и (2).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
OUT=build/gates/blackbox; mkdir -p "$OUT"; PY=.venv/bin/python; SCEN=~/.claude/skills/shar-level-polish/scripts/scen.py
printf 'scene probes\nflag msn\nwait 4\npress up 6\nwait 3\npress up 6\nwait 3\nend\n' > "$OUT/scenario.txt"
check() {   # $1 — папка прогона -> 0 зелёный
  local d="$1" bad=0
  head -1 "$d/blackbox.txt" | grep -q -E ' vol (0|-[0-9]+) [0-9]+K' || { echo "  нет пробы volatile в шапке: $(head -1 "$d/blackbox.txt" | cut -c1-120)"; bad=1; }
  grep -q 'BBCPU ok=1f' "$d/smoke.txt" || { echo "  потоки не найдены (нет BBCPU ok=1f)"; bad=1; }
  grep ' heap ' "$d/blackbox.txt" | grep -q -E 'cpu [0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+  cell [0-9]+ [0-9]+ms >100:[0-9]+ miss [0-9]+' || { echo "  нет полей cpu/cell в строках ящика"; bad=1; }
  local n; n=$(grep ' heap ' "$d/blackbox.txt" | sed -E 's/.*  cell ([0-9]+) .*/\1/' | awk '{s+=$1} END{print s+0}')
  [ "$n" -gt 0 ] || { echo "  клеток за прогон 0"; bad=1; }
  echo "  клеток загружено за прогон: $n; шапка: $(head -1 "$d/blackbox.txt" | grep -o 'vol [-0-9]* [0-9]*K')"
  return $bad
}
clean() { find "$1" -maxdepth 1 -type f \( -name '*.shr' -o -name '*.bin' -o -name 'EBOOT.PBP' -o -name 'ballast' \) -delete; rm -rf "$1/audio" "$1/chars" "$1/movies" "$1/l2" "$1/l3" "$1/l4" "$1/l5" "$1/l6" "$1/l7" 2>/dev/null; }
# красный: замеры выключены
rm -rf build/probes_off; cmake -S viewer -B build/probes_off -DCMAKE_TOOLCHAIN_FILE="$ROOT/pspdev/psp/share/pspdev.cmake" -DCMAKE_C_FLAGS=-DBB_PROBES_OFF > "$OUT/off_cmake.txt" 2>&1 &&
  cmake --build build/probes_off -j6 > "$OUT/off_build.txt" 2>&1 || { echo "FAIL: сборка красного"; exit 1; }
SCEN_EBOOT="$ROOT/build/probes_off/EBOOT.PBP" SCEN_HOME="$ROOT/$OUT/home" "$PY" "$SCEN" probes_off "$OUT/scenario.txt" > "$OUT/off_run.txt" 2>&1
red=0; if check build/twins/scen/full/probes_off > "$OUT/red.txt"; then echo "КРАСНЫЙ НЕ ПОЙМАН: замеры выключены, а гейт зелёный"; else echo "красный (BB_PROBES_OFF): упал, как должен"; red=1; fi
clean build/twins/scen/full/probes_off
# зелёный: обычная сборка движка
SCEN_EBOOT="$ROOT/viewer/build/EBOOT.PBP" SCEN_HOME="$ROOT/$OUT/home" "$PY" "$SCEN" probes "$OUT/scenario.txt" > "$OUT/on_run.txt" 2>&1
if check build/twins/scen/full/probes > "$OUT/green.txt"; then g=1; echo "зелёный: $(tail -1 "$OUT/green.txt")"; else g=0; echo "НЕ ЗЕЛЁНЫЙ:"; cat "$OUT/green.txt"; fi
clean build/twins/scen/full/probes
[ $red = 1 ] && [ $g = 1 ] && { echo "PASS: красный пойман, зелёный OK"; exit 0; }
echo "FAIL: красный $red, зелёный $g"; exit 1
