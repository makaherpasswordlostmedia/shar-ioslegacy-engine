#!/usr/bin/env python3
"""Автоисследователь, полоса Сборка3: склейка находок всех полос в кластеры и утренний отчёт (задание ЗАДАНИЕ_АВТОИССЛЕДОВАТЕЛЬ_2026-10-11.md).

Вход: TSV находок, по одной строке на находку (общий интерфейс полос):
    уровень <TAB> x <TAB> y <TAB> z <TAB> тип <TAB> вес <TAB> seed <TAB> кадр <TAB> описание
  Строки '#...' и пустые пропускаются; заголовок (первая колонка не число) тоже. Описание может содержать 'snap=ПУТЬ' (снимок от Трасс)
  и 'in=ПУТЬ' (файл ввода повтора). Полоса = имя папки tools/autoexplore/<полоса>/ (или build/autoexplore/<полоса>/), откуда взят файл.
Склейка: тот же уровень и тот же тип, точки ближе --radius (8 м по x,z, по y в пределах --dy 6 м: этаж/крыша не смешиваются с землёй)
  связываются в один кластер (union-find по сетке). В кластере: счёт повторов, сумма веса, число разных seed, полосы, минимальный повтор
  (запись с наименьшим кадром при наибольшем весе: seed + кадр + ввод), снимок, пример описания.
Выход (--out DIR): clusters.tsv (все кластеры), ОТЧЁТ_АВТОИССЛЕДОВАТЕЛЬ_<дата>.md (топ мест по уровням простыми словами, с координатами и картинкой).
  python3 tools/autoexplore/sborka/cluster.py [--root ДЕРЕВО ...] [--tsv ФАЙЛ ...] [--out DIR] [--top 15] [--also-worktrees]
Без аргументов: корень этого дерева; --also-worktrees добавляет ~/Downloads/shar-psp*/ (находки полос до влива)."""
import argparse, collections, datetime as dt, glob, math, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TYPES = {   # тип находки -> простыми словами (неизвестный тип печатается как есть)
    'ghostwall': 'прозрачная стена (упёрлись, видимой стены нет)', 'ghost_wall': 'прозрачная стена (упёрлись, видимой стены нет)',
    'phantom': 'прозрачная стена (упёрлись, видимой стены нет)', 'invisible_wall': 'прозрачная стена (упёрлись, видимой стены нет)',
    'through': 'сквозной проезд (стена видна, коллизии нет)', 'nocollide': 'сквозной проезд (стена видна, коллизии нет)',
    'fall': 'провал или выпадение из мира', 'void': 'провал или выпадение из мира',
    'hole': 'дыра в мире (нет ни геометрии, ни подложки)', 'gap': 'дыра в мире (нет ни геометрии, ни подложки)',
    'stuck': 'вечное застревание', 'trap': 'ловушка: застрял и не выехать', 'embed': 'зависание внутри объекта',
    'teleport': 'телепорт (скачок положения)', 'flip': 'переворот машины',
    'missing': 'недостающее (предмет, монета, NPC из данных не появился)', 'missing_item': 'недостающее (предмет, монета, NPC из данных не появился)',
    'heavy': 'тяжёлый кадр (> 31 мс по модели PSP)', 'slowframe': 'тяжёлый кадр (> 31 мс по модели PSP)', 'frame': 'тяжёлый кадр (> 31 мс по модели PSP)',
    'overload': 'долгая перегрузка кадра',
    'launch': 'подброс (машину выбросило вверх без зоны прыжка)', 'carunder': 'кузов в кузове другой машины (наезд или заезд под машину)',
    'carover': 'машина едет на крыше другой машины', 'roof': 'машина на крыше или плато выше окружения (вне дороги)',
    'ramp': 'прыжок без зоны (трамплин или край, от 1,5 с в воздухе)', 'recovery': 'игра вернула машину на надёжное место (была застрявшей или за миром)',
    'backfence': 'проезд забора с изнанки (по замыслу, как у PS2; справочно)',
    'phantom': 'проезд сквозь прозрачную стену (ящик без рисунка, правка 475, по замыслу; справочно)', 'death': 'зона DEATH вернула машину в точку возврата (как в игре; справочно)',
    'stuckbot': 'застрял бот, а игрок выбрался бы (один из 7 манёвров вывел машину; справочно)',
    'backreturn': 'отскок обратно через звено забора, в которое машина вошла с изнанки (по замыслу PS2; справочно)', 'escape': 'собственный выход игры (№738 зажата, перч, тупик 32): сдвиг в точку рядом, идёт сквозь забор по замыслу; справочно',
}


