#!/bin/bash
# №992 приёмка (окно «Управление», TEST71): появление пузыря сообщения миссии — короче и спокойнее (3 шага по 1/50 с вместо 8, старт 0,88 вместо 0,25),
# текст и аватар едут вместе с рамкой (тот же масштаб и прозрачность, без отставания 0,16 с и сдвига справа налево). Раскладка текста конечная, кегль и место не тронуты.
# Выключатели: BUBBLE992_OLD=1 (сборка) / файл bubble992old рядом с EBOOT / flag bubble992 0 (сценарий).
# Гейты: новый код ЗЕЛЁНЫЙ, прежний (сборка -DBUBBLE992_OLD=1) КРАСНЫЙ; flag bubble992 0 на новой сборке = прежнее (красный и зелёный по гейту №942). Последняя строка: PASS или FAIL.
#   tests/bubble992/accept60.sh          REUSE=1 — не пересобирать EBOOT, если уже есть
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
set -u
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"
export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
T=$HOME/Downloads/shar-psp/build/t71; B=${B992_OUT:-$T/work_bubble992}; SH=${B992_SHOTS:-$T/shots_bubble992}; mkdir -p "$B" "$SH"
C="python3 tests/bubble992/check.py"; C942="python3 tests/bubble942/check.py"; export EMU_OWNER=Управление EMU_MINE=2
BASEF="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1 -DZF932_OLD=1"
build() {   # build ИМЯ "ДОП_ФЛАГИ"
  [ "${REUSE:-0}" = 1 ] && [ -f "$B/eboot_$1.PBP" ] && return 0
  ( cd viewer && psp-cmake -S . -B "build_b992_$1" -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$BASEF $2" >/dev/null 2>&1 \
    && cmake --build "build_b992_$1" -j4 >"$B/build_$1.log" 2>&1 && cp "build_b992_$1/EBOOT.PBP" "$B/eboot_$1.PBP" )
}
build new "" & build old "-DBUBBLE992_OLD=1" & wait
for v in new old; do [ -f "$B/eboot_$v.PBP" ] || { echo "нет сборки $v (см. $B/build_$v.log)"; echo FAIL; exit 2; }; done
export OUT=$B
run() { bash tools/emu_run.sh "tests/bubble992/$2_scenario.txt" "$2_$1" "$B/eboot_$1.PBP" 900 >/dev/null 2>&1 || true; }   # run ВАРИАНТ СЦЕНАРИЙ -> $B/out_СЦЕНАРИЙ_ВАРИАНТ
run new pop & run old pop & wait
run new pop_old & wait
rc=0
verdict() { local o; o=$("$@" 2>&1); local r=$?; echo "$o" | grep замер >&2; echo "$o" | tail -1 | cut -c1-260 >&2; return $r; }
echo "— №992 новое появление (сборка по умолчанию):";           verdict $C pop "$B/out_pop_new" || { echo "  КРАСНЫЙ (плохо)"; rc=1; }
echo "— №992 красный контроль (сборка -DBUBBLE992_OLD=1, TEST70):"; if verdict $C pop "$B/out_pop_old"; then echo "  ЗЕЛЁНЫЙ (красный не пойман)"; rc=1; else echo "  красный (как нужно)"; fi
echo "— flag bubble992 0 на новой сборке = прежнее (гейт 992 красный):"; if verdict $C pop "$B/out_pop_old_new"; then echo "  ЗЕЛЁНЫЙ (флаг не работает)"; rc=1; else echo "  красный (как нужно)"; fi
echo "— прежнее появление держит гейт №942 (сборка OLD и flag bubble992 0):"
for d in pop_old pop_old_new; do verdict $C942 pop "$B/out_$d" || { echo "  КРАСНЫЙ (плохо): $d"; rc=1; }; done
echo "— новое появление гейт №942 не держит (он требует задержку и слайд, их заменил №992; ожидаемо красный):"; if verdict $C942 pop "$B/out_pop_new"; then echo "  ЗЕЛЁНЫЙ (новое = прежнее?)"; rc=1; else echo "  красный (ожидаемо)"; fi
# раскадровка TEST70 / стало: каждый кадр 50 к/с (шаг 0,02 с), 13 кадров = 0,24 с; s — короткий, m — 3 строки, a — короткий с аватаром, l — длинный (5 строк) с аватаром
for t in s m a l; do python3 tests/bubble992/sheet.py "$B/out_pop_old" $t "$SH/test70_$t.png" 13 >/dev/null 2>&1; python3 tests/bubble992/sheet.py "$B/out_pop_new" $t "$SH/stalo_$t.png" 13 >/dev/null 2>&1; done
echo "раскадровки: $SH"
[ $rc = 0 ] && echo PASS || echo FAIL
exit $rc
