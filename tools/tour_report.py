#!/usr/bin/env python3
"""Разбор замер-тура с PSP (tools/tour_psp.sh --fetch): папка с smoke.txt и shots/*.bmp -> ОТЧЁТ.md и лист снимков.

Что считается:
  сцены  — строки STAT (viewer/smoke.h): кадр p95/p99/max мс, пропуски периода, кадры с видимой незагруженной клеткой,
           минимум кучи и наибольшего куска, пик списка GE, отказы памяти, ошибки чтения;
  ящик   — строки BB раз в секунду: доли процессора потоков (main/loader/audio_mix/audio_io/bbw), клетки за секунду, худшая
           задержка «запрос -> готова», дольше 100 мс; шапка ящика — проба volatile;
  швы    — снимки *_gap.bmp (clearchk + nosky + seamchk: щель — пурпур) и *_gapold.bmp (как до правок 224/237/251): щелью
           считается тонкий пурпур — пиксели маски, которые снимает открытие 3×3 (открытый фон без неба — большие пятна,
           щель — линии в 1–2 пикселя); число по каждому виду, новый движок против прежнего.
  окна   — (наряд 24.10, Г1) ph0 > 2 мс подряд >= 3 с: начало/конец, средний ph0, кадр > 150 мс на конце окна и строка перед ним;
  стоя   — (Г2) секунды, где позиция BB не меняется больше 2 м, а загружено клеток > 5: подряд >= 3 с; секунды сразу после смены сцены не считаются;
  против прошлого тура — (Г3) по каждой сцене медиана vbl и ph0 (по строкам PHSEC), не p95: p95 хуже от окон Г1, хотя игра быстрее.
  python3 tools/tour_report.py ПАПКА [ПРОШЛЫЙ_ТУР]   (без второго аргумента — ближайшая более ранняя папка с теми же сценами)"""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter


def cracks(path):
    """щель — пурпур, НЕ связанный с открытым фоном (небо без неба): заливка от пурпура верхней строки и больших пятен
    (открытие 5×5) по 4-соседству внутри маски; что не залилось — дыры внутри геометрии (земля, стены, стыки).
    -> (пикселей щелей, пикселей пурпура всего, щелей ниже середины кадра — земля)"""
    a = np.asarray(Image.open(path).convert('RGB')).astype(int)
    m = (a[..., 0] > 200) & (a[..., 1] < 60) & (a[..., 2] > 200)
    im = Image.fromarray((m * 255).astype(np.uint8))
    big = np.asarray(im.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))) > 127
    seed = big.copy(); seed[0] |= m[0]
    reach = seed & m
    for _ in range(2000):   # заливка внутри маски
        n = reach.copy()
        n[1:] |= reach[:-1]; n[:-1] |= reach[1:]; n[:, 1:] |= reach[:, :-1]; n[:, :-1] |= reach[:, 1:]
        n &= m
        if (n == reach).all(): break
        reach = n
    holes = m & ~reach
    H = holes.shape[0]
    return int(holes.sum()), int(m.sum()), int(holes[H // 2:].sum())


PH0_MS, PH0_SEC, STAND_M, STAND_CELLS, STAND_SEC, SLOW_MS = 2.0, 3.0, 2.0, 5, 3, 150.0


def tour_series(sm):
    """smoke.txt -> (PHSEC [(t, сцена, ph0, vbl)], BB раз в секунду [(t тура, секунда BB, уровень, клетка, x, z, клеток за секунду, мс худшей, сцена)],
    SLOWFRAME > 150 мс [(t, work, сцена, номер строки)], старты сцен {сцена: t}); t тура — по последней строке PHSEC выше (у BB свои секунды: стенные)"""
    ph, bb, slow, starts = [], [], [], {}
    t, sc = 0.0, ''
    for i, ln in enumerate(sm):
        if ln.startswith('PHSEC '):
            kv = dict(re.findall(r'(\w+)=(\S+)', ln))
            if 'ph0' in kv and 'vbl' in kv:
                t, sc = float(kv['t']), kv['scene']; ph.append((t, sc, float(kv['ph0']), float(kv['vbl'])))
        elif ln.startswith('SCENE '):
            p = ln.split(); starts[p[1]] = float(p[2]); sc = p[1]
        elif ln.startswith('BB '):
            m = re.match(r'BB\s+(\d+)\s+-\s+L(\d+)\s+(\S+)\s+(-?\d+)\s+-?\d+\s+(-?\d+)\s', ln)   # '-' — строка раз в секунду, 'op' — по событию
            c = re.search(r'cell (\d+) (\d+)ms', ln)
            if m and c: bb.append((t, int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4)), int(m.group(5)), int(c.group(1)), int(c.group(2)), sc))
        if 'SLOWFRAME t=' in ln:   # строки лога местами склеены (хвост FLAT + SLOWFRAME), поэтому ищем внутри строки
            m = re.search(r'SLOWFRAME t=([\d.]+) work=([\d.]+).*?scene=(\S+)', ln)
            if m and float(m.group(2)) > SLOW_MS: slow.append((float(m.group(1)), float(m.group(2)), m.group(3), i))
    return ph, bb, slow, starts


