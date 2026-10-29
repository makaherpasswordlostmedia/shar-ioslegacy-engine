#!/bin/bash
# Общая проверка «картинка, а не цена» (урок 16.10: комментарий проглотил else drawGeo, кузова не рисовались, гейты по цене были зелёными). Берёт строки BIGCUT pm= pmgeo= из smoke.txt прогона:
# pm — куски, дошедшие до рисования в drawPieceM; pmgeo — отданные в drawGeo. Здоровый движок: pmgeo >= 95 % pm.
#   source tests/lib/drawn.sh; drawn_check ПАПКА_ПРОГОНА  -> печатает «pm pmgeo доля», код 0 = ок
drawn_check() {
  local f="$1/smoke.txt" r
  r=$(awk '/^BIGCUT/{for(i=1;i<=NF;i++){split($i,a,"="); if(a[1]=="pm") p+=a[2]; if(a[1]=="pmgeo") g+=a[2]}} END{printf "%d %d %.3f", p, g, (p? g/p : 0)}' "$f")
  echo "кусков drawPieceM $(echo "$r" | cut -d' ' -f1), отдано в drawGeo $(echo "$r" | cut -d' ' -f2), доля $(echo "$r" | cut -d' ' -f3)"
  echo "$r" | awk '{exit !($1 > 0 && $3 >= 0.95)}'
}
