#!/usr/bin/env python3
"""Гейт «свет уровня» по данным (29.09, docs/РЕЦЕПТ_УРОВНЯ.md §12): блок света уровня N в файлах = диску, машины запечены им.

  light_check.py --level N [N ...] [--shr P] [--traffic P]   PASS / FAIL (код 0 / 1)
  light_check.py --level 1 --same-as P                       + уровень 1 побайтно прежний, кроме CAR1 (v3 + LGT1) и смещения PVS1
  light_check.py --chunks                                    разбор 0x13008 и 0x12110f на всём диске (см. ниже)
  light_check.py --chunks --plant-13008 / --plant-12110f     красные: подложенное значение не проходит

Проверки уровня N (level.shr: build/levels/l<N>/level.shr, у уровня 1 — build/level.shr; traffic.shr — рядом):
  * CAR1 версии 3, блок LGT1 цел (сумма), уровень = N, группа sun; фон и 3 направленных (цвет побайтно, направление ±1e-4) =
    группа sun в art/l<N>_terra.p3d; множители ambS/dirS = отношение к уровню 1 (±1e-5) — tools/level_light.py;
  * TRF1: поле @156 -> тот же блок LGT1 уровня N (до сведения 03.10 — @148, там теперь nLoader правки 139);
  * машина игрока: средний цвет вершин её кусков (owner 1, ближняя версия) = светотень car_prims со светом уровня N (±2%
    по каждому каналу, 5650 у части кусков) и НЕ = светотени дня уровня 1 (на уровнях, где свет отличается больше чем на 10%);
  * машина трафика (модель 0 TRF1): то же.
Красные (сначала увидеть их): --shr build/levels/l6/level_pre_light.shr (день: CAR1 v2, машина в свете уровня 1);
--plant-lgt1 1 (в LGT1 файла уровня 6 — дневной блок уровня 1, сумма пересчитана); --traffic с трафиком до 29.09.
--chunks: 0x13008 — u32 = 1 у каждого источника 0x13000, где он есть (35 на диске, из них 21 в файлах уровней); 0x12110f — 8 байт
00000000 '1.15' у каждого канала 0x121105 (398 на диске: постоянная метка, значения анимации в ней нет)."""
import argparse, json, os, struct, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
import level_light as ll   # noqa: E402

TOL_DIR, TOL_S, TOL_COL = 1e-4, 1e-5, 0.02


def default(level, name):
    if level == 1 and (ROOT / 'build' / name).exists(): return ROOT / 'build' / name
    return ROOT / f'build/levels/l{level}/{name}'


def shr_car1(b):
    c1, = struct.unpack_from('<I', b, 100); pvs, = struct.unpack_from('<I', b, 88)
    if not c1 or b[c1:c1 + 4] != b'CAR1': return None, c1
    end = pvs if pvs > c1 else len(b)
    return b[c1:end], c1


def cmp_light(got, want, where):
    bad = []
    if got['level'] != want['level']: bad.append(f'{where}: уровень {got["level"]} != {want["level"]}')
    if got['group'] != want['group']: bad.append(f'{where}: группа {got["group"]} != {want["group"]}')
    if tuple(got['amb']) != tuple(want['amb']): bad.append(f'{where}: фон {got["amb"]} != диск {want["amb"]}')
    if len(got['dirs']) != len(want['dirs']): bad.append(f'{where}: направленных {len(got["dirs"])} != диск {len(want["dirs"])}')
    for i, ((gv, gc), (wv, wc)) in enumerate(zip(got['dirs'], want['dirs'])):
        if tuple(gc) != tuple(wc): bad.append(f'{where}: источник {i} цвет {gc} != диск {wc}')
        if max(abs(a - b) for a, b in zip(gv, wv)) > TOL_DIR: bad.append(f'{where}: источник {i} направление {gv} != диск {wv}')
    for k in ('ambS', 'dirS'):
        if max(abs(a - b) for a, b in zip(got[k], want[k])) > TOL_S: bad.append(f'{where}: {k} {got[k]} != {want[k]}')
    return bad


