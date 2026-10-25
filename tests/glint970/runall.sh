#!/bin/bash
# №970: все прогоны попарно (2 эмулятора): runall.sh СПИСОК   где элемент ОБЪЕКТ:ВАРИАНТ  (объект wrench|phone|lights|coin; вариант new|old|none|oldc)
W=$(cd "$(dirname "$0")/../.." && pwd); cd "$W"; T=tests/glint970; A=${A:-$W/build/g970/acc}; mkdir -p "$A"
ab() { case $1 in wrench) echo w;; phone) echo p;; lights) echo l;; coin) echo c;; *) echo $1;; esac; }   # lab1 lab2 glass excl — соседи, имя = объект
args=("$@"); i=0
run1() { o=${1%%:*}; v=${1##*:}; n=$(ab $o)_$v; case $v in old) b=new; f=1;; oldc) b=oldc; f=x;; *) b=$v; f=0;; esac; mx=300; [ $o = coin ] && mx=700; case $o in lab1|lab2) mx=120;; esac; "$T/run.sh" $o $n $b $f $mx > "$A/r_$n.log" 2>&1; }
while [ $i -lt ${#args[@]} ]; do
  run1 "${args[$i]}" & p1=$!; if [ $((i + 1)) -lt ${#args[@]} ]; then run1 "${args[$((i + 1))]}" & p2=$!; fi; wait; i=$((i + 2))
done
echo done > "$A/runall.done"
