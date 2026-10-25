#!/bin/bash
# сценарий замера кучи уровня N: загрузка уровня, в машину, автопилот 12 с (лента горизонта грузится на ходу; на L4 и L7 у точки старта её нет): строки HZLOAD (байты кучи после загрузки ленты) и STAT FOOT heapmin
N=$1
cat <<SC
wait 12
scene LOAD
flag golevel $N
wait 40
flag cfgdefaults 1
scene FOOT
press triangle 0.2
wait 3
flag drive 12
wait 12
flag stop
end
SC
