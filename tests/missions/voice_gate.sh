#!/bin/bash
# Гейт «Миссии: голос и музыка» без экрана (пакет озвучки миссий): тот же C-код, что EBOOT (viewer/game_msn.c + msn_audio.c),
# длины реплик и события музыки — из build/audio (tools/sound_export.py).
#   1) полнота пакета: все 80 реплик разговоров уровня 1 и музыка M1..M7 (tests/missions/voice_pack_check.py);
#   2) бот-миссионер m0: разговор с Мардж (icecream 1/2 mrg, 2/2 hom) и с Апу (congrats 3/3), конец разговора = конец
#      последней реплики, M0_win -> музыка победы; миссия пройдена (tests/missions/voice_check.py);
#   3) бот m1: после вступления событие M1_start -> collection02_pickup (музыка миссии).
#   tests/missions/voice_gate.sh              -> PASS / FAIL
#   tests/missions/voice_gate.sh --negative   отрицательный контроль: бот собран с -DMSN_AUDIO_BREAK=1 (правило имени реплики
#                                              сломано) -> «нет голоса» -> сверка обязана упасть (тогда PASS)
cd "$(dirname "$0")/../.."
NEG=0; [ "${1:-}" = --negative ] && NEG=1
OUT=${TMPDIR:-/tmp}/voice_gate.$$; mkdir -p "$OUT"; PY=.venv/bin/python
SUF=""; [ $NEG = 1 ] && SUF=_vbroken
if [ $NEG = 1 ]; then SUF=$SUF BINS=missioner tools/bots/build.sh -DMSN_AUDIO_BREAK=1 >/dev/null || { echo "FAIL: сборка"; exit 1; }
else BINS=missioner tools/bots/build.sh >/dev/null || { echo "FAIL: сборка"; exit 1; }; fi
M="build/bots/missioner$SUF"; A="build/level.shr build/homer.shr build/sandbox/roads-l1.bin build/missions/level01.msn"
R=0
if [ $NEG = 0 ]; then $PY tests/missions/voice_pack_check.py > /tmp/voice_pack.$$ 2>&1; rc=$?; tail -2 /tmp/voice_pack.$$; rm -f /tmp/voice_pack.$$; [ $rc = 0 ] || R=1; fi   # код проверки, не tail (была ложная зелень)
BW_AUDIO_LOG=1 $M $A --mission 0 --secs 600 --out "$OUT" > "$OUT/m0.txt" 2>/dev/null
grep -q "^M	0	m0	.*	пройдена	" "$OUT/m0.txt" || { echo "m0 не пройдена ботом"; R=1; }
$PY tests/missions/voice_check.py "$OUT/m0.txt" | tail -1 || R=1
$PY tests/missions/voice_check.py "$OUT/m0.txt" > /dev/null || R=1
BW_AUDIO_LOG=1 $M $A --mission 1 --secs 90 --out "$OUT" > "$OUT/m1.txt" 2>/dev/null
L=$(grep "MUSIC event M1_start" "$OUT/m1.txt" | head -1); echo "m1: ${L:-нет события M1_start}"
echo "$L" | grep -q "M1_start -> collection02_pickup" || R=1
echo "журналы: $OUT"
if [ $NEG = 1 ]; then
  if [ $R != 0 ]; then echo "PASS (отрицательный контроль: без голоса гейт красный, как должен)"; exit 0; fi
  echo "FAIL (отрицательный контроль прошёл — гейт ничего не ловит)"; exit 1
fi
if [ $R = 0 ]; then echo PASS; else echo FAIL; exit 1; fi