def vcols(b, base, fl, cnt):
    """цвета вершин куска (R, G, B 0..255): 16 Б — ABGR8888 @4; 12 Б (флаг 32) — 5650 @4"""
    if fl & 32:
        c = np.frombuffer(b, np.uint8, cnt * 12, base).reshape(cnt, 12)[:, 4:6].copy().view('<u2').ravel().astype(np.int64)
        return np.stack([(c & 31) * 255 / 31, ((c >> 5) & 63) * 255 / 63, ((c >> 11) & 31) * 255 / 31], 1)
    c = np.frombuffer(b, np.uint8, cnt * 16, base).reshape(cnt, 16)[:, 4:8].copy().view('<u4').ravel().astype(np.int64)
    return np.stack([c & 255, (c >> 8) & 255, (c >> 16) & 255], 1).astype(np.float64)


def shr_car_colours(b):
    """средний цвет вершин кусков машины игрока (owner 1, вариант 0 — не остов), ближняя версия"""
    npc, = struct.unpack_from('<I', b, 8); ptab, = struct.unpack_from('<I', b, 76); ncell, ctab = struct.unpack_from('<II', b, 80)
    cells = [struct.unpack_from('<6fIIIII', b, ctab + 48 * i) for i in range(ncell)]
    acc = []
    for i in range(npc):
        r = struct.unpack_from('<6fiIIII3ffIII2I', b, ptab + 80 * i)
        tex, fl, nv, ni, own = r[6:11]; off, nf, ci = r[15:18]; variant = r[19]
        if own != 1 or variant != 0 or not ni or not fl & 16: continue
        acc.append(vcols(b, cells[ci][9] + off, fl, ni))
    return np.concatenate(acc).mean(0) if acc else None


def trf_lgt1(b):
    off, = struct.unpack_from('<I', b, 156)   # @156 с 03.10 (сведение со 139: nLoader @148, offLoader @152)
    return ll.parse_block(b[off:off + ll.LGT1_LEN]) if off else None


def trf_model0_colours(b):
    f = struct.unpack_from('<35I', b, 12)
    offModel, offPiece, vertOff = f[9], f[11], f[12]
    name = b[offModel:offModel + 16].split(b'\0')[0].decode()
    first, n = struct.unpack_from('<HH', b, offModel + 16)
    acc = []
    for i in range(first, first + n):
        r = struct.unpack_from('<6fiIIII3ffIII', b, offPiece + 80 * i)
        fl, ni, off = r[7], r[9], r[15]
        if ni and fl & 16: acc.append(vcols(b, vertOff + off, fl, ni))
    return name, (np.concatenate(acc).mean(0) if acc else None)


_bake = {}
def baked_mean(carp, light, traffic=False):
    """средний цвет светотени car_prims (как экспорт): игрок — оси суставов (+ остов не берём); трафик — кузов в позе покоя,
    колёса в осях колеса"""
    key = (str(carp), light['level'], traffic)
    if key in _bake: return _bake[key]
    os.environ.setdefault('SHR_TMP', str(ROOT / 'build/tmp_conv/light_check'))
    import psp_export as pe, re
    conv = pe.Converter(); conv.export(carp, 'lc_car', vehicle=True)
    meta = json.loads((pe.OUT / 'lc_car.json').read_text()); raw = (pe.OUT / 'lc_car.bin').read_bytes()
    for ext in ('json', 'bin'): (pe.OUT / f'lc_car.{ext}').unlink()
    cache, blob = {}, []
    if traffic:
        body = [p for p in pe.car_prims(meta, raw, cache, blob, True, light) if not re.fullmatch(r'w[0-3]', p[0])]
        wheels = [p for p in pe.car_prims(meta, raw, cache, blob, False, light) if re.fullmatch(r'w[0-3]', p[0])]
        prims = body + wheels
    else: prims = pe.car_prims(meta, raw, cache, blob, False, light)
    C = np.concatenate([p[5] for p in prims]).astype(np.int64)
    m = np.stack([C & 255, (C >> 8) & 255, (C >> 16) & 255], 1).astype(np.float64).mean(0)
    _bake[key] = m
    return m


def col_ok(got, want): return got is not None and bool(np.all(np.abs(got / np.maximum(want, 1e-9) - 1) <= TOL_COL))


