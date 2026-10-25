#!/usr/bin/env python3
# №944 гейт «перепись путей»: все места, где игра рисует блик/светяшку сложением (additive blend, fxSprite), обязаны быть в tests/glint944/census.tsv
# с путём SHAPE941 (общий шейп №941), SHAPE944 (переведено в №944, под флагом GLINT944_OLD) или EXCLUDED (не блик взаимодействия, с причиной).
#  1. каждый якорь из census.tsv существует в своём файле (перепись привязана к коду, а не к памяти);
#  2. SHAPE944-файл содержит GLINT944_OLD (прежнее поведение под флагом);
#  3. любой файл viewer/*.c|h с аддитивным рисованием обязан быть в переписи — новый, не названный в переписи, место роняет гейт (FAIL).
# usage: census.py [ROOT] [--without ФАЙЛ]   — красный контроль: --without viewer/msnart.c убирает файл из переписи, гейт обязан упасть
import sys, re, os, glob
root = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
without = sys.argv[sys.argv.index('--without') + 1] if '--without' in sys.argv else None
rows = []; counts = {}
for ln in open(os.path.join(root, 'tests/glint944/census.tsv'), encoding='utf-8'):
    if ln.startswith('#COUNT\t'): _, cf, cn = ln.rstrip('\n').split('\t'); counts[cf] = int(cn); continue
    if ln.startswith('#') or not ln.strip(): continue
    p = ln.rstrip('\n').split('\t'); rows.append(p)
bad = 0
def fail(m):
    global bad; print('  FAIL', m); bad += 1
files = {}
for f, anchor, route, what, where in rows:
    if f == without: continue
    path = os.path.join(root, f)
    if not os.path.exists(path): fail(f'{f}: файла нет'); continue
    txt = open(path, encoding='utf-8', errors='replace').read()
    if not re.search(anchor, txt): fail(f'{f}: якорь «{anchor}» не найден — перепись устарела')
    if route == 'SHAPE944' and 'GLINT944_OLD' not in txt: fail(f'{f}: путь SHAPE944 без флага GLINT944_OLD')
    files.setdefault(f, set()).add(route)
# аддитивные места в коде
sig = re.compile(r'GU_SRC_ALPHA,GU_FIX,0,0xffffffff|GU_FIX,GU_FIX,0xffffffff,0xffffffff|GU_FIX,GU_FIX,col,0xffffffff|\bfxSprite\(')
found = {}
for path in sorted(glob.glob(os.path.join(root, 'viewer', '*.[ch]'))):
    rel = os.path.relpath(path, root)
    for i, ln in enumerate(open(path, encoding='utf-8', errors='replace'), 1):
        code = ln.split('//')[0].replace(' ', '').replace('\t', '')
        if sig.search(code): found.setdefault(rel, []).append(i)
for rel, lines in found.items():
    if rel in files:
        print(f'{rel}: {len(lines)} мест, в переписи ({"/".join(sorted(files[rel]))})')
        if counts.get(rel, len(lines)) != len(lines): fail(f'{rel}: мест {len(lines)}, в переписи {counts[rel]} — новое место рисования, назвать его в census.tsv и обновить #COUNT')
    else: fail(f'{rel}: аддитивное рисование (строки {lines[:6]}) не названо в переписи — отнести к SHAPE941/SHAPE944 или EXCLUDED с причиной')
n944 = sum(1 for r in rows if r[2] == 'SHAPE944' and r[0] != without)
print(f'строк переписи {len(rows)}, переведено в №944: {n944}, файлов с аддитивным рисованием {len(found)}')
print('PASS glint944 census' if not bad else 'FAIL glint944 census'); sys.exit(1 if bad else 0)
