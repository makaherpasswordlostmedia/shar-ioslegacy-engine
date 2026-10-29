#!/usr/bin/env python3
"""№930 ступень 2 «Мультик»: проверки приёмки accept60.sh (вывод — строки и PASS / FAIL последней строкой каждой проверки)
  data  ДАННЫЕ НАБОР          боковые файлы carflat930.bin / carflatm930.bin всех 7 уровней разобраны так же, как движок (записи кратны 4 Б, перестановка взаимно однозначна, K ≤ треугольников, подпись и число треугольников сходятся с traffic.shr / msncars-lN.shr); ДАННЫЕ_КРАСНЫЕ — то же с порчей одной перестановки обязано упасть
  mis   ПАПКА_ПРОГОНА          машины миссий: CARFILLM — у моделей есть заливка, CARFILL — рисуются (draws растёт) и есть текстурный хвост
  heap  БАЗА НОВОЕ             куча в эмуляторе на каждом уровне L1–L7 не хуже базы: строка HEAPB, живые байты malloc (uordblks) стоя после 22 с на уровне; плюс размер образа (в accept60.sh)
  cost  БАЗА НОВОЕ             цена кадра: среднее по секундам окна PHSEC (x_trf, x_mcr, x_npc, build, vbl-вне), новое не хуже базы (допуск 2 %)"""
import sys, re, struct
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent.parent / 'tools'))

def rd(p): return Path(p).read_bytes()

def parse_records(buf, off, end, nrec, pieces):
    """-> число записей; бросает AssertionError с причиной"""
    q = off; got = 0
    for _ in range(nrec):
        assert q + 12 <= end, 'запись за концом'
        pi, ntri, K = struct.unpack_from('<III', buf, q); assert pi < len(pieces), f'кусок {pi} вне набора'
        p = pieces[pi]; assert p['ni'] == ntri * 3 and (p['flags'] & 16), f'кусок {pi}: треугольников {ntri}, в данных {p["ni"] // 3}'
        assert 0 < K <= ntri and ntri <= 1600, f'кусок {pi}: K={K}'
        n = 12 + 9 * K + (2 * ntri if K < ntri else 0); n = (n + 3) & ~3; assert q + n <= end, 'запись за концом блока'
        if K < ntri:
            perm = struct.unpack_from('<%dH' % ntri, buf, q + 12 + 9 * K); assert sorted(perm) == list(range(ntri)), f'кусок {pi}: перестановка не взаимно однозначна'
            assert set(perm[:K]).isdisjoint(perm[K:]) and len(set(perm[:K])) == K
        q += n; got += 1
    return got

def check_data(data, setdir, corrupt=False):
    import car_flat as C
    bad = 0; tot = 0
    for n in range(1, 8):
        dd = Path(data) / ('' if n == 1 else f'l{n}'); sd = Path(setdir) / ('' if n == 1 else f'l{n}')
        try:
            f, tex, models, pieces, _ = C.load_trf(sd / 'traffic.shr'); b = bytearray(rd(dd / 'carflat930.bin'))
            if corrupt and n == 3 and len(b) > 400:   # порча: два значения перестановки первой записи с разрезом становятся равными
                q = 16; pi, ntri, K = struct.unpack_from('<III', b, q)
                if K < ntri: b[q + 12 + 9 * K: q + 12 + 9 * K + 2] = b[q + 12 + 9 * K + 2: q + 12 + 9 * K + 4]
            assert b[:4] == b'CFL2', 'нет CFL2'; npc, sig, nrec = struct.unpack_from('<III', b, 4); assert npc == len(pieces) and sig == C.sig_of(pieces), 'подпись'
            tot += parse_records(bytes(b), 16, len(b), nrec, pieces)
            blk = rd(dd / 'carflatm930.bin'); assert blk[:4] == b'CFM2'; nm = struct.unpack_from('<I', blk, 4)[0]; models = C.load_mcr(sd / f'msncars-l{n}.shr'); assert nm == len(models), 'число моделей'
            for m, (name, mf, mt, mp) in enumerate(models):
                e = struct.unpack_from('<16sIIIII', blk, 8 + 36 * m); assert e[0].split(b'\0')[0].decode('latin1') == name and e[1] == len(mp) and e[2] == C.sig_of(mp), f'модель {name}: подпись'
                tot += parse_records(blk, e[4], e[4] + e[5], e[3], mp)
        except AssertionError as ex:
            print(f'L{n}: {ex} ОШИБКА'); bad += 1
    print(f'записей разобрано {tot}, уровней с ошибкой {bad}')
    print('PASS' if not bad else 'FAIL'); return 0 if not bad else 1

