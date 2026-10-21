"""№697: после взрыва остаётся чёрный остов, огонь гаснет. Кадры husk_burn_{green,red}_{a..e} из tests/recheck28/husk_burn_*.txt
(red = flag burnold 1, горит постоянно). Считает оранжевые пиксели огня в кадрах d,e (17 и 24 с): зелёный ≤ 10, красный обязан быть > 30.
python3 -I tests/recheck28/husk_burn_gate.py DIR_GREEN DIR_RED -> 0 = PASS"""
import sys
from PIL import Image
def fire(p):
    im = Image.open(p).convert('RGB'); w, h = im.size
    return sum(1 for x in range(0, w, 2) for y in range(40, h, 2)
               if (lambda c: c[0] > 230 and 110 < c[1] < 200 and c[2] < 70)(im.getpixel((x, y))))
g = [fire(f'{sys.argv[1]}/green_{c}.png') for c in 'de']; r = [fire(f'{sys.argv[2]}/red_{c}.png') for c in 'de']
print('зелёный d,e', g, 'красный d,e', r)
ok = max(g) <= 10 and min(r) > 30
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
