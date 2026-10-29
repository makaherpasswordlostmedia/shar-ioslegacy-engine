#!/bin/bash
# Гейт «перепись миссий» (перепись 04.10, docs/МИССИИ_ПОЛНОТА_2026-10-04.md): каждая команда скриптов миссий уровней 1–7, которая
# ставит вещь в мир или на экран, — против движка (viewer/) и пакетов выпуска (tools/ship_files.sh --pairs, SHIP_LEVELS="2 3 4 5 6 7").
# Сверка — tools/missions/census.py --check tests/missions/census_expected.tsv (по семействам строк «нет/частично» не больше записанного).
# Сначала КРАСНЫЕ на подложенном входе (обязаны упасть), потом ЗЕЛЁНЫЙ:
#   красный 1 «пустой msnart»: уровень 1 с пустым msnart.shr (MSA2 без записей) — маркеры, значки, предметы целей обязаны упасть
#   красный 2 «нет заборов»: уровень 2 без l2/racefence-l2.bin — заборы трасс уличных гонок обязаны упасть
#   зелёный: дерево и build/ как есть (пакеты уровней 2–7 — build/levels/l<N>/, собираются строками {N} tools/ship_rules.txt)
#   tests/missions/census.sh [--use имя=файл ...]   — подменить пакеты выпуска (как tools/ship.sh --use), например новый экспорт
# Первая строка вывода — итог, код 0 = PASS; таблица — build/gates/census/<время>/census.tsv (+ census_grouped.tsv); подмена
# --use идёт до подложенного входа (последняя подмена имени выигрывает)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3
T="${CENSUS_OUT:-$ROOT/build/gates/census/$(date +%Y%m%d-%H%M%S)}"; mkdir -p "$T"   # CENSUS_OUT — своя папка (помощник на копии)
EXP="$ROOT/tests/missions/census_expected.tsv"
res=""; ok=1
# красный 1: пустой msnart уровня 1
printf 'MSA2\0\0\0\0\x20\0\0\0\x20\0\0\0' > "$T/empty_msnart.shr"; head -c 16 /dev/zero >> "$T/empty_msnart.shr"
"$PY" tools/missions/census.py --level 1 "$@" --use "msnart.shr=$T/empty_msnart.shr" --check "$EXP" --brief > "$T/red_msnart.txt" 2>&1
if [ $? = 0 ]; then ok=0; res="$res; КРАСНЫЙ НЕ ПОЙМАН: пустой msnart"; else res="$res; красный (пустой msnart): $(grep -m2 '^FAIL' "$T/red_msnart.txt" | tr '\n' ' ' | cut -c1-140)"; fi
# красный 2: нет заборов трасс уровня 2
"$PY" tools/missions/census.py --level 2 "$@" --use "l2/racefence-l2.bin=$T/нет_такого.bin" --check "$EXP" --brief > "$T/red_fence.txt" 2>&1
if [ $? = 0 ]; then ok=0; res="$res; КРАСНЫЙ НЕ ПОЙМАН: нет заборов"; else res="$res; красный (нет заборов): $(grep -m1 '^FAIL' "$T/red_fence.txt" | cut -c1-140)"; fi
# зелёный
"$PY" tools/missions/census.py "$@" --tsv "$T/census.tsv" --grouped "$T/census_grouped.tsv" --check "$EXP" --brief > "$T/green.txt" 2>&1
if [ $? = 0 ]; then res="$res; зелёный: $(head -1 "$T/green.txt")"; else ok=0; res="$res; НЕ ЗЕЛЁНЫЙ: $(grep '^FAIL' "$T/green.txt" | head -3 | tr '\n' ' ' | cut -c1-220)"; fi
echo "$([ $ok = 1 ] && echo PASS || echo FAIL)${res}"
echo "журнал ${T#$ROOT/}"
cat "$T/green.txt"
[ $ok = 1 ]
