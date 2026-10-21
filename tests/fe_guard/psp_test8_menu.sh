#!/bin/bash
# Правка Роба 265, разбор проверки на ЖЕЛЕЗЕ (часть M тура TEST 8, tests/fe_guard/psp_test8_menu.txt).
#   tests/fe_guard/psp_test8_menu.sh --read [ПАПКА_ТУРА]   по умолчанию — самая свежая build/psp-tour/* с кадрами fe265
# Тур кладёт и забирает терминал: tools/tour_psp.sh --deploy --test8 / --fetch (shots/ с fe265_* забираются вместе с туром).
# Что делает: строки FEFLY/MENU/GAME из smoke.txt тура; sweep_read.py --ref <кадры эмулятора> (сверка поз PSP и эмулятора:
# подтверждена ли версия 265 и убирает ли её правило); sweep_read.py --gate (проход b против a на самой PSP) и лист
# fe265_sheet.png (a | b | отличия) в папке тура. Кадры эмулятора — tests/fe_guard/run.sh
# (build/twins/scen/full/265-menu-floor_sweep_new/shots; другой путь — FE265_REF).
set -u
cd "$(dirname "$0")/../.."
PY=.venv/bin/python; REF="${FE265_REF:-build/twins/scen/full/265-menu-floor_sweep_new/shots}"
case "${1:-}" in
  --read)
    O="${2:-}"
    if [ -z "$O" ]; then O="$(ls -dt build/psp-tour/*/ 2>/dev/null | while read d; do ls "$d"shots/fe265_*.bmp > /dev/null 2>&1 && { echo "${d%/}"; break; }; done)"; fi
    [ -n "$O" ] && ls "$O"/shots/fe265_*.bmp > /dev/null 2>&1 || { echo "нет кадров fe265 в ${O:-build/psp-tour/*} (тур ещё не забран или перелёт не начался — см. smoke.txt тура: MENU / FEFLY)"; exit 1; }
    echo "тур: $O, кадров fe265: $(ls "$O"/shots/fe265_*.bmp | wc -l | tr -d ' ')"
    grep -E "^(SCENE M_|MENU |FEFLY|GAME |FE n=)" "$O/smoke.txt" 2>/dev/null | head -12
    if [ -d "$REF" ]; then "$PY" tests/fe_guard/sweep_read.py "$O/shots" --ref "$REF" | tee "$O/fe265_ref.txt" | grep -vE "^ +[0-9]"
    else echo "нет кадров эмулятора $REF (tests/fe_guard/run.sh) — только PSP a против b"; fi
    "$PY" tests/fe_guard/sweep_read.py "$O/shots" --gate --sheet "$O/fe265_sheet.png" > "$O/fe265_ab.txt"; tail -2 "$O/fe265_ab.txt" | cut -c1-300
    echo "таблицы: $O/fe265_ref.txt, $O/fe265_ab.txt; лист: $O/fe265_sheet.png" ;;
  *) echo "tests/fe_guard/psp_test8_menu.sh --read [ПАПКА_ТУРА]"; exit 2 ;;
esac
