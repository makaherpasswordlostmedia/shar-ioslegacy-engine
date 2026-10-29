#!/bin/bash
# Гейт правки Роба 241 (кольцо Hit & Run мигает и красится, как в оригинале). Хост: tests/ui/anim.py — зелёный, --mode pre241 и
# --mode old обязаны быть красными. Эмулятор без окна и без звука (tests/hnr/hud.py): настоящая шкала игры -> кольцо (UIHNR).
# КРАСНЫЕ: тот же EBOOT с прежним кодом кольца (flag uihnrtraceold) и EBOOT с -DHNR_HUD_ALARM_LATCH=1 (красно-синее с полной
# шкалы, ещё до полиции). ЗЕЛЁНЫЙ: viewer/build/EBOOT.PBP (или HUD_EBOOT). Итог: build/hnr/hud_*.txt (или HUD_OUT)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="${PY:-$ROOT/.venv/bin/python}"; OUT="${HUD_OUT:-build/hnr}"; mkdir -p "$OUT"
export PSPDEV="${PSPDEV:-$ROOT/pspdev}"; export PATH="$PSPDEV/bin:$PATH"
"$PY" tests/ui/anim.py > "$OUT/hud_host.txt"; h=$?
"$PY" tests/ui/anim.py --mode pre241 > "$OUT/hud_host_pre241.txt"; hp=$?
"$PY" tests/ui/anim.py --mode old > "$OUT/hud_host_old.txt"; ho=$?
echo "хост: зелёный rc=$h, pre241 rc=$hp, old rc=$ho"
psp-cmake -S viewer -B "$OUT/hud_red_build" -DCMAKE_C_FLAGS="-DHNR_HUD_ALARM_LATCH=1" > "$OUT/hud_red_cmake.txt" 2>&1 &&
  cmake --build "$OUT/hud_red_build" > "$OUT/hud_red_build.txt" 2>&1 || { echo "FAIL: красная сборка не собралась"; exit 2; }
"$PY" tests/hnr/hud.py green "${HUD_EBOOT:-viewer/build/EBOOT.PBP}" > "$OUT/hud_green.txt" 2>&1; g=$?; tail -1 "$OUT/hud_green.txt"
"$PY" tests/hnr/hud.py oldui "${HUD_EBOOT:-viewer/build/EBOOT.PBP}" > "$OUT/hud_oldui.txt" 2>&1; r1=$?; tail -1 "$OUT/hud_oldui.txt"
"$PY" tests/hnr/hud.py latch "$OUT/hud_red_build/EBOOT.PBP" > "$OUT/hud_latch.txt" 2>&1; r2=$?; tail -1 "$OUT/hud_latch.txt"
if [ $h -eq 0 ] && [ $hp -ne 0 ] && [ $ho -ne 0 ] && [ $g -eq 0 ] && [ $r1 -ne 0 ] && [ $r2 -ne 0 ]; then
  echo "PASS: хост зелёный (pre241 и old красные), эмулятор зелёный, красные пойманы: прежнее кольцо, красно-синее до полиции"; exit 0; fi
echo "FAIL: хост $h/$hp/$ho, эмулятор зелёный rc=$g, красные rc=$r1/$r2 (ждём 0/≠0/≠0, 0, ≠0/≠0)"; exit 1
