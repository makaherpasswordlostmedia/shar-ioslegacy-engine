#!/usr/bin/env python3
"""Гейт гостиной меню (пункт 12а): разбор прогона tools/fe_scenario.txt (tools/fe_gate.sh запускает и то и другое).
python tools/fe_check.py OUTDIR FE.SHR [--copy DIR]
Числами, без глаза:
  · сценарий дошёл до END; строка FE: файл загружен (ok=1), частота кадров меню по счётчику движка >= 30
  · FEMEM: куча после выхода из меню = до входа ±64 КБ (гостиная освобождена)
  · фон не пустой: в окне ТВ-рамки доля не-чёрных пикселей >= 0.9, и кадр похож на превью той же камеры из fe.shr
    (корреляция яркости с превью >= 0.6 в двух полосах сбоку от пунктов меню; градиент-заглушка даёт около 0)
  · подсветка меняется при смене пункта: маска подсветки пункта k = пиксели, где превью с подсветкой k отличается от
    превью без подсветок; на снимке пункта k «желтизна» (R+G-2B) в этой маске выше, чем на снимках других пунктов, на >= 12
Правки Роба 28.09 (главное меню 3D):
  · Гомер цельный и поверх подсветки дивана: маска Гомера = пиксели, где превью с Гомером отличается от превью без него
    (превью — та же поза и скиннинг, что GE); на снимке меню яркость в маске коррелирует с превью >= 0.6 (GE рисует то,
    что в файле; что в файле — кости по данным, проверяет frontend3d_export --check); желтизна в маске на снимке с
    подсветкой дивана (fe_sofa) не выше, чем на снимках других пунктов, больше чем на 12 (подсветка не светит сквозь)
  · перелёты: строки FEFLY движка = таблице FLT1 файла (кадры от/до), длительность = кадрам / 30 ±35%; перелёт есть у
    пунктов 5, 0, 1 (туда и обратно), 2 (туда, после Options — обратно), 4 (туда, потом загрузка), 3 — туда (правка 420: BONUS
    GAME открывает бонус-игру; обратного перелёта в данных нет — △ из выбора бонус-игры возвращает главный вид сразу); снимки fly_*: ближайшее по яркости превью среди кадров главного вида и перелёта пункта —
    кадр перелёта, корреляция >= 0.6 (у «туда и обратно» без остановки >= 0.5) и выше главного вида на 0.3;
    fly_home и fly_mini — главный вид
  · FEMUS: музыка меню — simpsons_theme (FE_region композиции), таблица перелётов загружена (flights >= 5)
Правка Роба 49 (29.09): рамка-телевизор TVFrame.pag не пропадает, пока камера летит (после NEW GAME — к газете): на каждом
снимке fly_* полосы рамки (сверху над строкой меню, снизу под подсказкой, бока; без бликов стекла) = тем же полосам снимка
главного меню fe_new, средняя разница <= FRAME_TOL [fly_frame]; красное — «flag flynoframe» (прежний код: в перелёте меню не
рисуется, в полосах видна гостиная). --expect-fail fly_frame — код 0, только если это поймано
Код 0 = OK, 1 = провал (первая строка вывода — причина)."""
import argparse, struct, sys
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
SHOTS = {'fe_new': 4, 'fe_load': 0, 'fe_mini': 3, 'fe_sofa': 2}   # снимок -> пункт (номер Glow)
ROOM = (60, 40, 420, 232)                                     # окно рамки ТВ в кадре 480x272 (x0, y0, x1, y1)
BANDS = [(64, 44, 170, 108), (330, 44, 416, 228)]             # слева сверху (над Гомером) и справа от пунктов
LOW = (64, 64, 416, 220)                                      # окно ТВ ниже строки пункта (для снимков перелётов)
FLY = {'fly_tv': (5, 2), 'fly_vcr': (0, 2), 'fly_book': (1, 2), 'fly_opt': (2, 0), 'fly_new': (4, 0)}   # снимок -> (пункт, режим)
HOME = ['fly_home', 'fly_mini']
FRAME_TOL = 6.0
FRAME_BANDS = [(0, 0, 480, 16), (0, 256, 480, 272), (0, 56, 20, 216), (458, 56, 480, 216)]   # непрозрачные полосы рамки (без
                                                                                               # строки меню, подсказки, бликов стекла)
