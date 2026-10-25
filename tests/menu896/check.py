#!/usr/bin/env python3
"""№896 (+893/894/895): проверка прогона бота меню tests/menu896/gen.py. check.py RUN_DIR [--expect-fail]
  1. газета всегда: каждый выбор миссии MISSION SELECT на том же уровне — крутится экран загрузки (LOADSPIN), каждая смена уровня — LEVELUP и LOADSPIN (№893);
  2. каждое открытие MISSION SELECT — экран пакета (MSNSEL open rows=1), без отказов открытия (MSNSEL openfail), число открытых уровней одно и то же (листание есть) (№894);
  3. рамка MISSION SELECT на снимках a*_ms — одна и та же у всех открытий (жёлтая кромка, ±2 px): не «чужая рамка» запасного списка (№894);
  4. пузыри сообщений после всех переходов (s1_*, a*_* после смены уровня) совпадают с пузырями на старте (s0_*): рамка x0..x1, высота, аватар (±1 px), буквы только на
     прямой части, правый край ≤ 341 (№895, закон пузырей v1: tests/ui/bubble_v1_check.py);
  5. игра дошла до конца сценария (строка END).
Код 0 — PASS; --expect-fail: 0, только если упало (красные: сборка -DMS_NEWS_OLD=1 / -DMS_OPEN_OLD=1 + gen.py --fail N)."""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import bubble_v1_check as B
BN = ('b_dest', 'c_m2', 'd_m3', 'e_m5', 'f_m6', 'g_long')


def border(p):   # жёлтая кромка рамки MISSION SELECT: bbox маски цвета золота
    a = np.asarray(Image.open(p).convert('RGB')).astype(int)[24:272]
    m = (a[..., 0] > 170) & (a[..., 1] > 120) & (a[..., 2] < 120)
    cols = np.nonzero(m.sum(0) > 100)[0]; rows = np.nonzero(m[:, 40:441].sum(1) > 330)[0]
    return None if len(cols) < 2 or len(rows) < 2 else (int(cols.min()), int(cols.max()), int(rows.min()), int(rows.max()))


def main():
    run = Path(sys.argv[1]); errs = []
    lines = (run / 'smoke.txt').read_text(errors='replace').splitlines()
    ev = [l for l in lines if re.match(r'(MSNSEL open |MSNSEL openfail|MSN select|MSNEWS|LEVELUP|LOADSPIN|END$)', l)]
    # 1: газета на каждый выбор
    sel = []   # (индекс события, тип)
    for i, l in enumerate(ev):
        if l.startswith('MSN select') and ' level=' not in l: sel.append(i)
    nonews = 0
    for k, i in enumerate(sel):
        nxt = sel[k + 1] if k + 1 < len(sel) else len(ev)
        seg = ev[i:nxt]
        if not any(s.startswith('LOADSPIN') for s in seg): nonews += 1   # газета = крутящийся экран загрузки (LOADSPIN)
    if nonews: errs.append(f'{nonews} из {len(sel)} выборов миссии на уровне без газеты (№893)')
    ups = [i for i, l in enumerate(ev) if l.startswith('LEVELUP')]
    for i in ups:
        if not (i + 1 < len(ev) and ev[i + 1].startswith('LOADSPIN')): errs.append('смена уровня без газеты: ' + ev[i])
    # 2: экран пакета
    opens = [l for l in ev if l.startswith('MSNSEL open ')]
    rows0 = [l for l in opens if 'rows=0' in l]
    fails = [l for l in ev if l.startswith('MSNSEL openfail')]
    lv = {re.search(r'levels=(\d+)', l).group(1) for l in opens}
    if not opens: errs.append('Mission Select ни разу не открыт')
    if rows0: errs.append(f'{len(rows0)} открытий в запасном списке (rows=0): чужая рамка, нет листания (№894)')
    if fails: errs.append(f'{len(fails)} отказов открытия пакета')
    if len(lv) > 1: errs.append(f'число уровней в списке гуляет {sorted(lv)}')
    # 3: рамка
    bs = {p.name: border(p) for p in sorted(run.glob('a*_ms.png'))}
    ok_b = [b for b in bs.values() if b]
    if len(ok_b) != len(bs): errs.append('рамка MISSION SELECT не найдена на снимках: ' + ','.join(n for n, b in bs.items() if not b))
    if ok_b:
        for j in range(4):
            if max(b[j] for b in ok_b) - min(b[j] for b in ok_b) > 2: errs.append('рамка MISSION SELECT гуляет: ' + str(sorted(set(ok_b))))
    # 4: пузыри
    base = {n: B.frame(str(run / f's0_{n}.png')) for n in BN if (run / f's0_{n}.png').exists()}
    if len(base) < len(BN): errs.append('нет базовых пузырей s0_*')
    sets = sorted({p.name.split('_')[0] for p in run.glob('*_b_dest.png')} - {'s0'})
    for tag in sets:
        for n in BN:
            p = run / f'{tag}_{n}.png'
            if not p.exists(): errs.append(f'нет кадра {p.name}'); continue
            f = B.frame(str(p)); b = base.get(n)
            if f is None: errs.append(f'{p.name}: рамка/текст не найдены'); continue
            if b and (abs(f['x1'] - b['x1']) > 1 or abs(f['H'] - b['H']) > 1): errs.append(f'{p.name}: рамка ..{f["x1"]} h{f["H"]} вместо ..{b["x1"]} h{b["H"]}')
            if b and not f['av'] and not b['av'] and (abs(f['x0'] - b['x0']) > 1 or abs(f['tl'] - b['tl']) > 1 or abs(f['tr'] - b['tr']) > 1):
                errs.append(f'{p.name}: рамка {f["x0"]}..{f["x1"]}, буквы x{f["tl"]}..{f["tr"]} вместо {b["x0"]}..{b["x1"]}, x{b["tl"]}..{b["tr"]} (выравнивание текста)')
            if f['av'] and f['tl'] < f['x0'] + 2: errs.append(f'{p.name}: текст с аватаром начинается раньше рамки (буквы x{f["tl"]}, рамка x{f["x0"]})')
            if not (f['av'] or f['tl'] >= f['x0'] + f['R'] - 1) or f['tr'] > f['x1'] - f['R'] + 1: errs.append(f'{p.name}: буквы в скруглении')
            if f['x1'] > 341: errs.append(f'{p.name}: правый край {f["x1"]} > 341')
    # 5: конец
    if not any(l == 'END' for l in lines): errs.append('нет END: сценарий не дошёл до конца')
    print(f'  выборов миссий {len(sel)}, смен уровня {len(ups)}, открытий Mission Select {len(opens)}, снимков рамки {len(bs)}, наборов пузырей {1 + len(sets)}')
    ok = not errs
    for e in errs[:12]: print('  FAIL', e)
    print(('PASS' if ok else f'FAIL ({len(errs)})') + f' · tests/menu896/check.py {run.name}')
    return (0 if not ok else 1) if '--expect-fail' in sys.argv else (0 if ok else 1)


if __name__ == '__main__':
    sys.exit(main())
