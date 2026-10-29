#!/usr/bin/env python3
"""Колёса машин и кузов (правка Роба 354, 05.10): какие колёса оригинал не рисует и на сколько колесу можно подняться над
покоем, пока оно не вылезло сквозь кузов. Из этого собирается viewer/carwheels.h (правило движка, viewer/carvis.c и traffic.c).

  .venv/bin/python tools/wheel_clear.py [машина ...]                 # таблица в терминал (без имён — все art/cars с .con)
  .venv/bin/python tools/wheel_clear.py --header viewer/carwheels.h  # собрать заголовок (все машины)
  .venv/bin/python tools/wheel_clear.py --check viewer/carwheels.h [машина ...]   # заголовок = пересчёт (без имён — машины
                                                                     # уровней 1–7 из leveli.mfk; --all — все) -> PASS / FAIL
  .venv/bin/python tools/wheel_clear.py --gate HOST.txt [--header viewer/carwheels.h]  # разбор tests/wheels/host: подъём
                                                                     # колёс движком ≤ запаса модели, скрытые не рисуются

Только чтение диска Роба: art/cars/<имя>.p3d (скелет, куски на суставах w0..w3, CollisionObject), scripts/cars/<имя>.con.

1. Скрытые колёса [PS2 код SLES_518.97]: при сборке машины (0x27b5e0…0x27b664) имя сравнивается с frink_v, honor_v, hbike_v,
   witchcar, ship, mono_v; совпало -> функция 0x27a140: для k = 0..3 имя сустава "w%d" (строка 0x479f28), каждому куску
   композита на этом суставе — метод куска (vtable +40) с аргументом 0: колёса не рисуются. rocke_v (0x27c780) -> 0x27a270, тот
   же цикл с k = 2: только передние w2, w3. [диск] у этих машин на суставах колёс заглушки: honor_v — куб 0,52 м (12 треуг.,
   краска кузова honor_vHoodNorm_m), а настоящие колёса вылеплены в самом кузове (honor_vWheel_m, 116 треуг.); сфера колеса
   в CollisionObject 0,349 м при кубе 0,26.
2. Запас вверх (правило порта: «колесо не видно сквозь кузов ни при каком сжатии»): точки поверхности модели (шаг 5 мм) —
   ортографические снимки сверху (13 направлений: сверху, по 4 стороны на 30° и 55°, 4 угла на 42°, пиксель 1 см), z-буфер
   кузова (все куски, кроме колёс); колесо поднимаем по оси Y модели шагом 1 см (как carvis.c jointXf) и считаем видимые
   пиксели ВЕРХНЕЙ части колеса (точки выше оси на 0.4 R). Пока колесо уходит в арку, их всё меньше; колесо вышло сквозь
   крыло — их снова больше. up[k] — последний шаг до роста больше допуска (TOL пикселей или 1 %); не вышло до UP_MAX — UP_MAX.
Ход колеса в порте (viewer/car.c derive + carvis.c): lim = R·SuspensionLimit, eq = (sqrt(1 + 5·lim/SpringK) − 1)/10 (не больше
0.9·lim); колесо над покоем поднимается до lim − eq (R — радиус колеса машины: меш + поправка эталона famil_v, psp_export.car_info)."""
import sys, struct, re, argparse, math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
try:                                        # без hit-and-run-web (облако) работает только --seed
    from p3d import read, walk, string      # noqa: E402  (MIT)
    from convert import geometry            # noqa: E402  (MIT)
except ImportError:
    read = walk = string = geometry = None

GAME = ROOT / 'hit-and-run-web/source/game'
CARS = GAME / 'art/cars'
HIDDEN = {'frink_v': 0xF, 'honor_v': 0xF, 'hbike_v': 0xF, 'witchcar': 0xF, 'ship': 0xF, 'mono_v': 0xF, 'rocke_v': 0xC}
PIX = 0.01           # пиксель снимка, м
SPACING = 0.005      # шаг точек поверхности, м
DY = 0.01            # шаг подъёма колеса, м
UP_MAX = 0.30        # дальше не ищем (ход подвески у всех машин меньше)
TOP = 0.4            # «верх колеса»: точки выше оси на TOP·R
TOL, TOL_K = 20, 0.01
REF_CAR, REF_R = 'famil_v', 0.37   # psp_export.CAR_REF_GEOM['wheelRad']: R машины = меш + (0.37 − меш famil_v)


