#!/bin/bash
# Гейт покрытия команд миссий (tools/missions/coverage.py): кто исполняет каждую команду пакетов уровней 1–7 — рантайм,
# игра, экспортёр или никто («ignored»). Ожидание — tests/levelmech/coverage_expected.tsv (обновлять сознательно:
# --write-expected). Красные: исходники игры без npc.remove (RemoveNPC уровней 2 и 5 становится ignored), пакет уровня 2
# с подложенной командой ResetCharacter (в пакетах её нет). Зелёный: статусы = ожиданию.
. "$(dirname "$0")/common.sh"
D=build/lm/msn
for n in 1 2 3 4 5 6 7; do [ -f $D/level0$n.msn ] || $PY tools/missions/compile.py --level $n --out $D > /dev/null || exit 2; done
if [ "$1" = "--write-expected" ]; then
  $PY tools/missions/coverage.py --msn-dir $D --write docs/state/msn_coverage.tsv --brief
  { echo "# ожидаемый статус команд пакетов (tools/missions/coverage.py); обновлено $(date '+%F %H:%M')"; grep -v '^#' docs/state/msn_coverage.tsv | tail -n +2 | cut -f1,2; } > tests/levelmech/coverage_expected.tsv
  echo "ожидание записано: $(grep -vc '^#' tests/levelmech/coverage_expected.tsv) команд"; exit 0
fi
# красный 1: игра без npc.remove
P=build/levelmech/src_noremove; rm -rf "$P"; mkdir -p "$P/mission"; cp viewer/*.c viewer/*.h "$P/"; cp viewer/mission/*.c viewer/mission/*.h "$P/mission/"
sed -i '' 's/api.npc.remove = npcRemove;//' "$P/game_msn.c"
red   "игра без npc.remove"          $PY tools/missions/coverage.py --msn-dir $D --src "$P" --check tests/levelmech/coverage_expected.tsv --brief
# красный 2: пакет уровня 2 с подложенной командой (опкод ResetCharacter вместо первой команды SetMaxTraffic)
Q=build/levelmech/msn_planted; rm -rf "$Q"; mkdir -p "$Q"; cp $D/level0?.msn "$Q/"
$PY - "$Q/level02.msn" <<'EOF'
import struct, sys
sys.path.insert(0, 'tools/missions'); import commands as C
p = sys.argv[1]; b = bytearray(open(p, 'rb').read())
off, cnt = struct.unpack_from('<II', b, 16 + 5 * 8); want = C.BY_NAME['setmaxtraffic'].op; new = C.BY_NAME['resetcharacter'].op
for i in range(cnt):
    if struct.unpack_from('<H', b, off + 12 * i)[0] == want: struct.pack_into('<H', b, off + 12 * i, new); break
open(p, 'wb').write(b)
EOF
red   "пакет с подложенной командой" $PY tools/missions/coverage.py --msn-dir "$Q" --check tests/levelmech/coverage_expected.tsv --brief
green "статусы команд = ожиданию"    $PY tools/missions/coverage.py --msn-dir $D --check tests/levelmech/coverage_expected.tsv --write docs/state/msn_coverage.tsv --brief
grep -h "FAIL\|RESULT\|ignored" "$LOGD"/*.log | head -8
echo "журнал: $LOGD"
[ $FAILS -eq 0 ] && echo "GATE coverage: PASS" || echo "GATE coverage: FAIL ($FAILS)"
exit $FAILS
