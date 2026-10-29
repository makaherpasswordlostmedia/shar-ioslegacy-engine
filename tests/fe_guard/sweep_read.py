#!/usr/bin/env python3
"""Правка Роба 265: читает кадры покадрового перелёта NEW GAME (flag fe265sweep 1, viewer/frontend3d.c sweepDump) и сравнивает
проход a (прежний мип, GU_TEXTURE_AUTO) с проходом b (текущий: правило — мип по глубине пикселя; или красный feold265 2).

  python3 tests/fe_guard/sweep_read.py ПАПКА [--gate] [--same] [--sheet OUT.png] [--ref ПАПКА_ЭМУЛЯТОРА]

ПАПКА — где лежат fe265_a_*.bmp, fe265_b_*.bmp и fe265_sweep.txt (в эмуляторе build/twins/scen/full/<имя>/shots, с PSP —
shots из папки тура). Для каждой позы камеры (кадр таймлайна × 100 в имени):
  метка   — 12 клеток 6×4 px у x 60, y 40 (frontend3d.c sweepMark): номер позы и проход совпадают с именем файла
  diff    — доля пикселей кадра, где a и b различаются больше чем на 24 из 255 (метка не в счёт)
  пол     — доля пикселей бирюзового пола floor3.bmp (g > r + 30, b > r + 20, g > 40: ковёр, тени мебели на нём) в a и b
  детали  — средний перепад яркости соседних блоков 4×4 на полу (тени мебели, затемнение к краям; у самого мелкого мипа их нет —
            «зелёный полигон» Роба), в a и b, по общей маске пола (блоки 4×4 гасят дизеринг 16-битного кадра)
  сдвиг   — средняя разница цвета a и b на общей маске пола, из 255 (ровный «средний» пол вместо своего места текстуры)
  резкость — средний перепад яркости блоков 4×4 по всему окну
--gate: зелёный, если все позы обоих проходов на месте, метки верны и в каждой позе, где пола ≥ 2 %:
  пол b ≥ 0,9 × пол a, детали b ≥ 0,75 × детали a, сдвиг цвета пола ≤ 6, резкость b ≥ 0,85 × резкость a, diff ≤ 0,15;
  и правило действует — a и b хоть где-то различаются (в эмуляторе SLOPE и AUTO дают разные уровни; сборка -DFE_MIP_OLD=1 —
  прежнее по умолчанию — даёт равные кадры и красный). Код возврата 0 / 1.
--same: контроль повторяемости (feold265 1 — оба прохода прежние): все пары обязаны совпасть попиксельно (кроме метки).
--ref: кадры с PSP сверяются с кадрами эмулятора тех же поз (tests/fe_guard/run.sh кладёт их в build/twins/scen/full/
  265-menu-floor_sweep_new/shots): на каждой позе сдвиг цвета пола a↔b на PSP и в эмуляторе, a и b PSP против эмулятора, детали
  пола PSP/эмулятор. «Пол другой»: a↔b на PSP больше эмуляторного на 5, или проход отстоит от эмулятора больше медианы + 6
  (медиана — общий фон железа: дизеринг, точность), или детали < 0,6 эмулятора. Ответ проверки на железе:
  в проходе a (прежний мип) такие позы в конце наезда есть, в b (правило) нет — версия 265 подтверждена и правка помогает;
  нет ни там, ни там — покадровый проход пропажу не повторил (смотреть настоящий перелёт глазами); есть в обоих — причина другая."""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image

MX, MY, CELL, NCELL = 60, 40, 6, 12          # метка (frontend3d.c sweepMark)
MASK = (slice(MY - 2, MY + 6), slice(MX - 2, MX + CELL * NCELL + 2))


def load(p):
    return np.asarray(Image.open(p).convert('RGB')).astype(np.int32)


