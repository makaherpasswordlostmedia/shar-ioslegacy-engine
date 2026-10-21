#!/bin/bash
# Метка этапа «купи машину» (L1 m3, Plow King) стоит там, где стоит продавец (запись PS2 13:51: круг и $ под Барни). Бот проходит стадию покупки только если метка ведёт к продавцу.
# Использование: DATA=каталог_с_уровнем(build) tests/missions/buymark.sh   (нужны level.shr homer.shr level01.msn sandbox/roads-l1.bin). RED=1 — старый код, обязан застрять на покупке
set -e
cd "$(dirname "$0")/../.."
D=${DATA:-$PWD/build}; O=${TMPDIR:-/tmp}/buymark.$$; mkdir -p $O
F=""; [ "$RED" = 1 ] && F="-DMSN_BUYMARK_OLD=1"
OUT_DIR=$O BINS=missioner tools/bots/build.sh $F > /dev/null
MISSIONER_COINS=3000 BW_FRAMES=1 BW_LEVEL=1 MISSIONER_SEED=1 $O/missioner $D/level.shr $D/homer.shr $D/sandbox/roads-l1.bin $D/level01.msn --mission 3 --secs 150 -v > $O/log.txt 2>&1 || true
last=$(grep "^  стадия" $O/log.txt | tail -1 | sed 's/^  стадия \([0-9.]*\).*/\1/')
echo "последняя стадия за 150 с: $last (покупка — стадия 0.9)"
rm -rf $O
if [ "$RED" = 1 ]; then [ "$last" = "0.9" ] && echo "красный контроль пойман" || { echo "красный контроль НЕ пойман"; exit 1; }
else [ "$last" != "0.9" ] && echo PASS || { echo FAIL; exit 1; }; fi
