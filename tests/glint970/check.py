#!/usr/bin/env python3
# №970: гейты бликов по числам. Сборки с одним и тем же кадром (эмулятор повторяет числа): none — все блики №970 погашены (-D… ноль), old — как TEST66 (flag glint970old 1), new — новое.
# Блик = разница снимка с none (сумма каналов > 12; строка HUD y < 60 не считается). Масса = сумма разницы по пикселям блика.
#   check.py host NEW.txt OLD.txt              числа хода слоёв ключа (host.c): сдвиг ближе к центру, нет шва и рывков, пульс не повторяется
#   check.py wrench NONE OLD NEW               ключ: блик меньше (площадь), прозрачнее (масса), слои на месте; серия p00..p15 живая
#   check.py phone  NONE OLD NEW               будка: блик слабее (масса ≈ 0,5), размер тот же
#   check.py coin   NONE OLD NEW               монета: несколько маленьких вокруг (≥ 3 пятен), каждое мельче прежнего, центр масс в центре монеты (№965), сдвиг к глазу цел
#   check.py lights NONE OLD NEW               огни машины: блик шире в 1,15..1,5 раза
#   check.py same A B NAME...                  снимки одинаковы пиксель в пиксель (соседние блики не тронуты); --coins — рядом с монетами можно
# последняя строка PASS / FAIL
import sys, os, re
from PIL import Image
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'coin965'))
def load(d, n): return np.asarray(Image.open(os.path.join(d, n + '.png')).convert('RGB')).astype(int)
def gl(none, img):
    g = np.abs(img - none).sum(axis=2); g[:60, :] = 0; return g
def blobs(m, minpx=6):   # связные пятна маски (4 соседа, без scipy), список (число пикселей, x0, x1, y0, y1)
    seen = np.zeros_like(m); out = []; H, W = m.shape
    for y0, x0 in zip(*np.nonzero(m)):
        if seen[y0, x0]: continue
        st = [(y0, x0)]; seen[y0, x0] = True; n = 0; xs = [x0, x0]; ys = [y0, y0]
        while st:
            y, x = st.pop(); n += 1; xs = [min(xs[0], x), max(xs[1], x)]; ys = [min(ys[0], y), max(ys[1], y)]
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                Y, X = y + dy, x + dx
                if 0 <= Y < H and 0 <= X < W and m[Y, X] and not seen[Y, X]: seen[Y, X] = True; st.append((Y, X))
        if n >= minpx: out.append((n, xs[0], xs[1], ys[0], ys[1]))
    return out
