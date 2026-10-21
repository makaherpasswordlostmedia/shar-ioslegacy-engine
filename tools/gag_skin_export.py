#!/usr/bin/env python3
"""Disc gag composites -> CHR1, preserving native PS2 skin weights and props.

Large scene skeletons are partitioned by drawable, retaining every ancestor;
each partition fits skin.c's 64 joints. No character or clip is substituted.
"""
import copy, struct, tempfile
from pathlib import Path
import numpy as np
import char_export as ce
from p3d import read, walk, string, Chunk
from frontend3d_export import anchor_place, col


def export(path):
    root = read(path)
    meshes = {string(c.data)[0]: c for c in root.children if c.id in (0x10000, 0x10001)}
    images = ce.load_images(read(ce.GAME / 'art/chars/global.p3d')); images.update(ce.load_images(root)); shaders = ce.load_shaders(root)
    for props in shaders.values():
        if props.get('TEX') in ('char_swatches.bmp', 'char_swatches_lit.bmp1'):
            props['TEX'] = 'char_swatches_lit.bmp'
        if props.get('TEX') == 'eyeball.0.bmp': props['TEX'] = 'eyeball.bmp.0'
        # Port rule: unsuffixed static eye material uses global frame zero
        if props.get('TEX') not in images and props.get('TEX', '') + '.0' in images:
            props['TEX'] += '.0'
    # Правка 483: шейдер сцены без текстуры (пусто или нет такой картинки) — белая 16×8, цвет даёт вершина (раньше KeyError: '' на сценах AddGagBinding Мо/DMV).
    # GAG_NOTEX_OLD=1 — как было (ошибка)
    import os
    if not os.environ.get('GAG_NOTEX_OLD'):
        white = (16, 8, np.array([[255, 255, 255, 255]] * 256, np.uint8), np.zeros(128, np.uint8))
        for props in shaders.values():
            if props.get('TEX', '') not in images:
                images['__white'] = white; props['TEX'] = '__white'
    # Disc rule (same orientation as psp_export.py, correction 226): P3DI
    # rows run bottom-up, PNG rows top-down. CHR1 flips V, so normalise P3DI.
    for image in (c for c in root.children if c.id == 0x19000):
        raw = next(c for c in walk(image) if c.id == 0x19002).data[4:]
        if raw[:4] == b'P3DI':
            key = string(image.data)[0].lower(); w, h, pal, idx = images[key]
            images[key] = (w, h, pal, idx.reshape(h, w)[::-1].copy().flatten())
    result = []
    for comp in (c for c in root.children if c.id == 0x4512):
        name, p = string(comp.data); skeleton, _ = string(comp.data, p)
        sk = next(c for c in root.children if c.id == 0x4500 and string(c.data)[0] == skeleton)
        joints = ce.load_skeleton(Chunk(0, b'', [sk]))
        animations = [c for c in root.children if c.id == 0x121000 and string(c.data, 4)[0] == 'PTRN_' + skeleton]
        clips = ce.load_clips(Chunk(0, b'', animations), joints)
        if not clips: raise ValueError(f'{path}: no PTRN for {skeleton}')
        groups = []
        for d in walk(comp):
            if d.id != 0x4515: continue  # rigid props/billboards remain in SPR1
            mn, _ = string(d.data)
            groups.extend(ce.load_strips(Chunk(0, b'', [meshes[mn]])))
        # One skin group can contain two characters. Split at the native strip
        # boundary before partitioning; do not change geometry or animation.
        partitions = []
        for shader, strips in groups:
            for strip in strips:
                needed = {int(b) for b, w in zip(strip['bones'].flat, strip['w'].flat) if w > 1e-4}
                for b in list(needed):
                    while joints[b]['parent'] >= 0:
                        b = joints[b]['parent']; needed.add(b)
                if len(needed) > 64: raise ValueError(f'{path}: drawable needs {len(needed)} ancestors')
                target = next((part for part in partitions if len(part[0] | needed) <= 64), None)
                if target is None: target = (set(), []); partitions.append(target)
                target[0].update(needed); target[1].append((shader, strip))
        place = anchor_place(root, name)
        place = np.eye(4) if place is None else col(place)
        for needed, parts in partitions:
            indices = sorted(needed); remap = {v: i for i, v in enumerate(indices)}
            jj = [copy.copy(joints[i]) for i in indices]
            for j in jj: j['parent'] = remap[j['parent']] if j['parent'] >= 0 else -1
            gg = []
            for shader, original in parts:
                s = dict(original); s['bones'] = np.array([[remap.get(int(b), 0) for b in row] for row in s['bones']])
                gg.append((shader, [s]))
            cc = [dict(c, tracks=[c['tracks'][i] for i in indices]) for c in clips]
            names = sorted({shaders[s]['TEX'] for s, _ in gg}); textures = [(n, images[n]) for n in names]
            batches = ce.build_batches(gg, shaders, {n: i for i, n in enumerate(names)}, None)
            batches = [dict(ce.batch_vertices(b), tex=b['tex'], eyes=False, alpha=b['alpha'],
                            strips=b['strips']) for b in batches]
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / 'scene.chr'; ce.write_chr(out, jj, batches, textures, cc, None, 0xffffffff)
                blob = bytearray(out.read_bytes())
            # A gag's root translation belongs to its animation, unlike locomotion.
            struct.pack_into('<I', blob, 52, 0xffffffff)
            result.append(dict(blob=bytes(blob), place=place[:3, :4], length=max((c['frames']-1)/c['fps'] for c in cc),
                               joints=len(jj), source=path.name, skeleton=skeleton, drawables=len(parts)))
    if not result: raise ValueError(f'{path}: empty gag composite')
    return result
