#!/usr/bin/env python3
"""Гейт №930 (ступень 2: цвет и порядок треугольников в вершинах на месте, без копий): в мультике куски машин трафика с ровной областью текстуры рисуются без текстуры, рисунок (фары, решётки, номер) остаётся текстурой хвоста куска;
оригинал возвращается из файла.   carfill930_check.py ПАПКА_ПРОГОНА   (PASS / FAIL последней строкой)
Окна по строкам CARFILL (сцены сценария): G_ON — заливка включена: draws растёт, цвет вершин отличается от файла (vh другой, changed > 0), заливка и текстурный хвост есть (flat_tri, tex_tri растут);
G_PL — рисуется машина игрока (carfillplayer 1): draws не растёт, оригинал для неё прочитан из файла (orig_b > 0); G_TEX — Textures On (flat912 0): draws не растёт, вершины возвращены из файла (vh равен исходному, restores > 0);
G_OFF — carfill930 0: draws не растёт. Снимки до/после у машины трафика плывут (кузов на подвеске), поэтому гейт по счётчикам и хэшу вершин."""
import sys, re
d = sys.argv[1]; txt = open(f'{d}/smoke.txt', errors='replace').read().splitlines()
sc = {}; cf = []
for ln in txt:
    m = re.match(r'SCENE (\S+) ([\d.]+)', ln)
    if m: sc[m.group(1)] = float(m.group(2))
    m = re.match(r'CARFILL t=([\d.]+) pieces=(\d+) mis=(\d+) on=(\d) player=(\d) draws=(\d+) bakes=(\d+) verts=(\d+) changed=(\d+) restores=(\d+) orig_b=(\d+) vh=([0-9a-f]+)(?: flat_tri=(\d+) tex_tri=(\d+))?', ln)
    if m: cf.append(dict(t=float(m.group(1)), pieces=int(m.group(2)), draws=int(m.group(6)), bakes=int(m.group(7)), verts=int(m.group(8)), changed=int(m.group(9)), restores=int(m.group(10)), orig=int(m.group(11)), vh=m.group(12), ft=int(m.group(13) or 0), xt=int(m.group(14) or 0)))
bad = 0
if not cf: print('FAIL нет строк CARFILL (трафик не рисовался или нет EBOOT с №930)'); print('FAIL'); sys.exit(2)
v0 = next((c['vh'] for c in cf if c['t'] < sc.get('G_ON', 1e9)), cf[0]['vh'])
print('кусков с заливкой в наборе трафика:', max(c['pieces'] for c in cf), ' хэш вершин в файле:', v0)
if max(c['pieces'] for c in cf) <= 0: print('набор кусков пуст (нет carflat930.bin или подпись не сошлась или CARFILL930_OLD) ОШИБКА'); bad += 1
order = ['G_ON', 'G_PL', 'G_TEX', 'G_OFF']
def win(k):
    a = sc.get(k); i = order.index(k); b = sc.get(order[i + 1]) if i + 1 < len(order) else (a or 0) + 6
    return [c for c in cf if a is not None and b is not None and a + 0.5 <= c["t"] < b]
def check(name, ok, info):
    global bad; print(f'{name}: {info} ' + ('ok' if ok else 'ОШИБКА')); bad += 0 if ok else 1
w = win('G_ON'); check('G_ON', len(w) >= 2 and w[-1]['draws'] > w[0]['draws'] and w[-1]['vh'] != v0 and w[-1]['changed'] > 0 and w[-1]['ft'] > w[0]['ft'] and w[-1]['xt'] > w[0]['xt'],
    f"draws {w[0]['draws']}→{w[-1]['draws']}, vh {w[-1]['vh']}, перекрашено {w[-1]['changed']} из {w[-1]['verts']}, треугольников заливкой {w[-1]['ft'] - w[0]['ft']}, текстурой хвоста {w[-1]['xt'] - w[0]['xt']}" if len(w) >= 2 else 'нет строк')
w = win('G_PL'); check('G_PL', len(w) >= 2 and w[-1]['draws'] == w[0]['draws'] and w[-1]['orig'] > 0, f"draws {w[0]['draws']}→{w[-1]['draws']}, оригинал из файла {w[-1]['orig']} Б" if len(w) >= 2 else 'нет строк')
w = win('G_TEX'); check('G_TEX', len(w) >= 2 and w[-1]['draws'] == w[0]['draws'] and w[-1]['vh'] == v0 and w[-1]['restores'] > 0, f"draws {w[0]['draws']}→{w[-1]['draws']}, vh {w[-1]['vh']} (файл {v0}), возвратов {w[-1]['restores']}" if len(w) >= 2 else 'нет строк')
w = win('G_OFF'); check('G_OFF', len(w) >= 2 and w[-1]['draws'] == w[0]['draws'], f"draws {w[0]['draws']}→{w[-1]['draws']}" if len(w) >= 2 else 'нет строк')
print('PASS' if not bad else 'FAIL'); sys.exit(0 if not bad else 1)
