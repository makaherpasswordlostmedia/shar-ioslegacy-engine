#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
OUT=${1:-build/fe-audio/gate}
mkdir -p "$OUT/new" "$OUT/old" "$OUT/early"
FLAGS='-DAUDIO_HOST -O2 -Wall -Wno-misleading-indentation -Wno-unused-parameter -Wno-sign-compare -Iviewer'
cc $FLAGS tests/fe_audio/host.c viewer/fe_audio.c viewer/audio.c -lm -o "$OUT/host" 2>"$OUT/compile.log"
cc $FLAGS -DFE_AUDIO_OLD=1 tests/fe_audio/host.c viewer/fe_audio.c viewer/audio.c -lm -o "$OUT/host-old" 2>"$OUT/compile-old.log"
cc $FLAGS -DFE_AUDIO_PREPARE_OLD=1 tests/fe_audio/host.c viewer/fe_audio.c viewer/audio.c -lm -o "$OUT/host-early" 2>"$OUT/compile-early.log"
.venv/bin/python tools/fe_audio_export.py --out "$OUT/fe_audio.sap" --manifest "$OUT/source.json" >"$OUT/export.log"
.venv/bin/python tools/fe_audio_export.py --out "$OUT/repeat.sap" >"$OUT/repeat.log"
cmp "$OUT/fe_audio.sap" "$OUT/repeat.sap"
.venv/bin/python tests/fe_audio/source.py "$OUT/fe_audio.sap" >"$OUT/source.log"
"$OUT/host" build/ship_stage/audio/ "$OUT/fe_audio.sap" "$OUT/new" >"$OUT/native-new.log" 2>&1
.venv/bin/python tests/fe_audio/source.py "$OUT/fe_audio.sap" --raw "$OUT/new" --native-log "$OUT/native-new.log" >"$OUT/decode.log"
cmp "$OUT/new/FE_Gag_Nick.raw" "$OUT/new/FE_Gag_Nick-repeat.raw"
if "$OUT/host-old" build/ship_stage/audio/ "$OUT/fe_audio.sap" "$OUT/old" >"$OUT/native-old.log" 2>&1;then echo 'FAIL old passed';exit 1;fi
grep -q 'actual_backend_voice_starts FAIL' "$OUT/native-old.log"
if "$OUT/host-early" build/ship_stage/audio/ "$OUT/fe_audio.sap" "$OUT/early" >"$OUT/native-early.log" 2>&1;then echo 'FAIL early passed';exit 1;fi
grep -q 'prepare_two_seconds_silent FAIL' "$OUT/native-early.log"
.venv/bin/python - "$OUT" <<'PY'
import struct,sys
from pathlib import Path
p=Path(sys.argv[1]);b=bytearray((p/'fe_audio.sap').read_bytes());struct.pack_into('<H',b,64+48,32000);(p/'plant-rate.sap').write_bytes(b)
b=bytearray((p/'fe_audio.sap').read_bytes());b[2048:]=bytes(len(b)-2048);(p/'plant-data.sap').write_bytes(b)
s=(p/'native-new.log').read_text().replace('CLIP FE_Gag_Nick index=5 seg=-1','CLIP FE_Gag_Nick index=3 seg=-1');(p/'plant-route.log').write_text(s)
PY
for plant in rate data;do
 if .venv/bin/python tests/fe_audio/source.py "$OUT/plant-$plant.sap" >"$OUT/red-$plant.log";then echo "FAIL $plant plant passed";exit 1;fi
done
if .venv/bin/python tests/fe_audio/source.py "$OUT/fe_audio.sap" --native-log "$OUT/plant-route.log" >"$OUT/red-route.log";then echo 'FAIL route plant passed';exit 1;fi
grep -q 'matches_original_observer FAIL' "$OUT/red-route.log"
pspdev/bin/psp-gcc -std=gnu11 -O2 -Wall -Wno-misleading-indentation -Iviewer -Ipspdev/psp/sdk/include -Ipspdev/psp/include -D_PSP_FW_VERSION=600 -c viewer/fe_audio.c -o "$OUT/fe_audio-psp.o" 2>"$OUT/compile-fe-psp.log"
pspdev/bin/psp-gcc -std=gnu11 -O2 -Wall -Wno-misleading-indentation -Iviewer -Ipspdev/psp/sdk/include -Ipspdev/psp/include -D_PSP_FW_VERSION=600 -include viewer/msio.h -c viewer/audio.c -o "$OUT/audio-psp.o" 2>"$OUT/compile-audio-psp.log"
{ date;git rev-parse HEAD;git status --short; } >"$OUT/identity.txt"
SHIP_LEVELS='2 3 4 5 6 7' bash tools/ship_files.sh --pairs >"$OUT/ship-pairs.txt"
grep -q '^fe_audio.sap|build/fe_audio.sap$' "$OUT/ship-pairs.txt"
tail -1 "$OUT/source.log";tail -1 "$OUT/native-new.log";tail -1 "$OUT/decode.log"
echo "GATE FE audio PASS old=red early=red plants=3 artifacts=$OUT" | tee "$OUT/summary.txt"
