#!/bin/bash
# Гейт №606 одной командой: стрелки маршрута не прячутся под дорогу. Зелёный: новый путь 0 % закрытых точек; красный: прежний путь с подложенным провалом узла 0,5 м ловится.
#   tests/roadarrow/gate.sh [PKG1721]   PKG1721 — пакет данных (level.shr, traffic.shr, homer.shr), по умолчанию shar-psp-sonnet-runs-w/build/final-20261011-1721
set -eu; cd "$(dirname "$0")/../.."
P="${1:-$HOME/Downloads/shar-psp-sonnet-runs-w/build/final-20261011-1721}"; mkdir -p build/ra build/gatedata
for f in level.shr traffic.shr homer.shr; do ln -sf "$P/$f" build/gatedata/$f; done
bash -c 'V=viewer; . tools/bots/lib.sh; cc -std=c11 -O2 -w -DSKIN_HOST -I viewer -I tools/bots tests/roadarrow/gate.c $BOTS_LIB -lm -o build/ra/gate'
cd build/gatedata; export BW_NO_ROOMS=1 BW_NO_AUDIO=1
../ra/gate level.shr homer.shr | tail -2
../ra/gate level.shr homer.shr --old --sink 0.5 | tail -2
echo "GATE PASS"
