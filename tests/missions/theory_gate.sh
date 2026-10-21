#!/bin/bash
# П1 (L1_ФИНИШ 30.09): теоретическое время блоков с таймером — missioner --theory (путь по графу дорог / TopSpeed машины из .con).
# Проверки: у каждого посчитанного блока путь по дорогам не короче прямой; теория — нижняя граница, не больше самого таймера;
# у уровня есть хотя бы один посчитанный блок. Красный: сборка -DTHEORY_BREAK=1 (путь = прямая / 4) обязана упасть.
#   tests/missions/theory_gate.sh [LEVEL.shr ROADS MSN]  -> PASS/FAIL; таблица блоков — build/bots/theory/theory.tsv
cd "$(dirname "$0")/../.."
LVL=${1:-build/level.shr}; ROADS=${2:-build/sandbox/roads-l1.bin}; MSN=${3:-build/missions/level01.msn}
O=build/bots/theory; mkdir -p "$O"   # свои бинарники: рабочие build/bots/missioner могут быть заняты прогоном миссий
BINS=missioner OUT_DIR=$O tools/bots/build.sh >/dev/null || exit 1
BINS=missioner OUT_DIR=$O SUF=_break tools/bots/build.sh -DTHEORY_BREAK=1 >/dev/null || exit 1
check() {   # stdin: строки T -> 0 если всё сходится
  awk -F'\t' '$1=="T" { n++; if ($10 < 0) next; k++
      if ($9 + 1 < $12) { printf "  путь по дорогам %s м короче прямой %s м: %s блок %s\n", $9, $12, $3, $4; bad++ }
      if ($10 > $5 + 0.5) { printf "  теория %s с больше таймера %s с: %s блок %s\n", $10, $5, $3, $4; bad++ } }
    END { printf "  блоков %d, посчитано %d, нарушений %d\n", n, k, bad; exit (k > 0 && bad == 0) ? 0 : 1 }'
}
echo "== отрицательный контроль (путь = прямая / 4, обязан упасть):"
$O/missioner_break "$LVL" build/homer.shr "$ROADS" "$MSN" --theory | check; NEG=$?
echo "== рабочая сборка:"
$O/missioner "$LVL" build/homer.shr "$ROADS" "$MSN" --theory | tee "$O/theory.tsv" | check; POS=$?
if [ $NEG != 0 ] && [ $POS = 0 ]; then echo PASS; else echo "FAIL (контроль: код $NEG, рабочая: код $POS)"; exit 1; fi
