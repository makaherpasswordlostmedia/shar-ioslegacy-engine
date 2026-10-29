"""All-level source -> exported bank audit, with actual previous rules as RED.

No speakers/emulator. Source trace evaluator walks raw RMS nodes and bounded
repeats independently of the production region compiler. Resource bytes and
profile assignments are read back from SAB/SAP, not trusted from a success log.
"""
import argparse
import collections
import hashlib
import itertools
import json
import os
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import audio_export as A
import sound_export as S
import rms
from traffic_export import level_script

FIELDS = ['EngineClipName', 'EngineIdleClipName', 'HornClipName', 'DamagedEngineClipName',
          'CarDoorOpenClipName', 'CarDoorCloseClipName', 'RoadSkidClipName', 'DirtSkidClipName']


def disc_trace(c, region, choice):
    def play(ref):
        typ, _, d = c.el(ref)
        if typ == 'event_stream':
            yield c.stream_file(c.owner(d[1])[1])[1].replace('\\', '/').lower()
        elif typ == 'logic_and':
            for child in c.store[d[1]]: yield from play(child)
        elif typ == 'logic_or':
            children = c.store[d[1]]
            yield from play(children[choice % len(children)])
        elif typ == 'logic_repeat':
            assert d[1] == d[2], ('uncovered random repeat', d)
            for _ in range(min(d[1], 16)): yield from play(d[3])
        else: raise AssertionError(('uncovered RMS node', typ))
    layers = c.store[c.pools['regions']['els'][region][1]]
    assert len(layers) == 1
    layer = c.el(layers[0])[2]
    return list(itertools.islice(play(c.el(layer[3])[2][0]), 8))