def car_mesh(p3d):
    """-> (суставы {имя: (x, y, z)}, куски [(имя сустава, треугольники (n, 3, 3))], имена суставов, корень p3d), поза покоя"""
    root = read(p3d)
    comp = next((c for c in root.children if c.id == 0x4512), None)
    if comp is None: return None, None, None, root
    _, p = string(comp.data); skname, _ = string(comp.data, p)
    sk = next((c for c in root.children if c.id == 0x4500 and string(c.data)[0] == skname), None)
    if sk is None: return None, None, None, root
    names, W = [], []
    for j in (c for c in sk.children if c.id == 0x4501):
        name, q = string(j.data)
        parent, = struct.unpack_from('<I', j.data, q)
        M = np.array(struct.unpack_from('<16f', j.data, q + 24), np.float64).reshape(4, 4)
        W.append(M @ W[parent] if W and parent < len(W) else M)
        names.append(name)
    jpos = {n: np.array([w[3, 0], w[3, 1], -w[3, 2]]) for n, w in zip(names, W)}
    meshes = {string(c.data)[0]: c for c in walk(root) if c.id == 0x10000}
    pieces = []
    for c in walk(comp):
        if c.id != 0x4516: continue
        dn, q = string(c.data); _, joint = struct.unpack_from('<II', c.data, q)
        if dn not in meshes or joint >= len(names): continue
        tris = []
        for pg in (x for x in meshes[dn].children if x.id == 0x10002):
            _, parts = geometry(pg)
            for part in parts: tris.append(part['position'].astype(np.float64)[part['indices'].reshape(-1, 3)])
        if tris: pieces.append((names[joint], np.concatenate(tris) + jpos[names[joint]]))
    return jpos, pieces, names, root


def wheel_spheres(root, car, names):
    """радиусы сфер колёс из CollisionObject машины (0x7010000 -> объём 0x7010001 на суставе w<k> -> сфера 0x7010002)"""
    out = {}
    co = next((c for c in root.children if c.id == 0x7010000 and string(c.data)[0].lower() == car.lower()), None)
    if co is None: return out
    for v in (c for c in walk(co) if c.id == 0x7010001):
        joint, = struct.unpack_from('<I', v.data, 0)
        sph = next((x for x in v.children if x.id == 0x7010002), None)
        if sph is not None and joint < len(names) and re.fullmatch(r'w\d', names[joint]):
            out[names[joint]] = struct.unpack_from('<f', sph.data, 0)[0]
    return out


def samples(T, sp=SPACING):
    """точки на треугольниках T (n, 3, 3) с шагом не больше sp (барицентрическая сетка)"""
    if not len(T): return np.zeros((0, 3))
    e = np.max([np.linalg.norm(T[:, a] - T[:, b], axis=1) for a, b in ((0, 1), (0, 2), (1, 2))], 0)
    n = np.clip(np.ceil(e / sp).astype(int), 1, 600); out = []
    for k in np.unique(n):
        S = T[n == k]; i, j = np.meshgrid(np.arange(k + 1), np.arange(k + 1), indexing='ij'); m = (i + j) <= k
        i, j = i[m] / k, j[m] / k
        out.append((S[:, None, 0] + (S[:, None, 1] - S[:, None, 0]) * i[None, :, None] + (S[:, None, 2] - S[:, None, 0]) * j[None, :, None]).reshape(-1, 3))
    return np.concatenate(out)


def views():
    out = []
    for el, az in [(90, 0)] + [(e, a) for e in (30, 55) for a in (0, 90, 180, 270)] + [(42, a) for a in (45, 135, 225, 315)]:
        e, a = np.radians(el), np.radians(az)
        d = np.array([np.cos(e) * np.sin(a), np.sin(e), np.cos(e) * np.cos(a)])           # на зрителя
        u = np.cross([0.0, 1.0, 0.0], d) if el < 89 else np.array([1.0, 0.0, 0.0])
        u /= np.linalg.norm(u); out.append(np.stack([u, np.cross(d, u), d], 1))
    return out


