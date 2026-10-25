#!/bin/bash
# №930 ступень 2 «Мультик»: ОДНА команда приёмки.   tests/mult930/accept60.sh      (последняя строка: PASS или FAIL)
#   Окружение (по умолчанию то, что в задании): SET — набор данных тура TEST59; DATA — папка-наложение с carflat930.bin / carflatm930.bin (если нет или устарела — считается на Маке из набора);
#   A — рабочая папка прогона; BASE_COMMIT — основа (TEST59 + датчики), с неё собирается база для кучи и цены; EMU_OWNER=mult, 2 эмулятора на хозяина (общий предел задаёт tools/emu_run.sh).
#   Что делает: данные (разбор как у движка, красный: порча перестановки), сборка трёх EBOOT тура (новый; красный CARFILL930_OLD=1; база с BASE_COMMIT), гейт carfill930 (L1: заливка, текстурный хвост, машина игрока, Textures On, выключатель),
#   красные (OLD-сборка и FLAT930_RED=1 обязаны упасть), машины миссий (L2, L4; красный OLD), куча L1–L7 (новое не хуже базы по байтам: строка LEVEL и минимум BB), цена кадра (PHSEC, новое не хуже базы).
set -u
export CARFLAT_RECOLOR_OLD=1   # №956 (перекраска серой краски в тона Симпсонов) проверяет tests/mult956; здесь измеряется заливка №930 как есть
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
W=$(cd "$(dirname "$0")/../.." && pwd); cd "$W"
export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test59tour/PSP/GAME/SHARTEST15}
DATA=${DATA:-$HOME/Downloads/shar-psp/build/t60/data_mult}
A=${A:-$W/build/mult/accept}; BASE_COMMIT=${BASE_COMMIT:-aa092b71}; export EMU_OWNER=${EMU_OWNER:-mult}; export EMU_MINE=${EMU_MINE:-2}
CK="python3 tests/mult930/accept60_check.py"; FLAGS_TOUR='-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1'
mkdir -p "$A"; BAD=0; SUM="$A/summary.txt"; : > "$SUM"
say() { echo "$@" | tee -a "$SUM"; }
verdict() {   # verdict ИМЯ ожидание(0 — должен пройти, 1 — должен упасть) код-возврата
  local n=$1 want=$2 rc=$3
  if [ "$want" = 0 ] && [ "$rc" = 0 ]; then say "  [ok]  $n: PASS"; elif [ "$want" = 1 ] && [ "$rc" != 0 ]; then say "  [ok]  $n: красный упал, как должен"; else say "  [BAD] $n: " $([ "$want" = 0 ] && echo "ожидался PASS, получен FAIL" || echo "красный НЕ упал"); BAD=$((BAD + 1)); fi
}
t0=$(date +%s)
say "== 1. данные боковых файлов ($DATA)"
need=0; [ -f "$DATA/carflat930.bin" ] && [ -f "$DATA/l7/carflatm930.bin" ] || need=1
for f in tools/car_flat.py tools/flat_list.py; do [ "$DATA/carflat930.bin" -nt "$f" ] || need=1; done
if [ $need = 1 ]; then say "  считаю на Маке (7 уровней параллельно)"; mkdir -p "$DATA"
  for n in 1 2 3 4 5 6 7; do ( if [ $n = 1 ]; then d=$SET; o=$DATA; else d=$SET/l$n; o=$DATA/l$n; mkdir -p "$o"; fi
    python3 tools/car_flat.py "$d/traffic.shr" --sidecar "$o/carflat930.bin" > "$A/data_l$n.log" 2>&1 && python3 tools/car_flat.py "$d/msncars-l$n.shr" --sidecar "$o/carflatm930.bin" >> "$A/data_l$n.log" 2>&1 ) & done; wait
