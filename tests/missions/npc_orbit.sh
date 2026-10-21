#!/bin/bash
# №813 (Роб 18.10, L2: «Милхаус обходит Барта и бесконечно ходит по кругу»): точка маршрута под стоящим игроком — персонаж миссии
# не кружит (проходит дальше / встаёт рядом), прохожий трафика идёт дальше по пути; честный проход мимо (№510) — как был.
# №831: игрок на пути — персонаж стоит и ждёт (не обходит, не смотрит на игрока). Красный: прежний код (-DGAME_NPC_ORBIT_OLD=1 -DPED_ORBIT_OLD=1 -DNPC_PC_WAIT_OLD=1) обязан упасть строками O1, O2 и P1.
# Данные — текущий тур (SET=папка набора). Правило остановки Мардж В85 выключено, как в npc_block.sh (его проверяет marge_v85.sh)
cd "$(dirname "$0")/../.."
S=${SET:-$HOME/Downloads/shar-psp-integ/build/test34tour/PSP/GAME/SHARTEST15}
BINS=npcorbit SUF=_new tools/bots/build.sh -DGAME_NPC_TALK_STOP_OLD=1 >/dev/null 2>&1 || exit 1
BINS=npcorbit SUF=_old tools/bots/build.sh -DGAME_NPC_ORBIT_OLD=1 -DPED_ORBIT_OLD=1 -DNPC_PC_WAIT_OLD=1 -DGAME_NPC_TALK_STOP_OLD=1 >/dev/null 2>&1 || exit 1
ok=1
for L in "1 $S/level.shr $S/level01.msn marge" "2 $S/l2/level.shr $S/l2/level02.msn milhouse"; do set -- $L
  echo "== L$1 $4, прежнее (обязано упасть):"; O=$(build/bots/npcorbit_old $2 $S/homer.shr $3 $4 | grep -v '^#'); echo "$O"
  for k in O1 O2 P1; do printf '%s\n' "$O" | grep -q "^$k .*-> FAIL$" || { echo "КРАСНЫЙ НЕ КРАСНЫЙ: L$1 $k"; ok=0; }; done
  echo "== L$1 $4, новое:"; build/bots/npcorbit_new $2 $S/homer.shr $3 $4 | grep -v '^#' || ok=0
done
[ $ok = 1 ] && echo PASS || { echo FAIL; exit 1; }
