#!/bin/bash
# №902 гейт-вердикт: правка stateprops.c (удар о стену мира засчитывается предмету рядом) не ухудшает ни один заезд и улучшает хотя бы один, все 7 уровней.
#   tests/smash902/gate.sh        — новое против прежнего (SP_WALL902_OLD=1): PASS
#   tests/smash902/gate.sh red    — красный контроль: «новое» тоже собрано с SP_WALL902_OLD=1 -> улучшений нет -> FAIL
# (tests/smash обнуляет остывание каждый кадр и поэтому правку не видит: проходит и с SP_WALL902_OLD=1, так задумано; задержку меряет этот гейт)
cd "$(dirname "$0")/../.."; SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test54tour/PSP/GAME/SHARTEST15}; O=build/tests/smash902; mkdir -p $O
NEWV=0; [ "$1" = red ] && NEWV=1
cc -std=c11 -O2 -DSKIN_HOST -DSP_WALL902_OLD=$NEWV -I viewer tests/smash902/host.c viewer/props.c viewer/col.c viewer/car.c viewer/coins.c -lm -o $O/gn || exit 2
cc -std=c11 -O2 -DSKIN_HOST -DSP_WALL902_OLD=1 -I viewer tests/smash902/host.c viewer/props.c viewer/col.c viewer/car.c viewer/coins.c -lm -o $O/go || exit 2
A=()
for L in 1 2 3 4 5 6 7; do f=$SET/level.shr; [ $L -gt 1 ] && f=$SET/l$L/level.shr
  $O/gn $f cases > $O/n$L.txt & $O/go $f cases > $O/o$L.txt & wait; A+=($O/n$L.txt $O/o$L.txt); done
python3 tests/smash902/verdict.py "${A[@]}"
