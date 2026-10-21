#!/bin/bash
# Кадры эмулятора для гейта «панель = игра» (tests/ui/typo_panel_check.py): сцены tests/ui/typo_scenes/*.txt с пакетами интерфейса из ПАКЕТЫ (tools/ui_packs.sh).
#   tools/typo_gate_frames.sh ПАКЕТЫ EBOOT ВЫХОД [СЦЕНЫ...]     ВЫХОД/typo_rob_<сцена>/…; сцены по умолчанию — все девять опорных и восемь дополнительных
#   SCEN_ROOT (репозиторий с данными, по умолчанию ~/Downloads/shar-psp-g-build-w) нужен scen.py; эмулятор безголовый, без звука, свой HOME
# Потом: python3 tests/ui/typo_panel_check.py build/ТИПОГРАФИКА_ПАНЕЛЬ --json build/ui_typo.json --shots ВЫХОД --prefix typo_rob_  (папки sync12_* — ссылки на typo_rob_*, см. «Панель» в ФИНАЛ_Интерфейс)
set -u; cd "$(dirname "$0")/.."
P=$(cd "${1:?ПАКЕТЫ}" && pwd); EB=$(cd "$(dirname "${2:?EBOOT}")" && pwd)/$(basename "$2"); OUTD="${3:?ВЫХОД}"; shift 3
SC="${*:-talk boom police tut brief pause race menusave booth title stage over load windows extra rewards dropped}"
G="${SCEN_ROOT:-$HOME/Downloads/shar-psp-g-build-w}"; mkdir -p "$OUTD"; OUTD=$(cd "$OUTD" && pwd)
OV=""; for f in ui psave pextra boot load menu pmenu fsave shop phone; do [ -f "$P/$f.shr" ] && OV="$OV,$f.shr=$P/$f.shr"; done; OV=${OV#,}
SCRIPTS="$HOME/.claude/skills/shar-level-polish/scripts"
run() { local h; h=$(mktemp -d); SCEN_ROOT=$G SCEN_HOME=$h SCEN_EBOOT=$EB SCEN_OVERRIDE="$OV" nice python3 -c "import sys; sys.path.insert(0,'$SCRIPTS'); import scen; scen.run('typo_rob_$1', open('tests/ui/typo_scenes/$1.txt').read().splitlines())" > "$OUTD/$1.log" 2>&1; echo "done $1"; }
n=0; for s in $SC; do run "$s" & n=$((n+1)); [ $((n % 3)) = 0 ] && wait; done; wait; echo ALLDONE
