#!/bin/bash
# Ждёт, пока цепочка закончит текущего персонажа, ставит ловушку гаража АЭС вне очереди, потом возвращает цепочку.
cd "$(dirname "$0")/../.." || exit 1
B=$HOME/Downloads/shar-psp/build/twins/o4_s2
while [ ! -f $B/ps2s2_bart_bart_turn/report.json ]; do sleep 10; done
pkill -f ps2s_chain.sh; sleep 1; pkill -f "pcsx2_s2/bin/pcsx2-twins"; sleep 3
export PCSX2_DIR=$HOME/Downloads/shar-psp/build/twins/pcsx2_s2 O4_NAME=o4_s2 ISO_PATH=$PWD/build/ps2stend/iso/garage.iso
nice -n 10 python3 -I tools/twins/orig2.py run build/ps2stend/rec/ps2s2_garage_boot.json 2>&1 | tail -1
touch build/ps2stend/garage_boot.done
