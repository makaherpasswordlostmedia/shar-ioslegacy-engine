#!/usr/bin/env python3
"""Разбор прогона tests/rooms/emu_scenario.txt в эмуляторе (пункт 11.2, tests/rooms/emu.sh). Строки движка (viewer/main.c):
  ROOMS pkg=ok rooms=N doors=N gfx=N                      пакеты комнат прочитаны (gfx — комнат с рисованием)
  ROOM ev=enter room=ИМЯ n=K heap0=Б heap=Б bytes=Б ...   вход: свободная куча до и после чтения блоба (smoke.h heapFreeBytes)
  ROOM ev=exit room=ИМЯ n=K heap=Б ... pos=x,y,z          выход: куча после освобождения, Гомер у двери в городе
  ROOM ev=fail room=ИМЯ err=E                            блоб не открылся — дверь не открывается
  HOMER t=.. pos=x,y,z h=.. room=ИМЯ|-                    раз в секунду, пока Гомер пешком
  строки раз в секунду (FPS, tris …) и STAT по сценам     — как у tools/smoke.sh
  emu_check.py ОТЧЁТ [--smoke-rc N]                        зелёный гейт: 0 = PASS
  emu_check.py ОТЧЁТ --smoke-rc N --expect-broken empty|garbled   красный: зелёный обязан упасть, игра цела, Гомер на улице
  emu_check.py --break empty|garbled ФАЙЛ                  испортить пакет рисования (копию!) для красного прогона"""
import sys, struct, argparse
from pathlib import Path

ROOMS = ('KwikEMart', 'SpringfieldElementary', 'SimpsonsHouse')
SHOTS_IN = {'KwikEMart': 'kwik_in', 'SpringfieldElementary': 'school_in', 'SimpsonsHouse': 'house_in'}
KWIK_CYCLES, HEAP_TOL, ROOM_TRIS_MAX = 5, 64 * 1024, 12000


def kv(line):
    return dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)


def parse(rep):
    log = (rep / 'smoke.txt').read_text().splitlines()
    ev, homer, fps, scene = [], [], [], None
    for l in log:
        p = l.split()
        if not p: continue
        if p[0] == 'SCENE': scene = p[1]; continue
        if p[0] == 'ROOM': ev.append(kv(l)); continue
        if p[0] == 'HOMER': d = kv(l); d['scene'] = scene; homer.append(d); continue
        try:
            fps.append(dict(scene=p[1], fps=float(p[2]), tris=int(p[6]), settling=p[-1] == 'settling'))
        except (ValueError, IndexError): pass
    rooms = next((kv(l) for l in log if l.startswith('ROOMS ')), {})
    return log, rooms, ev, homer, fps


def green(rep, smoke_rc):
    """-> список провалов (пусто = PASS) и сводка"""
    log, rooms, ev, homer, fps = parse(rep)
    bad, info = [], []
    if smoke_rc != 0: bad.append(f'tools/smoke.sh код {smoke_rc} (FPS, длинные кадры, куча — summary.txt)')
    if not any(l.startswith('END') for l in log): bad.append('нет END: упала или зависла')
    if rooms.get('pkg') != 'ok' or rooms.get('gfx') != '3': bad.append(f'пакеты комнат: {rooms or "нет строки ROOMS"}')
    for name in ROOMS:
        en = [e for e in ev if e.get('ev') == 'enter' and e.get('room') == name]; ex = [e for e in ev if e.get('ev') == 'exit' and e.get('room') == name]
        need = KWIK_CYCLES if name == 'KwikEMart' else 1
        if len(en) < need or len(ex) < need: bad.append(f'{name}: входов {len(en)}, выходов {len(ex)}, нужно по {need}')
        pairs = list(zip(en, ex))
        for k, (a, b) in enumerate(pairs):
            d = int(b['heap']) - int(a['heap0'])
            if abs(d) > HEAP_TOL: bad.append(f'{name} круг {k + 1}: куча после выхода {int(b["heap"]) / 2**20:.3f} МБ, до входа {int(a["heap0"]) / 2**20:.3f} МБ ({d:+d} Б)')
            y = float(b['pos'].split(',')[1])
            if y < -5: bad.append(f'{name} круг {k + 1}: после выхода Гомер не в городе (y {y})')
        if pairs:   # утечка — то, что комната не вернула: куча после выхода минус до входа того же круга (между кругами
                    # куча меняется от подгрузки клеток города — это не комната); сумма по кругам — накопленная утечка
            deltas = [int(b['heap']) - int(a['heap0']) for a, b in pairs]
            info.append(f'{name}: кругов {len(pairs)}, блоб {int(en[0]["bytes"]) / 1024:.0f} КБ, текстур {en[0]["tex"]}, кусков {en[0]["pieces"]}, '
                        f'чтение {en[0]["ms"]} мс; куча свободна: до входа {int(pairs[0][0]["heap0"]) / 2**20:.3f} МБ, в комнате '
                        f'{int(en[0]["heap"]) / 2**20:.3f} МБ; после выхода минус до входа по кругам {", ".join(f"{d / 1024:+.0f}" for d in deltas)} КБ')
            if sum(deltas) < -HEAP_TOL: bad.append(f'{name}: накопленная утечка {sum(deltas) / 1024:+.0f} КБ за {len(pairs)} кругов')
        sc = SHOTS_IN[name]
        png = rep / f'{sc}.png'
        if not png.exists(): bad.append(f'нет снимка {png.name}')
        else:
            from PIL import Image, ImageStat
            im = Image.open(png).convert('L'); w, h = im.size; st = ImageStat.Stat(im.crop((0, int(h * .1), w, h)))
            if st.stddev[0] < 20: bad.append(f'{png.name}: кадр почти однотонный (σ {st.stddev[0]:.0f}) — комната не нарисована')
        hs = [x for x in homer if x['scene'] == sc]
        if not hs or any(x.get('room') != name for x in hs): bad.append(f'сцена {sc}: Гомер не в комнате {name} ({[x.get("room") for x in hs][:6]})')
        rows = [r for r in fps if r['scene'] == sc and not r['settling']][1:]
        if rows:
            tmax, fmin = max(r['tris'] for r in rows), min(r['fps'] for r in rows); favg = sum(r['fps'] for r in rows) / len(rows)
            info.append(f'  сцена {sc}: FPS ср. {favg:.1f} (мин {fmin:.1f}), треуг. до {tmax / 1000:.1f}k')
            if tmax > ROOM_TRIS_MAX: bad.append(f'сцена {sc}: {tmax} треуг. в кадре — рисуется город, не комната')
            if favg < 30 * 0.98: bad.append(f'сцена {sc}: FPS {favg:.1f} < 30')
        else: bad.append(f'сцена {sc}: нет строк FPS')
    return bad, info


