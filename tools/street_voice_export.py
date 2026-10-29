"""Named pedestrian and doorbell voices, joined by authored resource folders.

Doorbells come from ActionEvent locator payloads and their TriggerVolumes;
coordinates, radii and rotations are never approximated by nearest buildings.
"""
import re, struct
import numpy as np
import npc_list
from p3d import read, walk, string

def extra(lv, game, resources, resolve):
    names = {x['name'].lower() for x in npc_list.npcs(lv)}
    art = game / 'art'; doors = {}; records = []
    for f in [art/f'l{lv}_terra.p3d', *sorted(art.glob(f'l{lv}[rzi]*.p3d'))]:
        for c in walk(read(f)):
            if c.id != 0x3000005: continue
            _, p = string(c.data); kind, n = struct.unpack_from('<II', c.data, p)
            data = c.data[p+8:p+8+4*n]; values = [s.decode('latin1') for s in data.split(b'\0') if s]
            if kind != 9 or 'Doorbell' not in values: continue
            speaker = values[0].removeprefix('DB_').lower()
            for t in c.children:
                if t.id != 0x3000006: continue
                _, q = string(t.data); rect, = struct.unpack_from('<I', t.data, q)
                half = struct.unpack_from('<3f', t.data, q+4)
                M = np.frombuffer(t.data, '<f4', 16, q+16).reshape(4,4)
                F = np.diag([1.,1.,-1.,1.]); M = F @ M @ F
                key = (speaker, rect, *half, *M.flatten())
                doors[key] = (speaker, rect, half, M)
    names.update(d[0] for d in doors.values())
    tracks = []; serials = {}; source_counts = {}; door_prefixes = set()
    for name, r in sorted(resources.items()):
        m = re.match(r'P_(N?HitByC|HitByW)_', name, re.I)
        bell = name.startswith('W_Doorbell_')
        if not (m or bell) or not r['files']: continue
        speaker = r['files'][0].split('/')[0].lower()
        # Authored character names: Dr.Nick = nriviera, Flanders = ned
        speaker = {'dr.nick': 'nriviera', 'flanders': 'ned'}.get(speaker, speaker)
        if speaker not in names: continue
        path = resolve(r['files'][0])
        if not path: raise ValueError(f'missing voice {name}')
        prefix = ('db_' if bell else 'p_'+m.group(1).lower()+'_') + speaker + '_'
        serials[prefix] = serials.get(prefix, 0) + 1
        alias = prefix + str(serials[prefix]); assert len(alias) <= 27, alias
        tracks.append((alias, path)); source_counts[prefix] = serials[prefix]
        if bell: door_prefixes.add(prefix)
    for speaker, rect, half, M in doors.values():
        prefix = 'db_'+speaker+'_'
        if prefix not in door_prefixes: raise ValueError(f'Doorbell {speaker}: no source voice')
        records.append(struct.pack('<28sI3f3f9f4x', prefix.encode(), rect, *M[3,:3], *half, *M[:3,:3].flatten()))
    return tracks, b''.join(records), source_counts
