#!/bin/bash
# Ночь ботов = мир EBOOT для миссий (разбор ночи 02.10 для приёмки L1, 03.10). Замороженные входы ночи (tools/bots/night.py freeze)
# обязаны давать миссионеру те же спутники уровня, что игра: кузова машин миссий и SetForcedCar (msncars-l1.shr), длины реплик и
# события музыки (audio/: sfx.sab, оглавление music.sap). Без них m6 «застрял» 22 прогона из 22 (самосвал cBone и машина Мардж
# были не те), а итог миссий в утре мерил не игру. Плюс потолок миссии на прогон: 1500 с (m5 в мире EBOOT проходит за 312 с).
# Красный: NIGHT_INPUTS_OLD=1 (прежний набор входов) и NIGHT_MSN_SECS_OLD=1 (прежние 300 с) — обязаны упасть; потом зелёный.
#   tests/bots/night_inputs.sh   -> PASS/FAIL; рабочие файлы build/bots/gate_night_inputs/
cd "$(dirname "$0")/../.."
O=build/bots/gate_night_inputs; rm -rf "$O"; mkdir -p "$O"
BINS=missioner OUT_DIR=$O tools/bots/build.sh >/dev/null || { echo "FAIL: сборка миссионера"; exit 1; }
for f in level.shr homer.shr msncars-l1.shr audio/music.sap audio/sfx.sab missions/level01.msn sandbox/roads-l1.bin; do
  [ -e "build/$f" ] || { echo "FAIL: нет build/$f (выпуск не собран)"; exit 1; }; done
freeze() {   # $1 — папка; окружение — набор входов (как freeze ночи: те же IN_FILES и copy_in)
  python3 - "$1" <<'PY'
import sys; sys.path.insert(0, 'tools/bots')
from pathlib import Path
import night
d = Path(sys.argv[1]); n = 0
for f in night.IN_FILES:
    s = night.ROOT / 'build' / f
    if s.exists(): night.copy_in(s, d / f, f); n += 1
print(f"входов {n}, потолок миссии {night.MSN_SECS_CAP} с")
PY
}
packs() { $O/missioner "$1/level.shr" "$1/homer.shr" "$1/sandbox/roads-l1.bin" "$1/missions/level01.msn" --packs | grep '^P'; }
msn() { nice -n 10 $O/missioner "$1/level.shr" "$1/homer.shr" "$1/sandbox/roads-l1.bin" "$1/missions/level01.msn" --mission $2 --secs $3 | grep '^M' | cut -f3,5,7; }
secs() { python3 -c "import sys; sys.path.insert(0, 'tools/bots'); import night; print(night.MSN_SECS_CAP)"; }
echo "== красный: прежний набор входов (NIGHT_INPUTS_OLD=1), прежний потолок (NIGHT_MSN_SECS_OLD=1)"
NIGHT_INPUTS_OLD=1 freeze "$O/old" | sed 's/^/  /'
PO=$(packs "$O/old"); M6O=$(msn "$O/old" 6 300); CO=$(NIGHT_MSN_SECS_OLD=1 secs)
echo "  мир миссий (P кузовов звук комнат трафик): $PO"; echo "  m6 за 300 с: $M6O"; echo "  потолок миссии $CO с"
red=0
case "$PO" in "P	0	0	"*) red=$((red + 1));; esac
case "$M6O" in *пройдена*) ;; *) red=$((red + 1));; esac
echo "== зелёный: входы как у EBOOT, потолок ночи"
freeze "$O/new" | sed 's/^/  /'
PN=$(packs "$O/new"); M6N=$(msn "$O/new" 6 300); CN=$(secs); M5N=$(msn "$O/new" 5 "$CN"); SZ=$(stat -f %z "$O/new/audio/music.sap")
M5C=$(msn "$O/new" 5 "$CO")
echo "  мир миссий: $PN; оглавление music.sap $SZ Б"; echo "  m6 за 300 с: $M6N"; echo "  потолок $CN с; m5: $M5N (за прежние $CO с: $M5C)"
green=1
awk -F'\t' '{ exit !($2 > 0 && $3 == 1 && $4 > 0 && $5 == 1) }' <<< "$PN" || { echo "  ✗ мир миссий не как у EBOOT"; green=0; }
case "$M6N" in *пройдена*) ;; *) echo "  ✗ m6 не пройдена"; green=0;; esac
[ "$SZ" -le 65536 ] || { echo "  ✗ music.sap в ночь целиком ($SZ Б), нужно только оглавление"; green=0; }
case "$M5N" in *пройдена*) ;; *) echo "  ✗ m5 не пройдена за потолок ночи"; green=0;; esac
case "$M5C" in *пройдена*) ;; *) red=$((red + 1));; esac   # прежний потолок режет честный проход
echo "красных поймано $red из 3"
[ $red = 3 ] && [ $green = 1 ] && echo "PASS" || { echo "FAIL"; exit 1; }
