#!/bin/bash
# №912 гейт: склейка квадов билбордов стейтпропов (BB_BATCH_OLD) и счётчики кандидатов в PHSUB.
#   gate.sh NEW_EBOOT   — NEW с правилом; OLD — тот же EBOOT с файлом bbbatchold рядом (прежний путь: вызов на квад)
#   1) PHSUB содержит sp_cand и bb_calls (счётчики №912)
#   2) картинка L6 «стоя» (10 квадов билбордов, ничего не движется): NEW == OLD (<= 50 px вне шапки)
#   3) квадов столько же, вызовов у NEW меньше (L6 стоя: 10 -> 2)
# Красный контроль: gate.sh NEW с BBOLD=1 (оба прогона на прежнем пути) -> FAIL (вызовов не меньше)
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; T=$ROOT/tests/bbbatch; W=${W:-$ROOT/build/gates/g912}; export OUT=$W
NEW=$1; rm -rf $W; mkdir -p $W; : > $W/bbbatchold; fail=0
if [ -n "$BBOLD" ]; then FLAGS=bbbatchold $RUN $T/l6_stand.txt g912_n $NEW 400 >/dev/null; else $RUN $T/l6_stand.txt g912_n $NEW 400 >/dev/null; fi
FLAGS=bbbatchold $RUN $T/l6_stand.txt g912_o $NEW 400 >/dev/null
mv $W/out_g912_n $W/n; mv $W/out_g912_o $W/o
get() { grep -h 'PHSUB' $1/smoke.txt | grep 'scene=S6_STAND' | tail -5 | grep -o "$2=[0-9.]*" | cut -d= -f2 | sort -n | sed -n 3p; }
nc=$(get $W/n sp_cand); nbc=$(get $W/n bb_calls); obc=$(get $W/o bb_calls); nq=$(get $W/n bb_quads); oq=$(get $W/o bb_quads)
echo "  PHSUB: sp_cand=$nc; квадов NEW $nq OLD $oq; вызовов NEW $nbc OLD $obc"
[ -n "$nc" ] && [ -n "$nbc" ] || { echo "КРАСНОЕ: в PHSUB нет sp_cand / bb_calls"; fail=1; }
[ "$nq" = "$oq" ] && [ "${nq%.*}" -gt 0 ] 2>/dev/null || { echo "КРАСНОЕ: квадов не поровну или нет"; fail=1; }
awk -v a="$nbc" -v b="$obc" 'BEGIN{exit !(a+0 < b+0)}' || { echo "КРАСНОЕ: вызовов у NEW не меньше"; fail=1; }
px=$(python3 - <<PYEOF
from PIL import Image
import numpy as np
a=np.asarray(Image.open('$W/n/stand.png').convert('RGB'),int)[70:]; b=np.asarray(Image.open('$W/o/stand.png').convert('RGB'),int)[70:]
print(int((np.abs(a-b).sum(2)>40).sum()))
PYEOF
)
echo "  картинка стоя: различие $px px вне шапки"; [ "$px" -le 50 ] || { echo "КРАСНОЕ: картинки различаются"; fail=1; }
[ $fail = 0 ] && echo PASS || echo FAIL; exit $fail
