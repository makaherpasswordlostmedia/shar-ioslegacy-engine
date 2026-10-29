#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build/perf9a-host
cc -std=c11 -O1 -g -fsanitize=address,undefined -DSKIN_HOST -Iviewer tests/perf9a/host.c viewer/coll_stream.c viewer/gag_skin.c viewer/collect.c viewer/stateprops.c viewer/skin.c viewer/homer.c viewer/col.c viewer/car.c viewer/coins.c viewer/ticket.c -lm -o build/perf9a-host/check
stage="${1:-build/perf789-stage}"
for l in 1 2 3 4 5 6 7; do
 p="$stage/l$l/collect-l$l.shr"; if [ "$l" = 1 ]; then p="$stage/collect-l1.shr"; fi
 build/perf9a-host/check "$p" >"build/perf9a-host/green-l$l.txt"
 cat "build/perf9a-host/green-l$l.txt"
 if [ "$l" = 1 ] || [ "$l" = 4 ] || [ "$l" = 7 ]; then
  build/perf9a-host/check "$p" old >"build/perf9a-host/old-l$l.txt"
  cat "build/perf9a-host/old-l$l.txt"
 fi
done
