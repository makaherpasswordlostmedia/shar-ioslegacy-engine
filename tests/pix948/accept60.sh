#!/bin/bash
# №948б приёмка (окно «Глюки», TEST60/61): битые пиксели снизу картинок меню будки (повтор №809) — хранимые строки страницы CLUT8 доходят до низа самой нижней картинки.
# Причина: страница хранила строки по последнему непрозрачному индексу (+8); у последней картинки страницы (каркас husk: 18 прозрачных строк из 116) хвост лежал глубже хранимых — GE читал за концом данных.
# Гейт: пакет будки (phone.shr) из прежнего экспорта (UI_ROWS948_OLD=1) ОБЯЗАН провалить rows_check.py (слотов с низом глубже хранимых > 0), из нового — пройти (0), и страницы нового хранят прежние строки как были.
#   tests/pix948/accept60.sh      последняя строка PASS или FAIL
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
set -u
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"; D=run/acc948; mkdir -p $D
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
UI_ROWS948_OLD=1 $PY tools/shop_export.py --phone-ui --out $D/old.shr >/dev/null 2>&1 || { echo "экспорт прежний не удался"; echo FAIL; exit 2; }
$PY tools/shop_export.py --phone-ui --out $D/new.shr >/dev/null 2>&1 || { echo "экспорт новый не удался"; echo FAIL; exit 2; }
o=$(python3 tests/pix948/rows_check.py $D/old.shr); orc=$?; n=$(python3 tests/pix948/rows_check.py $D/new.shr $D/old.shr); nrc=$?
echo "прежнее: $(echo "$o" | head -1) -> $([ $orc != 0 ] && echo 'красный, как нужно' || echo 'ЗЕЛЁНЫЙ (красный не пойман)')"
echo "новое:   $(echo "$n" | head -1); $(echo "$n" | grep страницы) -> $([ $nrc = 0 ] && echo зелёный || echo 'КРАСНЫЙ (плохо)')"
echo "размер: прежний $(stat -f %z $D/old.shr) Б, новый $(stat -f %z $D/new.shr) Б"
if [ $nrc = 0 ] && [ $orc != 0 ]; then echo PASS; else echo FAIL; fi
