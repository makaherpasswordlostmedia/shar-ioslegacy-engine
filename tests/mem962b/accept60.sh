#!/bin/bash
# №962б: запас lva на PSP брал 1,2 МБ из 2,6 (softmiss +1 на смене уровня): резерв под COL1/PRP2 считался по готовности чтения, хотя место загрузчик занимает сразу.
# Стенд: сборка с -DTAILSLOW_MS=700 (главный поток ждёт, пока загрузчик займёт место под COL1, как на железе). Зелёный: новый код — L5 soft=2647606, softmiss стоит. Красный (файл lvatail962bold): L5 soft=1201088, softmiss растёт — как в туре TEST62.
# Использование: EB=<EBOOT со стендом> tests/mem962b/accept60.sh ; последней строкой PASS/FAIL (код 0/1)
set -u; D="$(cd "$(dirname "$0")" && pwd)"; T="$(cd "$D/../.." && pwd)"; EB=${EB:?нужен EBOOT, собранный с -DTAILSLOW_MS=700}; OUT=${OUT:-/tmp/mem962b_acc}; mkdir -p "$OUT"
export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test63tour/PSP/GAME/SHARTEST15} EMU_OWNER=${EMU_OWNER:-Оптимизация} EMU_MINE=2 OUT
( "$T/tools/emu_run.sh" "$D/lvseq.txt" new "$EB" 900 >/dev/null 2>&1 & FLAGS="lvatail962bold" "$T/tools/emu_run.sh" "$D/lvseq.txt" old "$EB" 900 >/dev/null 2>&1 & wait )
g() { grep -h "LVA level=5 " "$OUT/out_$1/smoke.txt" | head -1 | sed -n 's/.*soft=\([0-9]*\) softmiss=\([0-9]*\).*/\1 \2/p'; }
l() { grep -h "LVA level=" "$OUT/out_$1/smoke.txt" | tail -1 | sed -n 's/.*softmiss=\([0-9]*\).*/\1/p'; }
read sn mn <<<"$(g new)"; read so mo <<<"$(g old)"; ln=$(l new); lo=$(l old)
echo "зелёный (новый): L5 soft=$sn softmiss=$mn, к концу тура softmiss=$ln"; echo "красный (lvatail962bold): L5 soft=$so softmiss=$mo, к концу тура softmiss=$lo"
ok=1; [ "${sn:-0}" -ge 2600000 ] && [ "${ln:-99}" -le 8 ] || ok=0
red=1; [ "${so:-0}" -lt 1300000 ] && [ "${lo:-0}" -ge 14 ] || red=0
[ $red = 1 ] && echo "красный контроль красный, как и должно быть" || { echo "красный контроль НЕ красный"; ok=0; }
[ $ok = 1 ] && { echo PASS; exit 0; } || { echo FAIL; exit 1; }
