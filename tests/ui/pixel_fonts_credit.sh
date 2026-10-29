#!/bin/bash
# Шрифты Lauke (CC BY 3.0): указание автора только при выборе (tools/pixel_fonts.py used/credit_text), строки влезают в страницу FONT CREDITS (52 знака по 8 px при 480 px),
# лицензии и readme обоих шрифтов лежат в assets/fonts/pixel/. Красный контроль: без выбора текст пустой, с выбором — оба автора
set -e
cd "$(dirname "$0")/../.."
PY=${PY:-.venv/bin/python}
$PY -I - <<'P'
import sys; sys.path.insert(0, 'tools')
import pixel_fonts as P
assert P.used(['boulder_16@1', 'msx_thin@1']) == [] and P.credit_text(P.used(['boulder_16@1'])) == '', 'без выбора текст не нужен'
u = P.used(['bart_16bit@1+1', 'simpsons_pix*2^1']); assert u == ['bart_16bit', 'simpsons_pix'], u
t = P.credit_text(u); assert 'Bart vs. the Space Mutants' in t and 'The Simpsons' in t and t.count('Patrick H. Lauke') == 3 - 1 and t.count('CC BY 3.0') == 2, t
assert max(len(l) for l in t.splitlines()) <= 52, 'строка шире экрана'
for n, f in P.FONTS.items():
    stem = f['file'].rsplit('.', 1)[0]
    for ext in ('license', 'readme'):
        assert (P.FONT_DIR / ('%s.%s.txt' % (stem, ext))).exists(), (stem, ext)
print('PASS fontcredit', len(t.splitlines()), 'lines')
P
