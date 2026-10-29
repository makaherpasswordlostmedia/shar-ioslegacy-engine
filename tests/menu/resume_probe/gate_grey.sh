#!/bin/bash
# Гейт серых пунктов главного меню (Sonnet-Типографика, 16.10): на пустой карте (RESUME GAME скрыт, PS2) ✕ на SCRAP BOOK / BONUS GAME = только locked_out, без облёта (FEFLY нет).
# Новый код: locked_out x3, FEFLY 0. -DRESUME_LOCK_OLD=1: FEFLY x2 (RESUME GAME item=5, SCRAP BOOK item=1; у BONUS GAME облёта нет в данных, feFly не находит отрезок) — красный. Контроль LOAD GAME (scn_probe.txt): облёт к видику и «No save data» остаются в обеих сборках.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; cd "$ROOT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
OUT="${GL_OUT:-$ROOT/build/greylock}"; mkdir -p "$OUT"; SCEN=~/.claude/skills/shar-level-polish/scripts/scen.py
for v in new RESUME_LOCK_OLD; do
  [ "${GL_REUSE:-0}" = 1 ] && [ -f "$OUT/gb/$v/EBOOT.PBP" ] && continue
  ( mkdir -p "$OUT/gb/$v" && cd "$OUT/gb/$v" && OPT=""; [ "$v" != new ] && OPT="-DSHAR_OPT=-D$v=1"
    psp-cmake -S "$ROOT/viewer" -B . $OPT >/dev/null 2>&1 && cmake --build . -j4 >/dev/null 2>&1 ) &
done; wait
rc=0
for v in new RESUME_LOCK_OLD; do
  [ -f "$OUT/gb/$v/EBOOT.PBP" ] || { echo "FAIL: нет сборки $v"; exit 2; }
  d=$(SCEN_HOME="$OUT/gb/home_$v" SCEN_EBOOT="$OUT/gb/$v/EBOOT.PBP" timeout 1500 python3 "$SCEN" "gl${$}_$v" tests/menu/resume_probe/scn_grey.txt 2>&1 | sed -n 's/^dir \([^ ]*\) .*/\1/p')
  lk=$(grep -c "name=locked_out" "$d"/smoke.txt 2>/dev/null); fl=$(grep -c "^FEFLY " "$d"/smoke.txt 2>/dev/null)
  echo "серые $v: dir=$d locked_out=$lk FEFLY=$fl"
  if [ "$v" = new ]; then { [ "$lk" = 2 ] && [ "$fl" = 0 ]; } || { echo "  КРАСНЫЙ (плохо): ждали locked_out=2 FEFLY=0"; rc=1; }
  else { [ "$lk" = 2 ] && [ "$fl" = 1 ]; } && echo "  красный (как нужно): облёт на SCRAP BOOK" || { echo "  красный не пойман"; rc=1; }; fi
  c=$(SCEN_HOME="$OUT/gb/home_$v" SCEN_EBOOT="$OUT/gb/$v/EBOOT.PBP" timeout 1500 python3 "$SCEN" "glc${$}_$v" tests/menu/resume_probe/scn_probe.txt 2>&1 | sed -n 's/^dir \([^ ]*\) .*/\1/p')
  cf=$(grep "^FEFLY " "$c"/smoke.txt | sed -n 's/.*item=\([0-9]*\).*/\1/p' | tr '\n' ' '); sv=$(grep -c "^SVOPEN mode=load .*slots=E,E,E,E" "$c"/smoke.txt)
  echo "контроль LOAD $v: dir=$c FEFLY items=[$cf] SVOPEN пустая карта=$sv"
  if [ "$v" = new ]; then [ "$cf" = "0 " ] && [ "$sv" = 1 ] || { echo "  КОНТРОЛЬ LOAD: плохо (ждали только облёт item=0 к видику и один SVOPEN на пустой карте)"; rc=1; }; fi
done
[ $rc = 0 ] && echo "ИТОГ: PASS (новое зелёное, старое красное, LOAD GAME не тронут)" || echo "ИТОГ: FAIL"; exit $rc
