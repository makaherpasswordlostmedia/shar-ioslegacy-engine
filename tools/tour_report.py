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
  python3 tools/tour_report.py ПАПКА"""
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


def main():
    d = Path(sys.argv[1]); sm = (d / 'smoke.txt').read_text(errors='replace').splitlines()
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
