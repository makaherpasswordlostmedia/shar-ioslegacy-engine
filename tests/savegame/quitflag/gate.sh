#!/bin/bash
# Гейт QUIT -> LOAD GAME (Sonnet-Типографика, 16.10): новый код — SVOPEN mode=load confirm=0 (предупреждения «progress to be lost» нет), -DQUIT_NOGAME_OLD=1 — confirm=1 (красный).
# Безголовый эмулятор (scen.py, свой HOME), две сборки движка. Нужно: pspdev в корне дерева, данные главного дерева.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; cd "$ROOT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
OUT="${QF_OUT:-$ROOT/build/quitflag}"; mkdir -p "$OUT"; SCEN=~/.claude/skills/shar-level-polish/scripts/scen.py
for v in new QUIT_NOGAME_OLD; do
  [ "${QF_REUSE:-0}" = 1 ] && [ -f "$OUT/gb/$v/EBOOT.PBP" ] && continue
  ( mkdir -p "$OUT/gb/$v" && cd "$OUT/gb/$v" && OPT=""; [ "$v" != new ] && OPT="-DSHAR_OPT=-D$v=1"
    psp-cmake -S "$ROOT/viewer" -B . $OPT >/dev/null 2>&1 && cmake --build . -j4 >/dev/null 2>&1 ) &
done; wait
rc=0
for v in new QUIT_NOGAME_OLD; do
  [ -f "$OUT/gb/$v/EBOOT.PBP" ] || { echo "FAIL: нет сборки $v"; exit 2; }
  d=$(SCEN_HOME="$OUT/gb/home_$v" SCEN_EBOOT="$OUT/gb/$v/EBOOT.PBP" timeout 1200 python3 "$SCEN" "qf${$}_$v" tests/savegame/quitflag/scenario.txt 2>&1 | sed -n 's/^dir \([^ ]*\) .*/\1/p')
  l=$(grep -h "^SVOPEN mode=load" "$d"/smoke.txt 2>/dev/null | tail -1)
  echo "$v: dir=$d  $l"
  c=$(echo "$l" | sed -n 's/.*confirm=\([0-9]\).*/\1/p')
  if [ "$v" = new ]; then [ "$c" = 0 ] || { echo "  КРАСНЫЙ (плохо): ждали confirm=0, получили '${c:-нет строки}'"; rc=1; }
  else [ "$c" = 1 ] && echo "  красный (как нужно): предупреждение есть" || { echo "  красный не пойман ('${c:-нет строки}')"; rc=1; }; fi
done
# сценарий B (сохранение на карте): SVOPEN confirm + кадры b_after_slot старого и нового должны различаться (старое — окно предупреждения)
for v in new QUIT_NOGAME_OLD; do
  d=$(SCEN_HOME="$OUT/gb/home_$v" SCEN_EBOOT="$OUT/gb/$v/EBOOT.PBP" timeout 1500 python3 "$SCEN" "qfb${$}_$v" tests/savegame/quitflag/scnB.txt 2>&1 | sed -n 's/^dir \([^ ]*\) .*/\1/p')
  eval "DB_$v=$d"; l=$(grep -h "^SVOPEN mode=load" "$d"/smoke.txt 2>/dev/null | tail -1); c=$(echo "$l" | sed -n 's/.*confirm=\([0-9]\).*/\1/p')
  echo "B $v: dir=$d  $l  slots в журнале: $(echo "$l" | sed -n 's/.*slots=//p')"
  if [ "$v" = new ]; then [ "$c" = 0 ] || { echo "  B КРАСНЫЙ (плохо): confirm='${c:-нет}'"; rc=1; }
  else [ "$c" = 1 ] && echo "  B красный (как нужно)" || { echo "  B красный не пойман ('${c:-нет}')"; rc=1; }; fi
done
python3 - "$DB_new/b_after_slot.png" "$DB_QUIT_NOGAME_OLD/b_after_slot.png" <<'PY' || rc=1
import sys, numpy as np
from PIL import Image
a, b = (np.asarray(Image.open(p).convert('RGB')).astype(int) for p in sys.argv[1:3])
d = float(np.abs(a - b).mean()); print(f'  B кадры b_after_slot новый/старый: средняя разница {d:.2f} (>2 — окно предупреждения есть только у старого)'); sys.exit(0 if d > 2 else 1)
PY
[ $rc = 0 ] && echo "ИТОГ: PASS (новое зелёное, старое красное)" || echo "ИТОГ: FAIL"; exit $rc
