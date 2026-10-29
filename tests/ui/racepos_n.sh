#!/bin/bash
# Гейт «1/2» в месте гонки (tests/ui/racepos_n.c). КРАСНЫЙ: -DUI_POS_RACERS_OLD=1 обязан упасть на pos. Мак, CPU, без эмулятора
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/racepos_n; mkdir -p "$OUT"
cc -std=c11 -O2 -Wall -I viewer -DUI_POS_RACERS_OLD=1 tests/ui/racepos_n.c -lm -o "$OUT/red" && cc -std=c11 -O2 -Wall -I viewer tests/ui/racepos_n.c -lm -o "$OUT/green" || { echo "FAIL: сборка"; exit 2; }
"$OUT/red" > "$OUT/red.txt"; if grep -q "CHECK pos FAIL" "$OUT/red.txt"; then echo "красный: $(grep -m1 'CHECK pos' "$OUT/red.txt")"; red=1; else echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0; fi
"$OUT/green" | tee "$OUT/green.txt"; rc=${PIPESTATUS[0]}
# glyph: в спрайтовом шрифте поля Position (Hud.pag, ingame.p3d диска) есть «/» — иначе «1/2» не нарисовать
G=$(cd tools && ../.venv/bin/python -c "
import ui_export as U
pr=U.project('ingame.p3d')
def walk(n):
    if isinstance(n,list):
        for x in n: yield from walk(x)
        return
    if n['kind'] in ('layer','group'):
        for c in n['children']: yield from walk(c)
    else: yield n
e=[n for n in walk(pr.pages['Hud.pag']) if n.get('name')=='Position'][0]
print(1 if '/' in U.sprite_font_map(e['images']) else 0)" 2>/dev/null)
if [ "$G" = 1 ]; then echo "CHECK glyph OK    в шрифте поля Position (Hud.pag) есть «/»"; else echo "CHECK glyph FAIL  нет «/» в шрифте Position"; rc=1; fi
[ $red = 1 ] && [ $rc = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
