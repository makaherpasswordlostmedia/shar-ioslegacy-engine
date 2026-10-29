#!/usr/bin/env python3
"""№574 срез 2b-2: масштаб отдельной надписи (elements[экран|text|имя].k) доходит до ui.shr.
  Экспорт с настройками Роба и с k=1.5 у hud|text|Laps: ровно одна запись меняет грань на «*» и строку (lh) растёт; остальные записи те же.
  КРАСНЫЙ: --red (UI_TYPO_ELTEXT_OLD=1) — изменений нет, гейт обязан упасть.
python3 tests/ui/typo_eltext.py [--red] -> 0 = PASS"""
import json, os, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from typo_bridge import parse, ROOT, PY


def export(tmp, name, typo, red):
    out = tmp / name; env = dict(os.environ, UI_SCRATCH=str(tmp / 'scratch'), UI_TYPO=str(typo))
    if red: env['UI_TYPO_ELTEXT_OLD'] = '1'
    r = subprocess.run([PY, 'tools/ui_export.py', '--out', str(out)], cwd=ROOT, env=env, capture_output=True, text=True)
    if r.returncode: print(r.stdout[-800:], r.stderr[-1500:]); raise SystemExit('экспорт упал')
    return out


def main(red):
    tmp = Path(tempfile.mkdtemp(prefix='typo_eltext_'))
    base = json.load(open(ROOT / 'build/ui_typo.json'))
    (tmp / 'a.json').write_text(json.dumps(base))
    KEY = os.environ.get('ELKEY', 'hud|text|Laps'); KK = float(os.environ.get('ELK', '1.5')); base['elements'][KEY] = dict(base['elements'].get(KEY, {}), k=KK)
    (tmp / 'b.json').write_text(json.dumps(base))
    P0 = parse(export(tmp, 'a.shr', tmp / 'a.json', red)); P1 = parse(export(tmp, 'b.shr', tmp / 'b.json', red))
    assert len(P0['items']) == len(P1['items']), 'число записей разное'
    ch = []
    key = lambda P, it: (it[0], P['fonts'][it[16]]['name'] if it[0] == 3 else None, P['fonts'][it[16]]['lh'] if it[0] == 3 else None) + tuple(it[9:13])
    for i, (a, b) in enumerate(zip(P0['items'], P1['items'])):
        if key(P0, a) != key(P1, b):
            ch.append((i, a[0], P0['fonts'][a[16]] if a[0] == 3 else None, P1['fonts'][b[16]] if b[0] == 3 else None, a[9:13], b[9:13]))
    for c in ch: print(c)
    bad = []
    if len(ch) != 1: bad.append('изменилось записей: %d (ждали 1)' % len(ch))
    elif '|rect|' in KEY:
        if ch[0][1] != 0: bad.append('изменилась не плоская плашка')
    elif not (ch[0][3] and '*' in ch[0][3]['name'] and ch[0][3]['lh'] > ch[0][2]['lh']): bad.append('грань/строка не выросли')
    if bad: print('FAIL:', bad); return 1
    if '|rect|' in KEY: print('PASS: плашка', KEY, 'x', KK, ch[0][4], '->', ch[0][5]); return 0
    print('PASS: масштаб надписи hud|text|Laps x1,5 доходит до пакета (%s -> %s, строка %d -> %d px)' % (ch[0][2]['name'], ch[0][3]['name'], ch[0][2]['lh'], ch[0][3]['lh'])); return 0


if __name__ == '__main__':
    sys.exit(main('--red' in sys.argv))
