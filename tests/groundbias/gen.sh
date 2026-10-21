#!/bin/bash
# Сцена «прямая дорога вдаль, медленный проезд» для замера ряби дальней дороги (№539): три множителя наклона мипа земли подряд в одном запуске
# (flag groundbias X, viewer/main_render.h texSlope; на железе то же задаёт файл `groundbias` рядом с EBOOT), по каждому ряд снимков во время медленного проезда
# gen.sh OUT ["1.0 1.5 2.0" [число_снимков [уровень 1|3]]]
#   L1: прямая улица x 100..216, z 265, курс 1,5708 (на восток), земля y около 3
#   L3: две прямые длиной 153 и 156 м без трафика (traffic.shr, flags 2): x −469,5..−316,1, z −116,2 (чище: ни одного кадра в воздухе у famil_v на полном газу) и z −45,1 (на 17 кадров машина отрывается от земли)
# машина 2 м/с (flag wpv), снимок каждые ~0,25 с (на железе ещё и время записи BMP). Строка SHOT в smoke.txt несёт позицию: y обязан быть около 3 (L1) / −68 (L3), иначе goto поставил машину на другую поверхность
MULS="${2:-1.0 1.5 2.0}"; N="${3:-12}"; LV="${4:-1}"
if [ "$LV" = 3 ]; then X0=-469.5; Z0=-116.2; X1=-320; Y0=-62; else X0=100; Z0=265; X1=210; Y0=""; fi
{ echo "scene start"; echo "wait 2"
  if [ "$LV" != 1 ]; then echo "scene L${LV}_load"; echo "flag golevel $LV"; echo "wait 20"; fi
  echo "scene L${LV}_gb"; echo "flag long"
  echo "foot $X0 $Z0 1.5708 $Y0"; echo "wait 2"; echo "press triangle"; echo "wait 4"
  for m in $MULS; do t=${m//./}
    echo "flag groundbias $m"; echo "goto $X0 $Z0 1.5708"; echo "wait 5"
    echo "shot gb${LV}_${t}_near"      # стоя: резкость ближней дороги
    echo "flag wpclear"; echo "flag wpv 2"; echo "flag wp $X1 $Z0"; echo "flag wpgo"; echo "wait 1"
    for i in $(seq -w 1 "$N"); do echo "shot gb${LV}_${t}_$i"; echo "wait 0.25"; done
    echo "flag stop"
  done; echo end; } > "$1"
