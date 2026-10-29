#!/usr/bin/env python3
"""Близнецы · Б2: таблица файлов диска Роба (ISO 9660) → какой файл лежит в каком секторе. Это данные диска, не код игры.

  python3 tools/twins/isomap.py [ISO] [--json OUT]     список: сектор начала, секторов, байт, путь
Сектор — 2048 байт (DVD PS2). Если файл диска — архив со своей таблицей (RCF и т.п.), его разбирает отдельный слой (archives)."""
import json, struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

ISO = C.DATA / 'game/Hit and Run.iso'
SEC = 2048


def _dir(f, lba, size, path, out):
    f.seek(lba * SEC); data = f.read(size); i = 0
    while i < len(data):
        n = data[i]
        if n == 0:                       # запись не пересекает сектор: добить до следующего
            i = (i // SEC + 1) * SEC; continue
        rec = data[i:i + n]
        ext = struct.unpack_from('<I', rec, 2)[0]; ln = struct.unpack_from('<I', rec, 10)[0]; flags = rec[25]
        nl = rec[32]; name = rec[33:33 + nl]
        i += n
        if name in (b'\x00', b'\x01'): continue
        nm = name.decode('ascii', 'replace').split(';')[0]
        p = f'{path}/{nm}' if path else nm
        if flags & 2: _dir(f, ext, ln, p, out)
        else: out.append(dict(path=p, lba=ext, sectors=(ln + SEC - 1) // SEC, bytes=ln))


def table(iso=ISO):
    with open(iso, 'rb') as f:
        f.seek(16 * SEC); pvd = f.read(SEC)
        if pvd[1:6] != b'CD001': raise SystemExit(f'{iso}: нет ISO 9660')
        root = pvd[156:156 + 34]
        lba = struct.unpack_from('<I', root, 2)[0]; ln = struct.unpack_from('<I', root, 10)[0]
        out = []; _dir(f, lba, ln, '', out)
    return sorted(out, key=lambda r: r['lba'])


def rcf_entries(f, base_byte):
    """таблица архива Radcore 1.2 (как hit-and-run-web/tools/extract.py, MIT): (crc, смещение, байт) по смещению + имена по порядку"""
    f.seek(base_byte); head = f.read(0x28)
    if not head.startswith(b'RADCORE CEMENT LIBRARY\0'): return None
    table = struct.unpack_from('<I', head, 0x24)[0]
    f.seek(base_byte + table); count, names = struct.unpack('<II', f.read(8))
    f.seek(base_byte + table + 16); raw = f.read(count * 12)
    ent = sorted((struct.unpack_from('<III', raw, i * 12) for i in range(count)), key=lambda v: v[1])
    f.seek(base_byte + names + 8); blob = f.read(4 << 20); cur = 0; out = []
    for crc, off, size in ent:
        ln = struct.unpack_from('<I', blob, cur)[0]; cur += 4
        name = blob[cur:cur + ln].rstrip(b'\0').decode('ascii').replace('\\', '/').lower(); cur += ln + 4
        out.append(dict(name=name, off=off, bytes=size))
    return out


def diskmap(iso=ISO, cache=None):
    """все файлы диска с байтами на диске: файлы ISO и файлы внутри архивов RCF -> список {path, start, end} (байты от начала диска)"""
    cache = cache or (C.OUT / 'diskmap.json')
    if cache.exists() and json.loads(cache.read_text()).get('iso_size') == Path(iso).stat().st_size:
        return json.loads(cache.read_text())['files']
    files = []
    with open(iso, 'rb') as f:
        for r in table(iso):
            base = r['lba'] * SEC
            ent = rcf_entries(f, base) if r['path'].upper().endswith('.RCF') else None
            if ent:
                files.append(dict(path=r['path'] + ':<таблица>', start=base, end=base + min(e['off'] for e in ent)))
                for e in ent: files.append(dict(path=f"{r['path']}:{e['name']}", start=base + e['off'], end=base + e['off'] + e['bytes']))
            else:
                files.append(dict(path=r['path'], start=base, end=base + r['bytes']))
    files.sort(key=lambda x: x['start'])
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(dict(iso_size=Path(iso).stat().st_size, files=files), ensure_ascii=False))
    return files


def files_in(files, start, end):
    """файлы, которые пересекает чтение байт [start, end)"""
    import bisect
    keys = [x['start'] for x in files]; k = max(0, bisect.bisect_right(keys, start) - 1); out = []
    while k < len(files) and files[k]['start'] < end:
        if files[k]['end'] > start: out.append(files[k])
        k += 1
    return out


def locate(rows, lsn):
    """сектор → (файл, смещение в файле, байт) или None; rows отсортированы по lba"""
    import bisect
    keys = [r['lba'] for r in rows]; k = bisect.bisect_right(keys, lsn) - 1
    if k < 0: return None
    r = rows[k]
    return (r, (lsn - r['lba']) * SEC) if lsn < r['lba'] + max(1, r['sectors']) else None


if __name__ == '__main__':
    if '--map' in sys.argv:
        fs = diskmap(); print(f'файлов на диске с архивами: {len(fs)}'); [print(' ', x['path'], x['end'] - x['start']) for x in fs if 'l1z1' in x['path'] or 'l1r1.' in x['path']]; sys.exit(0)
    rows = table(Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else ISO)
    if '--json' in sys.argv: Path(sys.argv[sys.argv.index('--json') + 1]).write_text(json.dumps(rows, ensure_ascii=False))
    print(f'файлов {len(rows)}, байт {sum(r["bytes"] for r in rows):,}')
    for r in sorted(rows, key=lambda r: -r['bytes'])[:25]: print(f"  {r['lba']:8d} {r['sectors']:7d} сект {r['bytes']:>12,} {r['path']}")
