#!/usr/bin/env python3
"""Гейт «атмосфера уровня» (29.09): каждые ворота атмосферы уровня N на диске привязаны к дорожке звука из композиции.

Истина — диск: локаторы-события уровня (tools/sound_export.locators, kind 0) и композиция sound/ambience/ambience.rms,
разобранная tools/rms.py (событие -> регион -> поток -> файл). Проверяется СОБРАННЫЙ пакет звука уровня
(music.sap + sfx.sab, секция ZONE расширения SXT1), тот, что читает viewer/sound.c:
  1) у каждого локатора-ворот со звучащим регионом в ZONE столько объёмов, сколько у локатора на диске, и дорожка —
     дорожка этого региона (amb_<регион>);
  2) дорожка есть в music.sap, шина атмосферы (1), петля, и её звук — байт в байт файл региона с диска (PS-ADPCM блоки);
  3) первая дорожка атмосферы (её играет старт уровня, sndLevelStart) — регион с наибольшим числом объёмов ворот.
  ambience_check.py --level N [N ...] [--pack DIR]   зелёный: PASS (по умолчанию DIR = build/levels/l<N>/audio, у 1 — build/audio)
  ambience_check.py --level N --plant DIR       красный: собрать пакет уровня с ПУСТОЙ привязкой (AMB_MAP = {}) в DIR и
                                                проверить его — обязан провалиться (так было у уровней 2–7 до 29.09)"""
import argparse, os, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import sound_export as SE   # noqa: E402
import audio_export as AE   # noqa: E402


def sap_tracks(p):
    b = Path(p).read_bytes()
    assert b[:4] == b'SAP1', p
    n, tbl = struct.unpack_from('<II', b, 8)
    out = {}
    for i in range(n):
        o = tbl + 64 * i
        name = b[o:o + 28].split(b'\0')[0].decode()
        off, nblk, nsamp, ls, le, rate, ch, flags, nxt, bus = struct.unpack_from('<IIIIIHBBhh', b, o + 28)
        out[name] = dict(index=i, off=off, nblk=nblk, nsamp=nsamp, loop=flags & 1, bus=bus, data=b[off:off + nblk * 32])
    return out


def sab_zones(p):
    b = Path(p).read_bytes()
    assert b[:4] == b'SAB1', p
    ext, n = struct.unpack_from('<II', b, 80)
    if not ext: return []
    e = b[ext:ext + n]
    assert e[:4] == b'SXT1'
    nsec, = struct.unpack_from('<I', e, 4)
    for k in range(nsec):
        tag = e[8 + 16 * k:12 + 16 * k]
        off, cnt, stride = struct.unpack_from('<III', e, 12 + 16 * k)
        if tag == b'ZONE':
            return [dict(event=struct.unpack_from('<I', e, off + stride * i + 4)[0],
                         t=struct.unpack_from('<3f', e, off + stride * i + 56),
                         track=e[off + stride * i + 68:off + stride * i + 96].split(b'\0')[0].decode()) for i in range(cnt)]
    return []


def expected(lv, amap):
    """-> [(имя локатора, событие, регион, дорожка, файл, [центры объёмов])] звучащих ворот уровня lv на диске"""
    out = []
    for fn, nm, kind, d, p3, vols in SE.locators(lv):
        if kind != 0 or len(d) < 4: continue
        ev, = struct.unpack_from('<I', d)
        m = amap.get(ev)
        if not m or not m['alts']: continue
        out.append((nm, ev, m['region'], m['track'], m['file'], [tuple(float(x) for x in v['t']) for v in vols]))
    return out


def check(lv, pack, amap, sab=None):
    bad = []
    exp = expected(lv, amap)
    if not exp:
        print(f'уровень {lv}: звучащих ворот атмосферы на диске нет'); return bad
    sap = Path(pack) / 'music.sap' if Path(pack).is_dir() else Path(pack)   # каталог пакета или путь music.sap (+ sab)
    tracks = sap_tracks(sap); zones = sab_zones(sab or sap.parent / 'sfx.sab')
    zi = {}
    for z in zones: zi.setdefault((z['event'], tuple(round(c, 2) for c in z['t'])), []).append(z['track'])
    regions = {}
    for nm, ev, reg, tn, f, centres in exp:
        regions.setdefault(tn, [reg, f, 0])[2] += len(centres)
        for c in centres:
            got = zi.get((ev, tuple(round(x, 2) for x in c)))
            if not got: bad.append(f'ворота {nm} (событие {ev}, {reg}): объёма нет в ZONE'); continue
            if tn not in got: bad.append(f'ворота {nm}: дорожка {got} вместо {tn} ({reg})')
    for tn, (reg, f, nvol) in regions.items():
        t = tracks.get(tn)
        if not t: bad.append(f'регион {reg}: дорожки {tn} нет в music.sap'); continue
        if t['bus'] != 1 or not t['loop']: bad.append(f'{tn}: шина {t["bus"]}, петля {t["loop"]} (ждём 1, петля)')
        rs = AE.read_rsd(f); d = rs['data']
        if rs['ch'] == 1: d = b''.join(d[i:i + 16] * 2 for i in range(0, len(d), 16))
        if t['data'] != d: bad.append(f'{tn}: звук не равен файлу региона {os.path.relpath(f, SE.GAME)}')
    amb = sorted((t for t in tracks.values() if t['bus'] == 1), key=lambda t: t['index'])
    first = next((n for n, t in tracks.items() if amb and t['index'] == amb[0]['index']), None)
    top = max(regions, key=lambda t: regions[t][2])
    if first is None or regions.get(first, [0, 0, -1])[2] != regions[top][2]:
        bad.append(f'старт: первая дорожка атмосферы {first}, ждём регион с наибольшим числом ворот {top}')
    print(f'уровень {lv}: ворот {len(exp)}, объёмов {sum(len(e[5]) for e in exp)}, регионов {len(regions)}: ' +
          ', '.join(f'{tn}={os.path.basename(f)}×{n}' for tn, (reg, f, n) in regions.items()) + f'; старт {first}')
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=int, nargs='+', required=True)
    ap.add_argument('--pack'); ap.add_argument('--plant')
    a = ap.parse_args()
    amap = SE.ambience_map()
    bad = []
    for lv in a.level:
        pack = a.pack or str(ROOT / ('build/audio' if lv == 1 and not (ROOT / 'build/levels/l1/audio/music.sap').exists()
                                     else f'build/levels/l{lv}/audio'))
        if a.plant:   # пустая привязка событий к регионам: экспорт звука уровня без атмосферы (прежнее состояние уровней 2–7)
            SE.AMB_MAP = {}
            sys.argv = ['sound_export.py', '--level', str(lv), '--out', a.plant]
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()): SE.main()
            pack = a.plant
        bad += [f'уровень {lv}: {x}' for x in check(lv, pack, amap)]
    for x in bad[:12]: print('ПРОВАЛ:', x)
    if len(bad) > 12: print(f'... ещё {len(bad) - 12}')
    print('FAIL' if bad else 'PASS')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
