#!/bin/bash
# pack_test.sh TITLE OUT_DIR : EBOOT тест-апки из viewer/build/EBOOT.PBP (секции ICON0/ICON1/PIC1/SND0 берутся у игры в build/tour/pbp соседнего дерева g-build)
set -e
cd "$(dirname "$0")/.."; export PSPDEV="$PWD/pspdev" PATH="$PWD/pspdev/bin:$PATH"
G=${PBP_SRC:-$HOME/Downloads/shar-psp-g-build-w/build/tour/pbp}; O=$2; rm -rf "$O"; mkdir -p "$O/unp" "$O/PSP/GAME/SHARTEST15"
(cd "$O/unp" && unpack-pbp "$OLDPWD/${EBOOT_SRC:-viewer/build/EBOOT.PBP}" >/dev/null)
mksfoex -d MEMSIZE=1 -s APP_VER= "$1" "$O/PARAM.SFO"
pack-pbp "$O/PSP/GAME/SHARTEST15/EBOOT.PBP" "$O/PARAM.SFO" "$G/ICON0.PNG" "$G/ICON1.PMF" NULL "$G/PIC1.PNG" "$G/SND0.AT3" "$O/unp/DATA.PSP" NULL >/dev/null
python3 - "$O/PSP/GAME/SHARTEST15/EBOOT.PBP" "$1" <<'PY'
import struct, hashlib, sys
b = open(sys.argv[1], 'rb').read(); o = struct.unpack_from('<8I', b, 8); n = ['SFO', 'ICON0', 'ICON1', 'PIC0', 'PIC1', 'SND0', 'DATA.PSP', 'PSAR']; e = list(o[1:]) + [len(b)]
print(len(b), hashlib.sha256(b).hexdigest()[:8], {k: y - x for k, x, y in zip(n, o, e)}, sys.argv[2].encode() in b[o[0]:o[1]])
PY
python3 tools/build_info.py "$O/PSP/GAME/SHARTEST15/EBOOT.PBP" "$O/BUILD_INFO.txt" "$1" "по умолчанию (тест-апка с оверлеем)" >/dev/null
