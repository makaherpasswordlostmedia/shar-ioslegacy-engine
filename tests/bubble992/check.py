#!/usr/bin/env python3
"""№992 гейт: появление пузыря сообщения — короче, текст и аватар вместе с рамкой (тот же масштаб, та же прозрачность, без отставания).
Читает строки UIBUB942 из smoke.txt (uiTrace POP; сценарий pop_scenario.txt, часы HUD стоят).
  check.py pop DIR    4 появления (короткий, 3 строки, с аватаром, длинный с аватаром): код выхода 0 — PASS"""
import re, sys
from pathlib import Path

ROW = re.compile(r'UIBUB942 age=(\S+) part=(\w) x0=(\S+) y0=(\S+) x1=(\S+) y1=(\S+) a=(\S+) wrapw=(-?\d+) nl=(-?\d+)')

def rows(d):
    out = []
    for m in ROW.finditer((Path(d) / 'smoke.txt').read_text()):
        g = m.groups(); out.append(dict(age=float(g[0]), part=g[1], x0=float(g[2]), y0=float(g[3]), x1=float(g[4]), y1=float(g[5]), a=float(g[6]), w=int(g[7]), nl=int(g[8])))
    return out

def sequences(rs):
    seqs, cur, last = [], [], None
    for r in rs:
        if last is not None and r['age'] < last - 0.3: seqs.append(cur); cur = []
        cur.append(r); last = r['age']
    if cur: seqs.append(cur)
    return [s for s in seqs if any(r['part'] == 't' for r in s)]

def byage(part_rows):
    d = {}
    for r in part_rows: d[round(r['age'], 3)] = r      # последний кадр на возраст
    return d

def pop(d):
    seqs = sequences(rows(d)); bad = []; info = []
    if len(seqs) < 4: return f'FAIL: найдено {len(seqs)} появлений из 4'
    for k, s in enumerate(seqs[:4]):
        fr = byage([r for r in s if r['part'] == 'f']); tx = byage([r for r in s if r['part'] == 't']); av = byage([r for r in s if r['part'] == 'a'])
        if not fr or not tx: bad.append(f'#{k}: нет рамки или текста в трассе'); continue
        f0 = min(fr); t0 = min(tx); fw = {a: r['x1'] - r['x0'] for a, r in fr.items()}; tw = {a: r['x1'] - r['x0'] for a, r in tx.items()}
        fwF = fw[max(fw)]; twF = tw[max(tw)]
        # 1: текст виден с того же кадра, что и рамка (отставание 0)
        lag = t0 - f0
        if lag > 0.011: bad.append(f'#{k}: текст появился на {lag:.2f} с позже рамки')
        # 2: появление короче 0,08 с, старт спокойный (не меньше 0,8 от конечной ширины)
        done = min((a for a in sorted(fw) if fw[a] >= 0.995 * fwF), default=9)
        if done > 0.08: bad.append(f'#{k}: рамка раскрывается {done:.2f} с (нужно не дольше 0,08)')
        if fw[f0] < 0.8 * fwF: bad.append(f'#{k}: рамка стартует с {fw[f0] / fwF:.2f} от конечной (нужно от 0,8)')
        # 3: текст растёт тем же масштабом, что рамка, и той же прозрачностью
        for a in sorted(set(fw) & set(tw)):
            if a > 0.1: break
            if abs(tw[a] / twF - fw[a] / fwF) > 0.03: bad.append(f'#{k}: возраст {a:.2f}: текст {tw[a] / twF:.2f} от конечного, рамка {fw[a] / fwF:.2f} (масштаб разный)'); break
            if abs(tx[a]['a'] - fr[a]['a']) > 0.03: bad.append(f'#{k}: возраст {a:.2f}: прозрачность текста {tx[a]["a"]:.2f}, рамки {fr[a]["a"]:.2f}'); break
        # 4: колонка текста не узкая, перенос не меняется, текст внутри рамки на каждом кадре
        if tw[t0] < 0.85 * twF: bad.append(f'#{k}: первый кадр текста {tw[t0]:.0f} из {twF:.0f} px (узкая колонка)')
        if len({(r['w'], r['nl']) for r in tx.values()}) > 1: bad.append(f'#{k}: перенос строк менялся по кадрам')
        for a in sorted(set(fr) & set(tx)):
            if tx[a]['x0'] < fr[a]['x0'] - 1 or tx[a]['x1'] > fr[a]['x1'] + 1 or tx[a]['y0'] < fr[a]['y0'] - 1 or tx[a]['y1'] > fr[a]['y1'] + 1:
                bad.append(f'#{k}: возраст {a:.2f}: текст выходит за рамку'); break
        # 5: аватар — с того же кадра и тем же масштабом
        if av:
            a0 = min(av); aw = {a: r['x1'] - r['x0'] for a, r in av.items()}; awF = aw[max(aw)]
            if a0 - f0 > 0.011: bad.append(f'#{k}: аватар на {a0 - f0:.2f} с позже рамки')
            for a in sorted(set(fw) & set(aw)):
                if a > 0.1: break
                if abs(aw[a] / awF - fw[a] / fwF) > 0.03: bad.append(f'#{k}: возраст {a:.2f}: аватар {aw[a] / awF:.2f}, рамка {fw[a] / fwF:.2f}'); break
        info.append(f'#{k}: рамка {fw[f0] / fwF:.2f}→1 за {done:.2f} с, текст с возраста {t0:.2f} (отставание {lag:.2f} с), текст {tw[t0] / twF:.2f} от конечного{", аватар с " + format(min(av), ".2f") if av else ""}')
    print('  замер:', '; '.join(info))
    return 'PASS' if not bad else 'FAIL: ' + '; '.join(bad)

if __name__ == '__main__':
    r = globals()[sys.argv[1]](sys.argv[2]); print(r); sys.exit(0 if r == 'PASS' else 1)