def num(s, d=0.0):
    try: return float(s)
    except Exception: return d


def parse_tsv(path, lane):
    out = []
    for n, ln in enumerate(Path(path).read_text(errors='replace').splitlines(), 1):
        if not ln.strip() or ln.lstrip().startswith('#'): continue
        f = ln.split('\t')
        if len(f) < 5: continue
        lv = f[0].strip().lstrip('Ll')
        if not lv.isdigit(): continue   # заголовок
        desc = f[8] if len(f) > 8 else ''
        snap = next((w[5:] for w in desc.split() if w.startswith('snap=')), '')
        inp = next((w[3:] for w in desc.split() if w.startswith('in=')), '')
        out.append(dict(level=int(lv), x=num(f[1]), y=num(f[2]), z=num(f[3]), kind=f[4].strip(), weight=num(f[5], 1.0) if len(f) > 5 else 1.0,
                        seed=f[6].strip() if len(f) > 6 else '', frame=int(num(f[7], 0)) if len(f) > 7 else 0, desc=desc, snap=snap, inp=inp,
                        lane=lane, src=f'{path}:{n}'))
    return out


def find_tsv(roots):
    seen, res = set(), []
    for r in roots:
        for pat in ('tools/autoexplore/*/*.tsv', 'tools/autoexplore/*/*/*.tsv', 'build/autoexplore/*/*.tsv', 'build/autoexplore/*/*/*.tsv'):
            for p in sorted(glob.glob(str(Path(r) / pat))):
                rp = os.path.realpath(p)
                if rp in seen or Path(p).name in ('clusters.tsv',): continue
                seen.add(rp); parts = Path(p).relative_to(r).parts; lane = parts[2] if len(parts) > 2 else parts[1]
                if Path(p).parent.name == 'findings': lane = Path(p).stem.split('_L')[0]   # build/autoexplore/<дата>/findings/<полоса>_L<ур>_s<seed>.tsv
                res.append((p, lane))
    return res


class UF:
    def __init__(s, n): s.p = list(range(n))
    def f(s, i):
        while s.p[i] != i: s.p[i] = s.p[s.p[i]]; i = s.p[i]
        return i
    def u(s, a, b): s.p[s.f(a)] = s.f(b)


