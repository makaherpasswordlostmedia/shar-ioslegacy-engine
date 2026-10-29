#!/bin/bash
# сценарий цены ленты в езде на уровне N: автопилот 26 с (flag drive), лента переключается каждые 6 с (мировая / прежняя / мировая / прежняя); строки HORIZON cost несут world=, wus=, builds=, verts=
N=$1
cat <<SC
scene HZC_L$N
flag cfgdefaults 1
flag golevel $N
wait 40
press triangle 0.2
wait 3
flag hzworld 1
flag drive 30
wait 6
flag hzworld 0
wait 6
flag hzworld 1
wait 6
flag hzworld 0
wait 6
flag stop
end
SC
