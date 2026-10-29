#!/bin/bash
# №873 вход в комнату внутри сферы гэга (tests/collect/gag_entry873.c). EXTRA=-DGAG_ENTRY873_OLD=1 — красный
set -u
cd "$(dirname "$0")/../.."; mkdir -p build/collect; V=viewer; . tools/bots/lib.sh
cc -std=c11 -O2 -w -DSKIN_HOST ${EXTRA:-} -I $V -I tools/bots tests/collect/gag_entry873.c $BOTS_LIB -lm -o build/collect/gag873 || exit 2
build/collect/gag873 "${1:-build/collect-l1.shr}"
