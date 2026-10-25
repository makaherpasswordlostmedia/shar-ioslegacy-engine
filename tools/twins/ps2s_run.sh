#!/bin/bash
# python запуск рецепта стенда 2: ps2s_run.sh ID [ISO]; печатает x z высоту камеры каждые 10 кадров
cd "$(dirname "$0")/../.." || exit 1
export PCSX2_DIR=$HOME/Downloads/shar-psp/build/twins/pcsx2_s2 O4_NAME=o4_s2 ISO_PATH=${2:-$PWD/build/ps2stend/iso/garage.iso}
nice -n 10 python3 -I tools/twins/orig2.py run build/ps2stend/rec/$1.json 2>&1 | tail -1
python3 -I - $1 <<'P'
import sys
rows=[l.rstrip('\n').split('\t') for l in open('/Users/USER/Downloads/shar-psp/build/twins/o4_s2/%s/trace.tsv'%sys.argv[1])]
h=rows[0]; print('кадр x y z camY'); 
for r in rows[1::2]: print(r[0], round(float(r[1]),2), round(float(r[2]),2), round(float(r[3]),2), round(float(r[5]),2))
P
