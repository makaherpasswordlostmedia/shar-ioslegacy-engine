"""Зоны ускорения прыжка машин и подкидывающие точки Гомера (правки Роба 46 и 47) -> блок JMP1 в секции COL1 level.shr.

Всё из данных диска, ни одной координаты руками:
  зоны прыжка  — локаторы Event 48 (jumpzone*) из файлов, которые грузит сценарий уровня: level.mfk уровня 1 прямо
                 подписывает строку LoadP3DFile("art\\missions\\level01\\jumps.p3d") комментарием «This is the level
                 "jump boost zones"» (уровни 4 и 7 грузят тот же файл, 5 — level02, 6 — level03). Объём зоны — её
                 TriggerVolume (ящик или сфера).
  подкидывающие точки (bounce pad) — локаторы Event 6 в сценах уровня (l{N}_terra, l{N}r*, l{N}z*) и в файлах сценария:
                 уровень 1 — towerjump, duffjump (крыша грузовика Duff у Kwik-E-Mart), gasjump, kwikjump, llard01/02,
                 steam1, spring1..3, sv01/02, sb01. Рядом стоят их системы пара (l1z2_steam*, spring2_steam_ps…), в
                 world.spt есть звук trampoline, в dialog.spt — реплики Гомера W_Springboard_Hom_* («whee», «bouncy»).
                 Объём — TriggerVolume (где стоит Гомер), точка — положение локатора (куда он взлетает: на крышу/этаж).

Как движок их использует (viewer/col.h ColZone/ColPad; правила порта — сила ускорения в данных не записана):
  машина, оторвавшись от земли внутри зоны прыжка с подъёмом, получает вертикальную скорость до верха объёма зоны
  (viewer/car.c, JUMP_BOOST_*); Гомер, встав в объём точки, взлетает по дуге с вершиной в точке локатора (viewer/homer.c).

Формат (little endian, float32; координаты движка — z отзеркален, как у hit-and-run-web):
  'JMP1' u32 version=1, nzone, npad, u32 reserved[4]                                   32 Б
  zone[nzone] 80 Б: float c[3], ax[3], ay[3], az[3], h[3]; u32 shape (1 ящик, 0 сфера: h = радиус ×3); char name[16]
  pad[npad]   96 Б: те же 80 Б объёма + float apex[3], u32 reserved
  phone[reserved[1]] 32 Б (с 29.09, правка 62) — телефонные будки (ActionEvent SummonVehiclePhone), формат как у ключей, после них
  wrench[reserved[0]] 32 Б (с 29.09, пункт 4): float pos[3], r; char name[16] — гаечные ключи (ActionEvent Wrench сцен уровня:
                 14 на уровне 1), сфера подбора. Модель ключа (art/wrench.p3d, составной рисунок wrench) — тип SPR1 уровня
                 (tools/prp2_export.py add_wrenches), экземпляр на каждый ключ в той же точке
  death[reserved[2]] 96 Б (с 30.09, правка 86) — зоны DEATH, формат подкидывающей точки, после будок. С 05.10 (правка 349)
                 запись на КАЖДЫЙ объём TriggerVolume локатора (у R6D01 горящих покрышек их два: x 262…287 и 284…312 — двор
                 за забором целиком; до 349 брался только первый), подряд, с тем же именем и точкой; u32 pad — курс возврата
                 движка + 16 рад, float (π − курс строки 2 LocatorMatrix: [PS2] 05.10 оригинал ставит машину курсом локатора —
                 R6D01 2,672 → 0,000, Z6D1 0,852 → 0,785); 0 — курса нет (прежние level.shr: курс остаётся)
  phonex[reserved[3]] 80 Б (с 01.10, правка 166) — у каждой будки, в порядке phone[]: float loc[3] — положение её
                 ActionEvent-локатора (над будкой: там значок phone_icon art/cards.p3d и начало кадра камеры phonecamera.p3d),
                 ax[3], ay[3], az[3] — строки матрицы локатора (чанк 0x300000C), car[3] — CarStart-локатор ТОГО ЖЕ ИМЕНИ (место
                 машины: у всех 22 будок уровня 1 в 6–9 м по оси −x будки, на полосатой разметке), carH — курс движка
                 (π − угол данных, как старт уровня), u32 flags (1 — CarStart найден), u32 pad[3]. Блока нет (reserved[3] = 0,
                 прежние level.shr) — движок ставит машину прежним правилом
Смещение блока от начала секции COL1 — в поле ColHdr.flags (0 — блока нет; прежние level.shr читаются как раньше).
  python tools/jumps_export.py [уровень]     — список зон и точек (проверка без сборки уровня)"""
