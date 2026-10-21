#!/usr/bin/env python3
"""Машина уровня N в движке — из данных (29.09): level.shr (CAR1 v2) и то, что из него берёт движок, против диска.

  car_check.py --level N SHR PARAMS          PASS / FAIL (код 0 / 1); PARAMS — вывод tests/cars/params_host SHR
  car_check.py --identity PARAMS DEFAULTS    уровень 1: всё, что движок берёт о машине, побайтно как до 29.09 (carDefaults)
  car_check.py --plant-seat SHR КОПИЯ        сиденье вынесено за борт кузова — обязан дать FAIL
  car_check.py --plant-door SHR КОПИЯ        точка у двери внутри коробки кузова — обязан дать FAIL
  car_check.py --plant-name SHR КОПИЯ ИМЯ    в CAR1 имя чужой машины — обязан дать FAIL
  car_check.py --plant-con H КОПИЯ          carparams.h с чужой массой honor_v (как устаревшая таблица) — обязан дать FAIL
Проверки (свой разбор файла; данные — диск Роба, только чтение):
  * машина: имя в CAR1 = первый аргумент InitLevelPlayerVehicle в scripts/missions/level0N/leveli.mfk; движок взял её же
    (carParamsFromCar1 = 1, имя в CarParams);
  * ходовые: каждое поле CarParams, которое читается из .con, = число команды в scripts/cars/<машина>.con (км/ч -> м/с,
    градусы -> рад; команды нет — значение по умолчанию tools/con2h.py FIELDS);
  * камера: угол и дистанция = FollowCameraData 0x3000100 модели машины (ближний вариант, индекс < 256);
  * сиденье = сустав dl таблицы суставов CAR1, внутри коробки кузова (борт, длина, от низа до крыши);
  * точка у двери — снаружи коробки кузова дальше радиуса Гомера (0.30 м), вдоль кузова; якорь посадки доезжает не дальше 1 м;
  * блок машины = правило tools/psp_export.car_info, пересчитанное с диска сейчас (файл не устарел против экспортёра)."""
import sys, struct, math, re, argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
GAME = (ROOT / 'hit-and-run-web/source/game').resolve()   # как convert.GAME (папка — ссылка на общую копию)
INFO_FMT = '<16s12f3f4f7fI'
GEOM = ('halfW', 'halfL', 'bodyOfs', 'wheelX', 'wheelF', 'wheelR', 'wheelRad', 'bodyLo', 'bodyHi', 'bandLo', 'bandHi', 'step')
HOMER_RADIUS = 0.30
# поле CarParams <- команда .con, умолчание (tools/con2h.py FIELDS), перевод единиц
CON = [('mass', 'SetMass', 1500.0), ('gasScale', 'SetGasScale', 4.5), ('slipGasScale', 'SetSlipGasScale', 'gasScale'),
       ('hsGasScale', 'SetHighSpeedGasScale', 'gasScale'), ('gasSpeedThreshold', 'SetGasScaleSpeedThreshold', 1.0),
       ('brakeScale', 'SetBrakeScale', 8.0), ('topSpeed', 'SetTopSpeedKmh', 120.0), ('maxWheelTurn', 'SetMaxWheelTurnAngle', 30.0),
       ('hsSteeringDrop', 'SetHighSpeedSteeringDrop', 0.27), ('tireGrip', 'SetTireGrip', 2.48), ('normalSteering', 'SetNormalSteering', 95.0),
       ('slipSteering', 'SetSlipSteering', 55.0), ('eBrakeEffect', 'SetEBrakeEffect', 0.4),
       ('slipSteeringNoEBrake', 'SetSlipSteeringNoEBrake', 'slipSteering'), ('slipEffectNoEBrake', 'SetSlipEffectNoEBrake', 0.0),
       ('cmX', 'SetCMOffsetX', 0.0), ('cmY', 'SetCMOffsetY', 0.0), ('cmZ', 'SetCMOffsetZ', 0.0),
       ('suspensionLimit', 'SetSuspensionLimit', 0.7), ('springK', 'SetSpringK', 0.3), ('damperC', 'SetDamperC', 0.15),
       ('suspensionYOffset', 'SetSuspensionYOffset', 0.0), ('hitPoints', 'SetHitPoints', 3.0), ('burnoutRange', 'SetBurnoutRange', 0.09),
       ('donutTorque', 'SetDonutTorque', 2.0), ('weebleOffset', 'SetWeebleOffset', -0.75), ('wheelieRange', 'SetWheelieRange', 0.0),
       ('wheelieY', 'SetWheelieOffsetY', 0.0), ('wheelieZ', 'SetWheelieOffsetZ', 0.0)]
UNIT = {'topSpeed': 1 / 3.6, 'maxWheelTurn': math.pi / 180}


def level_car(level):
    txt = re.sub(r'//[^\n]*', '', (GAME / f'scripts/missions/level0{level}/leveli.mfk').read_text(errors='replace'))
    return re.search(r'InitLevelPlayerVehicle\s*\(\s*"([^"]+)"', txt).group(1)


