#!/bin/bash
# Гейт №928 (ориентиры дали): L6, пирс C7-6, взгляд на холм с обсерваторией (−388;228) с высоты 36 м над пирсом: силуэт ориентира виден — пикселей, отличающихся между «flag hzlm 1» и «flag hzlm 0», больше PX_MIN (200);
# красное: тот же прогон со старым horizon.shr L6 (без ориентиров) обязан дать меньше — 0.
#   tests/horizon/lm928.sh EBOOT НАБОР horizon_с_ориентирами.shr horizon_старый.shr     (SMOKE_HOME — свой HOME эмулятора)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
[ $# -ge 4 ] || { echo "использование: $0 EBOOT НАБОР horizon_new.shr horizon_old.shr"; exit 2; }
EB=$1; SET=$2; HN=$3; HO=$4; T="${TMPDIR:-/tmp}/lm928.$$"; mkdir -p "$T"; trap 'rm -rf "$T"' EXIT
cat > "$T/scn.txt" <<'SC'
wait 12
scene LOAD
flag golevel 6
wait 40
flag cfgdefaults 1
scene FOOT
wait 6
flag stop
scene PIER
foot -417 -50 0.1
waitload 25
wait 3
cam -417 -30 -50 0.104 0.10 0.995
wait 3
flag hzlm 1
wait 3
shot lm_on
flag hzlm 0
wait 3
shot lm_off
end
SC
px=()
for mode in new old; do
  H=$HN; [ $mode = old ] && H=$HO
  R="$T/pk_$mode"; cp -cR "$SET" "$R" 2>/dev/null || cp -R "$SET" "$R"; cp "$EB" "$R/EBOOT.PBP"; cp "$H" "$R/l6/horizon.shr"
  cp "$T/scn.txt" "$R/scenario.txt"; rm -f "$R/smoke.txt"; touch "$R/smokelog"; mkdir -p "$T/out_$mode"
  python3 tools/smoke_headless.py "$R" "$T/out_$mode" 700 >/dev/null 2>&1; rm -rf "$R"
  n=$(python3 - "$T/out_$mode" <<'PY'
import sys, numpy as np
from PIL import Image
d = sys.argv[1]; a = np.array(Image.open(f'{d}/lm_on.png').convert('RGB')).astype(int); b = np.array(Image.open(f'{d}/lm_off.png').convert('RGB')).astype(int)
print(int((np.abs(a - b)[60:215].sum(-1) > 40).sum()))
PY
)
  echo "$mode: пикселей силуэта ориентиров $n"; px+=("${n:-0}")
done
[ "${px[0]}" -gt "${PX_MIN:-200}" ] && [ "${px[1]}" -lt 20 ] && { echo "ГЕЙТ №928: PASS (силуэт виден, красный на старом файле)"; exit 0; }
echo "ГЕЙТ №928: FAIL"; exit 1
