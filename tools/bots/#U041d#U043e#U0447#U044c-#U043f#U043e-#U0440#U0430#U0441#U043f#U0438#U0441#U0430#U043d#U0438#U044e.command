#!/bin/sh
# Ночь ботов по расписанию (Т1.6): это окно открывает launchd в 23:00 (tools/bots/night_schedule.sh). Внутри —
# tools/bots/night_launchd.sh: только от сети, Ночь.command до 07:00, без Claude и API. Окно можно не трогать; закрыть — остановить ночь.
cd "$(dirname "$0")/../.." || exit 1
sh tools/bots/night_launchd.sh "$@" 2>&1 | tee -a "$HOME/Library/Logs/shar-bots-night.log"
