#!/bin/bash
# Вечные углы погони ночи 30.09 (группа corners-roads, очередь пункт 11 «тупики общими правилами»). Пять раундов-повторов
# (гены беглеца и погони, старты) из build/bots/nights/20260930-2300/keep/chase — копии здесь, имя = место и что держало:
#   c124_220_pit       — щель между трамплином дороги 431/432 (земля 8.7 м) и приземлением (ящики b17/b18): погоня с разгона перелетает
#   c141_607_ledge     — беглец на уступе 4 м, погоня внизу упирается в стенку b42 (common_gens15) — объезд есть, по следу беглеца
#   c154_592_bumper    — кузова бампер в бампер, центры 4.6–5.5 м: старое правило «центры ближе 4.5 м» не ловит никогда
#   c380_-529_fence    — забор-ящик b1448 (fencelinesShape18) между погоней и беглецом, объезд по следу
#   c209_-484_barnfence — забор амбара b495 (Barnfence10Shape) поперёк прямой, объезд по следу
# Во всех пяти беглеца держит НЕ уровень: он стоит на ровной опоре без контактов, вокруг 97–144 из 144 мест поимки
# (CHASE_WHY=1 build/bots/chase ... --replay файл). Чинятся правила бота погони (tools/bots/chase.c: обход по следу,
# скорость по следу, «рядом» по зазору кузовов). Коллизия не тронута.
# Контроль: сборка -DCHASE_OLD_PURSUIT=1 (старые правила) обязана повторить ночь — тот же исход, угол, не пойман (красный).
# Рабочая сборка: все пять пойманы (зелёный). tests/chase_corners/run.sh -> PASS/FAIL
cd "$(dirname "$0")/../.."
BINS=chase tools/bots/build.sh >/dev/null || exit 1
BINS=chase SUF=_old tools/bots/build.sh -DCHASE_OLD_PURSUIT=1 >/dev/null || exit 1
A="build/level.shr build/homer.shr build/sandbox/roads-l1.bin"; ok=1; red=0; green=0; n=0
for f in tests/chase_corners/*.round; do
  n=$((n + 1)); b=$(basename "$f" .round)
  o=$(build/bots/chase_old $A --replay "$f" 2>/dev/null | grep '^повтор')
  if echo "$o" | grep -q "не пойман" && echo "$o" | grep -q "угол 1" && echo "$o" | grep -q "ТОТ ЖЕ ИСХОД"; then
    red=$((red + 1)); echo "$b: контроль (старые правила) — вечный угол, как ночью (красный, как надо)"
  else echo "$b: контроль НЕ повторил ночь — данные уровня/дорог не те или правило не ловит: $o"; ok=0; fi
  g=$(build/bots/chase $A --replay "$f" 2>/dev/null | grep '^повтор')
  if echo "$g" | grep -q "повтор: пойман"; then green=$((green + 1)); echo "$b: рабочая — $(echo "$g" | sed 's/^повтор: //; s/; угол.*//')"
  else echo "$b: рабочая — НЕ пойман: $g"; ok=0; fi
done
echo "контроль красный $red из $n, рабочая поймала $green из $n"
[ $ok = 1 ] && [ $n -gt 0 ] && echo PASS || { echo FAIL; exit 1; }
