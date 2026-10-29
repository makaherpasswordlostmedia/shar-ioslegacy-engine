#!/usr/bin/env python3
"""Правки Роба 172/186: камеры комнат — порт против оригинала (близнецы). Путь Гомера и камера оригинала по кадрам (cam_pos 0x7aaba0,
cam_fwd 0x7aabb8) из прогонов близнеца; тот же путь Гомера — через viewer/roomcam.c порта (tests/rooms/path_host.c, тот же код,
что в EBOOT). Сравнение покадрово: глаз (м) и направление взгляда (°). Кадры смены камеры у оригинала (переход плавный — его код,
у порта срез) и 0,3 с после неё не считаются.
  дом:          build/twins/o4/v17_house_cam/walk.tsv (tools/twins/walk.py --to 228.9 -178.0 228.9 -183.8 --seq … --cam)
  Kwik-E-Mart:  build/twins/o4/v11_kwik_fwd/visit.tsv (tools/twins/visit.py --door KwikEMart --seq … --cam)
Норма: глаз < 0,6 м и взгляд < 5° — дом ≥ 95 % кадров, Kwik-E-Mart ≥ 65 % (остаток — плавные переходы оригинала, правка 172).
  python3 tests/rooms/roomcam_twins.py            зелёный
  python3 tests/rooms/roomcam_twins.py --negative красный: прежние правила (взгляд на Гомера, весь рельс, камера держится) — обязан упасть"""
import argparse, math, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'build/interiors-l1-gfx.bin'
# норма по комнате: доля кадров в допуске. Дом — 100 % (было 19 % до правки 186). Kwik-E-Mart — 88 % (было 36 %, с правкой 186 — 71 %,
# с задержкой смены 1 с и стоящей прежней камерой правки 172 — 88 %): остаток — поза посередине между 06 и 07 (503,87; −18,00; 306,15 = 60 % пути, кадры
# 3140–3184), её правило не разгадано; норма Kwik — нижняя граница сделанного, не цель
RUNS = [('SimpsonsHouse', ROOT / 'build/twins/o4/v17_house_cam/walk.tsv', 'walk', 0.95),
        ('KwikEMart', ROOT / 'build/twins/o4/v11_kwik_fwd/visit.tsv', 'visit', 0.85),
        ('SpringfieldElementary', ROOT / 'build/twins/o4/s2_school/visit.tsv', 'visit', 0.90)]   # 17.10 школа (стенд 2): 89 % по правилу 172, 93 % по новому; остаток — возврат camera04 → path1 (7828–7878)
# прогулки ps2s_room.py (стенд 2, 17.10, tools/twins/ps2s_room.py: герой стартует у двери комнаты, обход по кругу): комната, запись, пакет рисования уровня, норма (нижняя граница сделанного)
RUNS2 = [('DMV', ROOT / 'build/twins/o4_s2/room_DMV/trace.tsv', 'build/interiors-l2-gfx.bin', 0.88), ('Moes', ROOT / 'build/twins/o4_s2/room_Moes/trace.tsv', 'build/interiors-l2-gfx.bin', 0.88),
         ('AndroidsDungeon', ROOT / 'build/twins/o4_s2/room_AndroidsDungeon/trace.tsv', 'build/interiors-l3-gfx.bin', 0.93), ('Observatory', ROOT / 'build/twins/o4_s2/room_Observatory/trace.tsv', 'build/interiors-l3-gfx.bin', 0.80),
         ('SimpsonsHouse', ROOT / 'build/twins/o4_s2/room_SimpsonsHouse/trace.tsv', 'build/interiors-l4-gfx.bin', 0.80), ('BartRoom', ROOT / 'build/twins/o4_s2/room_BartRoom/trace.tsv', 'build/interiors-l4-gfx.bin', 0.83)]
EYE_TOL, ANG_TOL = 0.6, 5.0


