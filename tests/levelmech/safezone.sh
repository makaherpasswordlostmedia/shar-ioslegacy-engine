#!/bin/bash
# Гейт AddSafeZone (уровень 2, bm1: 4 этапа с зоной радиусом 30 м): настоящий код (world.c, game_msn.c, рантайм миссий),
# пакет миссий уровня 2 (tools/missions/compile.py). Красные: игрок поставлен в 40 м от локатора зоны (неверный локатор),
# сборка без зон (-DGAME_SAFE_ON=0). Зелёный: в зоне шкала Hit & Run гаснет, вне — нет, на следующем этапе зон нет.
. "$(dirname "$0")/common.sh"
build_host
SUF=_nosafe bash tests/levelmech/build_host.sh -DGAME_SAFE_ON=0 > /dev/null || exit 2
MSN=${MSN:-build/lm/msn/level02.msn}
[ -f "$MSN" ] || $PY tools/missions/compile.py --level 2 --out build/lm/msn > /dev/null
L2=$(LV 2 level.shr)
export BW_NO_COLLECT=1
red   "неверный локатор (сдвиг 40 м)"   build/levelmech/lvmech "$L2" "$HOMER" --safezone "$MSN" 40
red   "сборка без зон GAME_SAFE_ON=0"   build/levelmech/lvmech_nosafe "$L2" "$HOMER" --safezone "$MSN"
green "зоны уровня 2 из данных"         build/levelmech/lvmech "$L2" "$HOMER" --safezone "$MSN"
tail -7 "$LOGD"/green_*.log
echo "журнал: $LOGD"
[ $FAILS -eq 0 ] && echo "GATE safezone: PASS" || echo "GATE safezone: FAIL ($FAILS)"
exit $FAILS
