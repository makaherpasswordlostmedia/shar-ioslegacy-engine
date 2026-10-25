#!/bin/bash
# ПРИЁМКА №957б (окно «Небо», ветка t64/pier): арки причала L6 без блика «блинк-блинк» на неоне (№944), семейство — все уровни. Одна команда: tests/pier64/accept60.sh, последняя строка PASS или FAIL
#   1 сборка   EBOOT тура (со смоуком, -DZF932_OLD=1)
#   2 движок   сценарий tests/pier64/arch.txt (L1…L7 по 20 с, на L6 три арки со снимками) на новом EBOOT и на нём же с файлом neonarch957old (красное: как было)
#   3 проверка check.py: в новом нет блика предмета крупнее 3 м ни на одном уровне; в старом на L6 есть; снимки арок различаются; красное: «старый против старого» — обязан упасть
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH; export PSPDEV=$ROOT/pspdev PATH=$ROOT/pspdev/bin:$PATH
PY=$ROOT/.venv/bin/python; SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test63tour/PSP/GAME/SHARTEST15}
A=${ACC_OUT:-${TMPDIR:-/tmp}/pier957_accept}; rm -rf "$A"; mkdir -p "$A"; export EMU_OWNER=${EMU_OWNER:-Небо} OUT=$A EMU_MINE=${EMU_MINE:-2} SET
FAIL=0; say() { echo "[$(date +%H:%M:%S)] $*"; }
res() { if [ "$1" = 0 ]; then say "  ok   $2"; else say "  ПАДАЕТ $2"; FAIL=1; fi; }
red() { if [ "$1" != 0 ]; then say "  ok   красное: $2"; else say "  ПАДАЕТ красное не упало: $2"; FAIL=1; fi; }
say "1 сборка"; ( cd "$ROOT/viewer" && { [ -d build_t64 ] || psp-cmake -S . -B build_t64 -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1 -DZF932_OLD=1" > /dev/null; } && cmake --build build_t64 -j4 > "$A/build.log" 2>&1 ); res $? "EBOOT тура"
EB=$ROOT/viewer/build_t64/EBOOT.PBP
say "2 движок: новый и красный (файл neonarch957old), около 6 минут"
( "$ROOT/tools/emu_run.sh" tests/pier64/arch.txt new "$EB" 600 > "$A/emu_new.log" 2>&1 ) & ( FLAGS="neonarch957old" "$ROOT/tools/emu_run.sh" tests/pier64/arch.txt old "$EB" 600 > "$A/emu_old.log" 2>&1 ) & wait
for v in new old; do [ -s "$A/out_$v/smoke.txt" ] && grep -q "^END" "$A/out_$v/smoke.txt"; res $? "прогон $v дошёл до END"; done
say "3 проверка"; $PY -I tests/pier64/check.py "$A/out_new" "$A/out_old" | tee "$A/check.txt"; [ "$(tail -1 "$A/check.txt")" = PASS ]; res $? "арки без блика, семейство чисто, снимки различаются"
$PY -I tests/pier64/check.py "$A/out_old" "$A/out_old" > "$A/check_red.txt"; [ "$(tail -1 "$A/check_red.txt")" = PASS ]; red $? "старый против старого: блик остался — обязан упасть"
[ $FAIL = 0 ] && echo PASS || echo FAIL