def original_trace(path, ystart):
    """прогон ps2s_room.py (стенд 2): колонки rel, cam xyz, fwd xyz, затем тройки адресов позиции Гомера; берём тройку, которая чаще всего на уровне пола
    комнаты (y около ystart) и двигалась (адреса-«копии» с чужими значениями до входа отсеиваются по y)"""
    lines = path.read_text().splitlines()[1:]; V = []
    for l in lines:
        try: V.append([float(x) for x in l.split('\t')])
        except ValueError: pass
    ncol = (len(V[0]) - 7) // 3 if V else 0; best = None
    for c in range(ncol):
        k = 7 + 3 * c; ok = [v for v in V if abs(v[k + 1] - ystart) < 1.5 and abs(v[k]) < 1e4 and v[2] < -10]
        if len(ok) < 20: continue
        mv = sum(1 for a, b in zip(ok, ok[1:]) if abs(b[k] - a[k]) + abs(b[k + 2] - a[k + 2]) > 1e-3)
        if best is None or (len(ok), mv) > best[0]: best = ((len(ok), mv), k)
    rows = []
    if best is None: return rows
    k = best[1]
    for v in V:
        if not (abs(v[k + 1] - ystart) < 1.5 and abs(v[k]) < 1e4 and v[2] < -10): continue   # не в интерьере (камера PS2 y < -10)
        e = [v[1], v[2], -v[3]]; d = [v[4], v[5], -v[6]]; n = math.sqrt(sum(x * x for x in d)) or 1.0
        rows.append((int(v[0]), v[k], -v[k + 2], e, [x / n for x in d]))
    return rows


def original(path, kind):
    if isinstance(kind, tuple): return original_trace(path, kind[1])
    rows = []
    for l in path.read_text().splitlines()[1:]:
        c = l.split('\t')
        if kind == 'walk':
            if len(c) < 13: continue
            hx, hz, cam, fw = float(c[1]), float(c[2]), c[7:10], c[10:13]
        else:
            if len(c) < 13: continue
            hx, hz, cam, fw = float(c[5]), float(c[6]), c[7:10], c[10:13]
        if hx < 400: continue   # снаружи
        e = [float(cam[0]), float(cam[1]), -float(cam[2])]; d = [float(fw[0]), float(fw[1]), -float(fw[2])]
        n = math.sqrt(sum(x * x for x in d)) or 1.0
        rows.append((int(c[0]), hx, -hz, e, [x / n for x in d]))
    return rows


def build(old):   # old: 0 — как в EBOOT; 1 — правила до 172/186; 2 — правило 172 до школы (ROOMCAM_SWITCH172_OLD)
    out = ROOT / 'build/rooms_cams' / ('path_host_old' if old == 1 else 'path_host'); out.parent.mkdir(parents=True, exist_ok=True)
    flags = ['-DROOMCAM_TRACK_OLD', '-DROOMCAM_RAIL_FULL', '-DROOMCAM_SWITCH_NOW'] if old == 1 else []
    subprocess.run(['cc', '-std=c99', '-O2', '-Wall', *([f'-DROOM_FOOT_R={os.environ["ROOM_FOOT_R"]}f'] if os.environ.get('ROOM_FOOT_R') else []), *flags, '-I', str(ROOT / 'viewer'), str(ROOT / 'tests/rooms/path_host.c'),
                    str(ROOT / 'viewer/roomcam.c'), '-lm', '-o', str(out)], check=True)
    return out


