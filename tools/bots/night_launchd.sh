#!/bin/sh
# Ночь ботов по расписанию Мака (Т1.6, docs/handoff/ДВА_ТЕСТИРОВЩИКА_2026-09-28.md §3). Запускает launchd в 23:00
# (tools/bots/night_schedule.sh install). Только локально: tools/bots/Ночь.command — процессор Мака, без Claude, без API, без сети.
# Запуск только от сети; ушёл на батарею посреди ночи или 07:10 уже наступило — ночь останавливается (Ctrl-C: итог пишется).
# Лог: ~/Library/Logs/shar-bots-night.log (launchd не пишет в ~/Downloads — защита папок macOS). Аргументы передаются в Ночь.command (пробный запуск: --until ЧЧ:ММ).
#   NIGHT_FAKE_BATTERY=1 — отрицательный контроль гейта: «Мак от батареи», ночь не начинается; NIGHT_ANY_TIME=1 — пробный запуск днём
# Старт только с 23:00 до 05:00: проснулся позже — пропуск (иначе ночь шла бы до 07:00 следующего дня)
cd "$(dirname "$0")/../.." || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
on_ac() { [ -z "$NIGHT_FAKE_BATTERY" ] && pmset -g ps | grep -q "AC Power"; }
say() { echo "$(date '+%F %H:%M:%S') $*"; }
stop_all() {   # ночь (Ctrl-C: итог пишется) и её прогоны: замороженные скрипты и бинарники из build/bots/nights/*/
  pkill -INT -f "tools/bots/night.py --procs"; pkill -TERM -f "build/bots/nights/[^ ]*/(bin|scripts)/"; }
H=$(date +%H)   # launchd догоняет пропущенный запуск при пробуждении: утром ночь не начинаем (до 07:00 следующего дня)
if [ -z "$NIGHT_ANY_TIME" ] && [ "$H" -lt 23 ] && [ "$H" -ge 5 ]; then say "не ночь ($(date +%H:%M)) — пропускаю"; exit 0; fi
if ! on_ac; then say "от батареи — ночь не запускаю"; exit 0; fi
if pgrep -f "tools/bots/night.py --procs" >/dev/null; then say "ночь уже идёт — второй не запускаю"; exit 0; fi
STOP="${NIGHT_HARD_STOP:-07:10}"
say "старт: tools/bots/Ночь.command $*"
sh tools/bots/Ночь.command "$@" &
PID=$!
while kill -0 $PID 2>/dev/null; do
  sleep 30
  NOW=$(date '+%H:%M')
  if ! on_ac; then say "ушёл на батарею — останавливаю"; stop_all; fi
  if [ "$NOW" = "$STOP" ]; then say "$STOP — жёсткая остановка"; stop_all; fi
done
wait $PID; say "конец, код $?"
