#!/usr/bin/env python3
"""Полнота звука миссий уровня в пакете (build/audio/music.sap + sfx.sab MEVT) против пакета миссий (tools/missions/compile.py).
   voice_pack_check.py [--audio build/audio] [--plant]   -> код 0 = зелёный
  * каждая реплика каждого разговора уровня (SetDialogueInfo / SetCompletionDialog / вступления бонусов) — дорожка
    music.sap по правилу имени (tools/sound_export.py voice_track_name = viewer/msn_audio.c msnAudioVoiceName), длина > 0.3 с;
  * у сюжетных миссий M1..M7 событие <код>_start и <код>_win/_lose в таблице MEVT ведут на существующие дорожки;
  * --plant: отрицательный контроль — из таблицы дорожек «пропадает» реплика Мардж icecream 1 -> обязан быть красным."""
import argparse, importlib.util, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import sound_export as SE

ap = argparse.ArgumentParser(); ap.add_argument('--audio', default=str(ROOT / 'build/audio')); ap.add_argument('--plant', action='store_true')
a = ap.parse_args()
sap = Path(a.audio, 'music.sap').read_bytes(); sab = Path(a.audio, 'sfx.sab').read_bytes()
nt, to = struct.unpack_from('<II', sap, 8)
tracks = {}
for i in range(nt):
    r = sap[to + 64 * i: to + 64 * (i + 1)]
    name = r[:28].split(b'\0')[0].decode(); nsamp, = struct.unpack_from('<I', r, 36); rate, = struct.unpack_from('<H', r, 48)
    tracks[name] = (i, nsamp / rate if rate else 0.0)
if a.plant: tracks.pop('v_icecream_1_ci_mrg_l1', None)
byidx = {i: n for n, (i, _) in tracks.items()}
eo, el = struct.unpack_from('<II', sab, 80); e = sab[eo:eo + el]; mev = {}
ns, = struct.unpack_from('<I', e, 4)
for k in range(ns):
    tag = e[8 + 16 * k: 12 + 16 * k]; off, cnt, st = struct.unpack_from('<III', e, 12 + 16 * k)
    if tag == b'MEVT':
        for j in range(cnt):
            r = e[off + j * st: off + (j + 1) * st]
            ids = struct.unpack_from('<3h', r, 28); n = r[34]
            mev[r[:28].split(b'\0')[0].decode()] = [byidx.get(t) for t in ids[:n]]
voice, bad_names = SE.mission_voice(1)
spec = importlib.util.spec_from_file_location('mc', ROOT / 'tools/missions/compile.py'); mc = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(ROOT / 'tools/missions')); spec.loader.exec_module(mc)
c = mc.Compiler(1); c.compile(); P = c.pack
bad, ok = [], 0
for clip in P.clips:
    f = P.strings[clip[0]]; tn = SE.voice_track_name(f)
    if tn not in tracks: bad.append(f'нет голоса: {f} (дорожка {tn})')
    elif tracks[tn][1] < .3: bad.append(f'пустая реплика {tn}')
    else: ok += 1
for m in range(1, 8):
    for suf in ('_start', '_win', '_lose'):
        ev = f'M{m}{suf}'
        if not mev.get(ev) or None in mev[ev]: bad.append(f'музыка: {ev} -> {mev.get(ev)}')
print(f'реплики: {ok}/{len(P.clips)} с голосом; события музыки: {len(mev)} ({", ".join(sorted(mev))})')
for b in bad[:20]: print('  ', b)
print('ИТОГ:', 'зелёный' if not bad else f'КРАСНЫЙ ({len(bad)})')
sys.exit(1 if bad else 0)
