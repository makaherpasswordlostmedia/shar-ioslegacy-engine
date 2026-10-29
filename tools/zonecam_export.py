#!/usr/bin/env python3
"""Камеры зон города (правка Роба 40: «правила камер оригинала»): локаторы уровня вида 12 (StaticCam) и вида 4 (Spline +
RailCam) в файлах города art/l<N>r*.p3d / l<N>z*.p3d — те же записи 512 Б, что у камер комнат (tools/interior_export.py
room_cams, разбор и поведение — viewer/roomcam.c). Камера снимает, пока ноги Гомера в её TriggerVolume: у двери дома
Симпсонов (z1_cam1), на задних дворах, в проходах и на мостках АЭС, в кабинете Гомера (homer_office) и т. д. Запись PS2
(tools/ps2ref, 12:23 и 12:37): у двери дома Симпсонов кадр — неподвижная камера со двора на дверь.

Для кого камера: поле Data статичной камеры — ПРАВИЛО ПОРТА по данным (кода оригинала нет): у всех 55 камер комнат диска
Data = 2 (в комнатах ходят только пешком), у камер узких проходов и дворов города — 2, у камер прыжков через дома (z1_housejump,
cam01 уровня 2 — глаз на высоте 18 м) — 0, у трёх больших зон с резкой сменой (r6_cam1, r3_cam1, z3_ufocam: Flags 2, CutInOut
1) — 1. Толкование: 0 — в машине, 1 — всегда, 2 — пешком. Сюда идут камеры для пешего Гомера (Data 1 и 2, и все рельсы —
у RailCam поля Data нет, их триггеры — дворы, мостки, подвал АЭС и воздух над трамплинами, куда пешком не попасть);
камеры машины (Data 0) — в сводке, в движке пока не подключены (нужен эталон PS2 прыжка через дом).

    python tools/zonecam_export.py [--level 1] [--out build/zonecam-l1.shr]

Формат ZCM1: заголовок 128 Б — 'ZCM1', u32 версия (1), u32 уровень, u32 камер машины (не в пакете), нули; @120 u32 смещение
таблицы камер (128), @124 u32 камер; дальше записи 512 Б (как у RMG1, viewer/roomcam.h roomCamsParse), за ними точки рельсов
длиннее 9 точек (tools/interior_export.py cam_table, смещение от начала файла в @504 записи).

№408 (Роб 09.10: «камеры, которые снимают сбоку во время прыжка, — как в оригинале на PS2»): --car пишет ВТОРОЙ пакет того же
формата ZCM1 — камеры зон для МАШИНЫ (carzone-l<N>.shr, движок viewer/carzone.c): статичные с Data 0 и рельсы, у которых объём
TriggerVolume касается объёма зоны прыжка уровня (Event 48 jumpzone*, файл «jump boost zones» сценария — tools/jumps_export.py
collect). Запись PS2 (близнец, build/codex-terminal/rob-rest/378/attempt1): на 107 км/ч через дом L1 срезом включается рельс
r1_cam1 (триггер — воздух над домом за jumpzone17), на 50 км/ч — нет, машина бьётся в стену и в объёме z1_housejump (Data 0)
включается она. Отбор рельсов по касанию зоны прыжка — ПРАВИЛО ПОРТА по данным (кода оригинала нет; у RailCam поля Data нет):
у остальных рельсов триггеры — дворы, мостки и подвалы (радиусы 1–6,5 м) или места без записи PS2 (вопрос близнецу В103).
Пакет пешком (без --car) не меняется.
    python tools/zonecam_export.py --level 1 --car [--out build/carzone-l1.shr]"""
import argparse, struct, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
import interior_export as IE   # noqa: E402  записи камер — тот же код, что у комнат

GAME = (ROOT / 'hit-and-run-web/source/game').resolve()
REC = IE.CAM_REC


def rec_data(r):   # поле Data статичной камеры (запись 512 Б: @32 вид, @124 Data)
    kind, = struct.unpack_from('<I', r, 32); data, = struct.unpack_from('<I', r, 124)
    return kind, data


def world_cams(level):
    """[(файл, запись, сводка)] — все камеры города уровня (без комнат l<N>i*)"""
    out = []
    for f in sorted(GAME.glob(f'art/l{level}*.p3d')):
        if len(f.stem) > 2 and f.stem[2] == 'i': continue   # комнаты — tools/interior_export.py
        recs, info = IE.room_cams(f)
        out += [(f.name, r, i) for r, i in zip(recs, info)]
    return out


