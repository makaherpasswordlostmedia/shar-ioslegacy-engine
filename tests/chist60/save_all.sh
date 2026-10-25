#!/bin/bash
# Гейт «сейв пройдено всё» (служебная запись, не входит в обычную игру: svmAllBoot живёт под -DSVM_ALLSAVE).
#   1) на Маке настоящими модулями игры (savegame.c, collect.c, msn_file.c) собирается allsave.bin по данным набора SET; svdump читает его обратно, check_save.py сверяет:
#      уровень записи 7, миссии всех 7 уровней, карточки 7x7, осы 20x7, гэги, купленное, строки MISSION SELECT, кошелёк. Красный: запись с одним испорченным байтом -> svRead != 0 -> проверка падает
#   2) в эмуляторе (свой HOME прогона, карты Роба не трогаются) сборка тура с -DSVM_ALLSAVE=1 при флаг-файле allsave=3 и allsave.bin пишет слот 3 утилитой сохранения и читает обратно:
#      строка SVALL boot slot=3 res=0 verify=O, DATA.BIN 784 байта. Красные: (а) обычная сборка тура (без SVM_ALLSAVE) — строки SVALL нет; (б) испорченный allsave.bin — skip=badbin
#   save_all.sh [EBOOT_ALLSAVE EBOOT_ОБЫЧНЫЙ]   без аргументов сборки делаются сами (viewer/build_t60_allsave, viewer/build_t60). Последняя строка PASS или FAIL
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; cd "$ROOT"
[ -d /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk ] && export SDKROOT=${SDKROOT:-/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk}
W=${W:-$ROOT/build/gates/saveall}; rm -rf "$W"; mkdir -p "$W/msn" "$W/ovl" "$W/ovl_bad"; export OUT=$W; fail=0
EA=${1:-}; EN=${2:-}
[ -n "$EA" ] || { tour_build build_t60_allsave -DSVM_ALLSAVE=1 || { echo "FAIL: сборка allsave"; exit 2; }; EA=$ROOT/viewer/build_t60_allsave/EBOOT.PBP; }
[ -n "$EN" ] || { tour_build build_t60 || { echo "FAIL: сборка тура"; exit 2; }; EN=$ROOT/viewer/build_t60/EBOOT.PBP; }
echo "--- 1) запись на Маке"
V=viewer; . tools/bots/lib.sh
CC="cc -std=c11 -O2 -w -DSKIN_HOST -I $V -I tools/bots"
$CC tools/savegen/mkallsave.c $V/savegame.c $BOTS_LIB -lm -o "$W/mkallsave" > "$W/cc1.txt" 2>&1 && $CC tools/savegen/svdump.c $V/savegame.c $BOTS_LIB -lm -o "$W/svdump" > "$W/cc2.txt" 2>&1 || { echo "FAIL: сборка savegen (см. $W/cc1.txt, cc2.txt)"; exit 2; }
for L in 1 2 3 4 5 6 7; do f=$SET/l$L/level0$L.msn; [ $L = 1 ] && f=$SET/level01.msn; cp "$f" "$W/msn/" || { echo "FAIL: нет $f"; exit 2; }; done
"$W/mkallsave" "$SET" "$W/msn" "$W/allsave.bin" > "$W/mk.txt" 2>&1 || { echo "FAIL: mkallsave"; tail -3 "$W/mk.txt"; exit 1; }; tail -1 "$W/mk.txt"
"$W/svdump" "$W/allsave.bin" > "$W/sv_good.txt"; "$PY" tests/chist60/check_save.py "$W/sv_good.txt" || fail=1
cp "$W/allsave.bin" "$W/bad.bin"; printf '\xff' | dd of="$W/bad.bin" bs=1 seek=300 conv=notrunc 2>/dev/null
"$W/svdump" "$W/bad.bin" > "$W/sv_bad.txt"; echo "красный (один байт записи испорчен):"; "$PY" tests/chist60/check_save.py "$W/sv_bad.txt" --expect-fail || { echo "КРАСНЫЙ НЕ ПОЙМАН"; fail=1; }
echo "--- 2) запись слота 3 в эмуляторе"
cp "$W/allsave.bin" "$W/ovl/allsave.bin"; cp "$W/bad.bin" "$W/ovl_bad/allsave.bin"; printf 'flag saves\nflag menu\nwait 12\nend\n' > "$W/save.txt"
OVL=$W/ovl FLAGS="allsave=3" $RUN "$W/save.txt" sv_good "$EA" 120 > /dev/null & OVL=$W/ovl FLAGS="allsave=3" $RUN "$W/save.txt" sv_plain "$EN" 120 > /dev/null & wait
OVL=$W/ovl_bad FLAGS="allsave=3" $RUN "$W/save.txt" sv_bad "$EA" 120 > /dev/null
line=$(grep -h '^SVALL boot' "$W/out_sv_good/smoke.txt" | head -1); echo "  зелёный: $line"
echo "$line" | grep -q 'slot=3 res=00000000 .*verify=O' || { echo "КРАСНОЕ: запись слота 3 не подтверждена чтением"; fail=1; }
sz=$(stat -f %z "$W"/emu_home_sv_good/.ppsspp/PSP/SAVEDATA/SLES5189703/DATA.BIN 2>/dev/null); echo "  DATA.BIN в слоте 3 прогона: ${sz:-нет} байт"; [ "${sz:-0}" = 784 ] || { echo "КРАСНОЕ: DATA.BIN не 784 байта"; fail=1; }
lp=$(grep -h '^SVALL boot' "$W/out_sv_plain/smoke.txt" | head -1); echo "  красный (обычная сборка без SVM_ALLSAVE): '${lp:-строки SVALL нет}'"; [ -z "$lp" ] || { echo "КРАСНЫЙ НЕ ПОЙМАН: обычная сборка пишет сейв"; fail=1; }
lb=$(grep -h '^SVALL boot' "$W/out_sv_bad/smoke.txt" | head -1); echo "  красный (испорченный allsave.bin): $lb"; echo "$lb" | grep -q 'skip=badbin' || { echo "КРАСНЫЙ НЕ ПОЙМАН: испорченная запись не отвергнута"; fail=1; }
[ $fail = 0 ] && echo "PASS (save_all: запись читается, слот 3 пишется и подтверждается, три красных пойманы)" || echo "FAIL (save_all)"; exit $fail
