#!/bin/bash
# Гейт правки 912 (viewer/tlines.h: линии мультика — матрица на клетку, подряд идущие записи одной подачей, отбор переиспользуется). Мак, только файлы.
#   tests/toon/lines912.sh [папка набора с toonlines.shr, roadlines.shr и l2…l7/]   код 0 = OK. Сначала КРАСНЫЕ подброски (обязаны упасть), потом ЗЕЛЁНЫЙ.
#   красные: -DTLBATCH912_OLD=1 (прежнее: подач столько же, сколько записей — проверка «подач вдвое меньше» падает), -DTL_REUSE_AGE=100000 -DTL_REUSE=1000.f (отбор не обновляется — наборы линий расходятся)
#   зелёные: (1) без переиспользования (-DTL_REUSE=0.f) наборы линий кадр в кадр те же, что у прежнего кода; (2) с переиспользованием по умолчанию набор отличается не больше 2 % линий в среднем;
#   (3) команд GE (матрица + подача) не больше 35 % от прежних
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
D="${1:-$HOME/Downloads/shar-psp-integ/build/test54tour/PSP/GAME/SHARTEST15}"; T="${TMPDIR:-/tmp}/l912.$$"; mkdir -p "$T"
b() { local n=$1; shift; cc -O1 "$@" tests/toon/lines912_host.c -lm -o "$T/$n" || { echo "FAIL: сборка $n"; exit 1; }; }
b old -DTLBATCH912_OLD=1; b new; b new0 -DTL_REUSE=0.f; b stale -DTL_REUSE_AGE=100000 -DTL_REUSE=1000.f
SETS=""; for L in ./ l2/ l3/ l4/ l5/ l6/ l7/; do { [ -f "$D/${L}toonlines.shr" ] || [ -f "$D/${L}roadlines.shr" ]; } && SETS="$SETS ${L}"; done
[ -n "$SETS" ] || { echo "FAIL: нет toonlines.shr в $D"; exit 1; }
cmpr() {   # cmpr бинарник_a бинарник_b: печатает "кадров расхождений_набора среднее_расхождение_линий_% команд_b/команд_a"
  local tot=0 diff=0 sa=0 sd=0 ca=0 cb=0
  for L in $SETS; do for seed in 1 2 3; do
    "$T/$1" "$D/${L}toonlines.shr" "$D/${L}roadlines.shr" $seed 800 > "$T/a.txt"; "$T/$2" "$D/${L}toonlines.shr" "$D/${L}roadlines.shr" $seed 800 > "$T/b.txt"
    read t d s1 s2 c1 c2 < <(paste -d' ' "$T/a.txt" "$T/b.txt" | awk '{tot++; if($5!=$12) d++; la=$3+$4; lb=$10+$11; ad=la-lb; if(ad<0) ad=-ad; sd+=ad; sa+=la; ca+=$6+$7; cb+=$13+$14} END{print tot+0, d+0, sd+0, sa+0, ca+0, cb+0}')
    tot=$((tot+t)); diff=$((diff+d)); sd=$((sd+s1)); sa=$((sa+s2)); ca=$((ca+c1)); cb=$((cb+c2))
  done; done
  awk -v t=$tot -v d=$diff -v sd=$sd -v sa=$sa -v ca=$ca -v cb=$cb 'BEGIN{p=0; r=0; if(sa>0) p=100*sd/sa; if(ca>0) r=cb/ca; printf "%d %d %.2f %.2f\n", t, d, p, r}'
}
read tot d_new0 pct_new0 cr_new0 < <(cmpr old new0); read _ d_new pct_new cr_new < <(cmpr old new); read _ d_stale pct_stale cr_stale < <(cmpr old stale); read _ d_oldself pct_oldself cr_oldself < <(cmpr old old)
echo "кадров $tot: new0 расхождений $d_new0 (команд ×$cr_new0); new отличие $pct_new % (команд ×$cr_new); stale отличие $pct_stale %; old/old команд ×$cr_oldself"
ok=1
awk -v v=$pct_stale 'BEGIN{exit !(v>2.0)}' || { echo "FAIL: красная подброска stale прошла (отличие $pct_stale %) — проверка слепая"; ok=0; }
awk -v v=$cr_oldself 'BEGIN{exit !(v>0.35)}' || { echo "FAIL: красная подброска old (прежний код) прошла проверку «команд не больше 35 %» ($cr_oldself)"; ok=0; }
[ "$d_new0" = 0 ] || { echo "FAIL: без переиспользования наборы линий расходятся в $d_new0 кадрах"; ok=0; }
awk -v v=$pct_new 'BEGIN{exit !(v<=2.0)}' || { echo "FAIL: с переиспользованием набор отличается на $pct_new % линий (> 2 %)"; ok=0; }
awk -v v=$cr_new 'BEGIN{exit !(v<=0.35)}' || { echo "FAIL: команд GE ×$cr_new от прежних (> 0,35)"; ok=0; }
[ $ok = 1 ] && echo "красные как надо (old команд ×$cr_oldself > 0,35; stale отличие $pct_stale % > 2); зелёный: наборы те же (new0), отличие $pct_new %, команд ×$cr_new" && echo PASS
[ $ok = 1 ]