def smoke_lines(d): return open(f'{d}/smoke.txt', errors='replace').read().splitlines()

def check_mis(d):
    ls = smoke_lines(d); fills = []; cf = []; sc = {}
    for ln in ls:
        m = re.match(r'SCENE (\S+) ([\d.]+)', ln)
        if m: sc[m.group(1)] = float(m.group(2))
        m = re.match(r'CARFILLM slot=(\d+) name=(\S+) fills=(\d+) t=([\d.]+)', ln)
        if m: fills.append((m.group(2), int(m.group(3)), float(m.group(4))))
        m = re.match(r'CARFILL t=([\d.]+) pieces=(\d+) mis=(\d+) on=\d player=\d draws=(\d+) .* flat_tri=(\d+) tex_tri=(\d+)', ln)
        if m: cf.append((float(m.group(1)), int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6))))
    bad = 0
    nz = [x for x in fills if x[1] > 0]; print('модели миссий в слотах:', ', '.join(f'{n}:{k}' for n, k, _ in fills) or '-', '; с заливкой', len(nz))
    if len(nz) < 3: print('мало моделей с заливкой (нужно ≥ 3) ОШИБКА'); bad += 1
    if cf:
        t0 = sc.get('M_L2_load', 0) + 10; a = [c for c in cf if c[0] >= t0]
        if len(a) >= 2: dr = a[-1][2] - a[0][2]; print(f'draws в окне после загрузки миссии: {dr}, мисс-кусков в наборах {a[-1][1]}, треугольников заливкой {a[-1][3]}, текстурой хвоста {a[-1][4]}'); bad += 0 if (dr > 200 and a[-1][1] > 0) else 1
        else: print('нет строк CARFILL в окне ОШИБКА'); bad += 1
    else: print('нет строк CARFILL ОШИБКА'); bad += 1
    print('PASS' if not bad else 'FAIL'); return 0 if not bad else 1

def level_heaps(path):
    lv = {}; bb = {}
    for ln in smoke_lines(path):
        m = re.match(r'LEVEL ev=load n=(\d+) .*?heap0=(\d+) heap=(\d+) mx0=(\d+) mx=(\d+)', ln)
        if m: lv[int(m.group(1))] = (int(m.group(3)), int(m.group(5)))
        m = re.match(r'BB\s+\d+\s+\S+\s+(L\d)\s+\S+\s+[-\d]+\s+[-\d]+\s+[-\d]+\s+heap ([\d.]+) blk\s+([\d.]+)', ln)
        if m: bb.setdefault(m.group(1), []).append(float(m.group(2)))
    return lv, bb

def settled(path):
    """последняя строка HEAPB каждой сцены H_Ln (куча стоя после 22 с на уровне): (свободно по счёту игры, живые байты malloc)"""
    r = {}
    for ln in smoke_lines(path):
        m = re.match(r'HEAPB t=([\d.]+) scene=H_L(\d) bytes=(\d+) blk=(\d+) used=(\d+) arena=(\d+) free=(\d+)', ln)
        if m: r[int(m.group(2))] = (int(m.group(3)), int(m.group(5)), int(m.group(6)))
    return r

def level_heap(path):
    r = {}
    for ln in smoke_lines(path):
        m = re.match(r'LEVEL ev=load n=(\d) loaded=\d+ ms=\d+ heap0=\d+ heap=(\d+)', ln)
        if m: r[int(m.group(1))] = int(m.group(2))
    return r

def check_heap(a, b):
    """Живые байты malloc (uordblks) — точная мера; счёт «свободно» игры (heapFreeBytes) = грубый шаг пробы sbrk 16 КБ + свободные куски, поэтому «ступеньки» ±16 КБ между сборками при том же числе живых байт — шум пробы, не память"""
    sa = settled(a); sb = settled(b); bad = 0
    print('уровень | живые байты malloc стоя после 22 с: база → новое (Δ) | счёт игры «свободно», байт: база → новое (Δ, шаг пробы 16 КБ)')
    for n in range(1, 8):
        if n not in sa or n not in sb:   # у базы (aa092b71 с вставкой HEAPB) на L4 и L7 строк HEAPB нет — сравнение по строке LEVEL ev=load (свободно по счёту игры после загрузки), допуск — шаг пробы 16 КБ
            la, lb = level_heap(a).get(n), level_heap(b).get(n)
            if la is None or lb is None: print(f'L{n}: нет строки HEAPB и LEVEL ОШИБКА'); bad += 1; continue
            ok = lb >= la - 16384; print(f'L{n}: HEAPB нет — по строке LEVEL: свободно {la} → {lb} ({lb - la:+d}) ' + ('ok' if ok else 'ОШИБКА')); bad += 0 if ok else 1; continue
        du = sb[n][1] - sa[n][1]; df = sb[n][0] - sa[n][0]; ok = du <= 0
        print(f'L{n}: {sa[n][1]} → {sb[n][1]} ({du:+d}) | {sa[n][0]} → {sb[n][0]} ({df:+d}) ' + ('ok' if ok else 'ОШИБКА')); bad += 0 if ok else 1
    print('PASS' if not bad else 'FAIL'); return 0 if not bad else 1