def compare(room, orig, host, old, pkg=None):   # old: 0/1/2 как в build(); pkg — пакет рисования уровня (по умолчанию L1)
    pkg = pkg or PKG; tsv = ROOT / 'build/rooms_cams' / f'path_{room}.tsv'
    tsv.write_text(''.join(f'{f} {x:.3f} {z:.3f}\n' for f, x, z, _, _ in orig))
    res = subprocess.run([str(host), str(pkg), room, str(tsv)] + (['old'] if old == 1 else ['old172'] if old == 2 else []), capture_output=True, text=True, check=True).stdout
    port = {}
    for l in res.splitlines():
        c = l.split('\t'); port[int(c[0])] = (c[1], [float(x) for x in c[2:5]], [float(x) for x in c[5:8]])
    ok = tot = 0; worst = []
    for i, (f, x, z, e, d) in enumerate(orig):
        # смена камеры у оригинала: скачок глаза > 0,5 м за 2 кадра — переход; эти кадры и 15 следующих (0,3 с) не в счёт
        if any(math.dist(orig[j][3], orig[j - 1][3]) > .5 for j in range(max(1, i - 7), i + 1)): continue
        if f not in port: continue
        name, pe, pl = port[f]
        pd = [pl[k] - pe[k] for k in range(3)]; n = math.sqrt(sum(v * v for v in pd)) or 1.0; pd = [v / n for v in pd]
        ang = math.degrees(math.acos(max(-1.0, min(1.0, sum(a * b for a, b in zip(pd, d))))))
        de = math.dist(pe, e); tot += 1
        if de < EYE_TOL and ang < ANG_TOL: ok += 1
        else: worst.append((de, ang, f, name))
    share = ok / tot if tot else 0.0
    worst.sort(reverse=True)
    print(f'{room}: совпало {ok} из {tot} кадров ({share:.0%}); хуже всего: ' +
          ', '.join(f'кадр {f} {nm} глаз {de:.2f} м взгляд {a:.1f}°' for de, a, f, nm in worst[:3]))
    return share


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--negative', action='store_true'); ap.add_argument('--old172', action='store_true', help='красный контроль школы: задержка 1 с и при входе в триггер, пока Гомер ещё в текущей (правило 172 до 17.10) — школа обязана упасть'); a = ap.parse_args()
    host = build(1 if a.negative else 2 if a.old172 else 0); res = []
    for room, path, kind, norm in RUNS:
        if not path.exists(): print(f'нет записи оригинала {path.relative_to(ROOT)}'); return 1
        res.append((compare(room, original(path, kind), host, 1 if a.negative else 2 if a.old172 else 0), norm))   # old для path_host (аргумент 'old' = прежний выбор камеры) только у --negative
    for room, path, pkg, norm in RUNS2:   # новые комнаты — если записи и пакеты на месте (в основном дереве build/twins/o4_s2)
        if not path.exists() or not (ROOT / pkg).exists(): print(f'{room}: нет записи или пакета ({path.name}, {pkg}) — пропуск'); continue
        res.append((compare(room, original(path, ('trace', -20.0)), host, 1 if a.negative else 2 if a.old172 else 0, ROOT / pkg), norm))
        RUNS.append((room + '/' + pkg[-17:-8], path, 'trace', norm))
    green = all(s >= norm for s, norm in res)
    if a.old172:
        if res[2][0] >= res[2][1]: print('ПРОВАЛ ГЕЙТА: старое правило 172 прошло школу'); return 1
        print(f'КРАСНЫЙ (ожидаемо): правило 172 до школы — школа {res[2][0]:.0%} < {res[2][1]:.0%}'); return 0
    if a.negative:
        if any(s >= n for s, n in res[:3]): print('ПРОВАЛ ГЕЙТА: прежние правила прошли сверку хотя бы в одной из комнат дом / Kwik / школа'); return 1   # новые комнаты на старых правилах нормы могут держать — красный по трём первым
        print('КРАСНЫЙ (ожидаемо): прежние правила камер комнат расходятся с оригиналом'); return 0
    if not green: print('ПРОВАЛ: ' + ', '.join(f'{RUNS[i][0]} {s:.0%} < {n:.0%}' for i, (s, n) in enumerate(res) if s < n)); return 1
    print('OK: камеры комнат как у оригинала'); return 0


if __name__ == '__main__':
    sys.exit(main())
