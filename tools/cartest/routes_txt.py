#!/usr/bin/env python3
"""routes.txt для движка (пункт 12 docs/handoff/LOOP_TERMINAL.md): служебный обход трамплинов на PSP, в машине ↑ / ↓.
Только чтение: build/sandbox/routes-l1.tsv (пункт 9: имя, старт x y z, направление dx dz, кромка x y z, стекло),
build/sandbox/routes-result.json (пункт 10: perRamp.<имя>.bySpeed.<кмч>.ok/runs), камеры прыжков из routes-l1.json,
спавн уровня из заголовка build/level.shr (@36). Ни одной координаты руками. Только стандартная библиотека.

  python3 tools/cartest/routes_txt.py [--out build/routes.txt]

Формат routes.txt — текст, строка '#' — комментарий, по строке на трамплин (движок viewer/main.c читает до 64):
  имя x y z курс кмч метка
  x y z  старт разгона на дороге перед трамплином (м, координаты SHR); движок ставит туда машину carPlace, скорость 0
  курс   рад, на кромку: h = atan2(dx, dz) (нос машины идёт x += sin h, z += cos h, как в main.c и routes_run.c)
  кмч    рекомендуемая скорость на кромке: наибольшая доля удачных заездов ботов, при равенстве меньшая; 0 — удачных нет
  метка  камера прыжка оригинала (towerjump, kwikjump, ...) или '-'
Порядок: по кругу по карте (угол вокруг центра стартов), первым — ближайший к спавну. Непроходимые (0 удачных у ботов)
не выбрасываются: Роб проверяет все."""
import argparse
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
SB = ROOT / 'build/sandbox'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, default=ROOT / 'build/routes.txt')
    ap.add_argument('--level', type=Path, default=ROOT / 'build/level.shr')
    a = ap.parse_args()
    rows = [l.split('\t') for l in (SB / 'routes-l1.tsv').read_text().splitlines() if l.strip()]
    per = json.loads((SB / 'routes-result.json').read_text())['perRamp']
    cams = {r['name']: r['camera']['name'] for r in json.loads((SB / 'routes-l1.json').read_text())['ramps'] if r.get('camera')}
    ramps = []
    for name, st, d, lip, _glass in rows:
        x, y, z = map(float, st.split()); dx, dz = map(float, d.split()); lx, _, lz = map(float, lip.split())
        bs = per.get(name, {}).get('bySpeed')
        if not bs:
            sys.exit('routes_txt: нет результата ботов для ' + name)
        k, ok, runs = max(((int(s), v['ok'], v['runs']) for s, v in bs.items()), key=lambda t: (t[1] / t[2], -t[0]))
        ramps.append(dict(name=name, x=x, y=y, z=z, h=math.atan2(dx, dz), kmh=k if ok else 0, tag=cams.get(name, '-'),
                          run=math.hypot(lx - x, lz - z), ok=sum(v['ok'] for v in bs.values()), runs=sum(v['runs'] for v in bs.values())))
    sx = sz = None
    if a.level.exists():
        b = a.level.read_bytes()[:52]
        if b[:4] == b'SHR7':
            sx, _, sz = struct.unpack('<3f', b[36:48])
    cx = sum(r['x'] for r in ramps) / len(ramps); cz = sum(r['z'] for r in ramps) / len(ramps)
    ramps.sort(key=lambda r: math.atan2(r['z'] - cz, r['x'] - cx))
    if sx is not None:
        i0 = min(range(len(ramps)), key=lambda i: math.hypot(ramps[i]['x'] - sx, ramps[i]['z'] - sz))
        ramps = ramps[i0:] + ramps[:i0]
    for r in ramps:
        if len(r['name']) > 23 or len(r['tag']) > 23:
            sys.exit('routes_txt: имя длиннее 23 символов: ' + r['name'])
    head = [l[2:] if l.startswith('  ') else l for l in __doc__.splitlines()[7:15]]
    out = ['# routes.txt · служебный обход трамплинов (пункт 12), генератор tools/cartest/routes_txt.py, не править руками',
           '# источник: build/sandbox/routes-l1.tsv (пункт 9) + routes-result.json (пункт 10); спавн %s' %
           ('%.1f %.1f' % (sx, sz) if sx is not None else 'нет level.shr: порядок от угла 0')] + ['# ' + l for l in head]
    out += ['%s %.3f %.3f %.3f %.4f %d %s' % (r['name'], r['x'], r['y'], r['z'], r['h'] + 0.0 if abs(r['h']) > 5e-5 else 0.0, r['kmh'], r['tag']) for r in ramps]
    tmp = a.out.with_suffix('.tmp'); a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text('\n'.join(out) + '\n'); tmp.replace(a.out)
    for i, r in enumerate(ramps):
        print('%2d/%d %-11s %-13s разгон %4.1f м  лучше %3d км/ч  удачных %3d/%d' % (i + 1, len(ramps), r['name'], r['tag'], r['run'],
              r['kmh'], r['ok'], r['runs']))
    print('routes_txt: %d трамплинов -> %s' % (len(ramps), a.out.relative_to(ROOT) if a.out.is_relative_to(ROOT) else a.out))


if __name__ == '__main__':
    main()