import re, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/missions')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3dlocs import read_locators   # локаторы 0x3000005 и их TriggerVolume, z отзеркален
GAME = ROOT / 'hit-and-run-web/source/game'
EV_BOUNCEPAD, EV_JUMPZONE = 6, 48
EV_DEATH = 4   # правка Роба 86: зоны DEATH (овраг, огонь покрышек): объём — где, положение локатора — куда вернуть
LOC_ACTION = 9


def script_files(level):
    """p3d, которые грузит сценарий уровня (level.mfk + leveli.mfk), в порядке строк"""
    out = []
    for n in ('level.mfk', 'leveli.mfk'):
        p = GAME / f'scripts/missions/level{level:02d}' / n
        if not p.exists(): continue
        for m in re.finditer(r'^\s*LoadP3DFile\(\s*"([^"]+)"', p.read_text(errors='replace'), re.M):
            f = GAME / m.group(1).replace('\\', '/')
            if f.suffix.lower() == '.p3d' and f.exists() and f not in out: out.append(f)
    return out


def scene_files(level):
    art = GAME / 'art'
    return [art / f'l{level}_terra.p3d'] + sorted(art.glob(f'l{level}r*.p3d')) + sorted(art.glob(f'l{level}z*.p3d'))


def phones(level):
    """Телефонные будки (правка Роба 62): ActionEvent-локаторы уровня с действием SummonVehiclePhone (22 на уровне 1)"""
    return wrenches(level, 'SummonVehiclePhone')


def wrenches(level, action='Wrench'):
    """Гаечные ключи (пункт 4): ActionEvent-локаторы (вид 9) сцен уровня с действием Wrench (строки данных: имя, имя, "Wrench");
    сфера TriggerVolume — где берётся. -> [dict(name, pos, r)] в порядке файлов сцен"""
    import struct as st
    from p3d import read, walk, string
    out, seen = [], set()
    for f in [p for p in scene_files(level) if p.exists()]:
        for c in walk(read(f)):
            if c.id != 0x3000005: continue
            name, p = string(c.data)
            kind, n = st.unpack_from('<II', c.data, p)
            if kind != LOC_ACTION: continue
            strs = [x.decode('latin1') for x in c.data[p + 8:p + 8 + 4 * n].split(b'\0') if x and all(32 <= ch < 127 for ch in x)]
            if not strs or strs[-1] != action: continue
            pos = st.unpack_from('<3f', c.data, p + 8 + 4 * n)
            loc = pos   # положение самого локатора (у будок — над будкой, на 2.27 м выше центра сферы)
            mat = next((st.unpack_from('<16f', k.data, 0) for k in c.children if k.id == 0x300000C and len(k.data) >= 64), None)
            r = 2.5
            for t in c.children:
                if t.id == 0x3000006:
                    _, q = string(t.data); r = st.unpack_from('<3f', t.data, q + 4)[0]; m = st.unpack_from('<16f', t.data, q + 16)
                    pos = m[12:15]; break
            key = (name, round(pos[0], 2), round(pos[2], 2))
            if key in seen: continue
            seen.add(key); out.append(dict(name=name, pos=(pos[0], pos[1], -pos[2]), r=r, loc=loc, mat=mat))
    return out


def car_starts(level):
    """CarStart-локаторы (вид 3) сцен уровня: {имя: [(pos игры, угол данных)]}"""
    import struct as st
    from p3d import read, walk, string
    out = {}
    for f in [p for p in scene_files(level) if p.exists()]:
        for c in walk(read(f)):
            if c.id != 0x3000005: continue
            name, p = string(c.data)
            kind, n = st.unpack_from('<II', c.data, p)
            if kind != 3 or n < 1: continue
            out.setdefault(name, []).append((st.unpack_from('<3f', c.data, p + 8 + 4 * n), st.unpack_from('<f', c.data, p + 8)[0]))
    return out