def dil(m, r):   # расширение маски на r пикселей (лучи одной звезды сливаются в одно пятно)
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy * dy + dx * dx <= r * r: out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out
def med(a): a = sorted(a); return a[len(a) // 2]
def host(nf, of):
    def rd(f):
        r = {}; w = []
        for l in open(f):
            m = re.match(r'HOST w=\d+ model=\S+ maxr=([\d.]+) seam=([\d.]+) vmax_x=([\d.]+) vmax_y=([\d.]+) amax_x=([\d.]+) amax_y=([\d.]+)', l)
            if m: w.append([float(x) for x in m.groups()])
            m = re.match(r'HOST rhythm model=\S+ rmax=([\d.]+) near_half=([\d.]+) autocorr_1to10s=([\d.]+)', l)
            if m: r['rhythm'] = [float(x) for x in m.groups()]
        r['w'] = w; return r
    n, o = rd(nf), rd(of); bad = 0
    if not n['w'] or not o['w'] or 'rhythm' not in n or 'rhythm' not in o: print('нет строк HOST'); return 1
    mx = lambda r, i: max(x[i] for x in r['w'])
    print('наибольший сдвиг второй звезды (доля размера): new %.4f old %.4f' % (mx(n, 0), mx(o, 0)))
    print('шов при переходе часов 60 с: new %.5f old %.5f' % (mx(n, 1), mx(o, 1)))
    print('ускорение сдвига (рывок): new %.2f old %.2f' % (max(mx(n, 4), mx(n, 5)), max(mx(o, 4), mx(o, 5))))
    print('доля времени сдвиг ≤ половины наибольшего: new %.2f old %.2f; повтор пульса на лагах 1…10 с: new %.2f old %.2f' % (n['rhythm'][1], o['rhythm'][1], n['rhythm'][2], o['rhythm'][2]))
    if mx(n, 0) > .6 * mx(o, 0): print('BAD: сдвиг не ближе к центру (new ≤ 0,6 old)'); bad += 1
    if mx(n, 1) > .01: print('BAD: шов при переходе часов > 0,01'); bad += 1
    if max(mx(n, 4), mx(n, 5)) > 5.: print('BAD: рывки (ускорение > 5)'); bad += 1
    if n['rhythm'][1] < .3: print('BAD: звёзды не сходятся к центру (доля ≤ половины радиуса < 0,3)'); bad += 1
    if n['rhythm'][2] > .85: print('BAD: пульс повторяется (корреляция на лагах 1…10 с > 0,85)'); bad += 1
    return bad
def wrench(nd, od, wd):
    names = ['k7'] + ['p%02d' % i for i in range(16)]; bad = 0; ro = []; rm = []; ra = []; mn = []; rp = []
    for n in names:
        try: none = load(nd, n); go = gl(none, load(od, n)); gn = gl(none, load(wd, n))
        except Exception as e: print('нет снимка', n, e); return 1
        mo, mw = go > 12, gn > 12
        if mo.sum() < 200: print(n, 'блик old не найден'); bad += 1; continue
        ra.append(mw.sum() / mo.sum()); rm.append(gn[mw].sum() / go[mo].sum()); mn.append(gn[mw].sum()); rp.append(np.percentile(gn[mw], 95) / np.percentile(go[mo], 95))
    print('ключ: площадь блика new/old медиана %.2f (кадры %.2f..%.2f); масса (яркость×площадь) new/old %.2f (%.2f..%.2f); яркость (95-й процентиль) %.2f' % (med(ra), min(ra), max(ra), med(rm), min(rm), max(rm), med(rp)))
    if med(ra) > .75: print('BAD: блик ключа не меньше (площадь new/old ≤ 0,75)'); bad += 1
    if med(ra) < .25: print('BAD: блик ключа исчез (площадь new/old ≥ 0,25)'); bad += 1
    if med(rm) > .38: print('BAD: блик ключа не прозрачнее (масса new/old ≤ 0,38)'); bad += 1
    print('серия: масса блика по кадрам живая: размах %.0f%%' % (100 * (max(mn) - min(mn)) / max(1, med(mn))))
    if (max(mn) - min(mn)) / max(1, med(mn)) < .02: print('BAD: блик не пульсирует'); bad += 1
    return bad
def phone(nd, od, wd):
    bad = 0; rm = []; rw = []
    for n in ['ph0', 'ph1', 'ph2', 'ph3']:
        try: none = load(nd, n); go = gl(none, load(od, n)); gn = gl(none, load(wd, n))
        except Exception as e: print('нет снимка', n, e); return 1
        mo, mw = go > 12, gn > 12
        if mo.sum() < 150: print(n, 'блик old не найден (px %d)' % mo.sum()); bad += 1; continue
        rm.append(gn[mw].sum() / go[mo].sum()); ys, xs = np.nonzero(mw); yo, xo = np.nonzero(mo); rw.append((xs.max() - xs.min()) / max(1, xo.max() - xo.min()))
    if not rm: return 1
    print('будка: масса new/old медиана %.2f (%.2f..%.2f); ширина new/old %.2f' % (med(rm), min(rm), max(rm), med(rw)))
    if not .3 <= med(rm) <= .62: print('BAD: блик будки не слабее вдвое (масса new/old .3..0,62)'); bad += 1
    if med(rw) < .75: print('BAD: блик будки стал меньше (размер должен остаться)'); bad += 1
    return bad
def coin(nd, od, wd):
    from check import glint as cglint, coin_mask   # tests/coin965/check.py
    bad = 0; rows = []
    for L in ('l1', 'l2', 'l5'):
        for k in 'abcd':
            n = 'c_%s_%s' % (L, k)
            try: none = load(nd, n); go = gl(none, load(od, n)); gn = gl(none, load(wd, n))
            except Exception as e: print('нет снимка', n, e); bad += 1; continue
            gno = np.abs(load(wd, n) - none).sum(axis=2)
            mo, mw = go > 12, gn > 12; mo[:, :150] = mo[:, 330:] = False; mw[:, :150] = mw[:, 330:] = False
            bo, bw = blobs(dil(mo, 5), 30), blobs(dil(mw, 5), 30)
            if not bo or not bw: print(n, 'блик не найден old=%d new=%d' % (len(bo), len(bw))); bad += 1; continue
            cm = coin_mask(none, mo | mw)
            if cm is None: print(n, 'монета не найдена'); bad += 1; continue
            ys, xs = np.nonzero(cm); cw = xs.max() - xs.min() + 1; ccx = (xs.max() + xs.min()) / 2; ccy = (ys.max() + ys.min()) / 2
            gy, gx = np.nonzero(mw); w = gl(none, load(wd, n))[gy, gx].astype(float); dx = ((gx * w).sum() / w.sum() - ccx) / cw; dy = ((gy * w).sum() / w.sum() - ccy) / (ys.max() - ys.min() + 1)
            wo = max(b[2] - b[1] + 1 for b in bo); wn = max(b[2] - b[1] + 1 for b in bw)
            rows.append((len(bw), wn / wo, abs(dx), abs(dy), go[mo].sum(), gn[mw].sum()))
            print('%s: пятен new %d old %d; ширина наибольшего new/old %.2f (монета %d пикс); центр масс dx=%+.2f dy=%+.2f (доли монеты); масса new/old %.2f' % (n, len(bw), len(bo), wn / wo, cw, dx, dy, gn[mw].sum() / go[mo].sum()))
    if not rows: print('нет данных'); return 1
    nb = med([r[0] for r in rows]); rw = med([r[1] for r in rows]); dxm = med([r[2] for r in rows]); dym = med([r[3] for r in rows])
    print('медианы: пятен %d; ширина наибольшего new/old %.2f; |dx| %.2f |dy| %.2f' % (nb, rw, dxm, dym))
    if nb < 3: print('BAD: вокруг монеты меньше трёх бликов'); bad += 1
    if rw > .6: print('BAD: блики не мельче прежнего (ширина наибольшего ≤ 0,6)'); bad += 1
    if dxm > .3 or dym > .3: print('BAD: центр бликов не в центре монеты (№965: ≤ 0,3 размера)'); bad += 1
    return bad
def lights(nd, od, wd):
    bad = 0; rw = []; rm = []
    for n in ['l_a', 'l_b', 'l_c', 'l_d', 'l_e']:
        try: none = load(nd, n); go = gl(none, load(od, n)); gn = gl(none, load(wd, n))
        except Exception as e: print('нет снимка', n, e); return 1
        mo, mw = go > 12, gn > 12
        bo, bw = blobs(dil(mo, 3), 20), blobs(dil(mw, 3), 20)   # каждый огонь — своё пятно (два фонаря на машине не слипаются)
        if not bo or not bw: print(n, 'блик не найден old=%d new=%d' % (len(bo), len(bw))); continue
        wo = max(max(b[2] - b[1], b[4] - b[3]) for b in bo); wn = max(max(b[2] - b[1], b[4] - b[3]) for b in bw)
        rw.append(wn / max(1, wo)); rm.append(gn[mw].sum() / go[mo].sum())
    if not rw: print('огни не найдены ни в одном кадре'); return 1
    print('огни: размер наибольшего пятна new/old медиана %.2f (%.2f..%.2f); масса new/old %.2f; кадров с бликом %d' % (med(rw), min(rw), max(rw), med(rm), len(rw)))
    if not 1.15 <= med(rw) <= 1.5: print('BAD: блик огней не крупнее на ~30 % (ждём 1,15..1,5)'); bad += 1
    return bad
def same(a, b, names, coins=False):
    bad = 0
    for n in names:
        try: x = load(a, n); y = load(b, n)
        except Exception as e: print('нет снимка', n, e); bad += 1; continue
        d = np.abs(x - y).sum(axis=2) > 0; d[:60, :] = False; tot = int(d.sum())
        if coins:
            from check import orange, near
            d &= ~near(orange(x) | orange(y), 32)
        out = int(d.sum()); print('%s: отличающихся пикселей %d%s' % (n, out, (' (у монет ещё %d, разрешено)' % (tot - out)) if coins else ''))
        if out: bad += 1
    return bad
if __name__ == '__main__':
    m = sys.argv[1]
    if m == 'host': bad = host(sys.argv[2], sys.argv[3])
    elif m == 'same': bad = same(sys.argv[2], sys.argv[3], [n for n in sys.argv[4:] if n != '--coins'], '--coins' in sys.argv)
    else: bad = {'wrench': wrench, 'phone': phone, 'coin': coin, 'lights': lights}[m](*sys.argv[2:5])
    print('FAIL' if bad else 'PASS'); sys.exit(1 if bad else 0)
