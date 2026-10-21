#!/usr/bin/env python3
"""Гейт правки 413а по прогону tests/hover/carsnd.txt (журнал звуков в smoke.txt: CARSND — каким профилем звучит машина игрока,
SFX <клип> skid — какой клип заноса реально запущен микшером viewer/audio.c audioSkid).
  python tests/hover/carsnd.py build/smoke/<время> build/levels/l7/audio/sfx.sab
Критерий (одинаковый для правила и красного контроля): машина звучит своим профилем пакета, и клипы заноса — ровно её занос из
данных диска (carSoundParameters RoadSkidClipName; blank — ни одного запуска). ship -> ship_skid (swoosh3), frink_v -> frink_skid
(frinkskid2), hbike_v -> тишина; мотор — EngineClipName своего профиля (gramR_v из будки -> gramR); наложение OverlayClipName (gramR_v -> rocket, петлёй, SLES 0x231254); гудок ↑ — HornClipName (gramR_horn, SLES 0x231860); сцена frink_old («flag carsndold 1», прежний путь) обязана упасть: там шины машины уровня (skid)."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sab_cars

SCENES = {'ship': 'ship', 'frink': 'frink_v', 'hbike': 'hbike_v', 'gramr': 'gramR_v', 'frink_old': 'frink_v', 'gramr_old': 'gramR_v'}


def main():
    run, sab = Path(sys.argv[1]), sys.argv[2]
    prof = sab_cars.cars(sab)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
    import audio_export as A
    res, data, _, _ = A.load_scripts()
    def ovl(car):   # наложение по данным: OverlayClipName, клип не потоковый (потоковые — открыто, поток music.sap)
        o = data[car].get('OverlayClipName'); return [o] if o and o in res and not res[o]['stream'] else []
    by = {}; cur = None
    for ln in (run / 'smoke.txt').read_text(errors='replace').splitlines():
        m = re.match(r'SCENE (\S+)', ln)
        if m: cur = m.group(1); by.setdefault(cur, dict(profile=None, skid=[], engine=[], overlay=[], horn=[])); continue
        if cur not in SCENES: continue
        m = re.match(r'CARSND car=(\S+) profile=(-?\d+)', ln)
        if m: by[cur]['profile'] = int(m.group(2)); continue
        m = re.match(r'SFX (\S+) skid ', ln)
        if m: by[cur]['skid'].append(m.group(1))
        m = re.match(r'SFX (\S+) engine ', ln)
        if m: by[cur]['engine'].append(m.group(1))
        m = re.match(r'SFX (\S+) overlay ', ln)
        if m: by[cur]['overlay'].append(m.group(1))
        m = re.match(r'SFX (\S+) horn ', ln)
        if m: by[cur]['horn'].append(m.group(1))
    out = []
    for sc, car in SCENES.items():
        r = by.get(sc)
        if not r: out.append((sc, False, 'сцены нет в журнале')); continue
        want = next(p for p in prof if p['name'].lower() == car.lower())
        got = prof[r['profile']]['name'] if r['profile'] is not None and 0 <= r['profile'] < len(prof) else None
        clips = sorted(set(r['skid'])); exp = [] if want['skid'] == 'blank' else [want['skid']]
        eng = sorted(set(r['engine'])); ov = sorted(set(r['overlay'])); hn = sorted(set(r['horn']))
        hexp = [data[car].get('HornClipName') or 'horn'] if sc.startswith('gramr') else []   # ↑ жмут только в сценах gramr
        ok = got == want['name'] and clips == exp and (exp == [] or len(r['skid']) > 0) and eng == [want['engine']] and ov == ovl(car) and hn == hexp
        out.append((sc, ok, f"профиль {got} (данные {want['name']}), мотор {eng} (данные {want['engine']}), наложение {ov} (данные {ovl(car)}), гудок {hn} (данные {hexp}), "
                            f"клипы заноса {clips} x{len(r['skid'])} (данные {exp or 'тишина'})"))
    bad = [x for x in out if not x[0].endswith('_old') and not x[1]]
    reds = [x for x in out if x[0].endswith('_old')]
    for sc, ok, msg in out:
        tag = ('ok  ' if ok else 'FAIL') if not sc.endswith('_old') else ('КРАСНЫЙ ПРОШЁЛ' if ok else 'красный упал (так и надо)')
        print(f'{tag} {sc}: {msg}')
    if bad: print('FAIL', bad[0][0]); return 1
    if any(r[1] for r in reds): print('FAIL красный контроль прошёл — гейт ничего не доказывает'); return 1
    print('PASS 413а: парящие звучат своим профилем и своим заносом из данных; прежний путь пойман'); return 0


if __name__ == '__main__':
    raise SystemExit(main())