def phone_ext(level):
    """Правка Роба 166 (01.10: «машину ставишь на проезжую часть, а там полосатая разметка — специальное место прямо рядом с
    будкой»; «над будками крутятся синие трубки»; облёт камеры «на тебя — на машину — на тебя»). У каждой будки (порядок
    phones) — её ActionEvent-локатор (положение и матрица) и CarStart-локатор ТОГО ЖЕ ИМЕНИ (R1P1 -> CarStart R1P1: 22 из 22
    будок уровня 1, 21 из 21 уровня 2). Прежняя заметка «своей точки у будок в данных нет» (правка 117) — ошибка: локаторы RxPCy —
    стоящие машины трафика, а место машины будки названо как сама будка. -> [dict(name, loc, ax, ay, az, car, carH, ok)],
    координаты движка (z отзеркален); carH = π − угол данных (как старт уровня, tools/level_sweep.find_spawn)"""
    import math
    cs = car_starts(level); out = []
    for b in phones(level):
        lx, ly, lz = b['loc']; M = b['mat'] or (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, lx, ly, lz, 1)
        rows = [(M[4 * i], M[4 * i + 1], -M[4 * i + 2]) for i in range(3)]   # строки матрицы в осях движка: z отзеркален
        cand = cs.get(b['name']) or next((v for k, v in cs.items() if k.lower() == b['name'].lower()), [])
        car, carH, ok = (lx, ly, -lz), 0.0, 0
        if cand:
            (cx, cy, cz), a = min(cand, key=lambda t: (t[0][0] - lx) ** 2 + (t[0][2] - lz) ** 2)
            if math.hypot(cx - lx, cz - lz) < 25.0:   # тот же объект: машина у своей будки, не однофамилец на другом краю карты
                car, ok = (cx, cy, -cz), 1
                carH = math.atan2(math.sin(math.pi - a), math.cos(math.pi - a))
        out.append(dict(name=b['name'], loc=(lx, ly, -lz), ax=rows[0], ay=rows[1], az=rows[2], car=car, carH=carH, ok=ok))
    return out


def collect(level):
    """-> (zones, pads): списки dict(name, file, c, axes, h, shape, apex)"""
    zones, pads, seen = [], [], set()
    for f in script_files(level) + [p for p in scene_files(level) if p.exists()]:
        locs, err = read_locators(f, str(f.relative_to(GAME)))
        if err: print('jumps: пропуск', err); continue
        for L in locs:
            if L.type != 0 or L.data not in (EV_BOUNCEPAD, EV_JUMPZONE) or not L.triggers: continue
            key = (L.name, round(L.pos[0], 2), round(L.pos[2], 2))
            if key in seen: continue          # один локатор в двух файлах (уровни с общими сценами)
            seen.add(key)
            rect, c, h, axes = L.triggers[0]
            if not rect: axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)); h = (h[0], h[0], h[0])
            row = dict(name=L.name, file=f.name, c=c, axes=axes, h=h, shape=1 if rect else 0, apex=L.pos)
            (zones if L.data == EV_JUMPZONE else pads).append(row)
    return zones, pads


def death_heading(mat):
    """курс движка у точки возврата DEATH: π − atan2(строка 2 LocatorMatrix по x, по z) (оси диска; как CarStart: π − угол данных)"""
    import math
    if not mat: return None
    a = math.pi - math.atan2(mat[8], mat[10])
    return math.atan2(math.sin(a), math.cos(a))


def deaths(level, every=False):
    """Зоны DEATH (Event 4, 21 локатор на уровне 1: R3D01…, R6D01 у горящих покрышек): объём TriggerVolume и точка возврата.
    every=False — только первый объём локатора (так до правки 349; этим списком пользуется опора по видимой земле
    psp_export.col_visible_ground, правка 95: коллизия уровня от правки 349 не меняется). every=True — каждый объём локатора
    отдельной записью (правка 349: R6D01 — два ящика, двор горящих покрышек за забором целиком; уровни 1–7: 21/4/68/20/4/68/18
    локаторов, объёмов 22/8/87/21/8/87/24), ret_h — курс возврата движка (None — у локатора нет матрицы)"""
    out, seen = [], set()
    for f in script_files(level) + [p for p in scene_files(level) if p.exists()]:
        locs, err = read_locators(f, str(f.relative_to(GAME)))
        if err: continue
        for L in locs:
            if L.type != 0 or L.data != EV_DEATH or not L.triggers: continue
            key = (L.name, round(L.pos[0], 2), round(L.pos[2], 2))
            if key in seen: continue
            seen.add(key)
            for k, (rect, c, h, axes) in enumerate(L.triggers if every else L.triggers[:1]):
                if not rect: axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)); h = (h[0], h[0], h[0])
                out.append(dict(name=L.name, file=f.name, c=c, axes=axes, h=h, shape=1 if rect else 0, apex=L.pos, vol=k,
                                ret_h=death_heading(getattr(L, 'mat', None))))
    return out