fi
$CK data "$DATA" "$SET" | tail -3 | tee -a "$SUM"; verdict "данные" 0 ${PIPESTATUS[0]}
$CK data "$DATA" "$SET" corrupt > "$A/data_red.log" 2>&1; verdict "данные, красный (порча перестановки)" 1 $?
say "== 2. сборка EBOOT тура (со смоуком): новый, красный (CARFILL930_OLD=1), база $BASE_COMMIT"
build() {   # build ПАПКА_ИСТОЧНИКА ПАПКА_СБОРКИ ДОП_ФЛАГИ
  ( cd "$1/viewer" && psp-cmake -S . -B "$2" -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$FLAGS_TOUR $3" > "$A/cfg_$2.log" 2>&1 && cmake --build "$2" -j4 > "$A/build_$2.log" 2>&1 ) || { say "  [BAD] сборка $2 не прошла (см. $A/build_$2.log)"; BAD=$((BAD + 1)); }
}
BS=$A/base_src; if [ ! -f "$BS/.commit2_$BASE_COMMIT" ]; then rm -rf "$BS"; mkdir -p "$BS"; git archive "$BASE_COMMIT" viewer | tar -x -C "$BS" && ln -s "$W/build" "$BS/build" && python3 tests/mult930/heapb_insert.py "$BS/viewer/smoke.h" && touch "$BS/.commit2_$BASE_COMMIT"; fi
build "$W" build_t60 ""; build "$W" build_t60_old "-DCARFILL930_OLD=1"; build "$BS" build_t60_base "${BASE_FLAGS:-}"   # BASE_FLAGS=-DCARFILL930_OLD=1 при BASE_COMMIT после слияния №930 (база без заливки того же кода)
EN=$W/viewer/build_t60/EBOOT.PBP; EO=$W/viewer/build_t60_old/EBOOT.PBP; EB=$BS/viewer/build_t60_base/EBOOT.PBP
for e in "$EN" "$EO" "$EB"; do [ -f "$e" ] || { say "  [BAD] нет $e"; BAD=$((BAD + 1)); }; done
IMG() { psp-size -A "$1" | awk '/^\.(text|rodata|data|sdata|sbss|bss) /{s+=$2} END {print s}'; }
IN=$(IMG "$W/viewer/build_t60/sharview"); IB=$(IMG "$BS/viewer/build_t60_base/sharview"); say "  образ (text+rodata+data+bss), Б: база $IB, новое $IN (Δ $((IN - IB)))"; [ "$IN" -le "$IB" ] && verdict "образ не больше базы" 0 0 || verdict "образ не больше базы" 0 1
say "== 3. эмулятор: гейт carfill930 (зелёный и красные), машины миссий, куча и цена"
export OVL=$DATA
run() { OUT="$A/$1" tools/emu_run.sh "$2" "$3" "$4" "${5:-900}" > "$A/$1.log" 2>&1; }   # run ПАПКА СЦЕНАРИЙ ИМЯ EBOOT [МАКС_С]
GATE=tests/toon/carfill930_scenario.txt; MIS=tests/mult930/mis_cars.txt; HEAP=tests/mult930/heap_levels.txt
( run g_new $GATE g_new "$EN" 420 & run g_old $GATE g_old "$EO" 420 & wait )
( awk '/^flag carfill930 1/ && !d {print "flag carfill930 0"; d=1; next} {print}' $GATE > "$A/scenario_red.txt"; run g_red "$A/scenario_red.txt" g_red "$EN" 420 & run m_new $MIS m_new "$EN" 600 & wait )
( run m_old $MIS m_old "$EO" 600 & run m_base $MIS m_base "$EB" 600 & wait )
( run h_base $HEAP h_base "$EB" 1200 & run h_new $HEAP h_new "$EN" 1200 & wait )
say "-- гейт carfill930 (L1)"; python3 tests/toon/carfill930_check.py "$A/g_new/out_g_new" | tee -a "$SUM" | tail -6; verdict "гейт carfill930 зелёный" 0 ${PIPESTATUS[0]}
python3 tests/toon/carfill930_check.py "$A/g_old/out_g_old" > "$A/g_old.txt" 2>&1; verdict "гейт, красный CARFILL930_OLD=1" 1 $?
python3 tests/toon/carfill930_check.py "$A/g_red/out_g_red" > "$A/g_red.txt" 2>&1; verdict "гейт, красный flag carfill930 0 в окне" 1 $?
say "-- машины миссий (L2, L4)"; $CK mis "$A/m_new/out_m_new" | tee -a "$SUM"; verdict "машины миссий" 0 ${PIPESTATUS[0]}
$CK mis "$A/m_old/out_m_old" > "$A/m_old.txt" 2>&1; verdict "машины миссий, красный OLD" 1 $?
say "-- куча L1–L7 (эмулятор, детерминированный: новое против базы $BASE_COMMIT)"; $CK heap "$A/h_base/out_h_base" "$A/h_new/out_h_new" | tee -a "$SUM"; verdict "куча" 0 ${PIPESTATUS[0]}
say "-- цена кадра: уровни L1–L7 стоя (мультик)"; $CK cost "$A/h_base/out_h_base" "$A/h_new/out_h_new" | tee -a "$SUM"; verdict "цена, уровни" 0 ${PIPESTATUS[0]}
say "-- цена кадра: машины миссий L2, L4"; $CK cost "$A/m_base/out_m_base" "$A/m_new/out_m_new" | tee -a "$SUM"; verdict "цена, машины миссий" 0 ${PIPESTATUS[0]}
say "-- очередь контура: пик заполненности (THQ_MAX в сборке $(grep -o 'CARFILL930_OLD ? 160 : [0-9]*' viewer/main_render.h | head -1))"; grep -a -h "^CARFILL t" "$A"/h_new/out_h_new/smoke.txt "$A"/m_new/out_m_new/smoke.txt "$A"/g_new/out_g_new/smoke.txt | grep -o "thq_peak=[0-9]*" | sort -t= -k2 -n | tail -1 | tee -a "$SUM"
say "== итог за $(( $(date +%s) - t0 )) с; нарушений: $BAD"
[ $BAD = 0 ] && echo PASS || echo FAIL