def mark(img):
    """-> (pass, idx) или None, если метка не читается"""
    bits = [int(img[MY + 2, MX + CELL * i + 3].mean() > 128) for i in range(NCELL)]
    if bits[0] != 1 or bits[1] != 0 or bits[11] != 1: return None
    code = sum(bits[2 + k] << k for k in range(8))
    if bits[10] != (bin(code).count('1') & 1): return None
    return code >> 7, code & 127


def floor_mask(img):
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    m = (g > r + 30) & (b > r + 20) & (g > 40)
    m[MASK] = False
    return m


def lum(img):
    return img[..., 0] * .299 + img[..., 1] * .587 + img[..., 2] * .114


def grad(L):
    """перепад яркости после усреднения 4×4 (16-битный кадр PSP с дизерингом 4×4: шум матрицы гасится), на сетке исходного
    размера (каждый пиксель блока получает перепад своего блока)"""
    h, w = L.shape[0] // 4 * 4, L.shape[1] // 4 * 4
    S = L[:h, :w].reshape(h // 4, 4, w // 4, 4).mean((1, 3))
    gx = np.zeros_like(S); gy = np.zeros_like(S)
    gx[:, :-1] = np.abs(np.diff(S, axis=1)); gy[:-1] = np.abs(np.diff(S, axis=0))
    G = np.zeros_like(L); G[:h, :w] = np.kron(gx + gy, np.ones((4, 4)))
    return G


def window(img):
    """окно рамки-телевизора меню (рамка одинакова в a и b): без 24 px по краям и без метки"""
    m = np.zeros(img.shape[:2], bool); m[24:-24, 24:-24] = True; m[MASK] = False
    return m


def ref_mode(d, ref):
    """PSP против эмулятора. На каждой позе: a↔b на PSP и a↔b в эмуляторе (сдвиг цвета пола), a и b PSP против эмулятора"""
    print(f'PSP {d} против эмулятора {ref}')
    rows = []
    for pa in sorted(d.glob('fe265_a_*.bmp')):
        k = pa.stem.split('_')[2]; pb = d / f'fe265_b_{k}.bmp'; ea, eb = ref / pa.name, ref / f'fe265_b_{k}.bmp'
        if not (pb.exists() and ea.exists() and eb.exists()): continue
        ha, hb, xa, xb = load(pa), load(pb), load(ea), load(eb); w = window(xa)
        m = floor_mask(xa) & floor_mask(xb) & w
        if m.sum() < 500: continue
        sh = lambda p, q: float(np.abs(p - q)[m].mean())
        G = lambda im: float(grad(lum(im))[m].mean())
        ma, mb = mark(ha), mark(hb)
        rows.append(dict(tl=int(k) / 100, hab=sh(ha, hb), eab=sh(xa, xb), ae=sh(ha, xa), be=sh(hb, xb),
                         da=G(ha) / max(G(xa), 1e-6), db=G(hb) / max(G(xb), 1e-6), mok=ma == (0, ma[1] if ma else -1) and mb is not None and mb[0] == 1))
    if not rows: print('нет пар кадров (fe265_a/b_* на PSP и в эмуляторе)'); return 1
    med_a = float(np.median([r['ae'] for r in rows])); med_b = float(np.median([r['be'] for r in rows]))
    print(f'поз {len(rows)}; пол PSP против эмулятора: медиана сдвига a {med_a:.1f}, b {med_b:.1f} (общий фон железа); метки PSP не прочитаны: '
          f'{sum(not r["mok"] for r in rows)}')
    print(' кадр  a↔b PSP  a↔b эмул  a-эмул  b-эмул  детали a  детали b')
    flag = []
    for r in rows:
        odd = r['hab'] > r['eab'] + 5 or r['ae'] > med_a + 6 or r['da'] < .6
        if odd: flag.append(r)
        print(f'{r["tl"]:5.2f}  {r["hab"]:7.1f}  {r["eab"]:8.1f}  {r["ae"]:6.1f}  {r["be"]:6.1f}  {r["da"]:7.2f}  {r["db"]:7.2f}'
              + ('  ← пол другой' if odd else ''))
    a_bad = [r['tl'] for r in flag if r['ae'] > med_a + 6 or r['da'] < .6]
    b_bad = [r['tl'] for r in rows if r['be'] > med_b + 6 or r['db'] < .6]
    ab = [r['tl'] for r in flag if r['hab'] > r['eab'] + 5]
    if a_bad and not b_bad: v = 'версия 265 подтверждена: на PSP пол другой только с прежним мипом (a), с правилом (b) — как в эмуляторе'
    elif not a_bad and not b_bad and not ab: v = 'покадровый проход пропажу не повторил ни в a, ни в b: смотреть настоящий перелёт глазами'
    elif b_bad: v = 'с правилом (b) пол на PSP тоже отличается от эмулятора — причина не только в выборе мипа'
    else: v = 'выбор мипа на PSP меняет пол сильнее, чем в эмуляторе, но ни один проход не выпадает из общего фона — смотреть кадры'
    print('ВЫВОД:', v, f'| a выпадает: {a_bad[:12]} | b выпадает: {b_bad[:12]} | a↔b сильнее эмулятора: {ab[:12]}')
    return 0


def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return 2
    d = Path(a[0]); gate = '--gate' in a; same = '--same' in a
    sheet = a[a.index('--sheet') + 1] if '--sheet' in a else None
    if '--ref' in a: return ref_mode(d, Path(a[a.index('--ref') + 1]))
    log = {}
    if (d / 'fe265_sweep.txt').exists():
        for ln in (d / 'fe265_sweep.txt').read_text().splitlines():
            m = re.match(r'SWEEP (\S+) pass=(\d) idx=(\d+) tl=([\d.]+) mode=(\d) ok=(\d) fmt=(\d+) ms=(\d+)', ln)
            if m: log[m.group(1)] = dict(pas=int(m.group(2)), idx=int(m.group(3)), tl=float(m.group(4)), mode=int(m.group(5)), ms=int(m.group(8)))
    A = {int(p.stem.split('_')[2]): p for p in d.glob('fe265_a_*.bmp')}
    B = {int(p.stem.split('_')[2]): p for p in d.glob('fe265_b_*.bmp')}
    keys = sorted(set(A) | set(B))
    modes = sorted({v['mode'] for k, v in log.items() if v['pas'] == 1})
    print(f'папка {d}: поз a {len(A)}, b {len(B)}, строк журнала {len(log)}; режим прохода b: {modes} '
          f'(0 правило, 1 прежнее, 2 самый мелкий мип); запись кадра {np.mean([v["ms"] for v in log.values()]) if log else 0:.0f} мс')
    bad = []; rows = []; shots = []
    if not keys:
        print('ИТОГ: КРАСНЫЙ нет кадров fe265_* — движок без покадрового перелёта 265 (flag fe265sweep) или перелёт не начался'); return 1
    print(' кадр   diff   пол a  пол b  детали a детали b  сдвиг  резк a резк b  метки')
    for k in keys:
        if k not in A or k not in B: bad.append(f'{k / 100:.2f}: нет пары'); continue
        ia, ib = load(A[k]), load(B[k])
        ma, mb = mark(ia), mark(ib)
        la, lb = log.get(A[k].stem), log.get(B[k].stem)
        mok = ma is not None and mb is not None and ma[0] == 0 and mb[0] == 1 and (la is None or ma[1] == la['idx']) and (lb is None or mb[1] == lb['idx'])
        if not mok: bad.append(f'{k / 100:.2f}: метка {ma} {mb}')
        w = window(ia); mk = np.zeros(w.shape, bool); mk[MASK] = True   # метка у проходов разная (бит прохода)
        dif = (np.abs(ia - ib).max(2) > 24) & w
        fa, fb = floor_mask(ia) & w, floor_mask(ib) & w
        both = fa & fb
        La, Lb = lum(ia), lum(ib); Ga, Gb = grad(La), grad(Lb)
        da = float(Ga[both].mean()) if both.sum() > 200 else float('nan'); db = float(Gb[both].mean()) if both.sum() > 200 else float('nan')
        sa, sb = float(Ga[w].mean()), float(Gb[w].mean())
        sh = float(np.abs(ia - ib)[both].mean()) if both.sum() > 200 else 0.
        r = dict(k=k, diff=float(dif.sum() / w.sum()), fa=float(fa.sum() / w.sum()), fb=float(fb.sum() / w.sum()), da=da, db=db, sa=sa, sb=sb,
                 sh=sh, eq=bool((ia == ib).all(2)[~mk].all()), mok=mok)
        rows.append(r)
        print(f'{k / 100:5.2f} {r["diff"]:6.3f}  {r["fa"]:5.2f}  {r["fb"]:5.2f}  {da:7.2f}  {db:7.2f}  {r["sh"]:5.1f}  {sa:6.2f} {sb:6.2f}  {"ok" if mok else "НЕТ"}')
        if sheet and k in (100, 2000, 3000, 3500, 3700, 3800, 3900, 3950, 4000):
            m = np.zeros_like(ia); m[dif] = [255, 0, 255]
            shots.append(np.concatenate([ia, ib, m], 1))
    if sheet and shots:
        Image.fromarray(np.concatenate(shots, 0).astype(np.uint8)).save(sheet); print('лист:', sheet, '(a | b | отличия > 24)')
    n_exp = len(log) // 2 if log else len(keys)
    if len(rows) != n_exp or len(rows) < 40: bad.append(f'поз с парой {len(rows)} из {n_exp}')
    if same:
        neq = [r['k'] / 100 for r in rows if not r['eq']]
        print(f'повторяемость: попиксельно равны {len(rows) - len(neq)} из {len(rows)}' + (f'; разные: {neq[:12]}' if neq else ''))
        ok = not neq and not bad
        print('ИТОГ:', 'зелёный' if ok else 'КРАСНЫЙ', '; '.join(bad)); return 0 if ok else 1
    if gate:
        fails = []
        for r in rows:
            if r['fa'] < .02: continue
            why = []
            if r['fb'] < .9 * r['fa']: why.append(f'пол {r["fb"]:.2f} < 0,9×{r["fa"]:.2f}')
            if not (r['db'] >= .75 * r['da']): why.append(f'детали пола {r["db"]:.2f} < 0,75×{r["da"]:.2f}')
            if r['sh'] > 6: why.append(f'сдвиг цвета пола {r["sh"]:.1f} > 6')
            if r['sb'] < .85 * r['sa']: why.append(f'резкость {r["sb"]:.2f} < 0,85×{r["sa"]:.2f}')
            if r['diff'] > .15: why.append(f'diff {r["diff"]:.3f} > 0,15')
            if why: fails.append(f'{r["k"] / 100:.2f}: ' + ', '.join(why))
        dd = [r['diff'] for r in rows]
        print(f'сводка: поз {len(rows)}, diff средн {np.mean(dd):.4f} макс {np.max(dd):.4f}; детали пола b/a мин '
              f'{np.nanmin([r["db"] / r["da"] for r in rows if r["fa"] >= .02]):.2f}; резкость b/a мин {min(r["sb"] / r["sa"] for r in rows):.2f}; сдвиг цвета пола макс {max(r["sh"] for r in rows):.1f}')
        if rows and all(r['eq'] for r in rows):   # по значению: в эмуляторе SLOPE и AUTO дают разные уровни — кадры обязаны где-то различаться
            bad.append(f'правило не действует: проходы a и b попиксельно равны во всех {len(rows)} позах (режим b {modes})')
        ok = not fails and not bad
        print('ИТОГ:', 'зелёный' if ok else 'КРАСНЫЙ', ('; '.join(bad + fails[:8]) + (f' … ещё {len(fails) - 8}' if len(fails) > 8 else '')) if not ok else '')
        return 0 if ok else 1
    if bad: print('замечания:', '; '.join(bad))
    return 0


if __name__ == '__main__':
    sys.exit(main())