def death_pad(d):
    """u32 pad записи DEATH: курс возврата + 16 (float, всегда > 0); 0 — курса нет"""
    return 0 if d.get('ret_h') is None else struct.unpack('<I', struct.pack('<f', d['ret_h'] + 16.0))[0]


def vol_bytes(r):
    return struct.pack('<15fI16s', *r['c'], *r['axes'][0], *r['axes'][1], *r['axes'][2], *r['h'], r['shape'],
                       r['name'].encode('latin1')[:15])


def jmp1(level):
    """-> bytes блока JMP1 (пустые b'' — если в данных уровня нет ни зон, ни точек)"""
    zones, pads = collect(level); wr = wrenches(level); ph = phones(level); px = phone_ext(level)
    import os
    dz = deaths(level, every=os.environ.get('JMP_DEATH_FIRST') != '1')   # правка 349: все объёмы; JMP_DEATH_FIRST=1 — как до неё (красный контроль)
    if not zones and not pads and not wr and not ph and not dz: return b'', zones, pads
    b = b'JMP1' + struct.pack('<3I4I', 1, len(zones), len(pads), len(wr), len(ph), len(dz), len(px))   # reserved: ключей, будок, зон DEATH (29.09), будок+ (01.10)
    for z in zones: b += vol_bytes(z)
    for p in pads: b += vol_bytes(p) + struct.pack('<3fI', *p['apex'], 0)
    for w in wr: b += struct.pack('<4f16s', *w['pos'], w['r'], w['name'].encode('latin1')[:15])
    for w in ph: b += struct.pack('<4f16s', *w['pos'], w['r'], w['name'].encode('latin1')[:15])   # будки — после ключей, тот же формат
    first = os.environ.get('JMP_DEATH_FIRST') == '1'
    for d in dz: b += vol_bytes(d) + struct.pack('<3fI', *d['apex'], 0 if first else death_pad(d))   # зоны DEATH — после будок; pad — курс возврата (правка 349)
    jmp1.deaths = dz
    for e in px: b += struct.pack('<16fI3I', *e['loc'], *e['ax'], *e['ay'], *e['az'], *e['car'], e['carH'], e['ok'], 0, 0, 0)   # правка 166: будки+ (80 Б)
    jmp1.wrenches = wr; jmp1.phonex = px
    return b, zones, pads


def top(r):
    return r['c'][1] + sum(abs(r['axes'][k][1]) * r['h'][k] for k in range(3))


def report(zones, pads):
    wr = getattr(jmp1, 'wrenches', [])
    print(f'JMP1: гаечных ключей {len(wr)} (' + ', '.join(f"{w['name']} r {w['r']:.1f}" for w in wr) + ')')
    px = getattr(jmp1, 'phonex', [])
    if px:
        import math
        print(f'JMP1: будок {len(px)}, место машины (CarStart того же имени) у {sum(e["ok"] for e in px)} (' +
              ', '.join(f"{e['name']} {math.hypot(e['car'][0] - e['loc'][0], e['car'][2] - e['loc'][2]):.1f} м" for e in px) + ')')
    print(f'JMP1: зон прыжка {len(zones)} (' + ', '.join(f"{z['name']} верх {top(z):.1f}" for z in zones) + ')')
    print(f'      подкидывающих точек {len(pads)} (' + ', '.join(f"{p['name']} {p['apex'][1] - (p['c'][1] - p['h'][1]):.1f} м" for p in pads) + ')')
    dz = getattr(jmp1, 'deaths', [])
    if dz:   # правка 349: зоны DEATH — объёмов и локаторов, у кого объёмов больше одного
        multi = {}
        for d in dz: multi[d['name']] = multi.get(d['name'], 0) + 1
        print(f'JMP1: зон DEATH {len(dz)} объёмов у {len(multi)} локаторов (несколько объёмов: ' +
              ', '.join(f'{n} ×{k}' for n, k in multi.items() if k > 1) + ')')


if __name__ == '__main__':
    lv = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b, z, p = jmp1(lv); report(z, p); print(len(b), 'Б')
