#!/bin/bash
# Стенд 2: для каждого персонажа клон ISO → холодный старт до L1 в машине → серия «сзади/выход/посадка» и «поворот» (вид сбоку). Один эмулятор за раз.
# tools/twins/ps2s_chain.sh bart lisa apu   (машина по умолчанию <имя>_v)
cd "$(dirname "$0")/../.." || exit 1
export PCSX2_DIR=$HOME/Downloads/shar-psp/build/twins/pcsx2_s2 O4_NAME=o4_s2
B=$HOME/Downloads/shar-psp/build/twins/o4_s2
for ch in "$@"; do
  python3 -I tools/twins/ps2_char_swap.py $ch ${CAR:-${ch}_v} | tail -1
  export ISO_PATH=$PWD/build/ps2stend/iso/${ch}_${CAR:-${ch}_v}.iso
  id=ps2s2_${ch}_${CAR:-$ch}
  python3 - <<P
import json
r=json.load(open('build/ps2stend/rec/ps2s2_marge_boot.json')); r['id']='${id}_boot'
json.dump(r,open('build/ps2stend/rec/${id}_boot.json','w'),ensure_ascii=False,indent=1)
P
  nice -n 10 python3 -I tools/twins/orig2.py run build/ps2stend/rec/${id}_boot.json 2>&1 | tail -1
  python3 -I tools/twins/ps2s_seat_recipe.py ${id}_seat $B/${id}_boot/snap_6250.p2s
  nice -n 10 python3 -I tools/twins/orig2.py run build/ps2stend/rec/${id}_seat.json 2>&1 | tail -1
  python3 - <<P
import json
r=json.load(open('build/ps2stend/rec/ps2s2_marge_turn.json')); r['id']='${id}_turn'; r['state']='build/twins/o4_s2/${id}_boot/snap_6250.p2s'
json.dump(r,open('build/ps2stend/rec/${id}_turn.json','w'),indent=1)
P
  nice -n 10 python3 -I tools/twins/orig2.py run build/ps2stend/rec/${id}_turn.json 2>&1 | tail -1
done
