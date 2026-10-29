#!/usr/bin/env python3
"""Крыши уровня 1: достижимы с дороги или нет и почему (пункт 10б, вход пункта 11). Только читает итоги ботов.
  python3 tools/bots/roofs.py [DIR]      -> раздел "roofs" в build/sandbox/routes-result.json (раздел трамплинов perRamp пункта 10
                                          не трогается: из него собирается routes.txt) и build/sandbox/roofs-result.md; DIR — ночь ботов (night.json) или прогон
                                          tools/bots/explorer.py (explore.json); по умолчанию последняя ночь
Источник: каскадёр и пешеход (tools/bots/explorer.c) из естественных стартов (дорога, трамплины), ночь build/bots/nights/*.
Крыша достигнута = машина или Гомер стоит на площадке (опора, высота площадки −0.5…+3 м); повтор — файл нажатий.
Недостигнута — лучший подход за ночь: сколько по плоскости до площадки и сколько не хватило по высоте; «соседняя крыша
достигнута» — переход с неё (граф соседей в 15 м, build/sandbox/routes-l1.json) не найден."""
import json, os, sys
from pathlib import Path
ROOT = Path(os.environ.get('BOTS_ROOT') or Path(__file__).resolve().parents[2])   # ночь запускает замороженную копию скрипта (Т1.1)
IN = Path(os.environ.get('BOTS_IN') or ROOT / 'build')   # входы: общие build/ или замороженный комплект ночи


def reason(a):
    if not a: return 'ни разу не подъехал ближе ~16 м'
    d, h = a['d'], a['h']
    if d < 1.0 and h > 0.5: return f'стоял под площадкой, не хватило {h:.1f} м высоты'
    if d < 1.0: return 'был над площадкой только в воздухе, не встал на неё'
    return f'ближе {d:.1f} м не подъехал' + (f', не хватило {h:.1f} м высоты' if h > 0.5 else '')


def main():
    nights = sorted(p for p in (ROOT / 'build/bots/nights').glob('*/night.json') if not p.parent.name.endswith('-gate'))
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else nights[-1].parent
    if (d / 'night.json').exists():
        src = d / 'night.json'; S = json.loads(src.read_text()); E = S['explore']
    else:   # прогон explorer.py
        src = d / 'explore.json'; X = json.loads(src.read_text())
        S = dict(started=src.parent.name); E = dict(reached={r['name']: r for r in X['rows'] if r['replay']}, approach=X.get('approach'))
    A = E.get('approach')   # None — ночь до 10б, подходы не писались
    if not E.get('reached') and not A:   # в источнике нет каскадёра (день, пустой прогон) — не затирать таблицу крыш
        print(f'roofs: в {src} нет данных каскадёра — таблицу крыш не трогаю'); return 1
    graph = {r['id']: r for r in json.loads((IN / 'sandbox/routes-l1.json').read_text())['roofs']}
    rows = []
    for i, g in sorted(graph.items()):
        n = f'roof{i}'; r = E['reached'].get(n)
        row = dict(id=i, name=n, x=g['x'], y=g['y'], z=g['z'], aboveGroundM=g['aboveGroundM'], areaM2=g['areaM2'], reachable=bool(r))
        if r: row.update(seconds=r['t'], onFoot=bool(r['foot']), repro=r['repro'])
        else:
            nb = [f"roof{x['id']}" for x in g['neighbours'] if f"roof{x['id']}" in E['reached']]
            row.update(why=reason(A.get(n)) if A is not None else 'подход не записан (ночь до 10б)', approach=(A or {}).get(n), reachedNeighbours=nb)
        rows.append(row)
    got = sum(r['reachable'] for r in rows)
    res = dict(source=str(src.resolve().relative_to(ROOT)), night=S['started'], roofs=len(rows), reachable=got,
               onFoot=sum(1 for r in rows if r.get('onFoot')), rows=rows)
    out = ROOT / 'build/sandbox/routes-result.json'
    old = json.loads(out.read_text()) if out.exists() else {}
    if 'perRamp' not in old: print('внимание: в routes-result.json нет perRamp (пункт 10) — python3 tools/cartest/routes_bots.py')
    old['roofs'] = res; out.write_text(json.dumps(old, ensure_ascii=False, indent=1))   # дописать раздел, остальное как было
    by = {}
    for r in rows:
        if not r['reachable']:
            w = r['why']; k = ('не подъезжал ближе 16 м' if w.startswith('ни ') else 'стоял под площадкой' if w.startswith('стоял') else
                               'был над площадкой только в воздухе' if w.startswith('был') else 'не подъехал к площадке' if w.startswith('ближе') else w)
            by[k] = by.get(k, 0) + 1
    L = [f"# Крыши уровня 1: достижимость с дороги (ночь ботов {S['started']})", '',
         f"Достижимы {got} из {len(rows)} (пешком {res['onFoot']}); недостижимы {len(rows) - got}: " + ', '.join(f'{k} — {v}' for k, v in sorted(by.items(), key=lambda kv: -kv[1])), '',
         '| крыша | над землёй, м | итог | повтор / почему |', '|---|---|---|---|'] + [
         f"| {r['name']} ({r['x']:.0f} {r['z']:.0f}) | {r['aboveGroundM']:.1f} | " + (f"за {r['seconds']:.0f} с{' пешком' if r['onFoot'] else ''} | `{r['repro']}` |" if r['reachable'] else
         f"нет | {r['why']}{'; соседняя достигнута: ' + ', '.join(r['reachedNeighbours'][:3]) if r['reachedNeighbours'] else ''} |") for r in rows]
    md = ROOT / 'build/sandbox/roofs-result.md'; md.write_text('\n'.join(L) + '\n')
    print('\n'.join(L[:3])); print('->', out, '(раздел roofs),', md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
