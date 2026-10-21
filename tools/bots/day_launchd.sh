#!/bin/sh
# Дневные боты по расписанию Мака (правка Роба 97, 30.09): launchd в 09:00 (ua.heartbeat.shar-bots-day) и кнопка
# «SHAR боты СТАРТ» на рабочем столе. День.command = tools/bots/night.py --day: 2 процесса с низким приоритетом до 23:00,
# только процессор Мака, без Claude и API. Только от сети; ушёл на батарею — остановка. В 23:00 начинается ночь.
# Остановить в любой момент: «SHAR боты СТОП» на рабочем столе (tools/bots/Стоп-боты.command) или закрыть окно Терминала.
cd "$(dirname "$0")/../.." || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
on_ac() { pmset -g ps | grep -q "AC Power"; }
say() { echo "$(date '+%F %H:%M:%S') $*"; }
H=$(date +%H)
if [ "$H" -lt 8 ] || [ "$H" -ge 23 ]; then say "не день ($(date +%H:%M)) — пропускаю"; exit 0; fi
if ! on_ac; then say "от батареи — день не запускаю"; exit 0; fi
if pgrep -f "python3 tools/bots/night[.]py" >/dev/null; then say "боты уже идут — второй раз не запускаю"; exit 0; fi
say "старт: tools/bots/День.command $*"
sh tools/bots/День.command "$@" &
PID=$!
while kill -0 $PID 2>/dev/null; do
  sleep 30
  if ! on_ac; then say "ушёл на батарею — останавливаю"; pkill -INT -f "tools/bots/night.py --day"; fi
done
wait $PID; say "конец, код $?"