def measure(car):
    """-> {w<k>: dict(r, sphere, up, counts, hidden)} или None (нет модели/колёс)"""
    jpos, pieces, names, root = car_mesh(CARS / f'{car}.p3d')
    if not pieces: return None
    wheels = {n: np.concatenate([T for m, T in pieces if m == n]) for n in sorted({m for m, _ in pieces if re.fullmatch(r'w[0-3]', m)})}
    body = [T for m, T in pieces if not re.fullmatch(r'w\d', m)]
    if not wheels or not body: return None
    sph = wheel_spheres(root, car, names)
    Sb = samples(np.concatenate(body))
    Sw = {}
    for n, T in wheels.items():
        S = samples(T); c = jpos[n]; r = float(np.abs(T[:, :, 1] - c[1]).max())
        Sw[n] = (S[S[:, 1] > c[1] + TOP * r], r)
    allP = np.concatenate([Sb] + [T.reshape(-1, 3) for T in wheels.values()])
    bufs = []
    for M in views():
        P = allP @ M; lo = P[:, :2].min(0) - UP_MAX - 0.05; W, H = (np.ceil((P[:, :2].max(0) + UP_MAX + 0.05 - lo) / PIX) + 1).astype(int)
        zb = np.full(W * H, -1e9); Q = Sb @ M
        np.maximum.at(zb, ((Q[:, 0] - lo[0]) / PIX).astype(int) * H + ((Q[:, 1] - lo[1]) / PIX).astype(int), Q[:, 2])
        bufs.append((M, lo, W, H, zb))
    res = {}
    for n, (S, r) in Sw.items():
        k = int(n[1]); hid = bool(HIDDEN.get(car, 0) >> k & 1)
        counts, up, low = [], UP_MAX, None
        for i in range(int(round(UP_MAX / DY)) + 1):
            if hid: break
            dy = i * DY; cnt = 0
            for M, lo, W, H, zb in bufs:
                Q = (S + np.array([0.0, dy, 0.0])) @ M
                idx = ((Q[:, 0] - lo[0]) / PIX).astype(int) * H + ((Q[:, 1] - lo[1]) / PIX).astype(int)
                wz = np.full(W * H, -1e9); np.maximum.at(wz, idx, Q[:, 2])
                cnt += int((wz > zb + 0.003).sum())
            counts.append(cnt)
            low = cnt if low is None else min(low, cnt)
            if cnt > low + max(TOL, TOL_K * counts[0]):
                up = round((i - 1) * DY, 3); break
        res[n] = dict(r=round(r, 4), sphere=round(sph[n], 4) if n in sph else None, up=0.0 if hid else up, counts=counts, hidden=hid)
    return res


def con_params(name):
    p = GAME / 'scripts/cars' / f'{name}.con'
    if not p.exists(): return {}
    s = re.sub(r'//[^\n]*', '', re.sub(r'/\*.*?\*/', ' ', p.read_text(errors='replace'), flags=re.S))
    return {m.group(1): float(m.group(2)) for m in re.finditer(r'(Set\w+)\s*\(\s*([-+0-9.eE]+)\s*\)', s)}


_ref = {}
def port_travel(car, res):
    """подъём колеса над покоем в порте без правила 354, м: lim − eq (car.c derive, carvis.c jointXf)"""
    con = con_params(car)
    if REF_CAR not in _ref: _ref[REF_CAR] = max(w['r'] for w in measure(REF_CAR).values())
    R = max(w['r'] for w in res.values()) + (REF_R - _ref[REF_CAR])
    lim = max(0.03, R * con.get('SetSuspensionLimit', 0.7))
    eq = min((math.sqrt(1 + 5 * lim / con.get('SetSpringK', 0.3)) - 1) / 10, lim * 0.9)
    return dict(R=round(R, 4), lim=round(lim, 4), eq=round(eq, 4), up=round(lim - eq, 4))


def all_cars():
    return sorted(p.stem for p in CARS.glob('*.p3d') if (GAME / 'scripts/cars' / f'{p.stem}.con').exists())


def level_cars():
    out = []
    for n in range(1, 8):
        t = re.sub(r'//[^\n]*', '', (GAME / f'scripts/missions/level0{n}/leveli.mfk').read_text(errors='replace'))
        out.append(re.search(r'InitLevelPlayerVehicle\s*\(\s*"([^"]+)"', t).group(1).lower())
    return out