def con_values(car):
    txt = re.sub(r'/\*.*?\*/', '', re.sub(r'//[^\n]*', '', (GAME / f'scripts/cars/{car}.con').read_text(errors='replace')), flags=re.S)
    cmd = {}
    for k, a in re.findall(r'(Set\w+)\s*\(([^)]*)\)', txt):
        try: cmd[k] = float(a.split(',')[0])
        except ValueError: pass
    out = {}
    for f, c, d in CON:
        out[f] = cmd[c] if c in cmd else (out[d] if isinstance(d, str) else d)
    return {f: v * UNIT.get(f, 1.0) for f, v in out.items()}


def car_model(level, car):
    txt = re.sub(r'//[^\n]*', '', (GAME / f'scripts/missions/level0{level}/level.mfk').read_text(errors='replace'))
    m = re.search(r'LoadDisposableCar\s*\(\s*"([^"]+)"\s*,\s*"' + re.escape(car) + r'"', txt)
    return GAME / m.group(1).replace('\\', '/') if m else GAME / 'art' / 'cars' / f'{car}.p3d'


def follow_cam(p3d):
    from p3d import read
    cams = sorted(struct.unpack_from('<I6f', c.data) for c in read(p3d).children if c.id == 0x3000100)
    return next(c for c in cams if c[0] < 256)


def read_params(path):
    out = {}
    for ln in Path(path).read_text().splitlines():
        k, _, v = ln.partition(' ')
        out[k] = v
    return out


def car1(d):
    c1, = struct.unpack_from('<I', d, 100)
    if not c1 or d[c1:c1 + 4] != b'CAR1': return None
    ver, nj, nh, nd, nf, io, il = struct.unpack_from('<7I', d, c1 + 4)
    lift, = struct.unpack_from('<f', d, c1 + 32)
    joints = {d[c1 + 80 + 28 * i:c1 + 92 + 28 * i].split(b'\0')[0].decode('latin1'): struct.unpack_from('<3f', d, c1 + 92 + 28 * i) for i in range(nj)}
    info = None
    if ver >= 2 and il >= struct.calcsize(INFO_FMT):
        v = struct.unpack_from(INFO_FMT, d, c1 + io)
        info = dict(car=v[0].split(b'\0')[0].decode('latin1'), **dict(zip(GEOM, v[1:13])), seat=v[13:16], seatA=v[16:18], door=v[18:20],
                    cam=v[20:26], camFar=v[26], flags=v[27])
    return dict(c1=c1, ver=ver, io=io, lift=lift, joints=joints, info=info)


def close(a, b, tol=1e-5): return abs(a - b) <= tol * max(1.0, abs(b))


