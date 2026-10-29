#!/bin/bash
# Дороги трафика под коллизией (группа corners-roads, очередь пункт 11). Утро 01.10: «мест 7, проб в коллизии 18 из 5740».
# Разбор по данным: все 18 проб — на отрезках дорог с shortcut = 1 и maxCars = 0 (поля Road 0x3000003 в l1_terra.p3d; так же их
# читает и пропускает экспорт трафика tools/traffic_export.py) — это срезки ИИ (прыжок через щель 124 220, двор с забором 175 173,
# крыша-трамплин −165 280 с ящиком 180, плита под мостом 224 −470), машин трафика там нет. Коллизия — из данных диска
# (StaticPhys без экземпляров, мировые координаты), экспорт её не искажал; вырезать нечего (закон 3).
# Ошибка была в станке: tools/cartest/roadblock.c считал все отрезки дорогами трафика. Теперь — только maxCars > 0 и не срезка
# (build/sandbox/roads-l1.meta.tsv от tools/cartest/roads.py), срезки — справочной строкой.
# Контроль: сборка -DRB_ALL_ROADS=1 (старое правило) обязана показать прежние 18 проб в коллизии (красный); рабочая — 0 на
# дорогах трафика и те же 18 на срезках (зелёный: ничего не потеряно, только разнесено). tests/roadblock/run.sh -> PASS/FAIL
cd "$(dirname "$0")/../.."
if [ ! -f build/sandbox/roads-l1.meta.tsv ]; then   # разметка дорог рядом с roads-l1.bin; сам .bin не трогаем, только сверяем
  T=$(mktemp -d); .venv/bin/python tools/cartest/roads.py --level 1 --out "$T/roads-l1.bin" >/dev/null || exit 1
  cmp -s "$T/roads-l1.bin" build/sandbox/roads-l1.bin || { echo "roads.py дал другой roads-l1.bin — разметка не к этому файлу; FAIL"; exit 1; }
  cp "$T/roads-l1.meta.tsv" build/sandbox/roads-l1.meta.tsv; rm -rf "$T"
fi
V=viewer; . tools/bots/lib.sh
CC="cc -std=c11 -O1 -Wall -Wno-unused-function -DSKIN_HOST -I viewer -I tools/bots"
$CC tools/cartest/roadblock.c $BOTS_LIB -lm -o build/bots/roadblock || exit 1
$CC -DRB_ALL_ROADS=1 tools/cartest/roadblock.c $BOTS_LIB -lm -o build/bots/roadblock_all || exit 1
o=$(build/bots/roadblock_all 2>/dev/null); n=$(build/bots/roadblock 2>/dev/null); ok=1
ob=$(echo "$o" | awk -F'\t' '$1=="S"{print $3}'); nb=$(echo "$n" | awk -F'\t' '$1=="S"{print $3}'); nq=$(echo "$n" | awk -F'\t' '$1=="Q"{print $3}')
nk=$(echo "$n" | grep -c '^K'); nr=$(echo "$n" | grep -c '^R')
if [ "${ob:-0}" -gt 0 ]; then echo "контроль (все отрезки как трафик): в коллизии $ob проб — красный, как ночью"; else echo "контроль: 0 — ГЕЙТ НЕ ЛОВИТ"; ok=0; fi
if [ "$nb" = 0 ] && [ "$nr" = 0 ]; then echo "рабочая: на дорогах трафика в коллизии 0 — зелёный"; else echo "рабочая: на дорогах трафика в коллизии $nb — FAIL"; echo "$n" | grep '^R' | head -5; ok=0; fi
if [ "$nq" = "$ob" ] && [ "$nk" = "$ob" ]; then echo "срезки ИИ: те же $nq проб справочно (ничего не потеряно)"; else echo "срезки ИИ: $nq (строк $nk) против контроля $ob — разнесено не всё; FAIL"; ok=0; fi
[ $ok = 1 ] && echo PASS || { echo FAIL; exit 1; }