JUMP_TOUCH = 0.5   # м: зазор между объёмами триггера рельса и зоны прыжка, который ещё «касание» (у r1_cam1 L1 — 0, следующий — 16,7)


def _box(t):
    """AABB объёма TriggerVolume (вид, центр, полуоси, оси) в осях движка"""
    kind, c, h, ax = t
    if not kind: return [(c[i] - h[0], c[i] + h[0]) for i in range(3)]
    ext = [sum(abs(ax[r][i]) * h[r] for r in range(3)) for i in range(3)]
    return [(c[i] - ext[i], c[i] + ext[i]) for i in range(3)]


def _gap(a, b):
    return sum(max(0.0, a[i][0] - b[i][1], b[i][0] - a[i][1]) ** 2 for i in range(3)) ** .5


def car_cams(level):
    """№408: [(файл, запись, сводка, почему)] — камеры зон для машины: статичные Data 0 и рельсы у зон прыжка"""
    sys.path.insert(0, str(ROOT / 'tools/missions'))
    import jumps_export as JE
    from p3dlocs import read_locators
    zones = [(z['name'], [(z['c'][i] - sum(abs(z['axes'][r][i]) * z['h'][r] for r in range(3)),
                           z['c'][i] + sum(abs(z['axes'][r][i]) * z['h'][r] for r in range(3))) for i in range(3)]) for z in JE.collect(level)[0]]
    out = []
    for f in sorted(GAME.glob(f'art/l{level}*.p3d')):
        if len(f.stem) > 2 and f.stem[2] == 'i': continue
        recs, info = IE.room_cams(f)
        if not recs: continue
        T = {l.name: l.triggers for l in read_locators(f, f.name)[0]}
        for r, i in zip(recs, info):
            kind, data = rec_data(r); name = r[:32].split(b'\0')[0].decode()
            if kind == 0:
                if data == 0: out.append((f.name, r, i, 'Data 0'))
                continue
            B = [_box(t) for t in T.get(name, [])[:IE.CAM_TRIGS]]
            near = min(((_gap(b, zb), zn) for b in B for zn, zb in zones), default=(1e9, ''))
            if near[0] <= JUMP_TOUCH: out.append((f.name, r, i, f'рельс у {near[1]}'))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=int, default=1); ap.add_argument('--out', default=None)
    ap.add_argument('--car', action='store_true', help='№408: пакет камер зон для машины (carzone-l<N>.shr)')
    a = ap.parse_args()
    if a.car:
        out = Path(a.out or ROOT / f'build/carzone-l{a.level}.shr')
        cams = car_cams(a.level)
        for fn, r, info, why in cams: print(f'машина  {fn}: {info[:110]} — {why}')
        head = bytearray(128); head[:4] = b'ZCM1'; struct.pack_into('<3I', head, 4, 1, a.level, 0)
        struct.pack_into('<2I', head, 120, 128, len(cams))
        body = IE.cam_table([r for _, r, _, _ in cams], 128)
        out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(bytes(head) + body)
        print(f'-> {out}: камер машины {len(cams)}, {128 + len(body)} Б')
        return
    out = Path(a.out or ROOT / f'build/zonecam-l{a.level}.shr')
    foot, car = [], []
    for fn, r, info in world_cams(a.level):
        kind, data = rec_data(r)
        (car if kind == 0 and data == 0 else foot).append((fn, r, info))
    for fn, r, info in foot: print(f'пешком  {fn}: {info[:120]}')
    for fn, r, info in car: print(f'машина  {fn}: {info[:120]} — не в пакете')
    head = bytearray(128); head[:4] = b'ZCM1'; struct.pack_into('<3I', head, 4, 1, a.level, len(car))
    struct.pack_into('<2I', head, 120, 128, len(foot))
    body = IE.cam_table([r for _, r, _ in foot], 128)
    assert all(len(r) >= REC and (len(r) - REC) % 12 == 0 for _, r, _ in foot)
    out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(bytes(head) + body)
    print(f'-> {out}: камер пешком {len(foot)}, машины (не в пакете) {len(car)}, {128 + len(body)} Б')


if __name__ == '__main__':
    main()
