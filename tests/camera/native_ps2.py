#!/usr/bin/env python3
"""Read archived original EE snapshots, never start or write to an emulator.

SuperCamCentral -> active SuperCam -> tPointCamera is verified through original
RTTI code, ownership, inverse matrices, position and lens fields. radSoundHalListener
is retained only as a rejected historical reference. Coordinates are native PS2,
the same axes as the archived trace; the port requires a single Z reflection.
Zstd P2S archives require Python 3.14; missing evidence is an error, never zero samples.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
CENTRAL = 0x609340
CLASSES = {0x455a58: 'FollowCam', 0x455730: 'RailCam', 0x455340: 'StaticCam'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_root(value=None):
    roots = [Path(value)] if value else [Path(os.environ.get('SHAR_PS2_REF_ROOT', ROOT)),
                                        ROOT.parent / 'shar-psp-ps2-w']
    for root in roots:
        if (root / 'build/twins/o4/ps2_v95_house_50_native/trace.tsv').is_file():
            return root.resolve()
    raise ValueError('НЕТ ДАННЫХ: --evidence-root с архивами оригинала; проверены ' + str(roots))


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


def native_runs(root=None):
    root = evidence_root(root)
    fact = json.loads((ROOT / 'knowledge/facts/ps2-house-native-supercam.yaml').read_text())
    runs = []
    for entry in fact['evidence']['runs']:
        trace = root / entry['run'] / 'trace.tsv'
        if not trace.is_file() or sha(trace) != entry['trace_sha256']:
            raise ValueError(f'НЕТ ДАННЫХ / SHA: {trace}')
        with trace.open() as f:
            rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(f, delimiter='\t')]
        by_frame = {int(row['rel']): row for row in rows}
        refs = {}
        for state in entry['states']:
            ee = read_state(root / state['path'], state['sha256'])
            reference = decode(ee)
            frame = int(Path(state['path']).stem.split('_')[-1])
            if reference['kind'] != state['type'] or reference['active'] != state['active']:
                raise ValueError('snapshot active SuperCam changed')
            row = by_frame.get(frame)
            if row is None or int(row['active_supercam_ptr']) != int(reference['active'], 16):
                raise ValueError('snapshot is not aligned to its original dense trace')
            reference.update(frame=frame, state=state['path'], sha256=state['sha256'])
            refs[frame] = reference
        runs.append(dict(name=Path(entry['run']).name, rows=rows, refs=refs,
                         trace=str(trace), trace_sha256=entry['trace_sha256']))
    return runs


def check(root=None):
    runs = native_runs(root)
    refs = [ref for run in runs for ref in run['refs'].values()]
    if len(refs) != 39:
        raise ValueError('incomplete native house reference coverage')
    jumps = jump_runs(root)
    refs += [ref for run in jumps for ref in run['refs'].values()]
    rejected = dict(wrong_class=0, listener_eye=0, shifted_position=0)
    owner = evidence_root(root)
    for ref in refs:
        ee = read_state(owner / ref['state'], ref['sha256'])
        for tag, kw in [('wrong_class', dict(camera_offset=0x44)), ('listener_eye', dict(use_listener=True))]:
            try:
                decode(ee, **kw)
            except ValueError:
                rejected[tag] += 1
            else:
                raise ValueError('negative control did not fail: ' + tag)
        damaged = bytearray(ee)
        p = int(ref['camera'],16)+0xcc
        struct.pack_into('<f',damaged,p,struct.unpack_from('<f',damaged,p)[0]+.01)
        try:
            decode(damaged)
        except ValueError:
            rejected['shifted_position'] += 1
        else:
            raise ValueError('1cm position mismatch control did not fail')
    if len(refs) != 64:
        raise ValueError('incomplete native reference coverage')
    return dict(status='PASS', snapshots=len(refs),house_snapshots=39,jump_snapshots=25, negative_controls=rejected,
                listener_distance_m=[min(r['listener_distance'] for r in refs), max(r['listener_distance'] for r in refs)],
                max_inverse_error=max(r['matrix_inverse_error'] for r in refs), runs=runs+jumps)


def jump_runs(root=None):
    """V104: dense body and byte-A callbacks; eyes only from 25 original snapshots."""
    root = evidence_root(root)
    fact = json.loads((ROOT / 'knowledge/facts/ps2-camera-after-landing.yaml').read_text())
    ledger = ROOT / 'knowledge/facts/ps2-native-camera-eye.yaml'
    hashes = {Path(x['path']).parent.name:x['sha256'] for x in json.loads(ledger.read_text())['jump_trace_inputs']} if ledger.is_file() else {}
    cases = []
    for entry in fact['table']:
        path = root / 'build/twins/o4' / entry['id'] / 'trace.tsv'
        if not path.is_file(): raise ValueError('НЕТ ДАННЫХ: '+str(path))
        if hashes and sha(path)!=hashes.get(entry['id']):
            raise ValueError('archived V104 trace SHA changed: '+str(path))
        with path.open() as f:
            rows = [{k:float(v) for k,v in row.items()} for row in csv.DictReader(f,delimiter='\t')]
        by_frame = {int(row['rel']):row for row in rows}
        refs = {}
        for state in fact['evidence']['snapshots']:
            if Path(state['path']).parent.name != entry['id']: continue
            ee = read_state(root/state['path'],state['sha256']); ref = decode(ee)
            frame = int(Path(state['path']).stem.split('_')[-1]); row=by_frame[frame]
            if ref['kind']!='FollowCam': raise ValueError('V104 reference is not FollowCam')
            if math.dist(ref['listener'],[row[f'cam_pos[{i}]'] for i in range(3)])>.001:
                raise ValueError('P2S not aligned with archived trace frame')
            u=lambda p:struct.unpack_from('<I',ee,p)[0]
            vehicle=0x1295b50
            if rtti(ee,u(vehicle))!='7Vehicle': raise ValueError('wrong native Vehicle class')
            callbacks=[]
            for i in range(4):
                wheel=u(vehicle+0x414+4*i)
                if u(wheel)!=vehicle or u(wheel+8)!=i: raise ValueError('wrong native Wheel owner/index')
                a=ee[wheel+0x34]
                if a!=(int(row[f'wheel{i}_contact_candidate'])&255):
                    raise ValueError('dense raw contact word is not typed Wheel byte A')
                callbacks.append(a)
            ref.update(frame=frame,state=state['path'],sha256=state['sha256'],wheel_callback_A=callbacks)
            refs[frame]=ref
        if len(refs)!=5: raise ValueError('incomplete V104 true eye coverage')
        cases.append(dict(name=entry['id'],rows=rows,refs=refs,trace=str(path),trace_sha256=sha(path),
                          lip=entry['lip']['frame'],landing=entry['landing_vertical_response_frame']))
    return cases


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence-root'); p.add_argument('--out', type=Path)
    a = p.parse_args()
    try:
        result = check(a.evidence_root)
        if a.out:
            a.out.parent.mkdir(parents=True, exist_ok=True)
            a.out.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({k: v for k, v in result.items() if k != 'runs'}, indent=2))
    except (ValueError, OSError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