def track_trace(tracks, first, choice, basedir):
    if not first: return []
    byname = {t[0]: t for t in tracks}; name = first[choice % len(first)]; trace = []
    for _ in range(8):
        row = byname[name]
        trace.append(os.path.relpath(Path(row[1]).resolve(), Path(basedir).resolve()).replace('\\', '/').lower().removesuffix('.rsd'))
        name = name if row[2] else row[3]
        if not name: break
    return trace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old', action='store_true')
    ap.add_argument('--packs', type=Path, default=ROOT/'build/audio-audit')
    args = ap.parse_args()
    if args.old: os.environ['MUSIC_GRAPH_OLD'] = os.environ['CAR_WORLD_AUDIO_OLD'] = '1'
    res, cars, _, gl = A.load_scripts()
    failures, events_report, levels, car_report = [], [], [], []
    used = collections.defaultdict(list)
    def check(ok, message):
        if not ok: failures.append(message)
    for lv in range(1, 8):
        tracks, events, _ = S.mission_music(lv)
        event_map = {n: ts for n, ts, _ in events}
        c = rms.read(S.SND/'music'/f'l{lv}_music.rms')
        role_tracks = S.music_table(lv)
        role_checks = [('Sunday_Drive_start', 'sunday_drive'), ('OF_explore_mission', 'of_explore'),
                       ('Store', 'muzak'), ('Hit_and_Run', 'hit_run')]
        for event_name, prefix in role_checks:
            actions = dict(c.events()).get(event_name)
            if actions is None: continue
            targets = [r for k, r in actions if k in ('play_region','push_region') and r is not None]
            if not targets: continue
            want = {c.stream_file(si)[1].replace('\\','/').lower()
                    for ss in c.region_streams(targets[0]) for si in ss}
            got = {p for n,p,_,_ in role_tracks if (n == prefix or n.startswith(prefix+'~')
                    or n == prefix+'_intro' or n == prefix+'_main')}
            check(want == got, f'L{lv} free/foot/shop/chase role {event_name}: {got} != {want}')
        for raw in c.pools['events']['els']:
            name = c.store[raw[0]].replace('_getoutofcar', '_get_out_of_car').replace('_Win', '_win')
            import re
            if not re.fullmatch(r'(M\d|Bonus|StreetRace0[123])_(start|drama|win|lose|get_out_of_car|10sec_to_go)', name): continue
            states = [None]
            if c.owner(raw[2]):
                refs = c.store[c.el(raw[2])[2][0]]; assert len(refs) == 1
                state = c.el(refs[0])[2]; states = [c.store[v] for v in c.store[state[1]]]
            for ai, arr in enumerate(c.store[raw[1]]):
                key = name + ('@' + states[ai] if states[ai] else '')
                regions = [c.owner(c.el(a)[2][1])[1] for a in c.store[arr] if c.el(a)[0] in ('play_region', 'push_region')]
                for choice in range(3):
                    expected = disc_trace(c, regions[0], choice) if regions else []
                    actual = track_trace(tracks, event_map.get(key, []), choice, S.SND/'music')
                    ok = key in event_map and actual == expected
                    check(ok, f'L{lv} {key} choice{choice}: {actual} != {expected}')
                    events_report.append(dict(level=lv, event=key, choice=choice, expected=expected, actual=actual, ok=ok))
        world = [d[8:].split(b'\0')[0].decode() for _, _, k, d, _, _ in S.locators(lv) if k == 3 and len(d) > 8]
        expected_cars = set(S.level_player_cars(lv)) | {n for n, _, _ in level_script(lv)[0]} | set(world)
        check(set(world) <= set(S.level_player_cars(lv)), f'L{lv} old export omits {world}')
        base = args.packs/f'l{lv}/audio'
        if not args.old:
            report = json.loads((base/'pack_report.json').read_text())
            b = (base/'sfx.sab').read_bytes()
            nr, nf, nc, ro, vo, fo, co = struct.unpack_from('<7I', b, 8)
            names = [b[ro+48*i:ro+48*i+24].split(b'\0')[0].decode() for i in range(nr)]
            data_off = struct.unpack_from('<I', b, 36)[0]
            for i, name in enumerate(names):
                first, count, trim, pmin, pmax = struct.unpack_from('<HHfff', b, ro+48*i+24)
                source = res[name]
                files = [f for f in source['files'] if A.game_path(f)]
                check(count == len(files), f'L{lv} resource variants {name}')
                check(abs(trim-source['trim']) < 1e-5 and abs(pmin-source['pitch'][0]) < 1e-5
                      and abs(pmax-source['pitch'][1]) < 1e-5, f'L{lv} resource tuning {name}')
                for j, file in enumerate(files):
                    fi = struct.unpack_from('<H', b, vo+2*(first+j))[0]
                    pos, nb, ns = struct.unpack_from('<III', b, fo+32*fi)
                    src = A.read_rsd(A.game_path(file))
                    check(b[data_off+pos:data_off+pos+len(src['data'])] == src['data'], f'L{lv} resident ADPCM {name}')
                    check(nb == src['nblk'] and ns == src['nsamp'], f'L{lv} resident length {name}')
            profiles = {}
            for i in range(nc):
                off = co+152*i; model = b[off:off+16].split(b'\0')[0].decode()
                ids = struct.unpack_from('<8h', b, off+16)
                profiles[model] = dict(zip(FIELDS, [names[j] if j >= 0 else None for j in ids]))
            check(set(profiles) == expected_cars, f'L{lv} car coverage: {set(profiles)^expected_cars}')
            for model, actual in profiles.items():
                used[model].append(lv); row = cars[model]
                for field in FIELDS:
                    want = row.get(field)
                    if field == 'RoadSkidClipName': want = want or gl.get('SkidRoadClipName', 'skid')
                    if field == 'DirtSkidClipName': want = want or gl.get('SkidDirtClipName', 'dirt_skid')
                    if field == 'HornClipName': want = want or 'horn'
                    check(actual[field] == (want if want in res else None), f'L{lv} {model} {field}: {actual[field]} != {want}')
                car_report.append(dict(level=lv, model=model, profile=actual, overlay=row.get('OverlayClipName')))
            sap = (base/'music.sap').read_bytes(); nt, to = struct.unpack_from('<II', sap, 8)
            manifest = {t['name']: t for t in report['music']}
            actual_tracks = []
            for i in range(nt):
                off = to+64*i; name = sap[off:off+28].split(b'\0')[0].decode()
                pos, nb, ns, ls, le, rate, ch, flags, nxt, bus = struct.unpack_from('<IIIIIHBBhh', sap, off+28)
                src = A.read_rsd(A.game_path(manifest[name]['file']))
                check((nb, ns, rate, ch) == (src['nblk'], src['nsamp'], src['rate'], 2), f'L{lv} stream metadata: {name}')
                raw = src['data']
                if src['ch'] == 1: raw = b''.join(raw[k:k+16]*2 for k in range(0,len(raw),16))
                check(sap[pos:pos+len(raw)] == raw, f'L{lv} changed ADPCM: {name}')
                nextname = sap[to+64*nxt:to+64*nxt+28].split(b'\0')[0].decode() if nxt >= 0 else None
                if bus == 0: actual_tracks.append((name, A.game_path(manifest[name]['file']), bool(flags&1), nextname))
            # Check production merge did not alias graphs by file alone.
            actual_map = {t[0]: t for t in actual_tracks}
            for n, p, loop, nxt in tracks:
                check(n in actual_map and actual_map[n][2:] == (loop,nxt), f'L{lv} graph descriptor changed in SAP: {n}')
            # Verify every MEVT row in the binary, including matrix variants.
            eo, es = struct.unpack_from('<II', b, 80); ext=b[eo:eo+es]; nsec=struct.unpack_from('<I',ext,4)[0]
            secs = {ext[8+16*i:12+16*i]:struct.unpack_from('<III',ext,12+16*i) for i in range(nsec)}
            off,count,stride=secs[b'MEVT']; actual_events={}
            for i in range(count):
                o=off+i*stride; name=ext[o:o+28].split(b'\0')[0].decode(); ids=struct.unpack_from('<3h',ext,o+28); n=ext[o+34]
                actual_events[name]=[sap[to+64*j:to+64*j+28].split(b'\0')[0].decode() for j in ids[:n]]
            check(actual_events == event_map, f'L{lv} binary MEVT differs')
            levels.append(dict(level=lv, profiles=nc, events=count, tracks=nt, sab=len(b), sap=len(sap),
                               resident=report['resident_audio_bytes'], world=world,
                               music_roles={n:p for n,p,_,_ in role_tracks},
                               sab_sha256=hashlib.sha256(b).hexdigest(), sap_sha256=hashlib.sha256(sap).hexdigest()))
        print(f'L{lv}: events={len(events)} profiles={len(expected_cars)} cumulative failures={len(failures)}', flush=True)
    all_cars = [dict(model=n, levels=used[n], clips={k:v for k,v in c.items() if 'ClipName' in k},
                     unresolved=[v for k,v in c.items() if 'ClipName' in k and v and v not in res]) for n,c in cars.items()]
    out=args.packs/('catalog-old.json' if args.old else 'catalog.json')
    out.write_text(json.dumps(dict(levels=levels,all_car_profiles=all_cars,cars=car_report,events=events_report,failures=failures),indent=2)+'\n')
    for msg in failures[:12]: print('FAIL',msg)
    print(f'{"FAIL" if failures else "PASS"} source traces={len(events_report)} disc profiles={len(cars)} failures={len(failures)}')
    return bool(failures)

if __name__ == '__main__': raise SystemExit(main())