WANT_FLY = [(5, 2), (0, 2), (1, 2), (2, 0), (2, 1), (3, 0), (4, 0)]   # (пункт, режим FE_GO 0 / FE_BACK 1 / FE_ROUND 2) по сценарию; (3, 0) — правка 420


def frame(p):
    im = Image.open(p).convert('RGB'); w, h = im.size; ch = min(h, round(w * 272 / 480))   # окно: кадр снизу
    return np.asarray(im.crop((0, h - ch, w, h)).resize((480, 272), Image.LANCZOS)).astype(np.float64)


def kv(l): return dict(p.split('=', 1) for p in l.split()[1:] if '=' in p)
lum = lambda x: x @ [.299, .587, .114]
yel = lambda x: x[..., 0] + x[..., 1] - 2 * x[..., 2]


def corr(a, b, box=None, mask=None):
    if box: x0, y0, x1, y1 = box; a, b = a[y0:y1, x0:x1], b[y0:y1, x0:x1]
    u, v = lum(a), lum(b)
    if mask is not None: u, v = u[mask], v[mask]
    u, v = u.ravel(), v.ravel()
    return float(np.corrcoef(u, v)[0, 1]) if u.std() > 0 and v.std() > 0 else 0.


def flight_table(fe):
    b = Path(fe).read_bytes()
    if b[-16:-12] != b'FLT1': return {}
    off, n = struct.unpack_from('<II', b, len(b) - 12)
    return {r[0]: r for r in (struct.unpack_from('<BBHHHHHf', b, off + 16 * i) for i in range(n))}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('fe'); ap.add_argument('--copy')
    ap.add_argument('--expect-fail', default='')
    a = ap.parse_args(); out = Path(a.out); errs = []; lines = []; keyed = set()
    log = (out / 'smoke.txt').read_text(errors='replace').splitlines() if (out / 'smoke.txt').exists() else []
    if not any(l.startswith('END') for l in log): errs.append('сценарий не дошёл до END')
    fe = [kv(l) for l in log if l.startswith('FE ')]
    mem = [kv(l) for l in log if l.startswith('FEMEM ')]
    if not fe: errs.append('нет строки FE (движок без гостиной?)')
    for d in fe:
        lines.append(f"FE: ok={d['ok']} {int(d['bytes']) / 1024:.0f} КБ, чтение {d['load']} мс, кадров {d['frames']}, "
                     f"{d['fps']} кадр/с, процессор {d['cpu']} мс, треугольников {d['tris']}, кусков {d['pieces']}, подсветок {d['bills']}")
        if d['ok'] != '1': errs.append('fe.shr не загрузился')
        if float(d['fps']) < 30.: errs.append(f"частота меню {d['fps']} < 30")
    if not mem: errs.append('нет строки FEMEM')
    for d in mem:
        dk = (int(d['after']) - int(d['before'])) / 1024
        lines.append(f"память: до входа {int(d['before'])} после выхода {int(d['after'])} (разница {dk:+.1f} КБ)")
        if abs(dk) > 64: errs.append(f'куча после меню {dk:+.0f} КБ')
    # музыка меню
    mus = [kv(l) for l in log if l.startswith('FEMUS ')]
    if not mus: errs.append('нет строки FEMUS (музыка меню не подключена)')
    for d in mus:
        lines.append(f"музыка меню: {d['music']} (состояние {d['state']}), перелётов в fe.shr {d['flights']}")
        if d['music'] != 'simpsons_theme': errs.append(f"в меню играет {d['music']}, а не simpsons_theme")
        if int(d['flights']) < 5: errs.append(f"перелётов в таблице {d['flights']} < 5")
    import frontend3d_export as fx
    ref = {k: fx.preview(a.fe, None, k).astype(np.float64) for k in sorted(set(SHOTS.values()))}
    none = fx.preview(a.fe, None, 99).astype(np.float64)
    shots = {}
    for s in SHOTS:
        p = out / f'{s}.png'
        if not p.exists(): errs.append(f'нет снимка {s}'); continue
        shots[s] = frame(p)
    for s, im in shots.items():
        x0, y0, x1, y1 = ROOM; r = im[y0:y1, x0:x1]
        nb = float((r.max(2) > 16).mean())
        cs = [corr(im, ref[SHOTS[s]], bx) for bx in BANDS]
        lines.append(f'{s}: не-чёрных {nb:.3f}, корреляция с превью {cs[0]:.2f} / {cs[1]:.2f}')
        if nb < .9: errs.append(f'{s}: фон пустой ({nb:.2f})')
        if min(cs) < .6: errs.append(f'{s}: не похоже на гостиную (корреляция {min(cs):.2f})')
    for s, k in SHOTS.items():
        if s not in shots: continue
        mask = np.abs(ref[k] - none).max(2) > 40
        if mask.sum() < 20: errs.append(f'подсветка пункта {k} не видна в превью'); continue
        own = yel(shots[s])[mask].mean()
        others = [yel(shots[o])[mask].mean() for o in shots if o != s]
        lines.append(f'подсветка пункта {k} ({mask.sum()} пикс.): желтизна на своём снимке {own:.0f}, на других {", ".join(f"{x:.0f}" for x in others)}')
        if others and own - max(others) < 12: errs.append(f'подсветка пункта {k} не меняется ({own:.0f} vs {max(others):.0f})')
    # Гомер: цельный (как в превью = как в данных) и поверх подсветки дивана
    nohomer = fx.preview(a.fe, None, 99, homer=False).astype(np.float64)
    hm = np.abs(none - nohomer).max(2) > 40
    hm[:, :ROOM[0]] = False; hm[:, ROOM[2]:] = False; hm[:ROOM[1]] = False; hm[ROOM[3]:] = False
    if hm.sum() < 300: errs.append(f'Гомера нет в превью ({hm.sum()} пикс.)')
    elif shots:
        hc = {s: corr(im, ref[SHOTS[s]] if s != 'fe_sofa' else none, mask=hm) for s, im in shots.items()}
        lines.append(f'Гомер ({hm.sum()} пикс.): корреляция снимков с превью (поза и скиннинг из файла) ' + ', '.join(f'{s} {c:.2f}' for s, c in hc.items()))
        if min(hc.values()) < .6: errs.append(f'Гомер на снимке не такой, как в файле (корреляция {min(hc.values()):.2f})')
        if 'fe_sofa' in shots:
            ys = yel(shots['fe_sofa'])[hm].mean(); yo = [yel(shots[o])[hm].mean() for o in shots if o != 'fe_sofa']
            lines.append(f'желтизна на Гомере: с подсветкой дивана {ys:.0f}, с другими пунктами {", ".join(f"{x:.0f}" for x in yo)}')
            if yo and ys - max(yo) > 12: errs.append(f'подсветка дивана светит сквозь Гомера ({ys:.0f} vs {max(yo):.0f})')
    # перелёты: строки движка = таблица файла
    tab = flight_table(a.fe)
    fly = [kv(l) for l in log if l.startswith('FEFLY ')]
    got = [(int(d['item']), int(d['mode'])) for d in fly]
    for d in fly:
        it, md = int(d['item']), int(d['mode']); r = tab.get(it)
        if not r: errs.append(f'FEFLY пункта {it}: в таблице fe.shr его нет'); continue
        want = (r[3], r[6] if md == 2 else r[4]) if md != 1 else (r[5], r[6])
        dur = (want[1] - want[0]) / 30.
        lines.append(f"FEFLY пункт {it} режим {md}: кадры {d['from']}→{d['to']} (таблица {want[0]}→{want[1]}), {d['s']} с (данные {dur:.2f} с)")
        if (int(float(d['from'])), int(float(d['to']))) != want: errs.append(f'перелёт пункта {it}: кадры {d["from"]}→{d["to"]} != {want}')
        if abs(float(d['s']) - dur) > .35 * dur + .1: errs.append(f'перелёт пункта {it}: {d["s"]} с вместо {dur:.2f}')
    for w in WANT_FLY:
        if w not in got: errs.append(f'нет перелёта пункт {w[0]} режим {w[1]}')
    if any(it == 3 and md != 0 for it, md in got): errs.append('у BONUS GAME (3) перелёт обратно / туда-обратно, а в данных только «туда»')
    # снимки перелётов: ближайшее превью — кадр перелёта
    menu = struct.unpack_from('<I', Path(a.fe).read_bytes(), 52)[0]
    main_pv = fx.preview(a.fe, None, 99, frame=menu).astype(np.float64)
    for s, (it, md) in FLY.items():
        p = out / f'{s}.png'
        if not p.exists(): errs.append(f'нет снимка {s}'); continue
        im = frame(p); r = tab.get(it)
        if not r: continue
        lo, hi = r[3], (r[6] if md == 2 else r[4])
        cand = sorted(set(list(range(lo, hi + 1, 2 if md == 2 else 4)) + [r[4]]))
        cs = {f: corr(im, fx.preview(a.fe, None, 99, frame=f).astype(np.float64), LOW) for f in cand}
        cm = corr(im, main_pv, LOW); bf = max(cs, key=cs.get)
        # «туда и обратно» без остановки: у прилёта камера поворачивает до 7°/кадр, снимок окна ловит промежуточный кадр
        # (±0.2 с) — порог 0.5 и отрыв от главного вида 0.3; у стоящей камеры (Options) и у NEW GAME — 0.6
        need = .5 if md == 2 else .6
        lines.append(f'{s}: ближе всего кадр {bf} (корреляция {cs[bf]:.2f}, порог {need}), главный вид {cm:.2f}')
        if cs[bf] < need or cs[bf] < cm + .3: errs.append(f'{s}: не кадр перелёта (кадр {bf} {cs[bf]:.2f}, главный вид {cm:.2f})')
    # правка 49: рамка-телевизор на снимках перелётов = рамке главного меню
    if 'fe_new' in shots:
        m = np.zeros((272, 480), bool)
        for x0, y0, x1, y1 in FRAME_BANDS: m[y0:y1, x0:x1] = True
        for s in FLY:
            p = out / f'{s}.png'
            if not p.exists(): continue
            d = float(np.abs(frame(p) - shots['fe_new'])[m].mean())
            lines.append(f'{s}: рамка-телевизор — разница полос рамки с главным меню {d:.1f} (<= {FRAME_TOL})')
            if d > FRAME_TOL: errs.append(f'[fly_frame] {s}: в перелёте нет рамки-телевизора ({d:.1f} > {FRAME_TOL})'); keyed.add('fly_frame')
    for s in HOME:
        p = out / f'{s}.png'
        if not p.exists(): errs.append(f'нет снимка {s}'); continue
        c = corr(frame(p), main_pv, LOW); lines.append(f'{s}: главный вид, корреляция {c:.2f}')
        if c < .6: errs.append(f'{s}: камера не в главном виде ({c:.2f})')
    if a.copy:
        dst = Path(a.copy); dst.mkdir(parents=True, exist_ok=True)
        for s, im in shots.items(): Image.fromarray(im.astype(np.uint8)).save(dst / f'fe_{s}.png')
        for s in list(FLY) + HOME:
            if (out / f'{s}.png').exists(): Image.fromarray(frame(out / f'{s}.png').astype(np.uint8)).save(dst / f'fe_{s}.png')
    if a.expect_fail:
        want = [k for k in a.expect_fail.split(',') if k]; miss = [k for k in want if k not in keyed]
        print(('fe: КРАСНЫЙ как надо — пойманы ' + ', '.join(want)) if not miss else 'fe: НЕ КРАСНЫЙ — не пойманы ' + ', '.join(miss))
        return 0 if not miss else 1
    print(('OK' if not errs else 'FAIL ' + '; '.join(errs)) + f' · fe_check {out.name}')
    for l in lines: print('  ' + l)
    return 0 if not errs else 1


if __name__ == '__main__':
    sys.exit(main())
