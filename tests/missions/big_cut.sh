#!/bin/bash
# 16.10 после катастрофы (комментарий проглотил else drawGeo, не рисовались кузова): гейт требует, чтобы дошедшие до рисования куски drawPieceM были отданы в drawGeo (>= 95 %) в обеих сборках.
# №640 срез крупных кусков пропов у глаза (ggCut, BIG_CUT_OLD=1 прежнее). Сцена: L1, глаз у щита 12 м (проп 401) — зелёный обязан разобрать треугольники щита (gg_exam > 0) и РЕЗАТЬ их (gg_tris > 0: аудит 16.10 поймал absM=0, срез шёл по чужим осям и ничего не резал), красный нет; цена: x_props в
# спокойной сцене (spawn L1) зелёный не больше 1,15 красного. Безоконный эмулятор, пакет RACE_PKG.   tests/missions/big_cut.sh
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; export TWINS_ROOT="$ROOT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"; OUT=build/big_cut; mkdir -p "$OUT"
export PF_SCEN="$ROOT/tests/missions/big_cut.txt"
for v in red green; do
  fl=""; [ $v = red ] && fl="-DCMAKE_C_FLAGS=-DBIG_CUT_OLD=1"
  psp-cmake -S viewer -B "$OUT/${v}_build" $fl > "$OUT/${v}_cmake.txt" 2>&1 && cmake --build "$OUT/${v}_build" -j4 > "$OUT/${v}_build.txt" 2>&1 || { echo "FAIL: сборка $v"; exit 2; }
  d=$("$ROOT/.venv/bin/python" tests/missions/prop_fast.py "$OUT/${v}_build/EBOOT.PBP" bc_$v | tail -1)
  ex=$(awk '/^BIGCUT/{for(i=1;i<=NF;i++) if($i ~ /^gg_exam=/){split($i,a,"="); m=a[2]}} END{print m+0}' "$d/smoke.txt")
  ct=$(awk '/^BIGCUT/{for(i=1;i<=NF;i++) if($i ~ /^gg_tris=/){split($i,a,"="); m=a[2]}} END{print m+0}' "$d/smoke.txt")
  pm=$(awk '/^BIGCUT/{for(i=1;i<=NF;i++){split($i,a,"="); if(a[1]=="pm") p+=a[2]; if(a[1]=="pmgeo") g+=a[2]}} END{printf "%d %d", p, g}' "$d/smoke.txt")
  xp=$(awk '/^SCENE H_L1/{r=1} /^SCENE H_in/{r=0} r&&/^PHSEC/{for(i=1;i<=NF;i++) if($i ~ /^x_props=/){split($i,a,"="); s+=a[2]; n++}} END{printf "%.3f", (n? s/n : 0)}' "$d/smoke.txt")
  eval "${v}_ex=$ex; ${v}_xp=$xp; ${v}_ct=$ct; ${v}_pm='$pm'"
done
echo "кусков в drawPieceM / отдано в drawGeo: красный $red_pm, зелёный $green_pm"
echo "разобрано треугольников у щита: красный $red_ex, зелёный $green_ex; срезано: красный $red_ct, зелёный $green_ct; x_props спокойной сцены, мс: красный $red_xp, зелёный $green_xp"
awk -v pr="$red_pm" -v pg="$green_pm" -v gc="$green_ct" -v re="$red_ex" -v ge="$green_ex" -v rx="$red_xp" -v gx="$green_xp" 'BEGIN{split(pr, R, " "); split(pg, G, " "); okp = (R[1] > 0 && R[2] >= 0.95 * R[1] && G[1] > 0 && G[2] >= 0.95 * G[1]); exit !(okp && gc > 0 && ge > 0 && ge > re && rx > 0 && gx <= 1.15*rx)}' && { echo PASS; exit 0; } || { echo FAIL; exit 1; }
