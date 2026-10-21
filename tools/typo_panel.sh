#!/bin/bash
# Правка Роба 312: пересобрать твик-панель типографики build/ТИПОГРАФИКА_ПАНЕЛЬ (страница + img/) с новыми снимками игры.
#   tools/typo_panel.sh [EBOOT]     EBOOT — сборка с флагом uitypo (viewer/ui.c uiTypoShot), по умолчанию viewer/build/EBOOT.PBP
# Снимки: сценарии tests/ui/typo_scenes/*.txt в безголовом эмуляторе (scen.py, без звука, свой HOME), по три параллельно;
# кадры <сцена>_a / _b / _c / _a2 (целиком / без текста / без интерфейса / целиком позже — для гейта). Потом tools/typo_panel.py
# и гейты страницы: tests/ui/typo_fonts.mjs (порт граней побайтно), tests/ui/typo_panel_check.py (текст панели = текст игры)
set -eu; cd "$(dirname "$0")/.."
EB="${1:-viewer/build/EBOOT.PBP}"; SCEN="$HOME/.claude/skills/shar-level-polish/scripts/scen.py"
case "$EB" in /*) ;; *) EB="$PWD/$EB" ;; esac
TAG="${SCEN_TAG:-typo}"; PANEL="${PANEL_OUT:-build/ТИПОГРАФИКА_ПАНЕЛЬ}"
HOMES=$(mktemp -d); OUT="${SCEN_OUT:-${SCEN_ROOT:-$HOME/Downloads/shar-psp}/build/twins/scen/full}"   # куда scen.py кладёт кадры (его SCEN_ROOT); папка создаётся при съёмке
run() { SCEN_HOME="$HOMES/$1" SCEN_EBOOT="$EB" nice python3 -c "import sys; sys.path.insert(0, '$(dirname "$SCEN")'); import scen; scen.run('${TAG}_$1', open('tests/ui/typo_scenes/$1.txt').read().splitlines())" > "$HOMES/$1.log" 2>&1; }
( run talk; run boom; run police ) & panel_job1=$!
( run tut; run brief; run pause ) & panel_job2=$!
( run race; run menusave; run booth ) & panel_job3=$!
panel_rc=0
for panel_job in "$panel_job1" "$panel_job2" "$panel_job3"; do wait "$panel_job" || panel_rc=1; done
if [ "$panel_rc" -ne 0 ]; then echo "Ошибка съёмки сцен, логи: $HOMES" >&2; exit "$panel_rc"; fi
.venv/bin/python tools/typo_panel.py --shots "$OUT" --shot-prefix "${TAG}_" --out "$PANEL"
.venv/bin/python tools/typo_panel.py --fontref "$HOMES/fontref.json" && node tests/ui/typo_fonts.mjs "$PANEL/index.html" "$HOMES/fontref.json"
.venv/bin/python tests/ui/typo_img_check.py "$PANEL"   # закон Роба 15.10: все ссылки на картинки страницы на месте
.venv/bin/python tests/ui/typo_panel_check.py "$PANEL"
