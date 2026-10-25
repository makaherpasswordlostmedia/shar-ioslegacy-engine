#!/bin/bash
# Гейт правки Роба 892 (viewer/tone.c, Cartoon: тёмное стекло окон не стягивается к среднему цвету текстуры). Мак, только файлы.
#   tests/tone/window892.sh [level.shr]   код 0 = OK. Сначала КРАСНЫЕ подброски (обязаны упасть), потом ЗЕЛЁНЫЙ.
#   красные: -DTONE_WIN892_OLD=1 (прежний код), -DTOON_WIN_K=.45f (правило есть, но доля рисунка прежняя)
#   зелёный: глубина тёмного >= 0,85 (старый код 0,65), хеши палитр земли, ровных текстур и режима без Cartoon те же, что у OLD=1
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
LV="${1:-$ROOT/build/level.shr}"; T="${TMPDIR:-/tmp}/w892.$$"; mkdir -p "$T"
b() { local n=$1; shift; cc -O1 -I viewer "$@" tests/tone/window892_host.c viewer/tone.c -lm -o "$T/$n" || { echo "FAIL: сборка $n"; exit 1; }; "$T/$n" "$LV" > "$T/$n.txt"; }
depth() { awk '/^DEPTH/{print $2}' "$T/$1.txt"; }
ok() { awk -v d="$1" 'BEGIN{exit !(d>=0.85)}'; }
b old -DTONE_WIN892_OLD=1; b k45 -DTOON_WIN_K=.45f; b new
for n in old k45; do if ok "$(depth $n)"; then echo "FAIL: подброска $n прошла (глубина $(depth $n)) — проверка слепая"; exit 1; fi; echo "красный как надо ($n): глубина тёмного $(depth $n) < 0,85"; done
ok "$(depth new)" || { echo "FAIL: глубина тёмного $(depth new) < 0,85"; exit 1; }
if [ "$(grep ^SAME "$T/new.txt")" != "$(grep ^SAME "$T/old.txt")" ]; then echo "FAIL: земля, ровные текстуры или режим без Cartoon изменились"; grep ^SAME "$T/old.txt" "$T/new.txt"; exit 1; fi
echo "зелёный: глубина тёмного $(depth new) (было $(depth old)); хеши земли/ровных/без Cartoon те же"; echo PASS
