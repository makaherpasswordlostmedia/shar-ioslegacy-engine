#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
out=build/content-ticket-c3
mkdir -p "$out"
.venv/bin/python tests/content/ticket/gate.py "$@" | tee "$out/gate-new.log"
for kind in flow persist room; do
  rc=0
  if [ "$kind" = room ]; then
    .venv/bin/python tests/content/ticket/gate.py --old-room "$@" > "$out/gate-old-room.log" 2>&1 || rc=$?
  else
    .venv/bin/python tests/content/ticket/gate.py "--old-$kind" "$@" > "$out/gate-old-$kind.log" 2>&1 || rc=$?
  fi
  if [ "$rc" = 0 ]; then
    echo "RED $kind unexpectedly passed"; exit 1
  fi
  case "$kind" in flow) n=31;; persist) n=2;; room) n=1;; esac
  if ! rg -q "RESULT FAIL failures=$n checks=55" "$out/gate-old-$kind.log"; then
    cat "$out/gate-old-$kind.log"; exit 1
  fi
  echo "RED $kind caught $n"
done
bash tests/movie/host.sh build/ship_stage/movies/fmv8.smv > "$out/movie-host.log" 2>&1
.venv/bin/python tools/movie_export.py --verify build/ship_stage/movies/fmv8.smv --rmv hit-and-run-web/source/game/movies/fmv8.rmv > "$out/movie-source.log" 2>&1
echo "GREEN route55, original voices7, persistence, fmv8 source1372"