def ph0_windows(ph):
    """подряд идущие секунды PHSEC (одна сцена, разрыв < 2,5 с) с ph0 > 2 мс, окно >= 3 с -> [(сцена, начало, конец, средний ph0, секунд)]"""
    out, run = [], []
    for x in ph + [(1e9, '', 0.0, 0.0)]:
        if x[2] > PH0_MS and (not run or (x[0] - run[-1][0] < 2.5 and x[1] == run[-1][1])): run.append(x); continue
        if run and run[-1][0] - run[0][0] >= PH0_SEC: out.append((run[0][1], run[0][0], run[-1][0], float(np.mean([r[2] for r in run])), len(run)))
        run = [x] if x[2] > PH0_MS else []
    return out


def stand_loads(bb, starts):
    """секунды BB, где игрок стоит (до 2 м за секунду, один уровень) и загружено > 5 клеток; подряд >= 3 с (разрыв до 1 с склеивается);
    первые 10 с сцены не считаются (вход в уровень грузит законно) -> [(сцена, уровень, клетка, x, z, t от, t до, секунда BB от, до, секунд, клеток всего, худшая мс)]"""
    hot, prev = [], None
    for b in bb:
        if prev and prev[2] == b[2] and ((b[4] - prev[4]) ** 2 + (b[5] - prev[5]) ** 2) ** 0.5 <= STAND_M and b[6] > STAND_CELLS \
                and b[0] - starts.get(b[8], -99) > 10: hot.append(b)
        prev = b
    out, run = [], []
    for b in hot + [None]:
        if b is not None and (not run or (b[1] - run[-1][1] <= 2 and b[8] == run[-1][8])): run.append(b); continue
        if len(run) >= STAND_SEC:
            r0 = run[0]; out.append((r0[8], r0[2], r0[3], r0[4], r0[5], r0[0], run[-1][0], r0[1], run[-1][1], len(run), sum(r[6] for r in run), max(r[7] for r in run)))
        run = [b] if b is not None else []
    return out


def scene_med(ph):
    """{сцена: (медиана vbl, медиана ph0, секунд)}"""
    g = {}
    for t, sc, p0, vbl in ph: g.setdefault(sc, []).append((p0, vbl))
    return {k: (float(np.median([v[1] for v in x])), float(np.median([v[0] for v in x])), len(x)) for k, x in g.items()}


def prev_tour(d):
    """ближайшая более ранняя папка рядом с теми же сценами (не меньше 80 % названий сцен) — база для сравнения"""
    mine = set(scene_med(tour_series((d / 'smoke.txt').read_text(errors='replace').splitlines())[0]))
    for q in sorted((x for x in d.parent.iterdir() if x.is_dir() and x.name < d.name and (x / 'smoke.txt').exists()), reverse=True):
        theirs = set(scene_med(tour_series((q / 'smoke.txt').read_text(errors='replace').splitlines())[0]))
        if mine and theirs and len(mine & theirs) >= 0.8 * min(len(mine), len(theirs)): return q
    return None


