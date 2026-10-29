#!/bin/bash
# набор замены TEST19: данные интерфейса (601 → 598 → v5 → [TYPO]) + уровни кустов Стен из test18set, сравнение с картой
set -e; cd ~/Downloads/shar-psp-sonnet-16b-w
S=build/t19stage; rm -rf $S; mkdir -p $S
for d in build/release_inputs/ui-pkg-601 build/release_inputs/ui-pkg-598 build/release_inputs/ui-pkg-v5 $TYPO; do [ -n "$d" ] && [ -d "$d" ] && cp -R "$d/." $S/; done
(cd build/test18set/PSP/GAME/SHARTEST15 && find . -name level.shr | while read f; do mkdir -p ../../../../$S/$(dirname $f); cp $f ../../../../$S/$f; done)
mkdir -p build/t19empty
python3 tools/test17_set.py /Volumes/PSP/PSP/GAME/SHARTEST15 $S build/t19empty build/test19/PSP/GAME/SHARTEST15/EBOOT.PBP tests/smoke_scenes/test19.txt build/test19set
cp build/test19/BUILD_INFO.txt build/test19set/BUILD_INFO.txt