def cluster(items, radius=8.0, dy=6.0):
    uf = UF(len(items)); grid = collections.defaultdict(list)
    for i, it in enumerate(items): grid[(it['level'], it['kind'], int(it['x'] // radius), int(it['z'] // radius))].append(i)
    for (lv, kd, gx, gz), idx in grid.items():
        for ox in (-1, 0, 1):
            for oz in (-1, 0, 1):
                for j in grid.get((lv, kd, gx + ox, gz + oz), ()):
                    for i in idx:
                        if i < j and math.hypot(items[i]['x'] - items[j]['x'], items[i]['z'] - items[j]['z']) <= radius and abs(items[i]['y'] - items[j]['y']) <= dy: uf.u(i, j)
    groups = collections.defaultdict(list)
    for i in range(len(items)): groups[uf.f(i)].append(items[i])
    res = []
    for g in groups.values():
        w = sum(x['weight'] for x in g); cx = sum(x['x'] * x['weight'] for x in g) / (w or 1); cy = sum(x['y'] * x['weight'] for x in g) / (w or 1); cz = sum(x['z'] * x['weight'] for x in g) / (w or 1)
        best = min(g, key=lambda x: (x['frame'] if x['frame'] > 0 else 10 ** 9, -x['weight']))   # минимальный повтор: самый ранний кадр
        res.append(dict(level=g[0]['level'], kind=g[0]['kind'], x=cx, y=cy, z=cz, n=len(g), weight=w, seeds=sorted({x['seed'] for x in g if x['seed']}),
                        lanes=sorted({x['lane'] for x in g}), replay=best, snap=next((x['snap'] for x in g if x['snap']), ''), desc=best['desc'][:160]))
    res.sort(key=lambda c: (c['level'], -c['weight'], -c['n']))
    return res


def write_all(cl, out, date, nfind, nfiles, nlevels_total=7, top=15, build=''):
    out.mkdir(parents=True, exist_ok=True)
    with open(out / 'clusters.tsv', 'w') as f:
        f.write('# уровень\tx\ty\tz\tтип\tповторов\tвес\tseed_всего\tполосы\tminimal_seed\tminimal_кадр\tввод\tснимок\tописание\n')
        for c in cl:
            r = c['replay']
            f.write('\t'.join(map(str, [c['level'], round(c['x'], 1), round(c['y'], 1), round(c['z'], 1), c['kind'], c['n'], round(c['weight'], 2), len(c['seeds']), ','.join(c['lanes']), r['seed'], r['frame'], r['inp'], c['snap'], c['desc']])) + '\n')
    L = [f'# Отчёт автоисследователя · {date}', '',
         f'Сборка: {build or "—"}. Файлов находок: {nfiles}, находок: {nfind}, мест (кластеров): {len(cl)}. Склейка: тот же уровень и тип, точки ближе 8 м (по высоте до 6 м).', '']
    bylv = collections.defaultdict(list)
    for c in cl: bylv[c['level']].append(c)
    L += ['## Сводка по уровням и типам', '', '| уровень | ' + ' | '.join(['мест', 'повторов всего', 'главный тип']) + ' |', '|---|---|---|---|']
    for lv in range(1, nlevels_total + 1):
        cs = bylv.get(lv, [])
        kinds = collections.Counter()
        for c in cs: kinds[c['kind']] += c['n']
        main = ', '.join(f'{TYPES.get(k, k).split(" (")[0]} ×{v}' for k, v in kinds.most_common(2)) or '—'
        L.append(f'| L{lv} | {len(cs)} | {sum(c["n"] for c in cs)} | {main} |')
    L.append('')
    for lv in range(1, nlevels_total + 1):
        cs = sorted(bylv.get(lv, []), key=lambda c: (-c['weight'], -c['n']))[:top]
        L += [f'## Уровень {lv}: топ мест', '']
        if not cs: L += ['Находок нет (или полосы ещё не сдали данные).', ''];  continue
        for i, c in enumerate(cs, 1):
            r = c['replay']
            L += [f'{i}. **{TYPES.get(c["kind"], c["kind"])}** · x {c["x"]:.0f}, y {c["y"]:.0f}, z {c["z"]:.0f} · повторов {c["n"]} (seeds {len(c["seeds"])}), вес {c["weight"]:.1f}, полосы: {", ".join(c["lanes"])}',
                  f'   - повторить: seed {r["seed"] or "—"}, кадр {r["frame"]}' + (f', ввод `{r["inp"]}`' if r['inp'] else '') + f' (из `{Path(r["src"].split(":")[0]).name}`)']
            if c['desc']: L.append(f'   - {c["desc"]}')
            if c['snap']: L.append(f'   - ![{c["kind"]} L{lv} {c["x"]:.0f},{c["z"]:.0f}]({c["snap"]})')
            else: L.append('   - снимка нет (полоса Трасс не приложила snap=)')
        L.append('')
    (out / f'ОТЧЁТ_АВТОИССЛЕДОВАТЕЛЬ_{date}.md').write_text('\n'.join(L) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', action='append', default=[]); ap.add_argument('--tsv', action='append', default=[])
    ap.add_argument('--out'); ap.add_argument('--top', type=int, default=15); ap.add_argument('--radius', type=float, default=8.0); ap.add_argument('--dy', type=float, default=6.0)
    ap.add_argument('--also-worktrees', action='store_true'); ap.add_argument('--date'); ap.add_argument('--build', default='')
    a = ap.parse_args()
    roots = [Path(r) for r in a.root] or [ROOT]
    if a.also_worktrees: roots += sorted(p for p in Path.home().glob('Downloads/shar-psp*/') if p.is_dir() and p not in roots)
    files = find_tsv(roots)
    known = {os.path.realpath(p) for p, _ in files}
    files += [(t, Path(t).parent.name) for t in a.tsv if os.path.realpath(t) not in known]
    items = []
    for p, lane in files: items += parse_tsv(p, lane)
    date = a.date or dt.date.today().isoformat()
    out = Path(a.out) if a.out else ROOT / 'build' / 'autoexplore' / date
    cl = cluster(items, a.radius, a.dy)
    write_all(cl, out, date, len(items), len(files), top=a.top, build=a.build)
    print(f'файлов {len(files)}, находок {len(items)}, кластеров {len(cl)} -> {out}')


if __name__ == '__main__': main()
