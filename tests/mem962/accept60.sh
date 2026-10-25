#!/bin/bash
# ПРИЁМКА №962 (окно «Небо», ветка t62/mem): куча на L3/L5/L7 после TEST61 (PVS1, PV2S и traffic.shr уходят из кучи в пустой запас участка lva). Одна команда: tests/mem962/accept60.sh, последняя строка PASS или FAIL
#   1 сборка   EBOOT тура (со смоуком)
#   2 движок   сценарий tests/mem962/mem_l357.txt (L1 → L3 → L5 → L7, по 20 с, снимки) на новом EBOOT и на нём же с файлом lvamem962old (красное: куча как до правки)
#   3 проверка check.py: выигрыш кучи L3 ≥ 1,0 МБ, L5 ≥ 1,0, L7 ≥ 1,5; на L3 в запас легло > 0; снимки уровней те же (средняя разница ≤ 3 из 255);
#              красное: «старый против старого» не даёт выигрыша — обязан упасть
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH; export PSPDEV=$ROOT/pspdev PATH=$ROOT/pspdev/bin:$PATH
PY=$ROOT/.venv/bin/python; SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test61tour/PSP/GAME/SHARTEST15}
A=${ACC_OUT:-${TMPDIR:-/tmp}/mem962_accept}; rm -rf "$A"; mkdir -p "$A"; export EMU_OWNER=${EMU_OWNER:-Небо} OUT=$A EMU_MINE=${EMU_MINE:-2} SET
FAIL=0; say() { echo "[$(date +%H:%M:%S)] $*"; }
res() { if [ "$1" = 0 ]; then say "  ok   $2"; else say "  ПАДАЕТ $2"; FAIL=1; fi; }
red() { if [ "$1" != 0 ]; then say "  ok   красное: $2"; else say "  ПАДАЕТ красное не упало: $2"; FAIL=1; fi; }
say "1 сборка"; ( cd "$ROOT/viewer" && { [ -d build_t60 ] || psp-cmake -S . -B build_t60 -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1" > /dev/null; } && cmake --build build_t60 -j4 > "$A/build.log" 2>&1 ); res $? "EBOOT тура"
EB=$ROOT/viewer/build_t60/EBOOT.PBP
say "2 движок: новый и красный (файл lvamem962old), около 4 минут"
( "$ROOT/tools/emu_run.sh" tests/mem962/mem_l357.txt new "$EB" 400 > "$A/emu_new.log" 2>&1 ) & ( FLAGS="lvamem962old" "$ROOT/tools/emu_run.sh" tests/mem962/mem_l357.txt old "$EB" 400 > "$A/emu_old.log" 2>&1 ) & wait
for v in new old; do [ -s "$A/out_$v/smoke.txt" ] && grep -q "^END" "$A/out_$v/smoke.txt"; res $? "прогон $v дошёл до END"; done
say "3 проверка"; $PY -I tests/mem962/check.py "$A/out_new" "$A/out_old" | tee "$A/check.txt"; [ "$(tail -1 "$A/check.txt")" = PASS ]; res $? "выигрыш кучи L3/L5/L7 и снимки те же"
$PY -I tests/mem962/check.py "$A/out_old" "$A/out_old" > "$A/check_red.txt"; [ "$(tail -1 "$A/check_red.txt")" = PASS ]; red $? "старый против старого не даёт выигрыша"
[ $FAIL = 0 ] && echo PASS || echo FAIL
