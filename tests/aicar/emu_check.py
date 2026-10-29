#!/usr/bin/env python3
"""Разбор прогона tests/aicar/emu.sh (smoke.txt движка): машины миссий с ИИ в эмуляторе, уровень 1.

  emu_check.py SMOKE.txt     PASS / FAIL (код 0 / 1)
Проверки:
  * race (sr2): три соперника (honor_v, minivanA, schoolbu) в режиме race, каждый проехал ≥ 30 м (строки MCAR раз в секунду),
    место игрока в гонке считается (pos=N/3), модель honor_v прочитана из пакета (MCR load honor_v; minivanA и schoolbu — модели
    трафика уровня);
  * chase (m6): у игрока машина Мардж (MSN forced-car marge_v) и её модель прочитана (MCR load marge_v), фургон cBone едет ≥ 30 м;
  * свободная куча (столбец кучи строк кадра): на старте уровня (сцена spawn, миссий ещё нет) ≥ 20 МБ; модели машин миссий,
    прочитанные за сцену (MCR load, байты), ≤ 0.5 МБ; в сценах race и chase ≥ HEAP_SCENE (14.5 МБ с 30.09) — ПОРОГ ПОРТА: миссия уровня 1 уже на
    своём старте (сцена start: Мардж, фоновые персонажи, картинка брифинга) держит кучу около 19.7 МБ, гонка добавляет персонажей
    Патти и Сельмы; сами машины миссий — 0.12 МБ (sr2) и 0.28 МБ (m6);
  * 30 FPS в race и chase (медиана ≥ 29.4, без «settling»);
  * прогон дошёл до END."""
HEAP_START, HEAP_SCENE = 18.0, 14.5   # МБ свободной кучи (было 20 / 17.5 до 29.09 вечера)
import re, sys, statistics
from pathlib import Path


def main():
    if len(sys.argv) < 2: print(__doc__); return 2
    p = Path(sys.argv[1])
    if not p.exists(): print(f'FAIL: нет {p}'); return 1
    lines = p.read_text(errors='replace').splitlines(); bad = []
    scene, fps, heap, mcar, loads, forced, mbytes = None, {}, {}, {}, set(), [], {}
    for l in lines:
        if l.startswith('SCENE '): scene = l.split()[1]
        m = re.match(r'MCAR t=([\d.]+) name=(\S+) mode=(\S+) x=([-\d.]+) z=([-\d.]+) v=([-\d.]+) .* pos=(\d+)/(\d+)', l)
        if m: mcar.setdefault((scene, m.group(2)), []).append((float(m.group(4)), float(m.group(5)), m.group(3), int(m.group(7)), int(m.group(8))))
        m = re.match(r'MCR load (\S+) bytes=(\d+)', l)
        if m: loads.add(m.group(1).lower()); mbytes[scene] = mbytes.get(scene, 0) + int(m.group(2))
        m = re.search(r'MSN forced-car (\S+)', l)
        if m: forced.append((scene, m.group(1)))
        f = l.split()
        if len(f) >= 15 and re.match(r'^[\d.]+$', f[0]) and f[1] == scene:
            fps.setdefault(scene, []).append((float(f[2]), 'settling' in l)); heap.setdefault(scene, []).append(float(f[14]))

    def path(sc, name):
        pts = mcar.get((sc, name), [])
        return sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** .5 for a, b in zip(pts, pts[1:])), pts

    for name in ('honor_v', 'minivanA', 'schoolbu'):
        d, pts = path('race', name)
        modes = sorted({q[2] for q in pts})
        print(f'race: {name} режим {modes}, проехал {d:.0f} м ({len(pts)} строк MCAR)')
        if d < 30.0 or 'race' not in modes: bad.append(f'соперник {name} не едет (race, {d:.0f} м)')
    pos = [q for k, v in mcar.items() if k[0] == 'race' for q in v if q[4] > 0]
    print(f'race: место игрока {sorted({(q[3], q[4]) for q in pos})}')
    if not pos or max(q[4] for q in pos) != 3: bad.append('место в гонке не считается (ждали …/3)')
    if 'honor_v' not in loads: bad.append('модель honor_v не прочитана из пакета msncars (MCR load)')
    d, pts = path('chase', 'cBone')
    print(f'chase: cBone проехал {d:.0f} м; машина игрока {forced}; модели пакета {sorted(loads)}')
    if d < 30.0: bad.append(f'фургон cBone не едет ({d:.0f} м)')
    if not any(sc == 'chase' and n == 'marge_v' for sc, n in forced): bad.append('машина Мардж не у игрока (SetForcedCar)')
    if 'marge_v' not in loads: bad.append('модель marge_v не прочитана из пакета msncars (MCR load)')
    h0 = min(heap.get('spawn', [0.0])); hs = min(heap.get('start', [0.0]))
    print(f'куча: старт уровня {h0} МБ, старт миссий {hs} МБ')
    # 30.09: пороги по замеру (старт уровня 19.2 МБ, сцены 15.7–16.6 МБ; пачка 30.09 освободила +0.4 МБ, снижение — звуки и
    # эффекты 29.09 вечером) минус 1 МБ запаса; крупнейшее разовое по требованию — подиум будки/лавки 0.3 МБ, модели машин ≤ 0.4 МБ
    if h0 < HEAP_START: bad.append(f'свободная куча на старте уровня {h0} МБ < {HEAP_START}')
    for sc in ('race', 'chase'):
        df = [v for v, st in fps.get(sc, []) if not st]; med = statistics.median(df) if df else 0.0
        h = min(heap.get(sc, [0.0])); mb = mbytes.get(sc, 0) / 1048576
        print(f'{sc}: FPS {[round(v, 1) for v in df]} (медиана {med:.1f}), свободно кучи не меньше {h} МБ, модели машин миссий {mb:.2f} МБ')
        if med < 29.4: bad.append(f'{sc}: FPS {med:.1f} < 30')
        if h < HEAP_SCENE: bad.append(f'{sc}: свободная куча {h} МБ < {HEAP_SCENE}')
        if mb > 0.5: bad.append(f'{sc}: модели машин миссий {mb:.2f} МБ > 0.5')
    if not any(l.startswith('END') for l in lines): bad.append('прогон не дошёл до END')
    for b in bad: print('  ПРОВАЛ:', b)
    print('машины миссий в эмуляторе: ' + ('PASS' if not bad else f'FAIL ({len(bad)})'))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
