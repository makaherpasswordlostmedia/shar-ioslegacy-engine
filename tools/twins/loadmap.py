#!/usr/bin/env python3
"""Близнецы · атлас подгрузки оригинала (слово Роба 02.10: «смотри, когда что подгружается, чтобы понять механику игры»).

  python3 tools/twins/loadmap.py [--level 1] [--out build/twins/loadmap]

[диск] Город уровня грузится не по расстоянию, а воротами: локаторы вида 5 (DynaLoad) с объёмом-триггером на дорогах. В каждом —
строка команд: имя файла и знак после него — что с ним сделать при въезде в объём:
  «:» — выгрузить, «;» — загрузить, «@» — загрузить помещение (дверь), «$» — выгрузить помещение
(грамматика выведена из строк самих ворот; у дверей SimpsonsHouse/KwikEMart/SpringfieldElementary — «@»). Точки телепорта
level.mfk (AddTeleportDest) несут набор файлов, который должен быть в памяти на месте, — им сверяются ворота.
[PS2] Сверка с ездой бота в своём PCSX2 (build/twins/b2/<прогон>/files.tsv, первый кадр чтения файла зоны и место): у каких ворот
оригинал прочитал файл.
Выход: <out>/gates.tsv (ворота: место в осях порта, объём, загрузить/выгрузить), <out>/atlas.md (сводка для Роба и сессий)."""
import argparse, json, math, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common as C

OPS = {':': 'выгрузить', ';': 'загрузить', '@': 'загрузить помещение', '$': 'выгрузить помещение'}


def parse_cmd(s):
    """'l1i01.p3d$l1z1.p3d:…;' -> [(файл, знак)] по порядку"""
    return [(m.group(1), m.group(2)) for m in re.finditer(r'([A-Za-z0-9_]+\.p3d)([:;@$])', s)]


def gates(level):
    import sound_export as S
    out = []
    for f, nm, kind, d, p, vols in S.locators(level):
        if kind != 5: continue
        s = d.split(b'\0')[0].decode('latin1', 'replace')
        ops = parse_cmd(s)
        box = [dict(c=[round(float(v), 2) for v in vv['t']], half=[round(float(h), 2) for h in vv['half']],
                    R=[[round(float(x), 4) for x in row] for row in vv['R']]) for vv in vols]
        out.append(dict(name=nm, file=f, pos=[round(v, 2) for v in p], cmd=s, ops=ops, boxes=box,
                        load=[a for a, o in ops if o == ';'], unload=[a for a, o in ops if o == ':'],
                        room_in=[a for a, o in ops if o == '@'], room_out=[a for a, o in ops if o == '$']))
    return out


def teleports(level):
    src = (C.DATA / f'hit-and-run-web/source/game/scripts/missions/level0{level}/level.mfk').read_text(errors='replace')
    out = []
    for m in re.finditer(r'AddTeleportDest\("([^"]+)",\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)\s*,\s*"([^"]*)"\)', src):
        name, x, y, z, files = m.groups()
        out.append(dict(name=name, pos=[float(x), float(y), -float(z)], files=[a for a in files.split(';') if a]))   # z порта = −z
    return out


