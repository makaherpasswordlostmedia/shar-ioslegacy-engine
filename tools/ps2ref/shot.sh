#!/bin/bash
# снимок только окна PCSX2 (эталон PS2): tools/ps2ref/shot.sh имя [ширина превью]
set -euo pipefail
cd "$(dirname "$0")/../.."
P=$(python3 tools/ps2ref/profile.py pid); W=$(tools/winid_pid $P | head -1)
[ -n "$W" ] || { echo "нет окна PCSX2"; exit 1; }
screencapture -x -o -l "$W" build/ps2ref/$1.png && .venv/bin/python -c "
from PIL import Image; im=Image.open('build/ps2ref/$1.png').convert('RGB'); w=${2:-960}; im.resize((w,int(im.height*w/im.width))).save('build/ps2ref/$1_s.png')" && echo build/ps2ref/$1_s.png
