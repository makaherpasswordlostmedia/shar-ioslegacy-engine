#!/bin/bash
# Гейт счётчика монет: coin_drawn в PHSUB различает «за спиной» (0) и «на виду» (>0).
#   tests/coins_drawn/gate.sh [DIR]            зелёный
#   tests/coins_drawn/gate.sh --negative [DIR] красный: все монеты бросаются позади — сверка «впереди > 0» обязана упасть
set -u; cd "$(dirname "$0")/../.."
NEG=""; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build}"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT; SCN=tests/coins_drawn/scenario.txt
if [ -n "$NEG" ]; then sed 's/^flag coindrop 5$/flag coindrop -5/' "$SCN" > "$T/s.txt"; SCN="$T/s.txt"; fi
L=$(SMOKE_HEADLESS=1 SMOKE_SCN="$SCN" tools/smoke.sh "$SRC" 2>&1); R=$(echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p')
[ -n "$R" ] || R=$(ls -dt build/smoke/* | head -1)
python3 -I - "$R" "$NEG" <<'PY'
import sys,re,glob
d,neg=sys.argv[1],sys.argv[2]=='1'
txt=open(d+'/smoke.txt',errors='replace').read()
def v(sc):
    r=[(float(a),float(b)) for s,a,b in re.findall(r'PHSUB t=\S+ scene=(\S+).*?coin_active=(\S+) coin_drawn=(\S+)',txt) if s==sc]
    return r
res={s:v(s) for s in ('coin_back','coin_front','coin_none')}
fails=[]
mx=lambda s,i:max([x[i] for x in res[s]] or [-1])
base=mx('coin_none',1)
if mx('coin_front',0)-mx('coin_none',0)<2: fails.append('сцена не бросила монеты впереди (активных не прибавилось)')
elif mx('coin_front',1)-base<2: fails.append('впереди монеты на виду, а coin_drawn не вырос')
if mx('coin_back',0)-mx('coin_none',0)<2: fails.append('сцена не бросила монеты позади')
elif (mx('coin_front',1)-base)-(mx('coin_back',1)-base)<1.5: fails.append('coin_drawn не отличает монеты на виду от монет за спиной')
line=' '.join(f'{s}: act={mx(s,0):.1f} drawn={mx(s,1):.1f}' for s in res)
if neg: print(('PASS (красный пойман): '+fails[0]) if fails else 'FAIL (красный не пойман): '+line); sys.exit(0 if fails else 1)
if fails: print('FAIL: '+fails[0]+' ['+line+']'); sys.exit(1)
print('OK: '+line)
PY
