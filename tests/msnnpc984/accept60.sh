#!/bin/bash
# №984 приёмка (окно «Глюки», основа test68): значки продавцов и собеседника — поиск персонажа по имени (gameMsnNpc) раз в кадр на продавца перебирал до 24 персонажей; теперь кэш по указателю имени
# с поколением списка персонажей (viewer/game_msn.c). Сценарий city.txt: езда автопилотом L3, L4, L6, L7 (flag drive), строки MSNNPC984 (flag msnnpcstat): обращения, промахи, расхождения с перебором, мкс на поиск.
# Новый движок — ЗЕЛЁНЫЙ (кэш работает: обращений > 0, промахов ≤ 1 %, расхождений с перебором 0, поиск быстрее прежнего перебором в 1,4 раза и больше), прежний (-DGAMEMSNNPC984_OLD=1) — КРАСНЫЙ (кэша нет, calls = 0).
# «Побитно тот же»: счётчик bad = 0 (каждый ответ сверен с npcFind) плюс стенд ботов t68/bots984 (tools/bots/city984.sh cmp: 30 маршрутов, расхождений 0).   REUSE=1 — не пересобирать
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
set -u
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"; export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH EMU_OWNER=${EMU_OWNER:-Glyuki} EMU_MINE=2 OUT=$W/run; mkdir -p run
export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test68tour/PSP/GAME/SHARTEST15}
BASEF="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1 -DZF932_OLD=1"
build() { [ "${REUSE:-0}" = 1 ] && [ -f "viewer/$1/EBOOT.PBP" ] && return 0
  ( cd viewer && psp-cmake -S . -B "$1" -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$BASEF $2" >/dev/null 2>&1 && cmake --build "$1" -j4 >"../run/build984_$1.log" 2>&1 ); }
build build_t60 "" & build build_old984 "-DGAMEMSNNPC984_OLD=1" & wait
for b in build_t60 build_old984; do [ -f viewer/$b/EBOOT.PBP ] || { echo "нет сборки $b"; echo FAIL; exit 2; }; done
sed '/^flag msnnpc984old/d; s/^flag msnnpctime 1/flag msnnpctime 1\nflag msnnpcchk 0/' tests/msnnpc984/city.txt > run/city_acc.txt
sed '/^flag msnnpc984old/d' tests/msnnpc984/city.txt | sed 's/^flag msnnpctime 1/flag msnnpctime 1\nflag msnnpcchk 1/' > run/city_chk.txt
bash tools/emu_run.sh run/city_chk.txt a984c viewer/build_t60/EBOOT.PBP 700 >/dev/null 2>&1 &
bash tools/emu_run.sh run/city_acc.txt a984n viewer/build_t60/EBOOT.PBP 700 >/dev/null 2>&1 & wait
bash tools/emu_run.sh run/city_acc.txt a984o viewer/build_old984/EBOOT.PBP 700 >/dev/null 2>&1 &
sed '/^flag msnnpc984old/d' tests/msnnpc984/city.txt > run/city_ref.txt; sed -i '' 's/^flag msnnpctime 1/flag msnnpctime 1\nflag msnnpc984old 1/' run/city_ref.txt
bash tools/emu_run.sh run/city_ref.txt a984r viewer/build_t60/EBOOT.PBP 700 >/dev/null 2>&1 & wait
c=$(python3 tests/msnnpc984/check.py run/out_a984c/smoke.txt); crc=$?
n=$(python3 tests/msnnpc984/check.py run/out_a984n/smoke.txt run/out_a984r/smoke.txt); nrc=$?
o=$(python3 tests/msnnpc984/check.py run/out_a984o/smoke.txt); orc=$?
echo "новое, сверка с перебором: $c -> $([ $crc = 0 ] && echo зелёный || echo 'КРАСНЫЙ (плохо)')"
echo "новое, цена:               $n -> $([ $nrc = 0 ] && echo зелёный || echo 'КРАСНЫЙ (плохо)')"
echo "прежнее:                   $o -> $([ $orc != 0 ] && echo 'красный, как нужно' || echo 'ЗЕЛЁНЫЙ (красный не пойман)')"
if [ $crc = 0 ] && [ $nrc = 0 ] && [ $orc != 0 ]; then echo PASS; else echo FAIL; fi