def check_level(level, shr=None, traffic=None, plant=None):
    bad = []; want = ll.level_light(level); day = ll.level_light(1)
    shr = Path(shr or default(level, 'level.shr')); traffic = Path(traffic or default(level, 'traffic.shr'))
    b = bytearray(shr.read_bytes())
    car1, c1 = shr_car1(b)
    if car1 is None: return [f'уровень {level}: в {shr.name} нет CAR1']
    ver, = struct.unpack_from('<I', car1, 4)
    if plant:   # отрицательный контроль: в LGT1 файла — блок уровня plant (сумма пересчитана, файл цел)
        if ver < 3: return [f'уровень {level}: подложить некуда — CAR1 версии {ver}']
        io, il = struct.unpack_from('<2I', car1, 24); o = c1 + io + il
        b[o:o + ll.LGT1_LEN] = ll.block(dict(ll.level_light(plant), level=level)); car1, _ = shr_car1(b)
        print(f'  (подложено: в LGT1 уровня {level} — свет уровня {plant})')
    if ver < 3: bad.append(f'уровень {level}: CAR1 версии {ver} — блока света LGT1 нет (свет уровня 1 на всех уровнях)')
    else:
        try: got = ll.car1_light(car1)
        except ValueError as e: got = None; bad.append(f'уровень {level}: LGT1 битый: {e}')
        if got:
            e = cmp_light(got, want, f'уровень {level} LGT1 level.shr'); bad += e
            print(f'уровень {level}: LGT1 level.shr — фон {got["amb"]}, направленных {len(got["dirs"])}, ambS {tuple(round(x, 3) for x in got["ambS"])}, '
                  f'dirS {tuple(round(x, 3) for x in got["dirS"])} — ' + ('= диск' if not e else 'НЕ как на диске'))
    # машина игрока: светотень в файле = свет уровня
    io, il = struct.unpack_from('<2I', car1, 24)
    car = car1[io:io + 16].split(b'\0')[0].decode() if ver >= 2 else 'famil_v'
    import psp_export as pe
    carp = pe.car_model(level, car)
    got_c = shr_car_colours(bytes(b)); exp_c = baked_mean(carp, want); day_c = baked_mean(carp, day)
    far_from_day = bool(np.any(np.abs(exp_c / day_c - 1) > .10))
    ok = col_ok(got_c, exp_c)
    print(f'уровень {level}: машина {car} — средний цвет кусков {np.round(got_c, 1) if got_c is not None else None}, '
          f'свет уровня даёт {np.round(exp_c, 1)}, день уровня 1 — {np.round(day_c, 1)}: ' + ('свет уровня' if ok else 'НЕ свет уровня'))
    if not ok: bad.append(f'уровень {level}: машина {car} запечена не светом уровня {level} (цвет {np.round(got_c, 1) if got_c is not None else None} против {np.round(exp_c, 1)})')
    if far_from_day and col_ok(got_c, day_c): bad.append(f'уровень {level}: машина {car} запечена дневным светом уровня 1')
    # трафик
    if not traffic.exists(): bad.append(f'уровень {level}: нет {traffic}')
    else:
        t = traffic.read_bytes()
        try: tl = trf_lgt1(t)
        except ValueError as e: tl = None; bad.append(f'уровень {level}: LGT1 в TRF1 битый: {e}')
        if tl is None: bad.append(f'уровень {level}: в TRF1 нет блока света LGT1 (@156 = 0: трафик без блока)')
        else:
            e = cmp_light(tl, want, f'уровень {level} LGT1 traffic.shr'); bad += e
            print(f'уровень {level}: LGT1 traffic.shr — ' + ('= диск' if not e else 'НЕ как на диске'))
        name, got_t = trf_model0_colours(t)
        tp = pe.GAME / 'art' / 'cars' / f'{name.lower()}.p3d'
        exp_t = baked_mean(tp, want, True); day_t = baked_mean(tp, day, True)
        ok = col_ok(got_t, exp_t)
        print(f'уровень {level}: трафик {name} — средний цвет {np.round(got_t, 1) if got_t is not None else None}, свет уровня даёт {np.round(exp_t, 1)}: '
              + ('свет уровня' if ok else 'НЕ свет уровня'))
        if not ok: bad.append(f'уровень {level}: машина трафика {name} запечена не светом уровня {level}')
        if far_from_day and col_ok(got_t, day_t): bad.append(f'уровень {level}: машина трафика {name} запечена дневным светом уровня 1')
    return bad


