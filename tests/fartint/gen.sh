#!/bin/bash
# Правка 411 (уточнение Роба 09.10: тумана не нужно; недотекстуренное — тоном горизонта): сценарий гейта tests/fartint/gate.py.
# 7 уровней, 4 курса машины у её места (заголовки level.shr), в каждом виде:
#   A — кадр как есть; F — тот же вид с прежней дымкой (fogcityold 1); T — без дымки (farprobe 2, свой цвет поверхностей);
#   M — маска города дальше 150 м (farprobe 1); E — маска края дальности (дальше 225 м из 250);
#   H — без города, взгляд по горизонту (farprobe 4: строка 136 — горизонт, над ней полоса 0..6°);
#   U, R — повтор T и P через 0,4 с (пол шума: трафик, анимация — запас гейта меряется, не задаётся);
#   P — заглушка у всего города (phplant 1); Q — то же прежним путём (phold 1: цвет вершин без текстуры).
#   Строки FOGZ old0/old1 — тон фона из данных неба (новый) и прежний. Сцена Ln_cost — 5 с езды для цены кадра.
# gen.sh OUT [red]   red = красный контроль: «новые» кадры снимаются прежним путём (дымка, цвет вершин, прежний тон)
OUT=$1; RED=${2:-}; B=0; [ "$RED" = red ] && B=1
SP=("" "220 172" "152 -38.44" "-3.35 -5.57" "214.88 172.27" "-154.9 -482.05" "-300.14 -218.57" "214.73 172.41")
{ echo "scene start"; echo "wait 2"; for n in 1 2 3 4 5 6 7; do
  if [ $n -gt 1 ]; then echo "scene L${n}_load"; echo "flag golevel $n"; echo "wait 20"; fi
  echo "scene L$n"; echo "flag long"; echo "flag fogcityold $B"; echo "flag phold $B"
  echo "flag fogzold 1"; echo "flag fogzold 0"; [ $B = 1 ] && echo "flag fogzold 1"
  read X Z <<< "${SP[$n]}"
  echo "foot $X $Z 0"; echo "wait 2"; echo "press triangle"; echo "wait 4"   # в машину: камера за машиной смотрит вдоль курса
  for h in 0 1.5708 3.1416 4.7124; do k=${h%%.*}
    echo "goto $X $Z $h"; echo "wait 5"; echo "shot L${n}h${k}_A"
    echo "flag fogcityold 1"; echo "wait 0.4"; echo "shot L${n}h${k}_F"; echo "flag fogcityold $B"
    for st in "M:1 150" "E:1 225" "T:2" "U:2" "H:4"; do echo "flag farprobe ${st#*:}"; echo "wait 0.4"; echo "shot L${n}h${k}_${st%%:*}"; done
    echo "flag farprobe 0"; echo "flag phplant 1"; echo "wait 0.4"; echo "shot L${n}h${k}_P"; echo "wait 0.4"; echo "shot L${n}h${k}_R"
    echo "flag phold 1"; echo "wait 0.4"; echo "shot L${n}h${k}_Q"; echo "flag phold $B"; echo "flag phplant 0"; echo "wait 0.3"
  done
  echo "scene L${n}_cost"; echo "flag autostraight 4"; echo "wait 5"; echo "flag stop"; done; echo end; } > "$OUT"
