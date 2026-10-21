#!/bin/sh
# Дневные боты (правка 97): окно открывает launchd в 09:00 или кнопка «SHAR боты СТАРТ». Закрыть окно — остановить.
cd "$(dirname "$0")/../.." || exit 1
sh tools/bots/day_launchd.sh "$@" 2>&1 | tee -a "$HOME/Library/Logs/shar-bots-day.log"
