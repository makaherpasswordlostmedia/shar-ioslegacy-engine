#!/bin/bash
# Гейт предотсева колесо-стена (COL_WHEEL_PRE_OLD): новый расчёт побитно равен прежнему на 4 уровнях × 400 тыс. запросов; красный контроль
# (-DCOL_WHEEL_PRE_BREAK=0.25f) обязан дать расхождения. DATA — пакет уровней (L1 в корне, l2..l7 подпапки), по умолчанию ../shar-psp-night-w/build.
set -e; cd "$(dirname "$0")/../.."; D=${DATA:-../shar-psp-night-w/build}; ok=1
BINS=wheelpre bash tools/bots/build.sh >/dev/null; BINS=wheelpre SUF=_broken OUT_DIR=/tmp/wheelpre_bp bash tools/bots/build.sh -DCOL_WHEEL_PRE_BREAK=0.25f >/dev/null
for L in 1 3 5 7; do
  if [ $L = 1 ]; then a=("$D/level.shr" "$D/homer.shr" "$D/level01.msn"); else a=("$D/levels/l$L/level.shr" "$D/levels/l$L/player.shr" "$D/levels/l$L/level0$L.msn"); fi
  g=$(BW_LEVEL=$L build/bots/wheelpre "${a[@]}" | tail -1); r=$(BW_LEVEL=$L /tmp/wheelpre_bp/wheelpre_broken "${a[@]}" | tail -1)
  echo "L$L: $g"; echo "L$L красный: $r"
  case "$g" in *PASS) ;; *) ok=0;; esac; case "$r" in *FAIL) ;; *) ok=0;; esac
done
[ $ok = 1 ] && echo "ГЕЙТ wheelpre: PASS (красный контроль ловит)" || { echo "ГЕЙТ wheelpre: FAIL"; exit 1; }