def check(level, shr, params):
    d = Path(shr).read_bytes(); bad = []
    C = car1(d)
    if not C: print('FAIL: нет CAR1'); return 1
    if C['ver'] < 2 or not C['info']: print(f'  ПРОВАЛ: CAR1 версии {C["ver"]} без блока машины'); print(f'уровень {level}: FAIL'); return 1
    I, P = C['info'], read_params(params)
    car = level_car(level)
    (bad.append if I['car'] != car else print)(f'машина: CAR1 {I["car"]}, InitLevelPlayerVehicle уровня {level} — {car}')
    (bad.append if P.get('src') != '1' or P.get('name') != car else print)(f'движок: carParamsFromCar1 = {P.get("src")}, машина {P.get("name")}')
    # ходовые из .con
    exp = con_values(car); wrong = [f'{f} {float(P[f]):.6g} (в .con {v:.6g})' for f, v in exp.items() if not close(float(P[f]), v)]
    (bad.append if wrong else print)(f'ходовые {car}.con: {len(exp) - len(wrong)} из {len(exp)} полей совпали' + (': ' + ', '.join(wrong[:4]) if wrong else ''))
    # камера
    cam = follow_cam(car_model(level, car))
    ok = close(float(P['camElev']), cam[2]) and close(float(P['camMag']), cam[3]) and close(I['cam'][1], cam[2]) and close(I['cam'][2], cam[3])
    (bad.append if not ok else print)(f'камера: движок {float(P["camElev"]):.3f} рад / {float(P["camMag"]):.2f} м; FollowCameraData #{cam[0]}: {cam[2]:.3f} / {cam[3]:.2f}')
    # кузов в движке = блок CAR1
    wrong = [g for g in GEOM if not close(float(P[g]), I[g], 1e-6)]
    (bad.append if wrong else print)(f'кузов в движке = CAR1: {len(GEOM) - len(wrong)} из {len(GEOM)}' + (f' (не так: {wrong})' if wrong else ''))
    # сиденье
    dl = C['joints'].get('dl')
    s = I['seat']; lift = C['lift']
    fwd = -s[2]                                                  # модель смотрит в -Z: вперёд = -z
    inside = abs(s[0]) + 0.05 <= I['halfW'] and abs(fwd - I['bodyOfs']) + 0.05 <= I['halfL'] and I['bodyLo'] <= s[1] + lift <= I['bodyHi']
    (bad.append if not dl or any(not close(a, b, 1e-6) for a, b in zip(dl, s)) else print)(
        f'сиденье = сустав dl: {tuple(round(v, 3) for v in s)}' + ('' if dl else ' (нет сустава dl)'))
    (bad.append if not inside else print)(f'сиденье внутри кузова: борт {abs(s[0]):.2f} < {I["halfW"]:.2f}, вдоль {fwd - I["bodyOfs"]:+.2f} '
                                          f'из ±{I["halfL"]:.2f}, высота {s[1] + lift:.2f} в [{I["bodyLo"]:.2f}, {I["bodyHi"]:.2f}]')
    # точка у двери и якорь (то, что берёт движок)
    dx, dz, ax, az = float(P['doorX']), float(P['doorZ']), float(P['seatAx']), float(P['seatAz'])
    out_ok = dx <= -(I['halfW'] + HOMER_RADIUS) and abs(-dz - I['bodyOfs']) <= I['halfL']
    (bad.append if not out_ok else print)(f'дверь снаружи кузова: x {dx:.3f} (борт {-I["halfW"]:.3f}, радиус Гомера {HOMER_RADIUS}), вдоль {-dz - I["bodyOfs"]:+.2f}')
    slide = math.hypot(ax - dx, az - dz)
    (bad.append if slide > 1.0 or not (close(ax, I['seatA'][0], 1e-6) and close(dx, I['door'][0], 1e-6)) else print)(
        f'якорь посадки ({ax:.3f}, {az:.3f}), от двери {slide:.2f} м')
    # правило экспорта, пересчитанное с диска сейчас
    import psp_export as PE
    R = PE.car_info(car, car_model(level, car))
    wrong = [g for g in GEOM if not close(R[g], I[g], 1e-5)] + [k for k in ('seat', 'seatA', 'door') if any(not close(a, b, 1e-5) for a, b in zip(R[k], I[k]))]
    (bad.append if wrong else print)(f'блок машины = правило tools/psp_export.car_info сейчас' + (f': не так {wrong}' if wrong else ''))
    for b in bad: print('  ПРОВАЛ:', b)
    print(f'уровень {level} ({car}): ' + ('PASS' if not bad else f'FAIL ({len(bad)})'))
    return 0 if not bad else 1


def identity(params, defaults):
    P, D = read_params(params), read_params(defaults)
    diff = [k for k in D if k != 'src' and P.get(k) != D[k]]
    for k in diff: print(f'  ПРОВАЛ: {k} {P.get(k)} (до 29.09 {D[k]})')
    print(f'уровень 1: полей машины {len(D) - 1}, отличий {len(diff)} — ' + ('PASS' if not diff else 'FAIL'))
    return 0 if not diff else 1


def plant(src, dst, what, arg=None):
    d = bytearray(Path(src).read_bytes()); C = car1(d); o = C['c1'] + C['io']
    v = list(struct.unpack_from(INFO_FMT, d, o)); I = C['info']
    if what == 'seat':                                              # сиденье (и сустав dl) за правым бортом
        v[13] = I['halfW'] + 0.5
        nj, = struct.unpack_from('<I', d, C['c1'] + 8)
        for i in range(nj):
            if d[C['c1'] + 80 + 28 * i:C['c1'] + 92 + 28 * i].split(b'\0')[0] == b'dl': struct.pack_into('<f', d, C['c1'] + 92 + 28 * i, v[13])
    if what == 'door': v[18] = -0.5 * I['halfW']; v[16] = v[18]      # дверь внутри коробки кузова
    if what == 'name': v[0] = arg.encode()
    struct.pack_into(INFO_FMT, d, o, *v); Path(dst).write_bytes(bytes(d)); return 0


def plant_con(src, dst):
    s = Path(src).read_text()
    s2 = re.sub(r'(\{"honor_v", )1200\.f', r'\g<1>1500.f', s)
    assert s2 != s; Path(dst).write_text(s2); return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('shr', nargs='?'); ap.add_argument('params', nargs='?'); ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--identity', nargs=2); ap.add_argument('--plant-seat', nargs=2); ap.add_argument('--plant-door', nargs=2)
    ap.add_argument('--plant-name', nargs=3); ap.add_argument('--plant-con', nargs=2)
    a = ap.parse_args()
    if a.identity: return identity(*a.identity)
    if a.plant_seat: return plant(*a.plant_seat, 'seat')
    if a.plant_door: return plant(*a.plant_door, 'door')
    if a.plant_name: return plant(a.plant_name[0], a.plant_name[1], 'name', a.plant_name[2])
    if a.plant_con: return plant_con(*a.plant_con)
    return check(a.level, a.shr, a.params)


if __name__ == '__main__':
    sys.exit(main())
