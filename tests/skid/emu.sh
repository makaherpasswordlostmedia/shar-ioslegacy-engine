#!/bin/bash
# Правка Роба 249: следы шин в безголовом эмуляторе (~/.claude/skills/shar-level-polish/scripts/scen.py, без окна и звука).
#   tests/skid/emu.sh [EBOOT]   по умолчанию viewer/build/EBOOT.PBP; рядом — данные build/ (fx.shr со skid.bmp: tools/fx_pack.py)
# Сценарий tests/skid/scenario.txt: улица у Kwik-E-Mart, газ с места, резкий тормоз, стоп. Красный — тот же EBOOT с «flag skidoff»
# (прежнее: следов нет) обязан упасть; зелёный — следы в журнале (SKID quads > 0) и на снимках (tests/skid/emu_check.py).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/gates/skid; mkdir -p "$OUT"; PY=.venv/bin/python; SCEN=~/.claude/skills/shar-level-polish/scripts/scen.py
EBOOT="${1:-$ROOT/viewer/build/EBOOT.PBP}"; RUNS=build/twins/scen/full
grep -v '^#' tests/skid/scenario.txt > "$OUT/scenario.txt"
# текстура следов (skid.bmp) — в fx.shr уровня 1 с правки 249 (tools/fx_pack.py SKID_TEX); старый build/fx.shr — собрать рядом, build/ не трогать
if ! grep -aq 'skid.bmp' build/fx.shr 2>/dev/null; then
  "$PY" tools/fx_pack.py --out "$ROOT/$OUT/fx.shr" > "$OUT/fx_pack.txt" 2>&1 || { echo "FAIL: tools/fx_pack.py"; exit 1; }
  export SCEN_OVERRIDE="fx.shr=$ROOT/$OUT/fx.shr${SCEN_OVERRIDE:+,$SCEN_OVERRIDE}"; echo "fx.shr без skid.bmp — собран $OUT/fx.shr"; fi
{ echo 'flag skidoff'; cat "$OUT/scenario.txt"; } > "$OUT/scenario_red.txt"
clean() { find "$1" -maxdepth 1 -type f \( -name '*.shr' -o -name '*.bin' -o -name '*.bmp' -o -name '*.msn' -o -name '*.prx' -o -name 'EBOOT.PBP' -o -name 'ballast' \) -delete
          rm -rf "$1/audio" "$1/chars" "$1/movies" "$1/l2" "$1/l3" "$1/l4" "$1/l5" "$1/l6" "$1/l7" 2>/dev/null; }
SCEN_EBOOT="$EBOOT" SCEN_HOME="$ROOT/$OUT/home" "$PY" "$SCEN" skid_red "$OUT/scenario_red.txt" > "$OUT/red_run.txt" 2>&1
SCEN_EBOOT="$EBOOT" SCEN_HOME="$ROOT/$OUT/home" "$PY" "$SCEN" skid_green "$OUT/scenario.txt" > "$OUT/green_run.txt" 2>&1
for n in red green; do cp "$RUNS/skid_$n/smoke.txt" "$OUT/${n}_smoke.txt" 2>/dev/null; for s in skid_brake skid_after skid_view; do cp "$RUNS/skid_$n/$s.png" "$OUT/${n}_$s.png" 2>/dev/null; done; done
# красный контроль самой проверки: красный против красного обязан упасть (следов на снимках нет)
red=0; if "$PY" tests/skid/emu_check.py "$RUNS/skid_red" "$RUNS/skid_red" > "$OUT/red.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: без следов проверка прошла"
else echo "красный (flag skidoff): упал, как должен — $(grep -c -E 'ЗЕЛЁНЫЙ|не видно' "$OUT/red.txt") замечаний"; red=1; fi
"$PY" tests/skid/emu_check.py "$RUNS/skid_green" "$RUNS/skid_red" > "$OUT/green.txt" 2>&1; g=$?; cat "$OUT/green.txt"
clean "$RUNS/skid_red"; clean "$RUNS/skid_green"
[ $red = 1 ] && [ $g = 0 ] && { echo "PASS: красный пойман, зелёный OK (снимки: $OUT/*_skid_*.png)"; exit 0; }
echo "FAIL: красный $red, зелёный $g"; exit 1
