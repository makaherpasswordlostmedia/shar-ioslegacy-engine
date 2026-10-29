#!/bin/bash
# №408: камера сбоку на прыжке через дом L1 в безголовом эмуляторе (EBOOT + пакет carzone-l1.shr из DIR).
# Сценарий tests/camera/carzone_scenario.txt: famil_v с газом прямо на трамплин jumpzone17. Зелёный: движок включает рельс r1_cam1
# (строка CARZONE) на скорости ≥ 20 м/с и выключает через 1,2–2,0 с (PS2, запись original-house-native2: 932 → 1016 = 1,68 с).
#   tests/camera/carzone_emu.sh [DIR]          зелёный (DIR по умолчанию build/camstage)
#   tests/camera/carzone_emu.sh --red [DIR]    красный: «flag carzoneoff 1» — как до №408 (камеры зон у машины нет), обязан упасть
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; RED=0; [ "${1:-}" = --red ] && { RED=1; shift; }
DIR="${1:-$ROOT/build/camstage}"; SCN="$ROOT/tests/camera/carzone_scenario.txt"
if [ $RED = 1 ]; then T=$(mktemp /tmp/carzone_red.XXXX); { echo "flag carzoneoff 1"; cat "$SCN"; } > "$T"; SCN="$T"; fi
SHIP_LEVELS="${SHIP_LEVELS-2 3 4 5 6 7}" SMOKE_HEADLESS=1 SMOKE_SCN="$SCN" "$ROOT/tools/smoke.sh" "$DIR" >/dev/null 2>&1
D=$(ls -td "$ROOT"/build/smoke/2* | head -1)
/opt/homebrew/bin/python3 - "$D/smoke.txt" <<'PY'
import re, sys
L = open(sys.argv[1], errors='replace').read().splitlines()
ev = [dict(re.findall(r'(\w+)=(\S+)', l)) for l in L if l.startswith('CARZONE t=')]
on = next((e for e in ev if e['cam'] == 'r1_cam1'), None)
off = next((e for e in ev if on and e['cam'] == '-' and float(e['t']) > float(on['t'])), None)
end = any(l.strip() == 'END' for l in L)
dur = float(off['t']) - float(on['t']) if on and off else None
ok = end and on is not None and float(on['v']) >= 20. and dur is not None and 1.2 <= dur <= 2.0
print(f"{'PASS' if ok else 'FAIL'} carzone emu: r1_cam1 {'вкл t=' + on['t'] + ' v=' + on['v'] if on else 'не включилась'}, "
      f"держит {dur if dur is None else round(dur, 2)} с (PS2 1,68), END={end} ({sys.argv[1]})")
sys.exit(0 if ok else 1)
PY
