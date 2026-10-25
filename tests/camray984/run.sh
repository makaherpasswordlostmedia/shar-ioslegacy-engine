#!/bin/bash
# №984: run.sh МАРШРУТ.txt ИМЯ СБОРКА [МАКС_С]  -> $A/out_ИМЯ ; ZPRE — строки (через \n) после «flag cfgdefaults 1»
W=$(cd "$(dirname "$0")/../.." && pwd); cd "$W"
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test66tour/PSP/GAME/SHARTEST15}; export EMU_OWNER=${EMU_OWNER:-Небо} EMU_MINE=${EMU_MINE:-2}
A=${A:-$W/build/c984/acc}; mkdir -p "$A"; export OUT=$A
S=$A/scn_$2.txt; if [ -n "${ZPRE:-}" ]; then awk -v p="$ZPRE" '{print} /^flag cfgdefaults 1/ && !d {gsub(/\\n/, "\n", p); print p; d=1}' "$1" > "$S"; else cp "$1" "$S"; fi
exec tools/emu_run.sh "$S" "$2" "viewer/build_cr_$3/EBOOT.PBP" "${4:-400}"