def main():
    d = Path(sys.argv[1]); old = Path(sys.argv[2]) if len(sys.argv) > 2 else None; sm = (d / 'smoke.txt').read_text(errors='replace').splitlines()
    stats, shots, bb, bbcpu, audq = [], {}, [], [], []
    for ln in sm:
        if ln.startswith('BBCPU '):   # правка 410: доли потоков — одна строка в секунду (строки BB повторяют её на каждом событии)
            m = re.search(r'pct=(\d+)/(\d+)/(\d+)/(\d+)/(\d+)', ln)
            if m: bbcpu.append(tuple(int(x) for x in m.groups()))
            continue
        if ln.startswith('AUDQ '):    # правка 410: опоздавшие буферы звука и цена отправки на ME
            audq.append(dict(re.findall(r'(\w+)=(\S+)', ln))); continue
        if ln.startswith('STAT '):
            p = ln.split(); name = p[1]; kv = dict(zip(p[2::2], p[3::2]))
            if kv.get('frames', '0') != '0': stats.append((name, kv))
        elif ln.startswith('SHOTFILE '):
            p = ln.split(); shots[p[1]] = dict(x.split('=', 1) for x in p[2:] if '=' in x)
        elif ln.startswith('BB '):
            m = re.search(r'heap\s+([\d.]+) blk\s+([\d.]+).*?cpu (\d+)/(\d+)/(\d+)/(\d+)/(\d+)\s+cell (\d+) (\d+)ms >100:(\d+) miss (\d+)', ln)
            if m: bb.append(tuple(float(x) for x in m.groups()))
    end = any(l.strip() == 'END' for l in sm)
    out = [f'# Замер-тур PSP · {d.name}', '', f'Тур дошёл до конца: **{"да" if end else "нет (последняя сцена — " + (stats[-1][0] if stats else "?") + ")"}**; '
           f'сцен с кадрами {len(stats)}, снимков {len(shots)}, строк ящика {len(bb)}', '']
    hdr = (d / 'blackbox.txt').read_text(errors='replace').splitlines()[0] if (d / 'blackbox.txt').exists() else ''
    vm = re.search(r'vol (-?\d+) (\d+)K', hdr)
    if vm: out += [f'Проба «лишних 4 МБ» (volatile): код {vm.group(1)}, {vm.group(2)} КБ ' + ('— доступны' if vm.group(1) == '0' else '— недоступны'), '']
    if bb:
        B = np.array(bb)
        out += ['## Процессор и подгрузка (строки ящика раз в секунду)', '',
                '| поток | средняя доля, % | максимум, % |', '|---|---|---|']
        C = np.array(bbcpu) if bbcpu else None
        if C is not None:   # правка 410: из BBCPU, секунды с долей > 100 (сбой зонда) отброшены с предупреждением
            badrows = (C > 100).any(axis=1); Cg = C[~badrows] if (~badrows).any() else C[:0]
        for i, n in enumerate(['main', 'loader', 'audio_mix', 'audio_io', 'bbw']):
            if C is not None and len(Cg): out.append(f'| {n} | {Cg[:, i].mean():.1f} | {Cg[:, i].max():.0f} |')
            else: out.append(f'| {n} | {B[:, 2 + i].mean():.1f} | {B[:, 2 + i].max():.0f} |')
        if C is not None and badrows.any():
            out += ['', f'**Внимание:** {int(badrows.sum())} секунд BBCPU с долей больше 100 % отброшены (сбой зонда после смены уровня, правка 410)']
        out += ['', f'Клеток загружено {int(B[:, 7].sum())}; худшая задержка «запрос -> готова» {B[:, 8].max():.0f} мс; секунд с клеткой дольше 100 мс '
                f'{int((B[:, 9] > 0).sum())}; кадров с видимой незагруженной {int(B[:, 10].sum())}; куча минимум {B[:, 0].min():.2f} МБ, наибольший кусок минимум {B[:, 1].min():.2f} МБ', '']
    if audq:   # правка 410: треск звука — буферы, ушедшие в канал, который уже доиграл всё (late); тишина при звучащем голосе (sil)
        num = lambda q, k: float(q[k].split('/')[0]) if k in q else 0.0
        late = sum(num(q, 'late') for q in audq); sil = sum(num(q, 'sil') for q in audq); su = sum(num(q, 'su') for q in audq)
        lsec = [q for q in audq if num(q, 'late') > 0]
        kk = [q for q in audq if num(q, 'kick') > 0]
        avg = lambda k: sum(num(q, k) for q in kk) / len(kk) if kk else 0.0
        rmin = [num(q, 'rest_min') for q in audq if num(q, 'rest_min') >= 0]
        out += ['## Звук: опоздания и отдача на ME (строки AUDQ)', '',
                f'Секунд {len(audq)}; опоздавших буферов (канал уже доиграл — дыра, треск) **{late:.0f}** в {len(lsec)} секундах; '
                f'тишина при звучащем голосе {sil:.0f}; голос потока без данных {su:.0f}; наименьший запас канала {min(rmin) if rmin else -1:.0f} сэмплов; '
                f'худший буфер {max(num(q, "wmax_us") for q in audq):.0f} мкс; буферов на главном при включённом ME {sum(num(q, "cpu") for q in audq):.0f}', '']
        if lsec: out += ['Секунды с опозданием: ' + ', '.join(f'{q.get("t")} ({q.get("sc")}: {q.get("late")})' for q in lsec[:20]), '']
        if kk:
            out += [f'Отдача на ME, среднее мкс на буфер: сброс кэша {avg("wb_us"):.0f}, meSvcSubmit {avg("svc_us"):.0f}, ожидание ответа {avg("col_us"):.0f}, '
                    f'mixPre {avg("pre_us"):.0f}, mixPost {avg("post_us"):.0f}; строк кэша в сбросе {avg("wbl"):.0f} из 684 за {avg("wbr"):.1f} вызова; '
                    f'сброс целиком (wbold) {"да" if any(q.get("wbold") == "1" for q in kk) else "нет"}', '']
    out += ['## Сцены', '', '| сцена | кадр p95 / p99 / max, мс | пропуски | видимые незагр. | куча мин, МБ | кусок мин, МБ | GE пик, КБ | отказы памяти | ошибки чтения |',
            '|---|---|---|---|---|---|---|---|---|']
    for name, kv in stats:
        out.append(f'| {name} | {kv.get("p95")} / {kv.get("p99")} / {kv.get("max")} | {kv.get("missed")} | {kv.get("missvis")} | {kv.get("heapmin")} | '
                   f'{kv.get("blkmin")} | {kv.get("gepeak")} | {kv.get("memfail")} | {kv.get("readerr")} |')
    ph, bbs, slow, starts = tour_series(sm)
    wins = ph0_windows(ph)
    out += ['', f'## Окна: ph0 > {PH0_MS:g} мс подряд >= {PH0_SEC:g} с (начало кадра, «ввод»; в здоровом туре ph0 около 0,1 мс)', '']
    if wins:
        out += ['| сцена | начало, с | конец, с | секунд | ph0 средний, мс | кадр > 150 мс на конце (мс) и строка перед ним |', '|---|---|---|---|---|---|']
        for sc, a, b, mean, n in wins:
            sf = [x for x in slow if x[2] == sc and a - 1 <= x[0] <= b + 3]
            if sf:
                t, w, _, i = max(sf, key=lambda x: x[1])
                fl = [x.split('SLOWFRAME t=')[0] for x in sm[max(0, i - 12):i + 1] if 'FLAT on=' in x]   # сводка мультика стоит в 1–10 строках перед кадром (строки лога местами склеены, ищем внутри строки)
                if fl: before = 'FLAT ' + ' '.join(f'{k}={v}' for k, v in re.findall(r'\b(on|cells|verts|res)=(\d+)', fl[-1][fl[-1].index('FLAT on='):][:200])[:4])
                else: before = sm[i - 1].strip()[:60].replace('|', '/') + ' (FLAT рядом нет)'
                tail = f'{w:.0f} (t={t:.1f}): `{before}`'
            else: tail = '—'
            out.append(f'| {sc} | {a:.1f} | {b:.1f} | {n} | {mean:.1f} | {tail} |')
        out += ['', f'Окон {len(wins)}, секунд в них {sum(w[4] for w in wins)}; **это не отрисовка**: ph0 — работа до отрисовки (логика, загрузка)']
    else: out += ['Окон нет']
    st = stand_loads(bbs, starts)
    out += ['', f'## Загрузки стоя: позиция BB не меняется > {STAND_M:g} м за секунду, а загружено клеток > {STAND_CELLS}, подряд >= {STAND_SEC} с (первые 10 с сцены не считаются)', '']
    if st:
        out += ['| сцена | ур. | клетка | x, z | t тура, с | секунды BB | секунд | клеток всего (в секунду) | худшая задержка, мс |', '|---|---|---|---|---|---|---|---|---|']
        for sc, lv, cell, x, z, t0, t1, s0, s1, n, cn, ms in st:
            out.append(f'| {sc} | L{lv} | {cell} | {x}, {z} | {t0:.1f}–{t1:.1f} | {s0}–{s1} | {n} | {cn} ({cn / n:.0f}) | {ms} |')
        out += ['', 'Секунды BB — стенные часы, не время тура: после замираний они уходят вперёд (в TEST57 к 160-й секунде тура на 22 с); сцену смотри по колонке t тура']
    else: out += ['Мест нет']
    if old is None: old = prev_tour(d)
    if old is not None and (old / 'smoke.txt').exists():
        pm = scene_med(tour_series((old / 'smoke.txt').read_text(errors='replace').splitlines())[0]); nm = scene_med(ph)
        out += ['', f'## Против прошлого тура `{old.name}`: медиана по секундам PHSEC (vbl — запас до кадра, больше = лучше; ph0 — меньше = лучше)', '',
                '| сцена | vbl было → стало, мс | ph0 было → стало, мс | вердикт |', '|---|---|---|---|']
        bad = 0
        for sc in nm:
            if sc not in pm: out.append(f'| {sc} | — → {nm[sc][0]:.1f} | — → {nm[sc][1]:.2f} | новая сцена |'); continue
            (v0, p0, _), (v1, p1, _) = pm[sc], nm[sc]
            tags = (['запас vbl упал %.1f' % (v0 - v1)] if v1 < v0 - 1.0 else []) + (['ph0 вырос на %.1f' % (p1 - p0)] if p1 > p0 + 0.5 else [])
            bad += bool(tags)
            out.append(f'| {sc} | {v0:.1f} → {v1:.1f} | {p0:.2f} → {p1:.2f} | {"**хуже:** " + ", ".join(tags) if tags else ("лучше" if v1 > v0 + 1.0 else "в норме")} |')
        out += ['', f'Сцен хуже прошлого тура: {bad} из {len([k for k in nm if k in pm])}']
    elif ph: out += ['', '## Против прошлого тура', '', 'Прошлый тур с теми же сценами рядом не найден (передай папку вторым аргументом)']
    pil, st0, psc = [], None, ''   # строки PILOT: сколько автопилот ехал против заданного и какой путь проехал
    for ln in sm:
        if ln.startswith('SCENE '): psc = ln.split()[1]
        m = re.match(r'PILOT start t=([\d.]+) secs=(\d+)', ln)
        if m: st0 = (float(m.group(1)), int(m.group(2)))
        m = re.match(r'PILOT end t=([\d.]+) dist=(\d+) stuck=(\d+)', ln)
        if m and st0: pil.append((psc, st0[1], float(m.group(1)) - st0[0], int(m.group(2)), int(m.group(3)))); st0 = None
    if pil:
        out += ['', '## Автопилот (`flag drive`): задано против проехано', '', '| сцена | задано, с | ехал, с | путь, м | застреваний | замечание |', '|---|---|---|---|---|---|']
        for sc, secs, dt, dist, stk in pil:
            note = ', '.join((['ехал меньше 75 % срока'] if dt < 0.75 * secs else []) + (['не сдвинулся: езды нет'] if dist < 20 else []))
            out.append(f'| {sc} | {secs} | {dt:.1f} | {dist} | {stk} | {note or "—"} |')
    gaps = sorted(n for n in shots if n.endswith('_gap'))
    if gaps:
        out += ['', '## Швы на железе: щели — пурпур внутри геометрии (не связан с открытым фоном), новый движок против прежнего (seamsold)', '',
                '| вид | щелей, новый (из них в нижней половине) | щелей, прежний (нижняя половина) | пурпура всего (фон без неба) |', '|---|---|---|---|']
        tn = to = 0
        for g in gaps:
            pn = d / 'shots' / f'{g}.bmp'; po = d / 'shots' / f'{g}old.bmp'
            if not pn.exists(): continue
            cn, an, gn = cracks(pn); co, _, go = cracks(po) if po.exists() else (-1, 0, -1)
            tn += cn; to += max(co, 0)
            out.append(f'| {g[:-4]} | {cn} ({gn}) | {co if co >= 0 else "—"} ({go if go >= 0 else "—"}) | {an} |')
        out += ['', f'Итого щелей: новый {tn}, прежний {to}' + (f' ({100 * (1 - tn / to):.0f} % меньше)' if to else '')]
    sh = sorted((d / 'shots').glob('*.bmp')) if (d / 'shots').exists() else []
    if sh:
        th = [Image.open(p).convert('RGB').resize((240, 136)) for p in sh]
        cols = 6; rows = (len(th) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * 244, rows * 152), (20, 20, 20))
        from PIL import ImageDraw
        dr = ImageDraw.Draw(sheet)
        for i, (t, p) in enumerate(zip(th, sh)):
            x, y = (i % cols) * 244, (i // cols) * 152; sheet.paste(t, (x + 2, y + 2)); dr.text((x + 4, y + 138), p.stem[:30], fill=(230, 230, 230))
        sheet.save(d / 'лист_снимков.png'); out += ['', f'Лист снимков: `{d / "лист_снимков.png"}`']
    (d / 'ОТЧЁТ.md').write_text('\n'.join(out) + '\n')
    print('\n'.join(out[:12])); print(f'... -> {d / "ОТЧЁТ.md"}')


if __name__ == '__main__':
    main()
