#!/usr/bin/env python3
"""Verify and export true tPointCamera references from existing owner PS2 states.

Based on Codex's tests/camera/native_ps2.py decoder (read-only). No emulator,
network, game writes or interpolation. Source archives and dense traces are
verified against hashes; dense cam_pos/cam_fwd remain sound-listener fields.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[2]
CENTRAL = 0x609340
CLASSES = {0x455a58: 'FollowCam', 0x455730: 'RailCam', 0x455340: 'StaticCam'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rtti(ee, vtable):
    """Decode the original typeinfo method's a1 literal, not a guessed object name."""
    u = lambda p: struct.unpack_from('<I', ee, p)[0]
    fn = u(vtable + 4)
    regs = {}
    for ins in struct.unpack_from('<32I', ee, fn):
        op, rs, rt, imm = ins >> 26, (ins >> 21) & 31, (ins >> 16) & 31, ins & 65535
        if op == 15:
            regs[rt] = imm << 16
        elif op in (9, 13) and rs in regs:
            regs[rt] = ((regs[rs] + (imm if imm < 32768 else imm - 65536)) & 0xffffffff
                        if op == 9 else regs[rs] | imm)
            if rt == 5:
                p = regs[rt]
                if 0 < p < len(ee) - 100:
                    return ee[p:p + 100].split(b'\0')[0].decode('ascii')
    raise ValueError(f'RTTI literal not proven for vtable {vtable:#x}')


def decode(ee, camera_offset=0x4c, use_listener=False):
    u = lambda p: struct.unpack_from('<I', ee, p)[0]
    f = lambda p, n=3: struct.unpack_from('<' + str(n) + 'f', ee, p)
    if u(CENTRAL) != 0x455f68 or rtti(ee, u(CENTRAL)) != '15SuperCamCentral':
        raise ValueError('wrong SuperCamCentral class')
    active, slot = u(CENTRAL + 0x8c), u(CENTRAL + 0x90)
    if slot >= 64 or u(CENTRAL + 0x0c + slot * 4) != active:
        raise ValueError('active SuperCam does not match its registered slot')
    vt = u(active)
    name = CLASSES.get(vt)
    if name is None or rtti(ee, vt) != str(len(name)) + name:
        raise ValueError('wrong active SuperCam class')
    camera = u(active + camera_offset)
    if not 0 < camera < len(ee) - 512 or u(camera) != 0x48df48 or rtti(ee, u(camera)) != '12tPointCamera':
        raise ValueError('wrong tPointCamera class/ownership')
    view, inverse = f(camera + 0x48, 16), f(camera + 0x88, 16)
    error = max(abs(sum(view[i * 4 + k] * inverse[k * 4 + j] for k in range(4)) - (i == j))
                for i in range(4) for j in range(4))
    # World translation around 600m magnifies binary32 roundoff. Use the
    # absolute dot-product sum as the condition scale, retaining strict
    # rotation checks; this is numerical validation, not a camera tolerance.
    invalid = any(abs(sum(view[i*4+k]*inverse[k*4+j] for k in range(4))-(i==j)) >
                  64 * 2**-23 * max(1.,sum(abs(view[i*4+k]*inverse[k*4+j]) for k in range(4)))
                  for i in range(4) for j in range(4))
    if invalid:
        raise ValueError('camera matrices are not inverse')
    position, target, listener = f(camera + 0xcc), f(camera + 0xd8), f(0x7aaba0)
    eye = listener if use_listener else position
    if max(abs(a - b) for a, b in zip(eye, inverse[12:15])) > 1e-5:
        raise ValueError('eye disagrees with actual camera world-matrix translation')
    lens, owner_lens = f(camera + 0x10, 4), f(active + 0x50, 4)
    if lens != owner_lens or not all(math.isfinite(x) for x in (*eye, *target, *lens)):
        raise ValueError('camera lens/owner mismatch')
    if name == 'StaticCam' and f(active + 0x10c) != position:
        raise ValueError('StaticCam authored and actual position disagree')
    return dict(kind=name, active=hex(active), slot=slot, camera=hex(camera), vtable=hex(u(camera)),
                eye=eye, target=target, forward=f(camera + 0xa8), up=f(camera + 0x98), lens=lens,
                listener=listener, listener_distance=math.dist(position, listener), matrix_inverse_error=error)


