#!/bin/bash
# Гейт правок Роба 22, 25, 26, 36, 38, 39, 41 (видео с PSP 28.09) и 48 (игра на PSP 29.09): хост (Мак) + эмулятор одним прогоном сценария.
#   tests/ui/rob_rows.sh [DIR]              -> PASS / FAIL; DIR — EBOOT.PBP и данные (по умолчанию build/), как у tools/smoke.sh
#   tests/ui/rob_rows.sh --negative [DIR]   подложено плохое: пульт по одному отсчёту (padbuf --old), простой Ланцош
#                                           (UI_UPSCALE_PLAIN), прежний брифинг (UI_BRIEF_OLD), в эмуляторе — дверь по
#                                           триггеру без △ (doorwalk), △ без пульса (uipulse0), аватар прежнего размера
#                                           (uiavatarold), текст без значка с места значка (uimsgnoiconold), прежнее кольцо (uihnrold), разговор не ставится (uitalkoff):
#                                           КАЖДЫЙ раздел обязан покраснеть (тогда PASS)
# Хост: tests/ui/padbuf.c (25), tests/ui/upscale_check.py (22), tests/ui/brief_layout.py (39), tools/ui_export.py legibility (39).
# Эмулятор: tests/ui/rob_rows_scenario.txt -> tests/ui/rob_rows_check.py (22, 25, 26, 36, 38, 41). Только через tools/smoke.sh.
cd "$(dirname "$0")/../.."
NEG=0; if [ "${1:-}" = --negative ]; then NEG=1; shift; fi
DIR="${1:-build}"; PY=.venv/bin/python; mkdir -p build/emu
R=0; say() { echo "$*"; }
cc -O1 -I viewer tests/ui/padbuf.c -o build/padbuf-host || { say "FAIL: сборка tests/ui/padbuf.c"; exit 1; }
if [ $NEG = 0 ]; then
  build/padbuf-host > build/emu/rr_padbuf.txt; P1=$?
  $PY tests/ui/upscale_check.py > build/emu/rr_upscale.txt; P2=$?
  $PY tests/ui/brief_layout.py > build/emu/rr_brief.txt; P3=$?
  UI_SCRATCH="$PWD/build/emu/ui" $PY tools/ui_export.py legibility > build/emu/rr_legib.txt; P4=$?
  say "хост: пульт $( [ $P1 = 0 ] && echo OK || echo КРАСНОЕ ), увеличитель $( [ $P2 = 0 ] && echo OK || echo КРАСНОЕ ), брифинг $( [ $P3 = 0 ] && echo OK || echo КРАСНОЕ ), читаемость $( [ $P4 = 0 ] && echo OK || echo КРАСНОЕ )"
  [ $P1$P2$P3$P4 = 0000 ] || R=1
  SCN=tests/ui/rob_rows_scenario.txt
else
  build/padbuf-host --old > build/emu/rr_padbuf.txt; P1=$?
  UI_UPSCALE_PLAIN=1 $PY tests/ui/upscale_check.py > build/emu/rr_upscale.txt; P2=$?
  $PY tests/ui/brief_layout.py --negative > build/emu/rr_brief.txt && P3=1 || P3=0   # --negative: 0 = прежняя раскладка покраснела
  say "хост (подложено): пульт $( [ $P1 != 0 ] && echo КРАСНОЕ || echo зелёное ), увеличитель $( [ $P2 != 0 ] && echo КРАСНОЕ || echo зелёное ), брифинг $( [ $P3 != 0 ] && echo КРАСНОЕ || echo зелёное )"
  [ $P1 != 0 ] && [ $P2 != 0 ] && [ $P3 != 0 ] || R=1
  SCN=build/emu/rob_rows_negative.txt
  awk 'BEGIN{n=0} { if ($0 == "flag uiavatar") print "flag uiavatarold"; else if ($0 == "flag uihnr") print "flag uihnrold"; else if ($0 == "flag uimsgnoicon") print "flag uimsgnoiconold"; else print;
        if ($0 == "wait 3" && !d) { print "flag doorwalk"; d=1 }
        if ($0 == "flag uipulsetrace" && !p) { print "flag uipulse0 0.01"; p=1 }
        if ($0 == "flag msn") { print "wait 0.5"; print "flag uitalkoff" } }' tests/ui/rob_rows_scenario.txt > "$SCN"
fi
OUT=$(SMOKE_SCN="$SCN" tools/smoke.sh "$DIR" 2>&1); SRC=$?
REP=$(echo "$OUT" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)
if [ -z "$REP" ] || [ ! -f "$REP/smoke.txt" ]; then say "FAIL: нет отчёта смоука"; echo "$OUT" | tail -5; exit 1; fi
CHK=$($PY tests/ui/rob_rows_check.py "$REP/smoke.txt"); CRC=$?
echo "$CHK"
if [ $NEG = 1 ]; then
  RED=$(echo "$CHK" | grep -cE '^(41 дверь по △|41 подсказка △ пульсирует|22 аватар = высота пузыря|48 пузырь как в оригинале, текст внутри|36 кольцо Hit & Run|26\+38 разговор) \(эмулятор\): КРАСНОЕ')
  if [ "$RED" = 6 ] && [ $R = 0 ]; then say "PASS (отрицательный контроль: покраснели все 6 разделов эмулятора и 3 хоста)"; R=0
  else say "FAIL (отрицательный контроль: эмулятор покраснел $RED из 6, хост $( [ $R = 0 ] && echo 3 || echo 'не все' ) из 3)"; R=1; fi
else
  [ $CRC = 0 ] || R=1
  [ $R = 0 ] && say PASS || say FAIL
fi
say "отчёт: $REP (снимки door_prompt, avatar, ring, briefing, getin, brief_cancel); смоук этого прогона: $([ $SRC = 0 ] && echo OK || echo "$(echo "$OUT" | head -1)")"
exit $R
