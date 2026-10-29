#!/bin/bash
# Конвейер tools/night913 (gen.py -> run.py -> analyze.py -> zones.py) на общем раннере tools/emu_run.sh: прогон без окна-хозяина и без папки ~/.claude/jobs/shar1023.
# Игрушечная зона: L1 одна клетка (точка у P061), остальные уровни пусты. Условия: gen выдал 1 точку и кусок сценария; run дал out_NL1_00/DONE; analyze нашёл 1 точку; zones записал hzzone_l1.bin.
# Красный: тот же run.py с несуществующим EBOOT -> DONE нет (прогон не мог пройти, гейт это видит).
#   night913_smoke.sh [EBOOT]   без аргумента — viewer/build_t60/EBOOT.PBP; последняя строка PASS или FAIL
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; cd "$ROOT"
EB=${1:-$ROOT/viewer/build_t60/EBOOT.PBP}; [ -f "$EB" ] || tour_build build_t60 || { echo "FAIL: нет EBOOT"; exit 2; }
J=${W:-$ROOT/build/gates/night913}; rm -rf "$J"; mkdir -p "$J/hz913" "$J/night913"; fail=0
python3 - "$J" <<'PYEOF'
import struct, sys
J = sys.argv[1]
for L in range(1, 8):
    hdr = b'HZZN' + struct.pack('<II', 1 if L == 1 else 0, 1 if L == 1 else 0) + struct.pack('<fff', 276.0, -511.0, 1.0)
    open('%s/hz913/hzzone_l%d.bin' % (J, L), 'wb').write(hdr + (bytes([0]) if L == 1 else b''))
PYEOF
(cd "$J" && python3 "$ROOT/tools/night913/gen.py") > "$J/gen.txt" 2>&1; cat "$J/gen.txt" | head -3
[ -f "$J/night913/sc/L1_00.txt" ] && grep -q '^scene b_0_0_0' "$J/night913/sc/L1_00.txt" || { echo "КРАСНОЕ: gen.py не выдал кусок L1_00"; fail=1; }
NIGHT913_DIR=$J EB=$EB EMU_MINE=1 EMU_OWNER=${EMU_OWNER:-gates} python3 tools/night913/run.py; tail -2 "$J/night913/progress.log"
[ -f "$J/out_NL1_00/DONE" ] || { echo "КРАСНОЕ: run.py не довёл прогон до DONE"; fail=1; }
NIGHT913_DIR=$J python3 tools/night913/analyze.py | tail -1 | tee "$J/an.txt"; grep -q '^1 точек' "$J/an.txt" || { echo "КРАСНОЕ: analyze.py не нашёл точку"; fail=1; }
NIGHT913_DIR=$J python3 tools/night913/zones.py | head -2; [ -f "$J/night913/hzzone_l1.bin" ] || { echo "КРАСНОЕ: zones.py не записал таблицу"; fail=1; }
J2=$J/red; mkdir -p "$J2/night913/sc"; cp "$J/night913/sc/L1_00.txt" "$J2/night913/sc/"
NIGHT913_DIR=$J2 EB=$J/нет_такого.PBP EMU_MINE=1 EMU_OWNER=${EMU_OWNER:-gates} python3 tools/night913/run.py; echo "  красный (EBOOT не существует): $(tail -1 "$J2/night913/progress.log")"
[ -f "$J2/out_NL1_00/DONE" ] && { echo "КРАСНЫЙ НЕ ПОЙМАН: DONE без EBOOT"; fail=1; }
[ $fail = 0 ] && echo "PASS (night913: gen, run, analyze, zones на общем раннере; красный пойман)" || echo "FAIL (night913)"; exit $fail
