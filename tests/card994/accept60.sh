#!/bin/bash
# №994 приёмка (окно «Управление», TEST71): карточка миссии перед миссией не показывается на месте до въезда — первый видимый кадр уже в руке за краем экрана, въезд без отката назад.
# Причина (трасса BRIEFANIM/BRIEFDRAW): таймер въезда запускался при открытии брифинга и второй раз при готовности карточки; между ними карточка стояла на месте, потом сбрасывалась за край и ехала заново.
# Выключатели: CARD994_OLD=1 (сборка) / файл card994old рядом с EBOOT / flag card994 0 (сценарий). Последняя строка: PASS или FAIL.
#   tests/card994/accept60.sh          REUSE=1 — не пересобирать EBOOT, если уже есть
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
set -u
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"
export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
T=$HOME/Downloads/shar-psp/build/t71; B=${B994_OUT:-$T/work_card994}; SH=${B994_SHOTS:-$T/shots_card994}; mkdir -p "$B" "$SH"
C="python3 tests/card994/check.py"; export EMU_OWNER=Управление EMU_MINE=2
BASEF="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1 -DZF932_OLD=1"
build() {
  [ "${REUSE:-0}" = 1 ] && [ -f "$B/eboot_$1.PBP" ] && return 0
  ( cd viewer && psp-cmake -S . -B "build_b994_$1" -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$BASEF $2" >/dev/null 2>&1 \
    && cmake --build "build_b994_$1" -j4 >"$B/build_$1.log" 2>&1 && cp "build_b994_$1/EBOOT.PBP" "$B/eboot_$1.PBP" )
}
build new "" & build old "-DCARD994_OLD=1" & wait
for v in new old; do [ -f "$B/eboot_$v.PBP" ] || { echo "нет сборки $v (см. $B/build_$v.log)"; echo FAIL; exit 2; }; done
export OUT=$B
run() { bash tools/emu_run.sh "tests/card994/$2_scenario.txt" "$2_$1" "$B/eboot_$1.PBP" 300 >/dev/null 2>&1 || true; }   # run ВАРИАНТ СЦЕНАРИЙ -> $B/out_СЦЕНАРИЙ_ВАРИАНТ
run new brief & run old brief & wait
run new brief_old & run new story & wait
run old story & wait
rc=0
verdict() { local o; o=$("$@" 2>&1); local r=$?; echo "$o" | grep замер >&2; echo "$o" | tail -1 | cut -c1-300 >&2; return $r; }
echo "— №994 новое (3 брифинга, первый после загрузки с газетой):"; verdict $C enter "$B/out_brief_new" || { echo "  КРАСНЫЙ (плохо)"; rc=1; }
echo "— красный контроль (сборка -DCARD994_OLD=1, TEST70):";       if verdict $C enter "$B/out_brief_old"; then echo "  ЗЕЛЁНЫЙ (красный не пойман)"; rc=1; else echo "  красный (как нужно)"; fi
echo "— flag card994 0 на новой сборке = прежнее:";                 if verdict $C enter "$B/out_brief_old_new"; then echo "  ЗЕЛЁНЫЙ (флаг не работает)"; rc=1; else echo "  красный (как нужно)"; fi
echo "— раскадровка новой сборки тем же гейтом (подряд снимки, 3 брифинга):"; verdict $C enter "$B/out_story_new" || { echo "  КРАСНЫЙ (плохо)"; rc=1; }
# раскадровка TEST70 / стало: каждый второй снимок подряд (в эмуляторе ≈ 30 кадров/с, то есть шаг ≈ 2 кадра); a — первая после загрузки (газета LOADING, потом въезд), b — вторая, c — третья
for p in a b c; do python3 tests/card994/sheet.py "$B/out_story_old" $p "$SH/test70_$p.png" 0 60 2 8; python3 tests/card994/sheet.py "$B/out_story_new" $p "$SH/stalo_$p.png" 0 60 2 8; done
echo "раскадровки: $SH"
[ $rc = 0 ] && echo PASS || echo FAIL
exit $rc
