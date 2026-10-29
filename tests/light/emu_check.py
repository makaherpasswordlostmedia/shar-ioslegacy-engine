#!/usr/bin/env python3
"""Разбор прогонов tests/light/emu.sh: яркость машины и Гомера против мира на экране (29.09, рецепт §12).

  emu_check.py --measure OUT --level N      замер одного прогона -> OUT/measure.json; PASS/FAIL: строка LIGHT (свет уровня N из
                                            LGT1; у прогона --pre — «свет уровня 1»), куча на старте ≥ 20 МБ, 30 FPS в сценах
                                            car и drive (медиана ≥ 29.4, без «settling»), прогон дошёл до END
  emu_check.py --new A --pre B --ref C      согласие с миром: PASS/FAIL (код 0 / 1)

Замер снимка: маска — пиксели цвета-ключа на снимке-ключе (flag lumakey: машина пурпурная, Гомер зелёный), сжатая на 1 пиксель
PSP; яркость Y (Rec.601) — медиана по маске на обычном снимке (объект) и по кольцу 2–12 пикселей PSP вокруг маски (мир рядом).
Согласие (одно место, одна карта; A — уровень N, B — тот же уровень N с машиной и персонажами в дневном свете уровня 1, C — дневной
уровень той же карты: 1 для 4 и 7, 3 для 6):
  мир темнее во столько раз:          w = средняя яркость запечённого мира уровня N / уровня C (цвет вершин всех кусков города
                                          level.shr; текстуры у уровней одной карты общие — это и есть яркость мира на экране)
  машина:  K = (машина(A) / машина(B)) / S(C) / w   (одна и та же машина уровня N — отличается только свет; S(C) — множитель
                                                    света дневного уровня C к уровню 1 из строки LIGHT, яркостью Rec.601)
  Гомер:   K = (Гомер(A) / Гомер(C)) / w         (Гомер один на всех уровнях, одно место и ракурс)
PASS, если оба K в [0.75, 1.33]: объект темнеет вместе с миром. Почему мир — по всему уровню, а не кольцо у объекта: запечённый
свет одного места у уровней одной карты расходится сильно (Squidport, земля в 10 м: L6/L3 от 0.9 до 1.46, в среднем по уровню
1.0–1.23 — у L3 закатный лот студии почти чёрный), кольцо печатается для справки. Подложенный день (--new = прогон --pre) даёт
K = 1/w и больше — на ночных уровнях ≈ 1.6–1.9, FAIL."""
import argparse, json, re, statistics, sys
from pathlib import Path
import numpy as np
from PIL import Image

KEY = {'car': (255, 0, 255), 'homer': (0, 255, 0)}
BAND = (0.75, 1.33)


def box(m, r):
    """двоичное расширение квадратом (2r+1)^2 — через суммы по префиксам"""
    a = np.pad(m.astype(np.int32), r + 1)
    c = a.cumsum(0).cumsum(1)
    k = 2 * r + 1
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return s[:m.shape[0], :m.shape[1]] > 0


def lum(img): return img[..., 0] * .299 + img[..., 1] * .587 + img[..., 2] * .114


def measure_pair(normal, key, which):
    A = np.asarray(Image.open(normal).convert('RGB')).astype(np.float64)
    B = np.asarray(Image.open(key).convert('RGB')).astype(np.float64)
    if A.shape != B.shape: return None
    kc = np.array(KEY[which], np.float64)
    m = np.abs(B - kc).max(2) < 48
    px = max(1, round(A.shape[1] / 480))            # пиксель PSP в снимке окна
    other = np.abs(B - np.array(KEY['car' if which == 'homer' else 'homer'])).max(2) < 48
    core = ~box(~m, px)                             # сжатие на 1 пиксель PSP
    ring = box(m, 12 * px) & ~box(m, 2 * px) & ~box(other, 2 * px)
    if core.sum() < 50 or ring.sum() < 200: return dict(n=int(core.sum()), ring_n=int(ring.sum()))
    Y = lum(A)
    return dict(obj=float(np.median(Y[core])), ring=float(np.median(Y[ring])), n=int(core.sum()), ring_n=int(ring.sum()))


def smoke_stats(txt, level, pre):
    lines = txt.splitlines(); bad = []
    li = next((l for l in lines if l.startswith('LIGHT ')), None)
    kv = dict(re.findall(r'(\w+)=(\S+)', li)) if li else {}
    src = re.search(r'src=(.*?) group=', li).group(1) if li else None
    print(f'LIGHT: {li[6:] if li else "нет строки"}')
    if pre:
        if src != 'CAR1 без LGT1: свет уровня 1': bad.append(f'прогон --pre: свет «{src}», ждали свет уровня 1')
    elif src != 'свет уровня из LGT1' or kv.get('level') != str(level): bad.append(f'свет уровня {level} не прочитан из LGT1 ({src}, level={kv.get("level")})')
    scene, fps, heap = None, {}, {}
    for l in lines:
        if l.startswith('SCENE '): scene = l.split()[1]
        f = l.split()
        if len(f) >= 15 and re.match(r'^[\d.]+$', f[0]) and f[1] == scene:
            fps.setdefault(scene, []).append((float(f[2]), 'settling' in l)); heap.setdefault(scene, float(f[14]))
    h = heap.get('spawn')
    if h is None or h < 20.0: bad.append(f'свободная куча на старте {h} МБ < 20')
    out = dict(light=kv, light_src=src, heap_spawn=h)
    for sc in ('car', 'drive'):
        v = [x for x, st in fps.get(sc, []) if not st]; med = statistics.median(v) if v else 0.0
        out[f'fps_{sc}'] = med
        if med < 29.4: bad.append(f'FPS сцены {sc} {med:.1f} < 30')
    print(f'куча на старте {h} МБ; FPS: car {out["fps_car"]:.1f}, drive {out["fps_drive"]:.1f}')
    if not any(l.startswith('END') for l in lines): bad.append('прогон не дошёл до END')
    return out, bad


