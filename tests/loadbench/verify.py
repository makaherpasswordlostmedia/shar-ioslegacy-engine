"""Independent binary parser: package/source identity, bounded entries, real decode."""
import argparse
import ctypes as C
import ctypes.util
import hashlib
import json
import struct
from pathlib import Path


def hash32(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) % (2**32)
    return value


def verify(folder, source=None):
    dataset = json.loads((folder/'lb_dataset.json').read_text())
    src = source.read_bytes() if source else None
    if src:
        assert hashlib.sha256(src).hexdigest() == dataset['source_sha256']
    lib = C.CDLL(ctypes.util.find_library('lz4'))
    lib.LZ4_decompress_safe.argtypes = [C.c_char_p, C.c_void_p, C.c_int, C.c_int]
    index = (folder/'lb_index.bin').read_bytes()
    magic, version, count, ng, *tail = struct.unpack_from('<4s7I', index)
    sizes, stride = tail[:3], tail[3]
    assert (magic, version, ng, stride) == (b'LB03', 3, 4, 48)
    assert count == dataset['records'] == 247 and len(index) == 32+48*count
    files = [(folder/name).read_bytes() for name in ('lb_raw.bin','lb_fast.bin','lb_hc.bin')]
    assert list(map(len, files)) == sizes
    ends, groups, raw_total, stored_total = [0]*3, [0]*4, 0, [0]*3
    for i in range(count):
        g, rawlen, off, expected, *rest = struct.unpack_from('<12I', index, 32+48*i)
        spans, mask, reserved = rest[:6], rest[6], rest[7]
        assert g < 4 and 0 < rawlen <= (16384 if g < 2 else 65536) and not reserved and not mask & ~6
        row = dataset['blocks'][i]
        assert row['id']==i and (g,rawlen,off,expected,mask)==(row['group'],row['raw_bytes'],row['source_offset'],row['fnv1a'],row['compressed_mask'])
        groups[g] += 1; raw_total += rawlen
        reference = None
        for c in range(3):
            pos, size = spans[2*c:2*c+2]
            assert pos == ends[c] and pos%16==0 and 0 < size <= rawlen and pos+size<=len(files[c])
            assert pos == row['offsets'][c] and size == row['stored_bytes'][c]
            block = files[c][pos:pos+size]
            if mask & (1 << c):
                assert c and size < rawlen
                decoded = C.create_string_buffer(rawlen)
                assert lib.LZ4_decompress_safe(block,decoded,size,rawlen)==rawlen
                block = decoded.raw
            else:
                assert size == rawlen
            assert hash32(block)==expected and hashlib.sha256(block).hexdigest()==row['sha256']
            if reference is None:
                reference = block
            assert block == reference
            if src:
                assert block == src[off:off+rawlen]
            end=(pos+size+15)&~15
            assert files[c][pos+size:end]==bytes(end-pos-size)
            ends[c]=end;stored_total[c]+=size
    assert ends==sizes and groups==[64,64,55,64]
    if (folder/'lb_package.json').exists():
        manifest=json.loads((folder/'lb_package.json').read_text())
        for row in manifest['files']:
            content=(folder/row['path']).read_bytes()
            assert len(content)==row['bytes'] and hashlib.sha256(content).hexdigest()==row['sha256'],row['path']
        pbp=(folder/'EBOOT.PBP').read_bytes()
        assert pbp[:4]==b'\0PBP'
        offsets=struct.unpack_from('<8I',pbp,8)
        assert list(offsets)==sorted(offsets) and offsets[0]>=40 and offsets[-1]<=len(pbp)
        assert b'SHAR Loading Bench R3' in pbp[offsets[0]:offsets[1]]
    return dict(verified=True,records=count,decode_comparisons=count*3,source_compared=bool(src),
                raw_sample_bytes=raw_total,stored_sample_bytes=stored_total,container_bytes=sizes,
                index_fnv=hash32(index),scope='Package integrity and lossless bytes; no PSP timing')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--source',type=Path)
    a=p.parse_args();print(json.dumps(verify(a.folder,a.source),indent=2))
