#!/bin/bash
# Гейт №536: посадка после прыжка урона не даёт (днище/крыша об опору), лобовой в стену — как прежде. Красный контроль: сборка с -DLAND_DAMAGE_OLD=1.
#   tools/bots/landgate.sh PACKAGE_DIR TARGETS_L1.tsv
set -e; cd "$(dirname "$0")/../.."; D=$1; T=$2
BINS=landtest bash tools/bots/build.sh >/dev/null; BINS=landtest SUF=_old bash tools/bots/build.sh -DLAND_DAMAGE_OLD=1 >/dev/null
n=$(BW_LEVEL=1 build/bots/landtest "$D/level.shr" "$D/homer.shr" "$D/level01.msn" "$T" | tee /tmp/landgate_new.txt | grep ИТОГ); o=$(BW_LEVEL=1 build/bots/landtest_old "$D/level.shr" "$D/homer.shr" "$D/level01.msn" "$T" | grep ИТОГ)
echo "новое:  $n"; echo "прежнее: $o"
gn=$(echo "$n" | sed 's/.*прыжки \([0-9.]*\).*/\1/'); go=$(echo "$o" | sed 's/.*прыжки \([0-9.]*\).*/\1/'); wn=${n##*урон }; wo=${o##*урон }
python3 -c "import sys; gn,go,wn,wo=map(float,sys.argv[1:]); ok=gn<0.001 and go>0.01 and abs(wn-wo)<1e-6 and wn>0.05; print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)" $gn $go $wn $wo
