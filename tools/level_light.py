#!/usr/bin/env python3
"""Свет уровня для освещаемых объектов (29.09, docs/РЕЦЕПТ_УРОВНЯ.md §12) — одно место правды для экспорта и проверок.

  python tools/level_light.py            # таблица света 7 уровней с диска (группа sun, множители к уровню 1)
  python tools/level_light.py --level 6  # один уровень

Что по данным диска (hit-and-run-web/source/game, только чтение):
  * мир запечён в цвет вершин: у мешей города, районов, зон, комнат, пропов, стейтпропов и миссионного реквизита шейдеры без
    LIT и свой цвет вершин (ColourList / цвет PS2) — ночь и закат уровня уже в геометрии, экспорт берёт их как есть;
  * освещаются на ходу только объекты с шейдером LIT 1 без цвета вершин: машины (игрок, трафик, стоящие), персонажи (Гомер,
    пешеходы, герои миссий) и редкие предметы мира (забор пристани l3z5/l6z5, пикап l5r4 и т. п.);
  * их свет — LightGroup "sun" (0x2380) в art/l<N>_terra.p3d: Light 0x13000 (имя, u32 версия, u32 вид 0 фон / 2 направленный,
    u32 цвет ARGB, f32 затухание ×3, u32 включён) с LightDirection 0x13001 (куда светит, оси игры), LightPosition 0x13002 и
    LightShadow 0x13004. Группа "sun" есть у всех 7 уровней и трасс бонусной игры (b00–b07): 1 фоновый + 3 направленных сверху
    под 30° через 120°. Комнаты — своя группа (tools/interior_export.light_group);
  * 0x13008 — u32 у источников «семисветовой» группы LightGroup (main + ±X ±Y ±Z) в l4r6, l7r6, l7z1, missgen, wrench: во
    всех 35 случаях на диске (21 в файлах уровней) = 1 (обычный, складывающийся свет). Эти группы ни одним именем не связаны с рантаймом (в l1_terra
    группа LightGroup ссылается на источники, которых в файле нет) — свет художника для запекания цвета вершин; мы их не
    применяем, флаг читаем и проверяем: не 1 — ошибка чтения (значит, данные не такие, как разобраны).

ПРАВИЛО ПОРТА (форма света; сверено с записью PS2 уровня 1, см. рецепт §12): форма — прежняя, принятая Робом на уровне 1
(машина: CAR_AMB + CAR_DIF по нормали, запечено экспортом в цвет вершин, psp_export.car_prims; персонажи: солнце SKIN_SUN_ABGR +
фон SKIN_AMB_ABGR на GE, viewer/skin.h), яркость и цвет — из группы "sun" уровня N по каналам R, G, B одним множителем
на всю форму: средняя по всем направлениям нормали освещённость в свете данных
    E = фон + ¼ Σ направленных      (каждый направленный освещает полусферу со средним косинусом ½),
    ambS = dirS = E(уровень N) / E(уровень 1).
Один множитель, а не «фон к фону, направленный к направленному»: у формы порта доля фона больше, чем в данных (0x70 из ~0x8c
против 0x59 из ~0xc0), и отдельный множитель фона переоценил бы потемнение там, где в данных меняется только фон (уровни 2, 3:
фон #333333 при ярких направленных — дневные уровни потемнели бы на треть). Уровень 1 — множитель ровно 1 (байты прежние).
Освещаемые предметы мира без цвета вершин — та же форма, что у персонажей (солнце и фон skin.h по мировой нормали), тот же
множитель. Поля ambS/dirS в LGT1 оставлены раздельными (формат не привязан к правилу).
"""
import argparse, re, struct, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
GAME = (ROOT / 'hit-and-run-web/source/game').resolve()
GROUP = 'sun'
LGT1_LEN = 128
ILLUM_OK = 1          # 0x13008: единственное значение на диске (35 из 35)


