#!/bin/bash
# Гейт разбора L3/L5, порядок кусков propFlush ключом (viewer/propsort913.h): та же перестановка, что у qsort по (флаги, текстура, номер). Мак, только числа. Красная подброска: -DPROPSORT_BREAK (две соседние позиции переставлены)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; T="${TMPDIR:-/tmp}/ps913.$$"; mkdir -p "$T"
cc -O2 -std=c11 -DPROPSORT_BREAK tests/propsort913/host.c -o "$T/red" && cc -O2 -std=c11 tests/propsort913/host.c -o "$T/green" || { echo "FAIL: сборка"; exit 1; }
if "$T/red" > "$T/red.txt"; then echo "FAIL: красная подброска прошла — проверка слепая"; cat "$T/red.txt"; exit 1; fi; echo "красный как надо: $(cat $T/red.txt)"
"$T/green" > "$T/green.txt" || { echo "FAIL: $(cat $T/green.txt)"; exit 1; }; echo "зелёный: $(cat $T/green.txt)"; echo PASS