def same_as(new, old):
    """уровень 1: всё до CAR1 побайтно то же (кроме смещения PVS1 @88: куски, в том числе светотень машины); CAR1 — то же тело
    (у прежней v2 и тот же блок машины), версия 3 и LGT1 за блоком машины; PVS1 тот же"""
    a, b = Path(old).read_bytes(), Path(new).read_bytes(); bad = []
    ca, cb = struct.unpack_from('<I', a, 100)[0], struct.unpack_from('<I', b, 100)[0]
    pa, pb = struct.unpack_from('<I', a, 88)[0], struct.unpack_from('<I', b, 88)[0]
    if ca != cb: bad.append(f'CAR1 сдвинулась {ca} -> {cb}')
    ha, hb = bytearray(a[:ca]), bytearray(b[:cb]); struct.pack_into('<I', ha, 88, 0); struct.pack_into('<I', hb, 88, 0)
    if ha != hb: bad.append(f'до CAR1 отличается {sum(x != y for x, y in zip(ha, hb))} Б')
    A, B = bytes(a[ca:pa]), bytes(b[cb:pb])
    va, vb = struct.unpack_from('<I', A, 4)[0], struct.unpack_from('<I', B, 4)[0]
    io, il = struct.unpack_from('<2I', B, 24)
    if vb != 3: bad.append(f'CAR1 версии {vb}, ждали 3')
    if A[8:24] != B[8:24]: bad.append('CAR1: числа суставов/шарниров/урона/бликов другие')
    body = io if va < 2 else struct.unpack_from('<I', A, 24)[0]   # тело секции до блока машины (v1 — всё, без хвостового выравнивания)
    if B[32:body].rstrip(b'\0') != A[32:body].rstrip(b'\0'): bad.append('CAR1: тело (суставы, шарниры, урон, блики) отличается')
    if va >= 2 and B[io:io + il] != A[io:io + il]: bad.append('CAR1: блок машины отличается')
    if B[io + il:io + il + 4] != b'LGT1': bad.append('за блоком машины нет LGT1')
    if a[pa:] != b[pb:]: bad.append('PVS1 отличается')
    print(f'уровень 1 против прежнего: CAR1 {len(A)} -> {len(B)} Б, PVS1 {pa} -> {pb}; ' + ('отличие только в CAR1 (v3 + LGT1)' if not bad else '; '.join(bad)))
    return bad


def chunks(plant=None):
    """0x13008 и 0x12110f на всём диске (art/**/*.p3d)"""
    from p3d import read, walk, string
    G = ll.GAME
    files = sorted(G.glob('art/**/*.p3d'))
    n8 = n15 = 0; bad = []
    for p in files:
        try: root = read(p)
        except Exception: continue
        planted = False
        for c in walk(root):
            for s in c.children:
                if s.id == 0x13008:
                    if plant == '13008' and not planted: s.data = struct.pack('<I', 2); planted = True
                    n8 += 1
                    if c.id != 0x13000: bad.append(f'{p.name}: 0x13008 не под источником света ({hex(c.id)})')
                    v, = struct.unpack_from('<I', s.data)
                    if v != ll.ILLUM_OK: bad.append(f'{p.name}: 0x13008 = {v} (разобрано только {ll.ILLUM_OK})')
                elif s.id == 0x12110f:
                    if plant == '12110f' and not planted: s.data = b'\0\0\0\0' + b'1.16'; planted = True
                    n15 += 1
                    if c.id != 0x121105: bad.append(f'{p.name}: 0x12110f не под каналом кватернионов ({hex(c.id)})')
                    if bytes(s.data) != b'\0\0\0\0' + b'1.15': bad.append(f'{p.name}: 0x12110f = {bytes(s.data).hex()} (не постоянная метка)')
        if planted: plant = None
    # чтение группы света уровня тоже обязано отвергнуть не 1 (tools/level_light.read_lights)
    print(f'диск: 0x13008 — {n8} (все u32 = 1 под 0x13000: {"да" if not any("13008" in x for x in bad) else "НЕТ"}); '
          f'0x12110f — {n15} (все 00000000 "1.15" под 0x121105: {"да" if not any("12110f" in x for x in bad) else "НЕТ"})')
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=int, nargs='*', default=[]); ap.add_argument('--shr'); ap.add_argument('--traffic')
    ap.add_argument('--same-as'); ap.add_argument('--plant-lgt1', type=int)
    ap.add_argument('--chunks', action='store_true'); ap.add_argument('--plant-13008', action='store_true'); ap.add_argument('--plant-12110f', action='store_true')
    a = ap.parse_args(); bad = []
    for lv in a.level:
        bad += check_level(lv, a.shr, a.traffic, a.plant_lgt1)
        if a.same_as and lv == 1: bad += same_as(a.shr or default(1, 'level.shr'), a.same_as)
    if a.chunks: bad += chunks('13008' if a.plant_13008 else '12110f' if a.plant_12110f else None)
    for x in bad: print('  ПРОВАЛ:', x[:300])
    print('FAIL' if bad else 'PASS')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