def header_rows(cars):
    rows = []
    for n in cars:
        r = measure(n)
        hide = HIDDEN.get(n, 0)
        up = [r[f'w{k}']['up'] if r and f'w{k}' in r else (0.0 if hide >> k & 1 else UP_MAX) for k in range(4)]
        rows.append((n, hide, up))
    return rows


def fmt(x):
    s = f'{x:.3f}'.rstrip('0'); return s + ('0f' if s.endswith('.') else 'f')


def write_header(path, rows, seed=False):
    L = (['// ЗАТРАВКА (--seed, без диска): только машины правила SLES, запас up не замерен (0.3 — без ограничения). Пересобрать:',
          '//   .venv/bin/python tools/wheel_clear.py --header viewer/carwheels.h'] if seed else []) + ['// Колёса машин (правка Роба 354, 05.10): какие колёса не рисуются и на сколько колесу можно подняться над покоем, не выйдя',
         '// сквозь кузов. СГЕНЕРИРОВАНО tools/wheel_clear.py --header — руками не править (источники и способ замера — в его шапке).',
         '//   hide  — бит k: колесо w<k> не рисуется [PS2 код SLES_518.97: frink_v honor_v hbike_v witchcar ship mono_v — все четыре,',
         '//           rocke_v — передние w2 w3]',
         '//   up[k] — подъём колеса w<k> над покоем по оси Y модели, м, до которого оно не видно сквозь кузов (снимки модели сверху);',
         f'//           {UP_MAX:g} — не выходит до {UP_MAX:g} м. Движок: viewer/carvis.c jointXf (ход подвески вверх не больше up[k])',
         '// Прежнее поведение (колёса-заглушки рисуются, ход вверх до lim − eq): -DCARWHEELS_OLD=1',
         '#ifndef SHAR_CARWHEELS_H', '#define SHAR_CARWHEELS_H', '',
         '#ifndef CARWHEELS_OLD', '#define CARWHEELS_OLD 0', '#endif', '',
         'typedef struct { const char *name; unsigned char hide; float up[4]; } CarWheelCon;', '',
         'static const CarWheelCon carWheelCons[] = {']
    for n, hide, up in rows: L.append(f'  {{"{n}", 0x{hide:X}, {{{", ".join(fmt(u) for u in up)}}}}},')
    L += ['};', '#define CAR_WHEEL_CONS ((int)(sizeof carWheelCons / sizeof carWheelCons[0]))', '',
          '// имя машины без учёта регистра (в TrModel трафика — как в скриптах: cPolice, compactA; в CAR1 — имя .con)',
          'static inline int carWheelNameEq(const char *a, const char *b) {',
          '  for (;; a++, b++) { char x = *a, y = *b; if (x >= \'A\' && x <= \'Z\') x += 32; if (y >= \'A\' && y <= \'Z\') y += 32;',
          '    if (x != y) return 0;',
          '    if (!x) return 1; }',
          '}',
          'static inline const CarWheelCon *carWheelsFor(const char *name) {',
          '  if (!name || !*name) return 0;',
          '  for (int i = 0; i < CAR_WHEEL_CONS; i++) if (carWheelNameEq(carWheelCons[i].name, name)) return &carWheelCons[i];',
          '  return 0;',
          '}',
          '// маска колёс, которые не рисуются (0 — все рисуются; при CARWHEELS_OLD — всегда 0)',
          'static inline unsigned carWheelHide(const char *name) {',
          '  if (CARWHEELS_OLD) return 0;',
          '  const CarWheelCon *w = carWheelsFor(name); return w ? w->hide : 0;',
          '}',
          '// запас хода колеса w<k> вверх над покоем, м (нет машины в таблице или CARWHEELS_OLD — dflt: без ограничения)',
          'static inline float carWheelUp(const char *name, int k, float dflt) {',
          '  if (CARWHEELS_OLD || k < 0 || k > 3) return dflt;',
          '  const CarWheelCon *w = carWheelsFor(name); return w ? w->up[k] : dflt;',
          '}', '', '#endif', '']
    Path(path).write_text('\n'.join(L))


