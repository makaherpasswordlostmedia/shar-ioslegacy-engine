#!/bin/bash
# Гейт правки 912, часть «матрица контура» (viewer/hullmat912.h): новая запись равна по числам (знак нуля не в счёт) прежнему полному умножению. Мак, только числа. Красная подброска: -DHULLMAT_BREAK (ошибка в одном элементе)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; T="${TMPDIR:-/tmp}/h912.$$"; mkdir -p "$T"
cc -O1 -DHULLMAT_BREAK tests/toon/hull912_host.c -lm -o "$T/red" && cc -O1 tests/toon/hull912_host.c -lm -o "$T/green" || { echo "FAIL: сборка"; exit 1; }
if "$T/red" > "$T/red.txt"; then echo "FAIL: красная подброска прошла — проверка слепая"; cat "$T/red.txt"; exit 1; fi; echo "красный как надо: $(cat $T/red.txt)"
"$T/green" > "$T/green.txt" || { echo "FAIL: $(cat $T/green.txt)"; exit 1; }; echo "зелёный: $(cat $T/green.txt)"; echo PASS