def skin_consts(path=ROOT / 'viewer/skin.h'):
    """числа солнца персонажей из viewer/skin.h (одна правда с движком): dir (x, y, z), sun ABGR, amb ABGR"""
    t = path.read_text()
    g = lambda k: re.search(r'#define\s+' + k + r'\s+(0x[0-9a-fA-F]+|[0-9]*\.?[0-9]+)', t).group(1)
    return (float(g('SKIN_SUN_DIR_X')), float(g('SKIN_SUN_DIR_Y')), float(g('SKIN_SUN_DIR_Z'))), int(g('SKIN_SUN_ABGR'), 16), int(g('SKIN_AMB_ABGR'), 16)


def read_lights(root):
    """-> {имя: dict(kind, rgb (0..255), enabled, dir (куда светит, оси игры) | None, illum)}, {группа: [имена]}"""
    from p3d import walk, string
    lights, groups = {}, {}
    for c in walk(root):
        if c.id == 0x13000:
            name, p = string(c.data)
            _ver, kind, argb = struct.unpack_from('<3I', c.data, p)
            enabled = struct.unpack_from('<I', c.data, p + 24)[0] if len(c.data) >= p + 28 else 1
            d, illum = None, ILLUM_OK
            for s in c.children:
                if s.id == 0x13001: d = struct.unpack_from('<3f', s.data)
                elif s.id == 0x13008:
                    illum, = struct.unpack_from('<I', s.data)
                    if illum != ILLUM_OK: raise ValueError(f'свет {name}: 0x13008 = {illum}, на диске разобрано только {ILLUM_OK}')
            lights[name] = dict(kind=kind, rgb=((argb >> 16) & 255, (argb >> 8) & 255, argb & 255), enabled=enabled, dir=d, illum=illum)
        elif c.id == 0x2380:
            name, p = string(c.data); n, = struct.unpack_from('<I', c.data, p); p += 4; names = []
            for _ in range(n):
                nm, p = string(c.data, p); names.append(nm)
            groups[name] = names
    return lights, groups


def group_light(path, group=GROUP):
    """группа света файла -> dict(amb (r, g, b), dirs [((x, y, z) НА источник в осях level.shr, (r, g, b))])"""
    from p3d import read
    lights, groups = read_lights(read(path))
    if group not in groups: raise ValueError(f'{path.name}: нет группы света "{group}" (есть: {sorted(groups)})')
    amb, dirs = None, []
    for nm in groups[group]:
        L = lights.get(nm)
        if L is None: raise ValueError(f'{path.name}: в группе "{group}" источник {nm}, которого нет в файле')
        if not L['enabled']: continue
        if L['kind'] == 0:
            if amb is not None: raise ValueError(f'{path.name}: в группе "{group}" два фоновых источника')
            amb = L['rgb']
        elif L['kind'] == 2 and L['dir']:
            d = np.array([-L['dir'][0], -L['dir'][1], L['dir'][2]], np.float64)   # НА источник = −направление; зеркало z
            dirs.append((tuple(float(x) for x in d / max(np.linalg.norm(d), 1e-9)), L['rgb']))
        else: raise ValueError(f'{path.name}: источник {nm} вида {L["kind"]} — в группе "{group}" разобраны только 0 и 2')
    if amb is None: amb = (0, 0, 0)
    if len(dirs) > 4: raise ValueError(f'{path.name}: направленных {len(dirs)} > 4 (GE держит 4)')
    return dict(amb=amb, dirs=dirs)


_cache = {}
def level_light(level):
    """свет освещаемых объектов уровня N: группа sun из art/l<N>_terra.p3d + множители к уровню 1"""
    if level in _cache: return _cache[level]
    g = group_light(GAME / 'art' / f'l{level}_terra.p3d')
    ref = g if level == 1 else level_light(1)
    irr = lambda G: np.array(G['amb'], np.float64) + .25 * np.sum([c for _, c in G['dirs']], 0).astype(np.float64)
    e, er = irr(g), irr(ref)   # средняя освещённость по сфере нормалей, R, G, B (правило порта в шапке)
    S = tuple(float(x / y) if y else 1.0 for x, y in zip(e, er))
    L = dict(level=level, group=GROUP, amb=g['amb'], dirs=g['dirs'], ambS=S, dirS=S)
    _cache[level] = L
    return L


def abgr(rgb): return 0xFF000000 | (rgb[2] << 16) | (rgb[1] << 8) | rgb[0]