def read_header(path):
    rows = {}
    for m in re.finditer(r'\{"([^"]+)", 0x([0-9A-F]+), \{([^}]*)\}\}', Path(path).read_text()):
        rows[m.group(1)] = (int(m.group(2), 16), [float(x.strip().rstrip('f')) for x in m.group(3).split(',')])
    return rows


def check_header(path, cars):
    have = read_header(path); bad = []
    if set(have) != set(all_cars()): bad.append(f'машины в заголовке ≠ art/cars с .con: лишние {sorted(set(have) - set(all_cars()))}, '
                                                f'нет {sorted(set(all_cars()) - set(have))}')
    for n, hide, up in header_rows(cars):
        h = have.get(n)
        if not h: continue
        if h[0] != hide or any(abs(a - b) > 1e-4 for a, b in zip(h[1], up)):
            bad.append(f'{n}: в заголовке hide=0x{h[0]:X} up={h[1]}, пересчёт hide=0x{hide:X} up={up}')
    for b in bad: print('ПРОВАЛ', b)
    print(('FAIL' if bad else 'PASS') + f': viewer/carwheels.h и пересчёт по {len(cars)} машинам ({", ".join(cars[:8])}{"…" if len(cars) > 8 else ""})')
    return 1 if bad else 0


def gate(host_txt, header):
    """строки tests/wheels/host: «WHEEL src=<файл> car=<имя> joint=w<k> dymax=<м> hidden=<0|1> lim=<м> eq=<м>»"""
    have = read_header(header); bad = []; n = 0; cars = set()
    for line in Path(host_txt).read_text().splitlines():
        if not line.startswith('WHEEL '): continue
        kv = dict(re.findall(r'(\w+)=(\S+)', line)); car = kv['car'].lower(); k = int(kv['joint'][1]); n += 1; cars.add(car)
        hid_need = bool(HIDDEN.get(car, 0) >> k & 1); hid = kv['hidden'] == '1'; dy = float(kv['dymax'])
        up = have.get(car, (0, [UP_MAX] * 4))[1][k]
        if hid != hid_need:
            bad.append(f"{kv['src']} {car} w{k}: {'не рисуется' if hid else 'рисуется'}, а у оригинала {'не рисуется' if hid_need else 'рисуется'}")
        if not hid and dy > up + 1e-4:
            bad.append(f"{kv['src']} {car} w{k}: колесо поднимается на {dy:.3f} м при запасе модели {up:.3f} — видно сквозь кузов "
                       f"на {100 * (dy - up):.1f} см")
    for b in bad: print('ПРОВАЛ', b)
    print(('FAIL' if bad or not n else 'PASS') + f': {n} колёс {len(cars)} машин — подъём ≤ запаса модели, скрытые как у оригинала')
    return 1 if bad or not n else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cars', nargs='*')
    ap.add_argument('--seed', action='store_true')   # --seed: заголовок без диска (только HIDDEN)
    ap.add_argument('--header'); ap.add_argument('--check'); ap.add_argument('--gate'); ap.add_argument('--all', action='store_true')
    a = ap.parse_args()
    if a.gate: return gate(a.gate, a.header or str(ROOT / 'viewer/carwheels.h'))
    if a.check: return check_header(a.check, a.cars or (all_cars() if a.all else sorted(set(level_cars()))))
    if a.header and a.seed:
        write_header(a.header, [(n, h, [0.0 if h >> k & 1 else UP_MAX for k in range(4)]) for n, h in sorted(HIDDEN.items())], seed=True)
        print(a.header); return 0
    if a.header:
        write_header(a.header, header_rows(all_cars())); print(a.header); return 0
    for n in a.cars or all_cars():
        r = measure(n)
        if not r: print(f'{n:10s} нет модели/колёс'); continue
        t = port_travel(n, r)
        ups = [w['up'] for w in r.values() if not w['hidden']]
        worst = max(0.0, t['up'] - min(ups)) if ups else 0.0
        print(f"{n:10s} ход вверх в порте {t['up']:.3f} м; запас модели " +
              ' '.join(f"{k}:{'скрыто' if w['hidden'] else format(w['up'], '.2f')}" for k, w in r.items()) +
              (f'; видно сквозь кузов до {100 * worst:.1f} см' if worst > 0 else '') +
              '; сфера/меш ' + ' '.join(f"{w['sphere'] or 0:.2f}/{w['r']:.2f}" for w in r.values()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
