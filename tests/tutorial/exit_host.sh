#!/bin/bash
# Ревизия 11.10, 3.1: хост-проверка ухода подсказки Барта (tests/tutorial/exit_host.c). Красный контроль: HOST_CFLAGS=-DTUT_EXIT_OLD=1 -> «bubble hangs»
set -e; cd "$(dirname "$0")/../.."
T=${TMPDIR:-/tmp}/tut_exit.$$
cc -std=c11 -O1 -Wall -Wno-unused-function -DSKIN_HOST $HOST_CFLAGS -I tests/tutorial/stub -I viewer tests/tutorial/exit_host.c viewer/tutorial.c -o "$T"
"$T"; r=$?; rm -f "$T"; exit $r