def fnv1a(b):
    h = 2166136261
    for x in b: h = ((h ^ x) * 16777619) & 0xFFFFFFFF
    return h


def block(L):
    """блок LGT1 (128 Б, формат — viewer/levlight.h)"""
    b = bytearray(LGT1_LEN)
    struct.pack_into('<4s4I', b, 0, b'LGT1', 1, L['level'], len(L['dirs']), abgr(L['amb']))
    for i, (v, c) in enumerate(L['dirs']): struct.pack_into('<3fI', b, 20 + 16 * i, *v, abgr(c))
    struct.pack_into('<3f3f', b, 84, *L['ambS'], *L['dirS'])
    struct.pack_into('<I', b, 108, fnv1a(bytes(b[:108])))
    b[112:128] = L['group'].encode()[:15].ljust(16, b'\0')
    return bytes(b)


def parse_block(b):
    """байты LGT1 -> dict (как level_light, цвета — (r, g, b)); ValueError, если блок битый"""
    if len(b) < LGT1_LEN or b[:4] != b'LGT1': raise ValueError('не LGT1')
    ver, level, n, amb = struct.unpack_from('<4I', b, 4)
    if ver != 1: raise ValueError(f'LGT1 версии {ver}')
    if struct.unpack_from('<I', b, 108)[0] != fnv1a(bytes(b[:108])): raise ValueError('LGT1: сумма не сходится')
    rgb = lambda c: (c & 255, (c >> 8) & 255, (c >> 16) & 255)
    dirs = []
    for i in range(n):
        x, y, z, c = struct.unpack_from('<3fI', b, 20 + 16 * i); dirs.append(((x, y, z), rgb(c)))
    s = struct.unpack_from('<6f', b, 84)
    return dict(level=level, group=b[112:128].split(b'\0')[0].decode(), amb=rgb(amb), dirs=dirs, ambS=s[:3], dirS=s[3:])


def car1_light(car1):
    """секция CAR1 (байты) -> блок LGT1 (dict) или None (версия < 3)"""
    ver, = struct.unpack_from('<I', car1, 4)
    if ver < 3: return None
    io, il = struct.unpack_from('<2I', car1, 24)
    return parse_block(car1[io + il:io + il + LGT1_LEN])


def world_lit_colours(P, light):
    """освещаемый предмет мира без цвета вершин (шейдер LIT 1): треугольники P (n*3, 3) в осях level.shr -> ABGR на вершину.
    Форма — как у персонажей (солнце и фон viewer/skin.h по мировой нормали), множители уровня (правило порта, см. выше)."""
    sd, sun, amb = skin_consts()
    S = np.array(sd, np.float64); S /= np.linalg.norm(S)
    T = P.reshape(-1, 3, 3).astype(np.float64)
    fn = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
    # двусторонне: у тонких предметов (забор) обход не говорит, какая сторона к свету — берём лучшую (как GE без отсечения)
    k_dir = np.abs(fn @ S)
    ch = lambda c, i: ((c >> (8 * i)) & 255) / 255.0
    out = np.zeros((len(T), 3))
    for i in range(3):
        out[:, i] = ch(amb, i) * light['ambS'][i] + ch(sun, i) * light['dirS'][i] * k_dir
    c = np.clip(np.round(out * 255), 0, 255).astype(np.uint32)
    col = (0xFF << 24) | (c[:, 2] << 16) | (c[:, 1] << 8) | c[:, 0]
    return np.repeat(col, 3).astype(np.uint32)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--level', type=int); a = ap.parse_args()
    for n in ([a.level] if a.level else range(1, 8)):
        L = level_light(n)
        print(f'уровень {n}: фон #{"%02x%02x%02x" % L["amb"]}, направленных {len(L["dirs"])}: ' +
              ', '.join(f'#{"%02x%02x%02x" % c} к ({v[0]:+.2f}, {v[1]:+.2f}, {v[2]:+.2f})' for v, c in L['dirs']) +
              f'; ambS {tuple(round(x, 3) for x in L["ambS"])}, dirS {tuple(round(x, 3) for x in L["dirS"])}')


if __name__ == '__main__':
    main()
