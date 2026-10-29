#!/bin/bash
# Гейт трафика, стоящих машин и пешеходов на Маке (tests/traffic/host.c): настоящие данные — зелёные, подброшенные плохие
# данные (полосы сдвинуты, стоящие повёрнуты/сдвоены/чужой модели, рост пешехода 0, трафик не твёрдый) — каждая красная.
#   tests/traffic/host.sh [level.shr] [traffic.shr] [homer.shr]      (по умолчанию из build/; нет traffic.shr — экспорт)
set -e
cd "$(dirname "$0")/../.."
if [ ! -f build/traffic.shr ] && [ -z "${2:-}" ]; then
  . .venv/bin/activate; SHR_TEX_CAP256=1 SHR_SMALL_MIPS=1 SHR_LAYERS=1 python tools/traffic_export.py > /dev/null
fi
T=${TMPDIR:-/tmp}/traffic_host.$$
cc -std=c11 -O2 -Wall -Wno-unused-function -DSKIN_HOST -I viewer tests/traffic/host.c viewer/traffic.c viewer/homer.c viewer/skin.c \
   viewer/col.c viewer/car.c -lm -o "$T"
set +e
"$T" "${1:-build/level.shr}" "${2:-build/traffic.shr}" "${3:-build/homer.shr}"; r=$?; rm -f "$T"; exit $r