def twins_loads():
    """[PS2] первое чтение файла зоны в прогонах близнецов: (прогон, файл, кадр, x, z оригинала)"""
    out = []
    for f in sorted((C.OUT / 'b2').glob('*/files.tsv')):
        for l in f.read_text().splitlines()[1:]:
            c = l.split('\t')
            m = re.search(r'art/(l\d[zri][\w]*\.p3d)$', c[0])
            p = re.match(r'\((-?[\d.]+), (-?[\d.]+)\)', c[5]) if len(c) > 5 else None
            if m and p: out.append(dict(run=f.parent.name, file=m.group(1), frame=float(c[4]), x=float(p.group(1)), zo=float(p.group(2))))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=int, default=1); ap.add_argument('--out', default=str(C.OUT / 'loadmap'))
    a = ap.parse_args(); out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    G = gates(a.level); T = teleports(a.level); P = [r for r in twins_loads() if r['file'].startswith(f'l{a.level}')]
    art = C.DATA / 'hit-and-run-web/source/game/art'
    size = {p.name: p.stat().st_size for p in art.glob(f'l{a.level}*.p3d')}
    with (out / 'gates.tsv').open('w') as fo:
        fo.write('ворота\tx\ty\tz (порт)\tобъёмов\tзагрузить\tвыгрузить\tпомещение: загрузить / выгрузить\n')
        for g in G:
            fo.write(f"{g['name']}\t{g['pos'][0]}\t{g['pos'][1]}\t{g['pos'][2]}\t{len(g['boxes'])}\t{' '.join(g['load'])}\t"
                     f"{' '.join(g['unload'])}\t{' '.join(g['room_in'])} / {' '.join(g['room_out'])}\n")
    # [PS2] у каких ворот прочитан файл: последние ворота, в объём которых въехала машина бота ДО кадра чтения (траектория
    # build/twins/o4/<прогон>/drive.tsv, оси оригинала -> порта), и есть ли файл в их «загрузить»
    def inside(b, x, y, z):
        d = [x - b['c'][0], y - b['c'][1], z - b['c'][2]]
        return all(abs(sum(d[j] * b['R'][k][j] for j in range(3))) <= b['half'][k] + 0.5 for k in range(3)) or \
               all(abs(sum(d[j] * b['R'][j][k] for j in range(3))) <= b['half'][k] + 0.5 for k in range(3))
    track = {}
    for r in {m['run'] for m in P}:
        f = C.OUT / 'o4' / r / 'drive.tsv'
        if f.exists():
            rows = [l.split('\t') for l in f.read_text().splitlines()[1:]]
            track[r] = [(int(c[0]), float(c[1]), float(c[2]), -float(c[3])) for c in rows if len(c) > 3]
    entries = {}
    for r, tr in track.items():
        ev, was = [], set()
        for fr, x, y, z in tr:
            now = {g['name'] for g in G if any(inside(b, x, y, z) for b in g['boxes'])}
            for nm in now - was: ev.append((fr, nm))
            was = now
        entries[r] = ev
    match = []
    for r in P:
        px, pz = r['x'], -r['zo']
        cand = [(math.hypot(g['pos'][0] - px, g['pos'][2] - pz), g['name']) for g in G if r['file'] in g['load'] + g['room_in']]
        d, nm = min(cand) if cand else (None, '-')
        # въезд в ворота, у которых файл в «загрузить», в окне −3…+1 с от чтения (чтение начинается, когда кузов касается объёма;
        # бот пишет центр машины раз в 2 кадра — въезд центра отстаёт на 6–8 кадров)
        near = [(fr, g) for fr, g in entries.get(r['run'], []) if r['frame'] - 150 <= fr <= r['frame'] + 50
                and r['file'] in next(x for x in G if x['name'] == g)['load'] + next(x for x in G if x['name'] == g)['room_in']]
        last = min(near, key=lambda e: abs(e[0] - r['frame'])) if near else None
        match.append(dict(r, gate=nm, dist=d, last_gate=last[1] if last else '-', last_frame=last[0] if last else None, in_last=bool(last)))
    L = [f'# Атлас подгрузки оригинала · уровень {a.level}', '',
         f'Время (date): {C.clock()}. Источники: диск (локаторы вида 5 в l{a.level}_terra.p3d, AddTeleportDest в level.mfk) и прогоны',
         'своего PCSX2 (build/twins/b2/*/files.tsv). Оси порта (z = −z оригинала).', '',
         '## Как оригинал держит город в памяти', '',
         f'- [диск] Постоянно: l{a.level}_terra.p3d ({size.get(f"l{a.level}_terra.p3d", 0) // 1024} КБ) — земля и дороги всего уровня.',
         f'- [диск] Остальное разрезано на зоны l{a.level}z* и полосы l{a.level}r*. Наборы и размеры взяты из точек телепорта ниже:',
         '  точки телепорта несут ровно такой набор (ниже). Ворота на дорогах при въезде выгружают лишние файлы и грузят нужные.',
         '- [диск] Помещения lNi* грузятся воротами у дверей (знак «@»); конкретные загрузки и выгрузки в таблице ворот.',
         '- [PS2 L1] В tw_b2_hops файлы меняют ворота при езде, сам телепорт зоны не грузит; на другие уровни вывод не переносится.', '',
         '## Наборы в памяти по местам (AddTeleportDest)', '', '| место | x, z порта | файлы | КБ |', '|---|---|---|---|']
    for t in T:
        kb = sum(size.get(f, 0) for f in t['files']) // 1024
        L.append(f"| {t['name']} | {t['pos'][0]:.0f}, {t['pos'][2]:.0f} | {' '.join(t['files'])} | {kb} |")
    L += ['', f'## Ворота подгрузки ({len(G)})', '', '| ворота | x, z порта | загрузить | выгрузить | помещение |', '|---|---|---|---|---|']
    for g in G:
        L.append(f"| {g['name']} | {g['pos'][0]:.0f}, {g['pos'][2]:.0f} | {' '.join(x.replace('.p3d', '') for x in g['load'])} | "
                 f"{' '.join(x.replace('.p3d', '') for x in g['unload'])} | {' '.join(x.replace('.p3d', '') for x in g['room_in'] + g['room_out'])} |")
    ok = sum(m['in_last'] for m in match)
    L += ['', '## Сверка с ездой оригинала (PS2, свой PCSX2)', '',
          f'Чтений файлов зон в прогонах: {len(match)}; у {ok} из них бот въехал в ворота с этим файлом в «загрузить» в окне −3…+1 с от чтения.', '',
          '| прогон | файл | кадр чтения | место x, z порта | ворота (кадр въезда) | совпало | ближайшие ворота с файлом, м |',
          '|---|---|---|---|---|---|---|']
    for m in match:
        lf = f"{m['last_gate']} ({m['last_frame']})" if m['last_frame'] is not None else '—'
        nd = f"{m['gate']} {m['dist']:.0f}" if m['dist'] is not None else '—'
        L.append(f"| {m['run']} | {m['file']} | {m['frame']:.0f} | {m['x']:.0f}, {-m['zo']:.0f} | {lf} | {'да' if m['in_last'] else 'нет'} | {nd} |")
    # [диск] миссии: что грузит скрипт «доступна» (m*sdl.mfk — игрок ездит, миссия ждёт у дающего) и «идёт» (m*l.mfk)
    mdir = C.DATA / f'hit-and-run-web/source/game/scripts/missions/level0{a.level}'
    root = C.DATA / 'hit-and-run-web/source/game'
    def loads_of(f):
        out_ = []
        for m in re.finditer(r'(LoadP3DFile|LoadDisposableCar)\(\s*"([^"]+)"', f.read_text(errors='replace')):
            rel = m.group(2).replace('\\', '/'); p_ = root / rel
            out_.append((m.group(1), rel, p_.stat().st_size if p_.exists() else 0))
        return out_
    L += ['', '## Миссии: что грузит скрипт (диск)', '',
          'Файлы m<N>sdl.mfk — пока миссия доступна (игрок ездит, у дающего значок), m<N>l.mfk — когда миссия началась. Размеры — файлы диска.', '',
          '| скрипт | файлов | КБ | что |', '|---|---|---|---|']
    for f in sorted(mdir.glob('*l.mfk')):
        ls_ = loads_of(f)
        if not ls_: continue
        kb = sum(x[2] for x in ls_) // 1024
        what = ', '.join(Path(x[1]).stem + (' (машина ' + x[0][4:] + ')' if x[0] == 'LoadDisposableCar' else '') for x in ls_)
        L.append(f"| {f.name} | {len(ls_)} | {kb} | {what[:300]} |")
    (out / 'atlas.md').write_text('\n'.join(L) + '\n')
    (out / 'gates.json').write_text(json.dumps(dict(gates=G, teleports=T, loads=match, size=size), ensure_ascii=False, indent=1))
    print(f'ворот {len(G)}, мест {len(T)}, чтений зон близнецов {len(P)} → {out}/atlas.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
