#!/bin/sh
# Днём фоном (пункт Б5): 2 процесса с низким приоритетом до 23:00 — догонялки и миссионер/навигатор (tools/bots/night.py --day).
# Итог: build/bots/morning.md. Остановить — закрыть окно Терминала.
cd "$(dirname "$0")/../.."
exec python3 tools/bots/night.py --day "$@"