def broken(rep, smoke_rc, kind):
    """красный прогон: зелёный обязан упасть; игра цела, в сломанную комнату не вошли, Гомер у двери на улице"""
    bad_g, _ = green(rep, smoke_rc)
    log, rooms, ev, homer, fps = parse(rep)
    bad = []
    if not bad_g: bad.append('зелёная проверка прошла на битом пакете — гейт ничего не ловит')
    if not any(l.startswith('END') for l in log): bad.append('нет END: игра упала на битом пакете')
    if kind == 'empty' and rooms.get('gfx') != '0': bad.append(f'пустой пакет рисования принят: {rooms}')
    if kind == 'garbled' and not any(e.get('ev') == 'fail' and e.get('room') == 'KwikEMart' for e in ev): bad.append('битый блоб Kwik-E-Mart не отвергнут (нет ROOM ev=fail)')
    broken_rooms = ROOMS if kind == 'empty' else ('KwikEMart',)
    if any(e.get('ev') == 'enter' and e.get('room') in broken_rooms for e in ev): bad.append('вошёл в комнату без рисования')
    near = [x for x in homer if x['scene'] in ('start', 'kwik_in')]
    if not near or any(x.get('room') != '-' or float(x['pos'].split(',')[1]) < 0 for x in near): bad.append('Гомер у Kwik-E-Mart не остался на улице')
    return bad, [f'зелёная проверка упала, как должна: {bad_g[0]}' if bad_g else '']


def cams(rep):
    """прогон tests/rooms/emu_cams.txt: в каждой сцене камеры движок снимал именно ей (строки HOMER cam=), снимок есть"""
    log, rooms, ev, homer, fps = parse(rep)
    scn = [l.split()[1] for l in (rep / 'scenario.txt').read_text().splitlines() if l.startswith('scene ') and l.split()[1][:3] in ('kc0', 'kc1', 'se_', 'sh_')]
    full = lambda s: s.replace('kc', 'int_kwik_camera', 1) if s.startswith('kc') else 'int_ele_' + s[3:] if s.startswith('se_') else 'int_sh_' + s[3:]
    bad, ok = [], 0
    if not any(l.startswith('END') for l in log): bad.append('нет END: упала или зависла')
    for s in scn:
        got = [x.get('cam') for x in homer if x['scene'] == s]
        if not got or any(g != full(s) for g in got): bad.append(f'{s}: ждали {full(s)}, движок снимал {sorted(set(got)) or "—"}')
        elif not (rep / f'{s}.png').exists(): bad.append(f'{s}: нет снимка')
        else: ok += 1
    return bad, [f'камер снято своими триггерами: {ok} из {len(scn)}']


def breakfile(kind, path):
    p = Path(path)
    if kind == 'empty': p.write_bytes(b''); return
    b = bytearray(p.read_bytes()); n, = struct.unpack_from('<I', b, 4)
    for i in range(n):
        name = b[16 + 48 * i:16 + 48 * i + 32].split(b'\0')[0].decode()
        off, = struct.unpack_from('<I', b, 16 + 48 * i + 32)
        if name == 'KwikEMart': b[off:off + 4] = b'XXXX'
    p.write_bytes(bytes(b))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('rep', nargs='?'); ap.add_argument('file', nargs='?')
    ap.add_argument('--smoke-rc', type=int, default=0); ap.add_argument('--expect-broken', choices=('empty', 'garbled'))
    ap.add_argument('--break', dest='brk', choices=('empty', 'garbled')); ap.add_argument('--cams', action='store_true', help='прогон emu_cams.txt')
    a = ap.parse_args()
    if a.brk: breakfile(a.brk, a.rep); return 0
    rep = Path(a.rep)
    bad, info = cams(rep) if a.cams else broken(rep, a.smoke_rc, a.expect_broken) if a.expect_broken else green(rep, a.smoke_rc)
    for l in info:
        if l: print(l)
    for l in bad: print('  ПРОВАЛ:', l)
    print(('PASS' if not bad else 'FAIL') + (f' (красный: {a.expect_broken})' if a.expect_broken else '') + f' — {rep}')
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
