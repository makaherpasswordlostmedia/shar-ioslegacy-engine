#!/bin/bash
# Гейт анимаций и звуков HUD в эмуляторе (пакет «Интерфейс в игре», 28.09): пульс △, ровное кольцо Hit & Run,
# всплывание уведомлений, звуки интерфейса оригинала, заголовок паузы. Хост-часть (математика и цвета из данных диска):
# tests/ui/anim.py. Эмулятор — только через tools/smoke.sh (общая очередь PPSSPP).
#   tools/ui_anim_gate.sh [DIR]              -> первая строка итога, код 0 = OK
#   tools/ui_anim_gate.sh --negative [DIR]   в сценарий подложены: △ без пульса (uipulse0), прежнее кольцо (uihnrold),
#                                            уведомления без всплывания (uipop0), звуки выключены (uisfx0) —
#                                            КАЖДЫЙ из четырёх разделов обязан покраснеть (тогда PASS)
#   tools/ui_anim_gate.sh --ui FILE [DIR]    тот же сценарий с другим ui.shr (прежний — отрицательный контроль заголовка
#                                            паузы: tests/ui/pause_title.py обязан покраснеть, тогда PASS)
#   ANIM_SHOTS=папка                         куда скопировать снимки (по умолчанию DIR/ui_shots/anim[_neg])
cd "$(dirname "$0")/.."
NEG=0; UI=""; if [ "${1:-}" = --negative ]; then NEG=1; shift; fi
if [ "${1:-}" = --ui ]; then UI="$2"; shift 2; fi
DIR="${1:-build}"; SCN=tests/ui/anim_scenario.txt
mkdir -p build/emu
if [ -n "$UI" ]; then   # копия DIR (клоны APFS) с подменённым ui.shr
  T=build/emu/anim_ui; rm -rf "$T"; mkdir -p "$T"; cp -c "$DIR/EBOOT.PBP" "$T/"
  for f in $(tools/ship_files.sh); do mkdir -p "$T/$(dirname "$f")"; cp -c "$DIR/$f" "$T/$f" 2>/dev/null || cp "$DIR/$f" "$T/$f"; done
  cp "$UI" "$T/ui.shr"; DIR="$T"
fi
if [ $NEG = 1 ]; then
  SCN=build/emu/anim_negative.txt
  awk '{ sub(/^flag uipulse /, "flag uipulse0 "); sub(/^flag uihnr$/, "flag uihnrold"); print;
         if ($0 == "scene anim" || $0 == "flag uioff") { print "flag uisfx0"; print "flag uipop0" } }' tests/ui/anim_scenario.txt > "$SCN"
fi
.venv/bin/python tests/ui/anim.py > build/emu/anim_host.txt; HRC=$?
OUT=$(SMOKE_SCN="$SCN" tools/smoke.sh "$DIR" 2>&1); SRC=$?
REP=$(echo "$OUT" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)
if [ -z "$REP" ] || [ ! -f "$REP/smoke.txt" ]; then echo "FAIL: нет отчёта смоука"; echo "$OUT" | tail -5; exit 1; fi
CHK=$(.venv/bin/python tests/ui/anim_check.py "$REP/smoke.txt"); CRC=$?
SH="${ANIM_SHOTS:-build/ui_shots/anim$([ $NEG = 1 ] && echo _neg)$([ -n "$UI" ] && echo _ui)}"; mkdir -p "$SH"; cp "$REP"/*.png "$SH"/ 2>/dev/null
TTL=$(.venv/bin/python tests/ui/pause_title.py "$REP/pause_title.png"); TRC=$?
CHK="$CHK
$TTL"
if [ -n "$UI" ]; then
  if [ $TRC != 0 ]; then echo "PASS (отрицательный контроль: заголовок паузы с $UI покраснел)"; R=0
  else echo "FAIL (отрицательный контроль: заголовок с $UI прошёл — замер ничего не ловит)"; R=1; fi
elif [ $NEG = 1 ]; then
  RED=$(echo "$CHK" | grep -cE '^(пульс △|кольцо Hit & Run|всплывание STAGE COMPLETE|звуки интерфейса) \(эмулятор\): КРАСНОЕ')
  if [ "$RED" = 4 ]; then echo "PASS (отрицательный контроль: покраснели все 4 раздела)"; R=0
  else echo "FAIL (отрицательный контроль: покраснело $RED из 4 — сверка что-то не ловит)"; R=1; fi
else
  if [ $CRC = 0 ] && [ $HRC = 0 ] && [ $TRC = 0 ]; then echo "PASS"; R=0; else echo "FAIL (эмулятор $CRC, хост $HRC, заголовок $TRC)"; R=1; fi
fi
echo "$CHK"
echo "хост: $(head -1 build/emu/anim_host.txt); смоук (FPS/кадры/память): $([ $SRC = 0 ] && echo OK || echo "ПРОВАЛ, $(echo "$OUT" | head -1)")"
echo "отчёт: $REP; снимки: $SH"
exit $R
