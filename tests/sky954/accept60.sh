#!/bin/bash
# ПРИЁМКА №954 + №957 (окно «Небо», ветка t60/sky954). Одна команда:  tests/sky954/accept60.sh      последняя строка: PASS или FAIL
# Что проверяется (у каждого гейта есть красный контроль, он обязан падать):
#   1 правило    tests/sky954/rows.py: какие текстуры неба 7 уровней становятся градиентом вершин (L6: 22 куска; облака и горы остаются текстурой); красное — порог 100 % (--loose) обязан упасть
#   2 сборка     EBOOT тура (со смоуком) и красный EBOOT -DSKY954_OLD=1 (небо как в TEST59)
#   3 движок     один сценарий tests/sky954/sky_l6.txt на обоих EBOOT: L6 (J6-2 в четыре стороны, вверх, причал C7-6 в три стороны), L2, L5, L4. Строка SKY954: на новом conv=22 (L6), 9 (L2), 17 (L5), 17 (L4),
#                звёзд-точек ≥ 100 на L6; красное — те же проверки на журнале красного EBOOT обязаны упасть
#   4 картинка   tests/sky954/shots.py: L6 изменился (≥ 1500 пикселей) и узнаётся (средняя разница ≤ 14), L2/L5/L4 не разошлись (≤ 6); красное — старый против старого не проходит «изменился»
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH; export PSPDEV=$ROOT/pspdev PATH=$ROOT/pspdev/bin:$PATH
PY=$ROOT/.venv/bin/python; SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test59tour/PSP/GAME/SHARTEST15}
A=${ACC_OUT:-${TMPDIR:-/tmp}/sky954_accept}; rm -rf "$A"; mkdir -p "$A"; export EMU_OWNER=${EMU_OWNER:-Небо} OUT=$A EMU_MINE=${EMU_MINE:-2}
FAIL=0; say() { echo "[$(date +%H:%M:%S)] $*"; }
res() { if [ "$1" = 0 ]; then say "  ok   $2"; else say "  ПАДАЕТ $2"; FAIL=1; fi; }
red() { if [ "$1" != 0 ]; then say "  ok   красное: $2"; else say "  ПАДАЕТ красное не упало: $2"; FAIL=1; fi; }
say "1 правило rows.py"; $PY -I tests/sky954/rows.py "$SET" > "$A/rows.txt"; res $? "градиент только у градиентов (L6 22 куска, облака остаются)"
$PY -I tests/sky954/rows.py "$SET" --loose > /dev/null; red $? "порог 100 % превращает облака"
say "2 сборка"; B() { ( cd "$ROOT/viewer" && { [ -d "$1" ] || psp-cmake -S . -B "$1" -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1 $2" > "$A/cfg_$1.log" 2>&1; } && cmake --build "$1" -j4 > "$A/build_$1.log" 2>&1 ); }
B build_t60 ""; res $? "EBOOT тура"; B build_t60_old "-DSKY954_OLD=1"; res $? "EBOOT красный (SKY954_OLD=1)"
EBN=$ROOT/viewer/build_t60/EBOOT.PBP; EBO=$ROOT/viewer/build_t60_old/EBOOT.PBP
say "3 движок: сценарий на новом и красном EBOOT (≈ 12 мин)"
( "$ROOT/tools/emu_run.sh" tests/sky954/sky_l6.txt new "$EBN" 900 > "$A/emu_new.log" 2>&1 ) & ( "$ROOT/tools/emu_run.sh" tests/sky954/sky_l6.txt old "$EBO" 900 > "$A/emu_old.log" 2>&1 ) & wait
chk() { # chk ЖУРНАЛ — SKY954: conv 22/9/17/17 по уровням, звёзд ≥ 100
  local f=$1 ok=0; for c in 22 9 17; do grep -q "^SKY954 old=0 .* conv=$c " "$f" || ok=1; done
  grep "^SKY954 old=0 .* conv=22 " "$f" | awk '{split($5,a,"="); if (a[2] >= 100) f = 1} END {exit f ? 0 : 1}' || ok=1; return $ok; }
[ -s "$A/out_new/smoke.txt" ] && grep -q "^END" "$A/out_new/smoke.txt"; res $? "прогон нового дошёл до END"
chk "$A/out_new/smoke.txt"; res $? "новый: превращено 22 / 9 / 17 кусков и ≥ 100 звёзд"
chk "$A/out_old/smoke.txt"; red $? "красный EBOOT не превращает ничего"
say "4 картинка"; $PY -I tests/sky954/shots.py "$A/out_old" "$A/out_new" --expect-change | tee "$A/shots.txt" | tail -14; [ "$(tail -1 "$A/shots.txt")" = PASS ]; res $? "L6 изменился и узнаётся, L2/L5/L4 не разошлись"
$PY -I tests/sky954/shots.py "$A/out_old" "$A/out_old" --expect-change > /dev/null; red $? "старый против старого: «изменился» не проходит"
[ $FAIL = 0 ] && echo PASS || echo FAIL
