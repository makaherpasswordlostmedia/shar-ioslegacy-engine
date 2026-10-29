"""Build local-only LZ4 loading samples. Never alters the source level or game.
Independent blocks, no dictionaries. Sampling spans HC compression quantiles;
this is a diagnostic sample, not the city's size-weighted loading distribution.
"""
import argparse
import ctypes as C
import ctypes.util
import hashlib
import json
import shutil
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VERSION = 'LB3-20260927'
NAMES = ['lb_raw.bin', 'lb_fast.bin', 'lb_hc.bin']


def fnv(data):
    h = 2166136261
    for byte in data:
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return h


def library():
    lib = C.CDLL(ctypes.util.find_library('lz4'))
    lib.LZ4_versionString.restype = C.c_char_p
    lib.LZ4_compressBound.argtypes = [C.c_int]
    lib.LZ4_compress_default.argtypes = [C.c_char_p, C.c_void_p, C.c_int, C.c_int]
    lib.LZ4_compress_HC.argtypes = [C.c_char_p, C.c_void_p, C.c_int, C.c_int, C.c_int]
    lib.LZ4_decompress_safe.argtypes = [C.c_char_p, C.c_void_p, C.c_int, C.c_int]
    return lib


def compress(lib, data, hc=False):
    cap = lib.LZ4_compressBound(len(data))
    out = C.create_string_buffer(cap)
    n = (lib.LZ4_compress_HC(data, out, len(data), cap, 12) if hc else
         lib.LZ4_compress_default(data, out, len(data), cap))
    assert n > 0
    decoded = C.create_string_buffer(len(data))
    assert lib.LZ4_decompress_safe(out, decoded, n, len(data)) == len(data)
    assert decoded.raw == data
    return out.raw[:n]


def prepare(out, source):
    data = source.read_bytes()
    assert data[:4] == b'SHR7'
    table, nc, co, _ = struct.unpack_from('<4I', data, 76)
    w, h = struct.unpack_from('<2I', data, 68)
    align = lambda n: (n + 15) & ~15
    start = align(align(104 + w * h * 8) + w * h * 4)
    regions = [[(start, table - start)], []]
    for i in range(nc):
        off, size = struct.unpack_from('<2I', data, co + i * 48 + 36)
        assert off + size <= len(data)
        if size:
            regions[1].append((off, size))
    lib = library()
    blobs = [bytearray(), bytearray(), bytearray()]
    rows, groups, records = [], [], bytearray()
    for size in (16384, 65536):
        for kind, items in enumerate(regions):
            gid = len(groups)
            candidates = []
            for off, length in items:
                for pos in range(0, length, size):
                    raw = data[off + pos:off + min(length, pos + size)]
                    hc = compress(lib, raw, True)
                    candidates.append((len(hc) / len(raw), off + pos, raw, hc))
            candidates.sort(key=lambda x: (x[0], x[1]))
            count = min(64, len(candidates))
            selected = [candidates[round(i * (len(candidates) - 1) / (count - 1))] for i in range(count)]
            selected.sort(key=lambda x: x[1])
            groups.append(dict(id=gid, kind=('textures', 'cells')[kind], block_limit=size,
                               candidates=len(candidates), samples=count, first=len(rows)))
            for ratio, off, raw, hc in selected:
                variants = [raw, compress(lib, raw), hc]
                offsets, lengths, mask = [], [], 0
                for vi, packed in enumerate(variants):
                    use = vi > 0 and len(packed) < len(raw)
                    if not use:
                        packed = raw
                    else:
                        mask |= 1 << vi
                    offsets.append(len(blobs[vi])); lengths.append(len(packed))
                    blobs[vi].extend(packed)
                    blobs[vi].extend(bytes((-len(blobs[vi])) % 16))
                record = [gid, len(raw), off, fnv(raw)]
                for a, b in zip(offsets, lengths):
                    record.extend((a, b))
                record.extend((mask, 0))
                records.extend(struct.pack('<12I', *record))
                rows.append(dict(id=len(rows), group=gid, source_offset=off, raw_bytes=len(raw),
                                 fnv1a=fnv(raw), sha256=hashlib.sha256(raw).hexdigest(),
                                 offsets=offsets, stored_bytes=lengths, compressed_mask=mask))
    index = struct.pack('<4s7I', b'LB03', 3, len(rows), 4, *map(len, blobs), 48) + records
    (out / 'lb_index.bin').write_bytes(index)
    for name, blob in zip(NAMES, blobs):
        (out / name).write_bytes(blob)
    header = ('/* Generated dataset identity, no game assets. */\n'
              f'#define LOADBENCH_VERSION "{VERSION}"\n'
              f'#define DATA_COUNT {len(rows)}u\n'
              f'#define DATA_INDEX_SIZE {len(index)}u\n'
              '#ifndef DATA_INDEX_FNV\n'
              f'#define DATA_INDEX_FNV 0x{fnv(index):08x}u\n#endif\n')
    (HERE / 'dataset_ids.h').write_text(header)
    report = dict(version=VERSION, source=str(source), source_sha256=hashlib.sha256(data).hexdigest(),
                  compressor_version=lib.LZ4_versionString().decode(), groups=groups, blocks=rows,
                  records=len(rows), cases=72, expected_samples=len(rows)*18,index_fnv=fnv(index),
                  selection='64 HC-ratio quantiles per group (55 for textures/64K), sorted by original offset',
                  limitations='No cold-cache claim, no concurrent game/audio/GPU, no size-weighted city estimate; isolated reads include seek, decode and output cache writeback. Quantiles include short cell tails.')
    (out / 'lb_dataset.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'blocks'}, indent=2))


def finalize(out):
    shutil.copy2(HERE / 'build/EBOOT.PBP', out / 'EBOOT.PBP')
    (out / 'LOAD_README.txt').write_text(
        'SHAR Loading Bench R3 / LB3-20260927\n\n'
        'Launch from Game > Memory Stick. Test begins automatically.\n'
        'Wait for DONE / Results saved. Press X, then reconnect USB.\n'
        'Each launch creates load0001, load0002...; old runs are preserved.\n'
        '72 small cases: raw, LZ4, LZ4 HC12; real textures/cells; 16/64 KiB;\n'
        'sequential/shuffled reads; three rounds with rotating codec order.\n'
        'Fixed RAM buffers, safe decompression, full-output checksums.\n'
        'No GE scenes or framebuffer file captures. No memory stress.\n'
        'If STOPPED appears, press X and reconnect USB; keep partial results.\n'
        'This is a loading experiment, not a game FPS benchmark.\n')
    names = ['EBOOT.PBP', 'LOAD_README.txt', 'lb_index.bin', 'lb_dataset.json'] + NAMES
    manifest = dict(version=VERSION, files=[dict(path=n, bytes=(out/n).stat().st_size,
                     sha256=hashlib.sha256((out/n).read_bytes()).hexdigest()) for n in names],
                    sources={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in HERE.iterdir() if p.is_file()})
    (out / 'lb_package.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Finalized', sum(x['bytes'] for x in manifest['files']), 'bytes')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--source', type=Path, default=ROOT/'build/level_ni.shr')
    p.add_argument('--finalize', action='store_true')
    args = p.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    finalize(args.out) if args.finalize else prepare(args.out, args.source)
