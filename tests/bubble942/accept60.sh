#!/bin/bash
# №942 приёмка (окно «Пузырь», TEST60): появление пузыря сообщения — текст и аватар не растут с рамкой (конечная раскладка с первого кадра, проявление после раскрытия рамки),
# перенос строк считается один раз, подвисший кадр не съедает анимацию. Каждое поведение под флагом *_OLD (1 = прежнее): BUBBLE_TEXT942_OLD, BUBBLE_WRAP942_OLD, BUBBLE_LAG942_OLD.
# Гейты: новый код ЗЕЛЁНЫЙ, прежний КРАСНЫЙ (отдельная сборка с -D<ИМЯ>_OLD=1). Последняя строка: PASS или FAIL.
#   tests/bubble942/accept60.sh          REUSE=1 — не пересобирать EBOOT, если уже есть
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
set -u
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"
export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
T=$HOME/Downloads/shar-psp/build/t60; B=${B942_OUT:-$T/work_bubble}; SH=$T/shots_bubble; mkdir -p "$B" "$SH"
C="python3 tests/bubble942/check.py"; export EMU_OWNER=bubble
BASEF="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1"
build() {   # build ИМЯ "ДОП_ФЛАГИ"
  [ "${REUSE:-0}" = 1 ] && [ -f "$B/eboot_$1.PBP" ] && return 0
  ( cd viewer && psp-cmake -S . -B "build_b942_$1" -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$BASEF $2" >/dev/null 2>&1 \
    && cmake --build "build_b942_$1" -j4 >"$B/build_$1.log" 2>&1 && cp "build_b942_$1/EBOOT.PBP" "$B/eboot_$1.PBP" )
}
build new "" & build text "-DBUBBLE_TEXT942_OLD=1" & wait
build wrap "-DBUBBLE_WRAP942_OLD=1" & build lag "-DBUBBLE_LAG942_OLD=1" & wait
build all "-DBUBBLE_TEXT942_OLD=1 -DBUBBLE_WRAP942_OLD=1 -DBUBBLE_LAG942_OLD=1"
for v in new text wrap lag all; do [ -f "$B/eboot_$v.PBP" ] || { echo "нет сборки $v (см. $B/build_$v.log)"; echo FAIL; exit 2; }; done
run() { bash tools/emu_run.sh "tests/bubble942/$2_scenario.txt" "$2_$1" "$B/eboot_$1.PBP" 900 >/dev/null 2>&1 || true; }   # run ВАРИАНТ СЦЕНАРИЙ -> $B/out_СЦЕНАРИЙ_ВАРИАНТ
export OUT=$B
run new pop & run text pop & wait
run wrap pop & run all pop & wait
run new lag & run lag lag & wait
rc=0
gate() {   # gate ИМЯ ПРОВЕРКА НОВЫЙ СТАРЫЙ
  local n o nrc orc
  n=$($C "$2" "$B/out_$3" 2>&1); nrc=$?; o=$($C "$2" "$B/out_$4" 2>&1); orc=$?
  echo "$1: новый $([ $nrc = 0 ] && echo ЗЕЛЁНЫЙ || echo "КРАСНЫЙ (плохо): $(echo "$n" | tail -1)"); прежний ($4) $([ $orc != 0 ] && echo "красный (как нужно): $(echo "$o" | tail -1 | cut -c1-150)" || echo "ЗЕЛЁНЫЙ (красный не пойман)")"
  echo "$n" | grep замер; [ $nrc = 0 ] && [ $orc != 0 ] || rc=1
}
gate "№942 текст и аватар не растут с рамкой, после раскрытия, слайд справа налево" pop pop_new pop_text
gate "№942 перенос строк один раз на текст"                                       wrap pop_new pop_wrap
gate "№942 подвисший кадр не съедает анимацию"                                     lag  lag_new lag_lag
# куча и цена: против сборки со всеми прежними поведениями (тот же код кадра, UIT — мс на кадр HUD на Маке; PSP = ×5,8)
python3 - "$B/out_pop_new/smoke.txt" "$B/out_pop_all/smoke.txt" <<'PY' || rc=1
import re, sys
def ui(p):
    t = open(p).read(); L = [float(m.group(1)) + float(m.group(2)) for m in re.finditer(r'UIT n=\d+ items=\S+ setup=(\S+) loop=(\S+)', t)]
    h = re.search(r'heap free at start (\S+) MB', t); return (sum(L) / len(L) if L else -1), float(h.group(1)) if h else -1
(a, ha), (b, hb) = ui(sys.argv[1]), ui(sys.argv[2])
print(f'цена кадра HUD (setup+loop): новый {a:.3f} мс, прежний {b:.3f} мс (PSP ×5,8: {a*5.8:.2f} против {b*5.8:.2f}); куча на старте: новый {ha} МБ, прежний {hb} МБ')
ok = a >= 0 and a <= b * 1.15 + 0.03 and abs(ha - hb) <= 0.01
print('цена и куча не хуже:', 'PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
PY
# снимки до/после для Роба: кадры появления (шаг 0,02 с) — короткий, 3 строки, с аватаром короткий, с аватаром длинный
for t in s m a l; do python3 tests/bubble942/sheet.py "$B/out_pop_all" $t "$SH/before_$t.png" 13 >/dev/null 2>&1; python3 tests/bubble942/sheet.py "$B/out_pop_new" $t "$SH/after_$t.png" 13 >/dev/null 2>&1; done
echo "снимки до/после: $SH"
[ $rc = 0 ] && echo PASS || echo FAIL
exit $rc
