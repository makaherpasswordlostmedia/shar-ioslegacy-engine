#!/bin/bash
# Гейт №689 + №708/№710 (запас справа у пузырей с аватаром; пузырь без аватара у левого поля и полукруглые края). Красные: BUBBLE_AVATAR_PAD_OLD, MSG_PILL_OLD (прежнее VCENTER1 убрано: на trunk-test30 оно не отличалось и не ловилось).
# Гейт №689: правила Роба для баблов сообщений (текст слева, рамка по ширине текста, левее радара, не выше его верха, не квадратная). Сборки: new и BUBBLE_VCENTER1_OLD (прежнее trunk-test28, красная).
#   tests/ui/b689_gate.sh   (B689_REUSE=1 — не пересобирать)    pspdev/.venv-ссылки на главное дерево; эмулятор безголовый через scen.py
set -u; ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
SCEN=~/.claude/skills/shar-level-polish/scripts/scen.py; OUT="$ROOT/build/b671"; V="new BUBBLE_AVATAR_PAD_OLD MSG_PILL_OLD"
for v in $V; do [ "${B689_REUSE:-0}" = 1 ] && [ -f "$OUT/gb/$v/EBOOT.PBP" ] && continue
  ( mkdir -p "$OUT/gb/$v" && cd "$OUT/gb/$v" && O=""; [ $v != new ] && O="-DSHAR_OPT=-D$v=1"; psp-cmake -S "$ROOT/viewer" -B . $O >/dev/null 2>&1 && cmake --build . -j4 >/dev/null 2>&1 ) & done; wait
for v in $V; do ( until [ "$(pgrep -x PPSSPPHeadless | wc -l)" -lt 5 ]; do sleep 8; done
  SCEN_HOME="$OUT/gb/home_$v" SCEN_EBOOT="$OUT/gb/$v/EBOOT.PBP" timeout 1500 python3 "$SCEN" "b689g_$v" tests/ui/b689_msgs_scenario.txt 2>&1 | sed -n 's/^dir \([^ ]*\) .*/\1/p' > "$OUT/dir689_$v" ) & done; wait
for v in $V; do mkdir -p "$OUT/frames_$v"; cp "$(cat "$OUT/dir689_$v")"/*.png "$OUT/frames_$v/"; done
python3 tests/ui/b689_check.py "$OUT/frames_new" > "$OUT/b689_new.txt" && n=ЗЕЛЁНЫЙ || n="КРАСНЫЙ (плохо)"; ok=1; [ "$n" = ЗЕЛЁНЫЙ ] || ok=0
echo "№689/708/710 баблы сообщений: новый $n"
for v in BUBBLE_AVATAR_PAD_OLD MSG_PILL_OLD; do python3 tests/ui/b689_check.py --red "$OUT/frames_$v" > "$OUT/b689_$v.txt" && r="красный (как нужно)" || { r="ЗЕЛЁНЫЙ (красный не пойман)"; ok=0; }; echo "  $v: $r"; done
for v in $V; do rm -rf "$(cat "$OUT/dir689_$v")"; done   # диск общий: каждая постановка 0,7 ГБ
[ $ok = 1 ]
