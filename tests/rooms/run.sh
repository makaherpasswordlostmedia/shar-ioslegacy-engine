#!/bin/bash
# Комнаты (пункт 11.2): миссия m0 «The Cola Caper» в игре без экрана — ездой и пешком, с входом в Kwik-E-Mart (дверь -> старт
# комнаты -> Апу -> ведёрко льда). Без пакета комнат (BW_NO_ROOMS=1) бот обязан остановиться у двери «не покрыто» (красный),
# с build/interiors-l1.bin (tools/interior_export.py) — «пройдена» (зелёный).   tests/rooms/run.sh -> PASS/FAIL
cd "$(dirname "$0")/../.."
[ -f build/interiors-l1.bin ] || .venv/bin/python tools/interior_export.py >/dev/null || exit 1
BINS=missioner tools/bots/build.sh >/dev/null || exit 1
A="build/level.shr build/homer.shr build/sandbox/roads-l1.bin build/missions/level01.msn --mission 0 --secs 240"
no=$(BW_NO_ROOMS=1 build/bots/missioner $A | awk -F'\t' '$1=="M"{print $5}'); yes=$(build/bots/missioner $A | awk -F'\t' '$1=="M"{print $5 " за " $7 " с"}')
echo "без комнат: $no; с комнатами: $yes"
[ "$no" = "не покрыто" ] && [ "${yes%% *}" = "пройдена" ] && echo PASS || { echo FAIL; exit 1; }
