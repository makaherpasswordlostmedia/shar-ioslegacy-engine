#!/bin/sh
# Двойной клик перед сном: ночной прогон до 07:00 (tools/cartest/night.py). Только процессор Мака, без AI и API,
# на PSP ничего. caffeinate не даёт Маку уснуть, пока идёт прогон, и отпускает сам по его окончании.
# Утром: build/sandbox/night/<дата>/СВОДКА.md
cd "$(dirname "$0")/../.."
exec caffeinate -ims python3 tools/cartest/night.py "$@"
