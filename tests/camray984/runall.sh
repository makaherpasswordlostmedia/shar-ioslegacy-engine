#!/bin/bash
# №984: все прогоны попарно: runall.sh ЭЛЕМЕНТ...  где элемент L:ВАРИАНТ (L — уровень 3..7; new — как в игре, old — flag camrayboxold 1 на той же сборке, red — красная сборка)
W=$(cd "$(dirname "$0")/../.." && pwd); cd "$W"; T=tests/camray984; A=${A:-$W/build/c984/acc}; mkdir -p "$A"
run1() { L=${1%%:*}; v=${1##*:}; case $v in old) b=new; z='flag camrayboxold 1\nflag camnfstillold 1';; red) b=red; z='';; *) b=new; z='';; esac; ZPRE="$z" "$T/run.sh" "$T/route_l$L.txt" "r${L}_$v" $b 420 > "$A/r_r${L}_$v.log" 2>&1; }
args=("$@"); i=0
while [ $i -lt ${#args[@]} ]; do run1 "${args[$i]}" & if [ $((i + 1)) -lt ${#args[@]} ]; then run1 "${args[$((i + 1))]}" & fi; wait; i=$((i + 2)); done
echo done > "$A/runall.done"
