#!/bin/bash
# №970: прогоны сценариев на сборке: run.sh ОБЪЕКТ ИМЯ СБОРКА OLD [МАКС_С]   -> $A/out_ИМЯ (smoke.txt + снимки)
W=$(cd "$(dirname "$0")/../.." && pwd); cd "$W"
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test66tour/PSP/GAME/SHARTEST15}; export EMU_OWNER=${EMU_OWNER:-Небо} EMU_MINE=${EMU_MINE:-2}
A=${A:-$W/build/g970/acc}; mkdir -p "$A"; export OUT=$A
S=$A/scn_$2.txt   # OLD = x — строку flag glint970old убрать совсем (проверка выключателя при сборке)
if [ "$4" = x ]; then grep -v "glint97[06]old" tests/glint970/$1.txt > "$S"; else sed "s/@OLD@/$4/g" tests/glint970/$1.txt > "$S"; fi
exec tools/emu_run.sh "$S" "$2" "viewer/build_g_$3/EBOOT.PBP" "${5:-300}"
