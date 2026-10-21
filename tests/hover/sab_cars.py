#!/usr/bin/env python3
"""Правка 413а: профили машин в пакете звука sfx.sab (tools/audio_export.py encode_car): имя, мотор, холостой, гудок, занос по
дороге / грунту — именами ресурсов. -> печать; с --check сверка заноса с данными диска (carSoundParameters RoadSkidClipName /
DirtSkidClipName, иначе общий skid / dirt_skid из globalSettings).
  .venv/bin/python tests/hover/sab_cars.py build/levels/l7/audio/sfx.sab [--check]"""
import struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))


def cars(path):
    b = open(path, 'rb').read()
    ver, nres, nfile, ncar, resOff, varOff, fileOff, carOff = struct.unpack_from('<8I', b, 4)
    names = [b[resOff + 48 * i:resOff + 48 * i + 24].split(b'\0')[0].decode() for i in range(nres)]
    out = []
    for i in range(ncar):
        o = carOff + 152 * i; nm = b[o:o + 16].split(b'\0')[0].decode(); r = struct.unpack_from('<8h', b, o + 16)
        n = lambda k: names[k] if k >= 0 else None
        out.append(dict(name=nm, engine=n(r[0]), idle=n(r[1]), horn=n(r[2]), skid=n(r[6]), dirtSkid=n(r[7])))
    return out


if __name__ == '__main__':
    rows = cars(sys.argv[1]); bad = 0
    if '--check' in sys.argv:
        import audio_export as A
        _, data, _, gl = A.load_scripts()
    for c in rows:
        line = f"{c['name']:10} engine={c['engine']} idle={c['idle']} horn={c['horn']} skid={c['skid']} dirt={c['dirtSkid']}"
        if '--check' in sys.argv:
            d = data[c['name']]
            want = (d.get('RoadSkidClipName') or gl.get('SkidRoadClipName', 'skid'), d.get('DirtSkidClipName') or gl.get('SkidDirtClipName', 'dirt_skid'),
                    d.get('EngineClipName'))
            ok = (c['skid'], c['dirtSkid'], c['engine']) == want; bad += not ok
            line += '' if ok else f'   FAIL данные: skid={want[0]} dirt={want[1]} engine={want[2]}'
        print(line)
    raise SystemExit(1 if bad else 0)
