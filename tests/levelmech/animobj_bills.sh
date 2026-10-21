#!/bin/bash
# Гейт 04.10: квады свечения анимированных объектов уровня (красное пульсирующее кольцо у выключателя грузовика Duff,
# кольца звонков, огни пульта АЭС и ещё ~130 типов на уровнях 1–7) — tools/animobj_export.py.
# 1) данные (tests/levelmech/animobj_bills_check.py, диск Роба, экспорт без конвертера), уровни LEVELS (по умолчанию 1-7):
#    красные AO_BILL_CENTER_OLD=1 (экземпляр в начале координат) и AO_BILL_FRAMES_OLD=1 (кадр BQG стоит) обязаны упасть;
# 2) игра (безголовый эмулятор, ~/.claude/skills/shar-level-polish/scripts/scen.py, флаг spbillnear): Гомер у грузовика
#    Duff (m2 этап 8, как запись PS2 10:02) — у выключателя (203.2, 5.0, 293.0) квады типа видны (SPBILL ok=1) и меняются
#    по кадрам (пульс). Уровень — LEVEL_SHR (по умолчанию build/level.shr; собирается tools/build_level.sh), красный —
#    RED_LEVEL_SHR (уровень того же кода с AO_BILL_CENTER_OLD=1), если задан.
#   tests/levelmech/animobj_bills.sh [--data]      --data — только пункт 1
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/gates/animobj_bills; mkdir -p "$OUT"; PY=.venv/bin/python; SCEN=~/.claude/skills/shar-level-polish/scripts/scen.py
EB="${EBOOT:-$ROOT/viewer/build/EBOOT.PBP}"; LV="${LEVELS:-1-7}"; FAILS=0
red() { if env "$1" "$PY" tests/levelmech/animobj_bills_check.py --levels "$LV" > "$OUT/red_$1.txt" 2>&1; then
          echo "КРАСНЫЙ НЕ ПОЙМАН: $1"; FAILS=$((FAILS + 1)); else echo "красный $1: $(grep -m1 FAIL "$OUT/red_$1.txt" | cut -c1-140)"; fi; }
red AO_BILL_CENTER_OLD=1; red AO_BILL_FRAMES_OLD=1
if "$PY" tests/levelmech/animobj_bills_check.py --levels "$LV" > "$OUT/green.txt" 2>&1; then echo "зелёный данные: $(grep '^итого' "$OUT/green.txt")"
else grep FAIL "$OUT/green.txt" | head -5; FAILS=$((FAILS + 1)); fi
if [ "${1:-}" != --data ]; then
  scn() { printf '%s\n' 'flag msn' 'wait 2' 'flag msnmainat 208' 'wait 3' 'press cross' 'wait 2' 'press cross' 'wait 2' \
            'foot 201 288 0.4' 'wait 2.5' 'shot p0' 'flag spbillnear 8' 'wait 0.33' 'shot p1' 'flag spbillnear 8' 'end'; }
  emu() {   # $1 имя, $2 level.shr -> 0, если у выключателя есть видимые пульсирующие квады
    scn > "$OUT/sw.txt"
    SCEN_EBOOT="$EB" SCEN_HOME="$ROOT/$OUT/home" SCEN_OVERRIDE="level.shr=$2" "$PY" "$SCEN" "aob_$1" "$OUT/sw.txt" > "$OUT/emu_$1.txt" 2>&1
    "$PY" - "build/twins/scen/full/aob_$1/smoke.txt" <<'EOF'
import re, sys
rows = [l for l in open(sys.argv[1], errors='replace') if l.startswith('SPBILL')]
near = [l for l in rows if (m := re.search(r'pos=([-\d.]+),([-\d.]+),([-\d.]+)', l)) and abs(float(m[1]) - 203.17) + abs(float(m[3]) - 293.0) < 1.0]
ok = [l for l in near if ' ok=1 ' in l]
cols = {re.search(r'col=(\w+)', l)[1] for l in ok}
print(f'квадов у выключателя: {len(near)}, видимых {len(ok)}, разных цветов по кадрам {len(cols)}')
sys.exit(0 if len(ok) >= 2 and len(cols) >= 2 else 1)
EOF
  }
  L="${LEVEL_SHR:-$ROOT/build/level.shr}"
  if [ -n "${RED_LEVEL_SHR:-}" ]; then
    if emu red "$RED_LEVEL_SHR" > "$OUT/emu_red_check.txt"; then echo "КРАСНЫЙ НЕ ПОЙМАН: игра на $RED_LEVEL_SHR"; FAILS=$((FAILS + 1))
    else echo "красный игра ($RED_LEVEL_SHR): $(cat "$OUT/emu_red_check.txt")"; fi
  fi
  if emu green "$L" > "$OUT/emu_green_check.txt"; then echo "зелёный игра ($L): $(cat "$OUT/emu_green_check.txt")"
  else echo "FAIL игра ($L): $(cat "$OUT/emu_green_check.txt") — уровень собран прежним экспортом? LEVEL=1 tools/build_level.sh"; FAILS=$((FAILS + 1)); fi
fi
[ $FAILS -eq 0 ] && { echo "PASS animobj_bills"; exit 0; }
echo "FAIL animobj_bills ($FAILS)"; exit 1