def read_state(path, expected_sha):
    if not path.is_file():
        raise ValueError(f'НЕТ ДАННЫХ: {path}')
    if sha(path) != expected_sha:
        raise ValueError(f'original snapshot hash mismatch: {path}')
    try:
        with zipfile.ZipFile(path) as z:
            return z.read('eeMemory.bin')
    except NotImplementedError as e:
        raise ValueError('Zstd P2S: run with python3.14 (read-only archive support)') from e


CARDS = {'ps2-camera-after-landing': 25, 'ps2-house-camera-speeds': 20,
         'ps2-house-native-supercam': 39}


def elevation(vector):
    return math.degrees(math.atan2(vector[1], math.hypot(vector[0], vector[2])))


def angle(a, b):
    value = sum(x*y for x,y in zip(a,b)) / math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    return math.degrees(math.acos(max(-1., min(1., value))))


def collect(root):
    """Export original measurements; native frame/body independently align the trace."""
    from collections import Counter
    cards = {}
    for name, expected in CARDS.items():
        fact = json.loads((root / 'knowledge/facts' / (name + '.yaml')).read_text())
        states = fact['evidence'].get('snapshots')
        if states is None:
            states = [state for run in fact['evidence']['runs'] for state in run['states']]
        if len(states) != expected:
            raise ValueError(f'НЕТ ДАННЫХ: {name}: {len(states)}/{expected} states')
        if len({state['path'] for state in states}) != expected:
            raise ValueError('duplicate snapshot coverage: '+name)
        expected_runs={entry['id'] for entry in fact['table']}
        if {Path(state['path']).parent.name for state in states} != expected_runs:
            raise ValueError('missing/foreign run coverage: '+name)
        traces, refs, controls = {}, [], Counter()
        for state in sorted(states, key=lambda s: (str(Path(s['path']).parent), int(Path(s['path']).stem.split('_')[-1]))):
            path = root / state['path']; frame = int(path.stem.split('_')[-1]); run = path.parent.name
            if run not in traces:
                trace = path.parent / 'trace.tsv'
                if not trace.is_file(): raise ValueError('НЕТ ДАННЫХ: ' + str(trace))
                trace_sha = sha(trace)
                previous = {entry['path']:entry['sha256'] for entry in fact.get('camera_relabel',{}).get('traces',[])}
                if previous and previous.get(str(trace.relative_to(root))) != trace_sha:
                    raise ValueError('archived trace hash mismatch: '+str(trace))
                with trace.open() as stream:
                    rows = [{k: float(v) for k,v in row.items()} for row in csv.DictReader(stream, delimiter='\t')]
                traces[run] = dict(path=str(trace.relative_to(root)), sha256=trace_sha, rows={int(r['rel']):r for r in rows})
            row = traces[run]['rows'].get(frame)
            if row is None: raise ValueError('НЕТ ДАННЫХ: trace frame ' + str(frame))
            ee = read_state(path, state['sha256']); ref = decode(ee)
            u = lambda p: struct.unpack_from('<I', ee, p)[0]
            f = lambda p,n=3: struct.unpack_from('<' + str(n) + 'f', ee, p)
            if u(0x5167d8) != int(row['frame']): raise ValueError('snapshot/trace native-frame mismatch')
            if max(abs(a-row[f'cam_pos[{i}]']) for i,a in enumerate(ref['listener'])) > .001:
                raise ValueError('snapshot/trace listener alignment mismatch')
            vehicle = 0x1295b50; sim = u(vehicle+0x4a8)
            if rtti(ee,u(vehicle)) != '7Vehicle' or u(sim) != 0x484030:
                raise ValueError('wrong native Vehicle/SimState binding')
            matrix = f(sim+0x10,16); body = list(matrix[12:15]); velocity = list(f(sim+0x50))
            if max(abs(a-row[f'mat[{12+i}]']) for i,a in enumerate(body)) > .001:
                raise ValueError('snapshot/trace body alignment mismatch')
            wheels=[]
            for i in range(4):
                wheel=u(vehicle+0x414+4*i)
                if u(wheel)!=vehicle or u(wheel+8)!=i: raise ValueError('wrong native Wheel owner/index')
                wheels.append(dict(pointer=hex(wheel),index=i,byte_A=ee[wheel+0x34],byte_B=ee[wheel+0x35],semantics='raw callback/status bytes, not proven floor support'))
            direction=[ref['target'][i]-ref['eye'][i] for i in range(3)]
            # The independent target/eye and inverse-matrix direction agree.
            if angle(direction,ref['forward']) > .002: raise ValueError('camera ray/matrix direction mismatch')
            h,aspect,near,far=ref['lens']; ph=2*math.atan2(abs(f(int(ref['camera'],16)+0x2c,1)[0]),abs(f(int(ref['camera'],16)+0x28,1)[0])); pv=2*math.atan2(abs(f(int(ref['camera'],16)+0x3c,1)[0]),abs(f(int(ref['camera'],16)+0x38,1)[0]))
            if abs(ph-h)>.00001 or abs(pv-2*math.atan(math.tan(h/2)/aspect))>.00001: raise ValueError('lens/frustum mismatch')
            listener_forward=[row[f'cam_fwd[{i}]'] for i in range(3)]
            ref.update(state=state['path'],state_sha256=state['sha256'],frame=frame,native_frame=u(0x5167d8),run=run,body=body,body_pitch_deg=elevation(matrix[8:11]),velocity=velocity,horizontal_kmh=3.6*math.hypot(velocity[0],velocity[2]),true_view_elevation_deg=elevation(ref['forward']),true_eye_above_body=ref['eye'][1]-body[1],legacy_listener_view_elevation_deg=elevation(listener_forward),legacy_listener_elevation_error_deg=elevation(listener_forward)-elevation(ref['forward']),target_matrix_angle_error_deg=angle(direction,ref['forward']),horizontal_fov_deg=math.degrees(h),vertical_fov_deg=math.degrees(pv),wheel_raw_bytes=wheels)
            refs.append(ref)
            for tag,kw in [('wrong_camera_field',dict(camera_offset=0x44)),('listener_as_eye',dict(use_listener=True))]:
                try: decode(ee,**kw)
                except ValueError: controls[tag]+=1
                else: raise ValueError('negative control did not fail: '+tag)
            if ref['kind']=='StaticCam':
                dirty=bytearray(ee); active=int(ref['active'],16); struct.pack_into('<f',dirty,active+0x10c,f(active+0x10c,1)[0]+.01)
                try:decode(dirty)
                except ValueError:controls['authored_eye_shift_1cm']+=1
                else:raise ValueError('StaticCam shifted-eye negative control did not fail')
        if controls['wrong_camera_field']!=expected or controls['listener_as_eye']!=expected:
            raise ValueError('negative control coverage incomplete')
        cards[name]=dict(status='PASS',expected_states=expected,states=refs,negative_controls=dict(controls),types=dict(Counter(ref['kind'] for ref in refs)),listener_distance_m=[min(r['listener_distance']for r in refs),max(r['listener_distance']for r in refs)],max_listener_elevation_error_deg=max(abs(r['legacy_listener_elevation_error_deg'])for r in refs),max_inverse_error=max(r['matrix_inverse_error']for r in refs),traces=[{k:v for k,v in info.items()if k!='rows'}for info in traces.values()])
    return dict(schema='ps2-native-camera-reference-v1',source_revision='c2ae6bb',axes='original PS2 world; port reflects Z once',sample_domain='P2S snapshot only; no interpolated or densely reconstructed eye',camera_binding='SuperCamCentral609340+8c -> activeSuperCam+4c -> tPointCamera eye+cc/target+d8; inverse88 translation+b8',cards=cards,total_states=sum(len(c['states'])for c in cards.values()))


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    try:
        data=collect(args.root.resolve())
        if args.out:
            args.out.parent.mkdir(parents=True,exist_ok=True)
            tmp=args.out.with_suffix(args.out.suffix+'.tmp')
            tmp.write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n');tmp.replace(args.out)
        for name,c in data['cards'].items():
            print(name,c['status'],len(c['states']),'states',c['types'],'RED',c['negative_controls'],'listener meters',c['listener_distance_m'],'pitch delta',c['max_listener_elevation_error_deg'])
        print('TOTAL',data['total_states'])
    except (ValueError,OSError,KeyError) as e:
        print(str(e),file=__import__('sys').stderr);return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
