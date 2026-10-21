#!/bin/bash
# №522: тень не уходит под землю — настоящий уровень, сравнение с плоскостью №433 (SHADOW_OLD=1). tests/shadow522/run.sh [LEVEL.shr] -> PASS/FAIL
set -eu
cd "$(dirname "$0")/../.."; LV=${1:-build/level.shr}; mkdir -p build/tmp
for mode in new old; do
  fl="${SHFLAGS:-}"; [ "$mode" = old ] && fl="-DSHADOW_OLD=1"
  cc -std=c11 -O2 -w -DSKIN_HOST $fl -I tests/shadow433/stub -I viewer -I tools/autoexplore/walls tests/shadow522/host.c viewer/carvis.c viewer/car.c viewer/col.c viewer/props.c viewer/stateprops.c viewer/coins.c -lm -o build/tmp/shadow522_$mode
  echo "== $mode"; build/tmp/shadow522_$mode "$LV"; cp build/tmp/shadow522.txt build/tmp/shadow522_$mode.txt
done
python3 - <<'P'
n=list(map(float,open('build/tmp/shadow522_new.txt').read().split())); o=list(map(float,open('build/tmp/shadow522_old.txt').read().split()))
cn=n[4]/max(n[0],1); co=o[4]/max(o[0],1); rn=n[1]/max(n[0],1); ro=o[1]/max(o[0],1)
ok=(co>0 and cn<=co*0.10 and cn<=0.005)
print('PASS' if ok else 'FAIL', f': тень ниже опоры коллизии больше чем на 2 см: новая {100*cn:.3f} % против {100*co:.3f} % (плоскость №433); для справки ниже нарисованной земли: {100*rn:.2f} % против {100*ro:.2f} %')
raise SystemExit(0 if ok else 1)
P
