#!/bin/sh
# Живая страница ботов SHAR в браузере (просьба Роба 30.09). Закрыть окно Терминала — страница перестанет обновляться.
cd "$(dirname "$0")/../.." || exit 1
( sleep 3; open http://127.0.0.1:8777 ) &
exec .venv/bin/python tools/bots/live.py
