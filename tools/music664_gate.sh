#!/bin/bash
# Гейт №664 «музыка уровня после входа в уровень»: tools/music664_gate.sh <пакет с тур-EBOOT> [resume|new]
#   resume: титул -> RESUME (сохранение Роба, L1 миссия 4, Гомер пешком в гараже) -> телепорт в машину -> езда
#   new:    титул -> NEW GAME -> ролик -> облёт -> игра
# PASS, если после загрузки уровня была строка LEVELAUDIO и тема меню (simpsons_theme) в конце прогона не играет (AUDV cur=).
# Факт PS2 (Дирижёр 16.10): пешком в L1 музыки уровня нет, за рулём sunday_drive. Красный контроль: EBOOT без правки (сборка с -DLEVEL_MUSIC_NOLOAD_OLD=1)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; PKG="${1:?пакет}"; MODE="${2:-resume}"
SCN=$ROOT/tests/smoke_scenes/music664.txt; [ "$MODE" = new ] && SCN=$ROOT/tests/smoke_scenes/music664_new.txt
OUT=$(SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_SCN=$SCN SMOKE_MAXT=${MAXT:-330} nice -n 20 "$ROOT/tools/smoke.sh" "$PKG" 2>&1 | grep -o 'build/smoke/[0-9-]*' | tail -1)
L="$ROOT/$OUT/smoke.txt"; [ -f "$L" ] || { echo "music664[$MODE]: нет smoke.txt"; exit 2; }
la=$(grep -c '^LEVELAUDIO' "$L")
last=$(grep '^AUDV' "$L" | tail -1 | sed -n 's/.*cur=\([^ ]*\).*/\1/p')
trk=$(awk '/^LEVEL ev=load/{f=1} f&&/^STREAM s=music track=/{printf "%s ", $3}' "$L")
echo "music664[$MODE] $OUT: LEVELAUDIO=$la; после загрузки: ${trk:-нет смен}; в конце cur=${last:-?}"
# №665: музыка уровня стартует на первом кадре игры (PS2: жёсткий срез, ирис не ждём) и не режет недоигранный стингер газеты (newsleft<=0,05); газета держит стингер до конца (строка NEWSMUS left= <= 0,05)
la_line=$(grep '^LEVELAUDIO onfoot' "$L" | tail -1); iris=$(echo "$la_line" | sed -n 's/.* iris=\([0-9]*\).*/\1/p'); nl=$(echo "$la_line" | sed -n 's/.* newsleft=\([0-9.]*\).*/\1/p')
nm=$(grep '^NEWSMUS' "$L" | tail -1 | cut -c1-90)
echo "  старт музыки уровня: iris=${iris:-?} newsleft=${nl:-?}; ${nm:-NEWSMUS нет}"
ok665=1; awk -v v="${nl:-9}" 'BEGIN{exit !(v<=0.05)}' || ok665=0
[ "${G665:-1}" = 0 ] && ok665=1
[ "$la" -ge 1 ] && [ "$last" != simpsons_theme ] && [ -n "$last" ] && [ $ok665 = 1 ] && { echo "PASS"; exit 0; }
echo "FAIL"; exit 1
