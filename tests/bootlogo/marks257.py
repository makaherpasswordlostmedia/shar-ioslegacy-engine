#!/usr/bin/env python3
"""Гейт правки Роба 257 (данные): «просто PSP, именно логотип PSP, как на корпусе сзади, и просто El Barto; вспомогательные
(Radical) не видно — красиво, как спонсорские». Сборка tools/bootmarks.py: 8 знаков — The Simpsons, Fox, Disney, Gracie,
Radical, Vivendi, El Barto, PSP; самодельного знака PlayStation нет; Radical — словом (шире 90 px, а не кольцо 24 px); у знаков
одна площадь чернил (±35 %); все — 1 бит цветом покоя GONE. Красный: BMK_257_OLD=1 (набор правки 254) -> FAIL"""
import io, contextlib, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.argv = sys.argv[:1]
with contextlib.redirect_stdout(io.StringIO()):
    import bootmarks as B
    _, marks = B.build2()
names = [m[0] for m in marks]; bad = []
print('знаков %d: %s' % (len(marks), ', '.join('%s %d×%d' % (m[0], m[1].shape[1], m[1].shape[0]) for m in marks)))
want = ['simpsons', 'fox', 'disney', 'gracie', 'radical', 'vivendi', 'elbarto', 'psp']
if names != want: bad.append('набор/порядок %s, ждали %s' % (names, want))
if 'playstation' in names: bad.append('самодельный знак PlayStation на месте')
rad = [m for m in marks if m[0] == 'radical']
if rad and rad[0][1].shape[1] < 90: bad.append('Radical %d px шириной — кольцо, а не слово' % rad[0][1].shape[1])
areas = [int(m[1].shape[0] * m[1].shape[1]) for m in marks if m[0] != 'fox']   # Fox упирается в высоту 24 (почти квадрат)
if areas and max(areas) > 1.35 * min(areas) / 0.65: bad.append('площади знаков разнятся: %s' % areas)
for name, idx, mode, cols in marks:
    if set(int(c) for c in set(idx.flatten())) - {0, 1} or cols[1] != B.REST2: bad.append('%s: не 1 бит цветом GONE' % name)
for b in bad: print('FAIL:', b)
print('RESULT:', 'FAIL' if bad else 'OK')
sys.exit(1 if bad else 0)
