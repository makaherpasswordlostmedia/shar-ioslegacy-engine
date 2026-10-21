#!/bin/bash
# Гейт №671: однострочный бабл задания у верха (как до №640, PS2 и панель Роба). Три сборки: new, BUBBLE_VCENTER1_OLD (красная, прежнее №640), BUBBLE_EVEN_OLD (эталон «до №640»).
#   tests/ui/b671_gate.sh   (нужны pspdev/.venv-ссылки на главное дерево; эмулятор безголовый через scen.py, свой HOME на сборку)
set -u; ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
SCEN=~/.claude/skills/shar-level-polish/scripts/scen.py; OUT="$ROOT/build/b671"; V="new BUBBLE_VCENTER1_OLD BUBBLE_EVEN_OLD"
for v in $V; do [ "${B671_REUSE:-0}" = 1 ] && [ -f "$OUT/gb/$v/EBOOT.PBP" ] && continue
  ( mkdir -p "$OUT/gb/$v" && cd "$OUT/gb/$v" && O=""; [ $v != new ] && O="-DSHAR_OPT=-D$v=1"; psp-cmake -S "$ROOT/viewer" -B . $O >/dev/null 2>&1 && cmake --build . -j4 >/dev/null 2>&1 ) & done; wait
for v in $V; do ( SCEN_HOME="$OUT/gb/home_$v" SCEN_EBOOT="$OUT/gb/$v/EBOOT.PBP" timeout 900 python3 "$SCEN" "b671g_$v" tests/ui/b671_bubble_scenario.txt 2>&1 | sed -n 's/^dir \([^ ]*\) .*/\1/p' > "$OUT/dir_$v" ) & done; wait
D() { cat "$OUT/dir_$1"; }
python3 tests/ui/b671_check.py "$(D new)" "$(D BUBBLE_EVEN_OLD)" && n=ЗЕЛЁНЫЙ || n="КРАСНЫЙ (плохо)"
python3 tests/ui/b671_check.py --red "$(D BUBBLE_VCENTER1_OLD)" "$(D BUBBLE_EVEN_OLD)" && o="красный (как нужно)" || o="ЗЕЛЁНЫЙ (красный не пойман)"
echo "№671 бабл у верха: новый $n; BUBBLE_VCENTER1_OLD $o"; [ "$n" = ЗЕЛЁНЫЙ ] && [ "${o:0:7}" = красный ]
