#!/bin/sh
# Остановить всех ботов SHAR на Маке (правка Роба 97): дневных и ночных. Итог прогона пишется (Ctrl-C), утренний отчёт —
# build/bots/morning.md. Снова запустить днём — «SHAR боты СТАРТ» на рабочем столе.
echo "Останавливаю ботов SHAR…"
pkill -INT -f "tools/bots/night.py" 2>/dev/null
pkill -TERM -f "build/bots/nights/[^ ]*/(bin|scripts)/" 2>/dev/null
sleep 3
if pgrep -f "python3 tools/bots/night[.]py" >/dev/null; then pkill -TERM -f "tools/bots/night.py"; sleep 2; fi
if pgrep -f "python3 tools/bots/night[.]py" >/dev/null; then echo "ещё идут — попробуй ещё раз"; else echo "Боты остановлены. Мощность Мака свободна."; fi
