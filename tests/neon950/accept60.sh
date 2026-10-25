#!/bin/bash
# №950 приёмка (окно «Глюки», TEST60/61): L6 причал C8-6 — у вывесок нет свечения (таблица света не строит невысокие аддитивные плашки: неон, таблички), только текстура; конусы ламп остаются.
# Один тур-EBOOT, в сценарии ab.txt flag neonsign950 1 (новое — ЗЕЛЁНЫЙ) и 0 (прежнее: плашки как были — КРАСНЫЙ), одни и те же три ракурса на вывески (-419,-58,62). Последняя строка PASS или FAIL.
#   tests/neon950/accept60.sh      REUSE=1 — не пересобирать и не гонять эмулятор, если прогон уже есть
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
set -u
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"; export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH EMU_OWNER=${EMU_OWNER:-Glyuki} EMU_MINE=2 OUT=$W/run; mkdir -p run
if [ "${REUSE:-0}" != 1 ] || [ ! -f viewer/build_t60/EBOOT.PBP ]; then
  ( cd viewer && psp-cmake -S . -B build_t60 -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1" >/dev/null 2>&1 && cmake --build build_t60 -j4 >run/build950.log 2>&1 ) || { echo "сборка не удалась (run/build950.log)"; echo FAIL; exit 2; }
fi
[ "${REUSE:-0}" = 1 ] && [ -f run/out_ab/o_c.png ] || bash tools/emu_run.sh tests/neon950/ab.txt ab viewer/build_t60/EBOOT.PBP 900 >/dev/null 2>&1
[ -f run/out_ab/o_c.png ] || { echo "прогон не дал кадров"; echo FAIL; exit 2; }
r=$(python3 tests/neon950/check.py run/out_ab); rc=$?; echo "$r" | head -1
if [ $rc = 0 ]; then echo PASS; else echo FAIL; fi