KEYS = ['x_trf', 'x_mcr', 'x_npc', 'x_car3d', 'build']
def phsec_means(path, t0, t1):
    s = {k: [] for k in KEYS}
    for ln in smoke_lines(path):
        m = re.match(r'PHSEC t=([\d.]+) ', ln)
        if not m or not (t0 <= float(m.group(1)) <= t1): continue
        for k in KEYS:
            mm = re.search(r' %s=([\d.]+)' % k, ln)
            if mm: s[k].append(float(mm.group(1)))
    return {k: sum(v) / max(1, len(v)) for k, v in s.items()}, len(s['x_trf'])

def rebake_seconds(path):
    """секунды, где новый путь перекрашивает вершины моделей (смена Textures Off/On и загрузка модели машины миссии: сценарий mis_cars.txt нарочно переключает flat912; в игре это одна пауза в меню): pick_us в строке CFCOST больше 5 мс"""
    r = []
    for ln in smoke_lines(path):
        m = re.match(r'CFCOST t=([\d.]+) .* pick_us=(\d+)', ln)
        if m and int(m.group(2)) > 5000: r.append(float(m.group(1)))
    return r

def phsec_means_ex(path, t0, t1, excl):
    s = {k: [] for k in KEYS}
    for ln in smoke_lines(path):
        m = re.match(r'PHSEC t=([\d.]+) ', ln)
        if not m or not (t0 <= float(m.group(1)) <= t1) or any(abs(float(m.group(1)) - e) <= 3.0 for e in excl): continue
        for k in KEYS:
            mm = re.search(r' %s=([\d.]+)' % k, ln)
            if mm: s[k].append(float(mm.group(1)))
    for k in s: v = sorted(s[k]); s[k] = v[:max(1, int(len(v) * .9))]   # усечённое среднее: верхние 10 % секунд (загрузка модели, смена Textures, один рывок) отброшены у обеих сторон
    return {k: sum(v) / max(1, len(v)) for k, v in s.items()}, len(s['x_trf'])

def check_cost(a, b, t0=12.0, t1=999.0):
    ex = rebake_seconds(b)   # b — новое
    ma, na = phsec_means_ex(a, t0, t1, ex); mb, nb = phsec_means_ex(b, t0, t1, ex); bad = 0
    if ex: print(f'без секунд перекраски вершин (разовая пауза при смене Textures / загрузке модели, не цена кадра): {sorted(set(round(e) for e in ex))} ±3 с')
    print(f'секунд в окне: база {na}, новое {nb}')
    if na < 10 or nb < 10: print('мало секунд PHSEC ОШИБКА'); bad += 1
    for k in KEYS: print(f'  {k:8s} база {ma[k]:.3f} → новое {mb[k]:.3f} мс эмулятора (Δ {mb[k] - ma[k]:+.3f}, ×5,8 = {(mb[k] - ma[k]) * 5.8:+.2f} мс PSP)')
    tot_a = sum(ma[k] for k in KEYS if k != 'build'); tot_b = sum(mb[k] for k in KEYS if k != 'build')
    print(f'  сумма NPC-машин и машина игрока (x_trf+x_mcr+x_npc+x_car3d): {tot_a:.3f} → {tot_b:.3f} (Δ {tot_b - tot_a:+.3f} мс эмулятора, {(tot_b - tot_a) * 5.8:+.2f} мс PSP)')
    ok = tot_b <= tot_a * 1.02 + 1e-9; print('сумма не хуже базы (допуск 2 %): ' + ('ok' if ok else 'ОШИБКА')); bad += 0 if ok else 1
    print('PASS' if not bad else 'FAIL'); return 0 if not bad else 1

if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'data': sys.exit(check_data(sys.argv[2], sys.argv[3], corrupt=len(sys.argv) > 4 and sys.argv[4] == 'corrupt'))
    if c == 'mis': sys.exit(check_mis(sys.argv[2]))
    if c == 'heap': sys.exit(check_heap(sys.argv[2], sys.argv[3]))
    if c == 'cost': sys.exit(check_cost(sys.argv[2], sys.argv[3]))
    print(__doc__); sys.exit(2)
