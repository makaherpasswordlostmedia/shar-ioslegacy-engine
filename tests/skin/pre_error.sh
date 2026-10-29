#!/bin/bash
# Ревизия 11.10, 1.2: хост-проверка ошибки фонового чтения модели. Красный контроль: HOST_CFLAGS=-DSKINPRE_ERR_OLD=1
set -e; cd "$(dirname "$0")/../.."
T=${TMPDIR:-/tmp}/skin_pre.$$
cc -std=c11 -O1 -Wall -Wno-unused-function -DSKIN_HOST $HOST_CFLAGS -I viewer tests/skin/pre_error.c viewer/skin.c -lm -o "$T"
"$T"; r=$?; rm -f "$T"; exit $r