def measure(d, level):
    d = Path(d); bad = []
    pre = '_pre_' in d.name
    txt = (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''
    st, b = smoke_stats(txt, level, pre); bad += b
    res = dict(level=level, pre=pre, **st)
    for which, (n, k) in dict(car=('car.png', 'carkey.png'), homer=('homer.png', 'homerkey.png')).items():
        if not (d / n).exists() or not (d / k).exists(): bad.append(f'нет снимков {n}/{k}'); continue
        r = measure_pair(d / n, d / k, which); res[which] = r
        if not r or 'obj' not in r: bad.append(f'{which}: маска пустая ({r})'); continue
        print(f'{which}: яркость {r["obj"]:.1f} (пикселей {r["n"]}), мир рядом {r["ring"]:.1f} (пикселей {r["ring_n"]})')
    (d / 'measure.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for x in bad: print('  ПРОВАЛ:', x)
    print(f'замер уровня {level}{" (--pre)" if pre else ""}: ' + ('PASS' if not bad else f'FAIL ({len(bad)})'))
    return 1 if bad else 0


def world_mean(shr):
    """средняя яркость (Rec.601) цвета вершин кусков города level.shr (owner 0, без неба), ближние версии"""
    import struct
    b = Path(shr).read_bytes()
    npc, = struct.unpack_from('<I', b, 8); ptab, = struct.unpack_from('<I', b, 76); ncell, ctab = struct.unpack_from('<II', b, 80)
    cells = [struct.unpack_from('<6fIIIII', b, ctab + 48 * i) for i in range(ncell)]
    s = n = 0.0
    for i in range(npc):
        r = struct.unpack_from('<6fiIIII3ffIII2I', b, ptab + 80 * i)
        fl, nv, ni, own = r[7:11]; off, ci = r[15], r[17]
        if own != 0 or not ni or not fl & 16 or fl & 4: continue
        vs = 12 if fl & 32 else 16; raw = np.frombuffer(b, np.uint8, ni * vs, cells[ci][9] + off).reshape(ni, vs)
        if vs == 12:
            c = raw[:, 4:6].copy().view('<u2').ravel().astype(np.int64)
            rgb = np.stack([(c & 31) * 255 / 31, ((c >> 5) & 63) * 255 / 63, ((c >> 11) & 31) * 255 / 31], 1)
        else:
            c = raw[:, 4:8].copy().view('<u4').ravel().astype(np.int64)
            rgb = np.stack([c & 255, (c >> 8) & 255, (c >> 16) & 255], 1).astype(np.float64)
        s += float((rgb @ [.299, .587, .114]).sum()); n += ni
    return s / max(n, 1)


def compare(new, pre, ref):
    A, B, C = (json.loads((Path(x) / 'measure.json').read_text()) for x in (new, pre, ref))
    bad = []
    wa, wc = (world_mean((Path(x) / 'level_shr.txt').read_text().strip()) for x in (new, ref))
    w_world = wa / wc
    def g(M, w, k):
        v = (M.get(w) or {}).get(k)
        if v is None: bad.append(f'нет замера {w}.{k} уровня {M.get("level")}')
        return v or 1.0
    ring_car = g(A, 'car', 'ring') / g(C, 'car', 'ring'); ring_h = g(A, 'homer', 'ring') / g(C, 'homer', 'ring')
    ls = [float(x) for x in (C.get('light') or {}).get('dirS', '1,1,1').split(',')]
    s_ref = .299 * ls[0] + .587 * ls[1] + .114 * ls[2]   # машина в свете дневного уровня C = в свете уровня 1 × S(C)
    k_car = (g(A, 'car', 'obj') / g(B, 'car', 'obj')) / s_ref / w_world
    k_h = (g(A, 'homer', 'obj') / g(C, 'homer', 'obj')) / w_world
    lv = A.get('level')
    print(f'уровень {lv} против дня (уровень {C.get("level")}, то же место): мир ×{w_world:.2f} (запечённый свет уровня; кольцо у машины '
          f'×{ring_car:.2f}, у Гомера ×{ring_h:.2f} — справка); '
          f'машина ×{g(A, "car", "obj") / g(B, "car", "obj"):.2f} к дню уровня 1 (свет уровня {C.get("level")} ×{s_ref:.2f}) -> K {k_car:.2f}; Гомер ×{g(A, "homer", "obj") / g(C, "homer", "obj"):.2f} -> K {k_h:.2f}')
    for nm, k in (('машина', k_car), ('Гомер', k_h)):
        if not BAND[0] <= k <= BAND[1]: bad.append(f'{nm}: K {k:.2f} вне [{BAND[0]}, {BAND[1]}] — яркость не согласна с миром')
    for x in bad: print('  ПРОВАЛ:', x)
    print(f'уровень {lv}: ' + ('PASS' if not bad else f'FAIL ({len(bad)})'))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--measure'); ap.add_argument('--level', type=int)
    ap.add_argument('--new'); ap.add_argument('--pre'); ap.add_argument('--ref')
    a = ap.parse_args()
    if a.measure: return measure(a.measure, a.level)
    return compare(a.new, a.pre, a.ref)


if __name__ == '__main__':
    sys.exit(main())
