#!/bin/bash
# Правка 416 («даль рассыпается на пиксели, швы рвутся вдали»): замер на 7 уровнях, 4 курса у места машины.
#   n — тот же вид через 0,5 с без сдвига (пол шума: трафик, оседание машины);
#   a / b — один вид и сдвиг машины на 4 см вбок (мерцание текстур при движении: что меняет субпиксельный сдвиг вдали);
#   m — маска города дальше 60 м (farprobe 1, за LOD_DIST 50 м — дальние версии); k — clearchk + nosky (дыры/швы пурпуром).
# gen.sh OUT ["флаги через ;"]
SP=("" "220 172" "152 -38.44" "-3.35 -5.57" "214.88 172.27" "-154.9 -482.05" "-300.14 -218.57" "214.73 172.41")
{ echo "scene start"; echo "wait 2"; for n in 1 2 3 4 5 6 7; do
  if [ $n -gt 1 ]; then echo "scene L${n}_load"; echo "flag golevel $n"; echo "wait 20"; fi
  echo "scene L$n"; echo "flag long"; [ -n "${2:-}" ] && echo "$2" | tr ';' '\n'
  set -- "$1" "${2:-}"; read X Z <<< "${SP[$n]}"
  echo "foot $X $Z 0"; echo "wait 2"; echo "press triangle"; echo "wait 4"
  for h in 0 1.5708 3.1416 4.7124; do k=${h%%.*}
    echo "goto $X $Z $h"; echo "wait 6"; echo "shot L${n}h${k}_a"; echo "wait 0.5"; echo "shot L${n}h${k}_n"
    echo "flag farprobe 1 60"; echo "wait 0.4"; echo "shot L${n}h${k}_m"; echo "flag farprobe 0"
    echo "flag clearchk 1"; echo "flag nosky 1"; echo "wait 0.4"; echo "shot L${n}h${k}_k"; echo "flag clearchk 0"; echo "flag nosky 0"
    dx=$(python3 -c "import math;print(round($X+0.04*math.cos($h),3), round($Z-0.04*math.sin($h),3))")
    echo "goto $dx $h"; echo "wait 6"; echo "shot L${n}h${k}_b"
  done; done; echo end; } > "$1"
