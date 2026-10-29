#!/bin/bash
# Правка 345: реплики водителя уровня (W_Mstart_<код>_* на ✕ Continue карточки миссии, W_GOC_<код>_* на выходе из машины) и
# атмосфера комнат (таблица RAMB: Kwik-E-Mart, дом, школа -> room_small_01, DMV -> DMV) — tests/sound/pcsay_host.c на настоящих
# пакетах уровней. Красный: --old (flag pcsayold / roomambold) и прежний пакет (PCSAY_OLD=папка: без семейств и RAMB) обязаны упасть.
#   tests/sound/pcsay.sh                    пакеты build/audio (уровень 1) и build/levels/l<N>/audio (2–7, какие есть)
#   PCSAY_PACKS="1=dir,2=dir" PCSAY_OLD=dir tests/sound/pcsay.sh   свои папки пакетов
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/pcsay; mkdir -p "$OUT"
cc -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DAUDIO_HOST -I viewer -o "$OUT/pcsay" tests/sound/pcsay_host.c viewer/sound.c viewer/audio.c -lm 2> "$OUT/build.txt" \
  || { echo "FAIL: сборка"; head -5 "$OUT/build.txt"; exit 1; }
CODE=(- hom brt lis mrg apu brt hom); ROOM=(- KwikEMart DMV - KwikEMart DMV - KwikEMart); TRK=(- amb_room_small_01 amb_room_dmv - amb_room_small_01 amb_room_dmv - amb_room_small_01)
pack() { local p; p=$(echo ",${PCSAY_PACKS:-}," | sed -n "s/.*,$1=\([^,]*\),.*/\1/p"); [ -n "$p" ] && { echo "$p"; return; }
         [ "$1" = 1 ] && echo build/audio || echo "build/levels/l$1/audio"; }
ok=1; P1=$(pack 1)
if "$OUT/pcsay" "$P1/" hom KwikEMart amb_room_small_01 --old > "$OUT/red.txt" 2>&1; then echo "КРАСНЫЙ (--old) НЕ ПОЙМАН"; ok=0
elif grep -q 'CHECK.*FAIL' "$OUT/red.txt"; then echo "красный (--old): $(grep -c 'CHECK.*FAIL' "$OUT/red.txt") провал(а): $(grep 'CHECK.*FAIL' "$OUT/red.txt" | cut -c1-110 | tr '\n' ';')"; else echo "FAIL: отрицательный контроль не дошёл до проверок"; ok=0; fi
if [ -n "${PCSAY_OLD:-}" ]; then
  if "$OUT/pcsay" "$PCSAY_OLD/" hom KwikEMart amb_room_small_01 > "$OUT/red_pack.txt" 2>&1; then echo "КРАСНЫЙ (прежний пакет) НЕ ПОЙМАН"; ok=0
  else echo "красный (прежний пакет): $(grep -c 'CHECK.*FAIL' "$OUT/red_pack.txt") провал(а): $(grep 'CHECK.*FAIL' "$OUT/red_pack.txt" | cut -c1-110 | tr '\n' ';')"; fi
fi
for L in 1 2 3 4 5 6 7; do
  P=$(pack $L); [ -f "$P/sfx.sab" ] && [ -f "$P/music.sap" ] || { echo "уровень $L: пакета нет ($P) — FAIL"; ok=0; continue; }
  GIC_ARG=""
  if python3 - "${CODE[$L]}" <<'SOURCE'
import pathlib,re,sys
p=pathlib.Path('hit-and-run-web/source/game/sound/scripts/dialog.spt')
if not p.is_file():sys.exit(2)
sys.exit(1 if re.search(r'create\s+daSoundResourceData\s+named\s+W_GIC_'+re.escape(sys.argv[1])+r'_',p.read_text(errors='replace'),re.I) else 0)
SOURCE
  then
    GIC_ARG=--no-gic-source
    echo "диск: семейства W_GIC_${CODE[$L]} нет; точечное исключение только Апу по решению Роба 09.10 (В93)"
  fi
  echo "проверка, уровень $L ($P):"; "$OUT/pcsay" "$P/" "${CODE[$L]}" "${ROOM[$L]}" "${TRK[$L]}" ${GIC_ARG:+"$GIC_ARG"} > "$OUT/l$L.txt" 2>&1; r=$?
  grep -E "CHECK|INFO|RESULT" "$OUT/l$L.txt"; [ $r = 0 ] || ok=0
done
[ $ok = 1 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
