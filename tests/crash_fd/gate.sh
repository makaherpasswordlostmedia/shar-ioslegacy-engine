#!/bin/bash
# Ловушка 05.10 (Роб: «загрузил DEV — Гомер в пустоте без текстур, карта не догрузилась, мигает»; ящик PSP: ошибки чтения клеток
# ~160/с за 0 мс, куча свободна — у потока загрузки отняли файл level.shr: на PSP номер закрытого файла тут же получает следующий
# открытый, повторное закрытие старого номера закрывает файл загрузчика). Правило (viewer/main.c loaderThread, __wrap_sceIoClose):
# чужое закрытие файла загрузчика ловится обёрткой (строка IOCLOSE в ящике), загрузчик открывает level.shr заново; два упавших
# чтения подряд — тоже переоткрытие (≤ 16 за запуск). Гейт: безголовый эмулятор, служебно «flag fdsteal» — закрыть файл
# загрузчика и занять номер другим файлом, все клетки выгрузить, отъехать; зелёный — клетки грузятся, ошибок чтения нет,
# в журнале IOCLOSE steal=1 reopen; красный «flag fdfixold 1» — ошибки чтения растут.
#   tests/crash_fd/gate.sh [EBOOT]   (по умолчанию viewer/build/EBOOT.PBP)
set -u; cd "$(dirname "$0")/../.."
EB=$(cd "$(dirname "${1:-viewer/build/EBOOT.PBP}")" && pwd)/$(basename "${1:-viewer/build/EBOOT.PBP}")
H=${CRASHFD_HOME:-build/gates/crash_fd}; mkdir -p "$H"; TAG=${CRASHFD_TAG:-crashfd}
mk() { { echo "flag msn"; echo "wait 4"; [ "$1" = red ] && echo "flag fdfixold 1"; echo "flag fdsteal"; echo "wait 1"
         echo "goto -150 -300 0"; echo "wait 6"; echo "goto 150 600 0"; echo "wait 6"; echo "shot fd_$1"; echo "end"; } > "$H/$1.txt"; }
for k in green red; do mk $k; SCEN_HOME="$PWD/$H/home_$k" SCEN_EBOOT="$EB" nice python3 ~/.claude/skills/shar-level-polish/scripts/scen.py "${TAG}_$k" "$H/$k.txt" > "$H/$k.log" 2>&1 & done; wait
ok=1
for k in green red; do
  S="${SCEN_ROOT:-$HOME/Downloads/shar-psp}/build/twins/scen/full/${TAG}_$k/smoke.txt"
  st=$(grep "^FDSTEAL" "$S" | head -1); re=$(grep -E "^STAT " "$S" | grep -oE "readerr [0-9]+" | awk '{s+=$2} END {print s+0}'); io=$(grep "^IOCLOSE" "$S" | tail -1)
  cells=$(grep "^BB" "$S" | tail -1 | grep -oE "cells +[0-9]+" | awk '{print $2}')
  echo "  $k: ${st:-нет FDSTEAL}; ошибок чтения $re; клеток в памяти ${cells:-?}; ${io:-нет IOCLOSE}"
  if [ "$k" = green ]; then { [ -n "$st" ] && [ "$re" -eq 0 ] && [ "${cells:-0}" -ge 50 ] && echo "$io" | grep -qE "steal=[1-9]" && echo "$io" | grep -qE "reopen=[1-9]"; } || ok=0
  else { [ -n "$st" ] && [ "$re" -gt 0 ]; } || ok=0; fi
done
[ $ok = 1 ] && echo "ИТОГ: PASS (отнятый файл загрузчика переоткрывается, карта грузится; красный fdfixold — ошибки чтения)" || { echo "ИТОГ: FAIL"; exit 1; }
