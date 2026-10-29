#!/usr/bin/env python3
"""Цели каскадёра и пешехода (пункт Б3) из данных уровня 1 -> build/bots/targets-l1.tsv (одна строка на цель):
  kind  name  x y z  r  x0 z0 x1 z1
roof — крыши (build/sandbox/routes-l1.json, пункт 10: площадка, высота, рамка); ramp — трамплины (routes-l1.tsv: кромка);
glass — стёкла Krusty (PRP1, обломок 19); coin — монеты мира (PRP2, таблица монет); wasp и card — игровые объекты пакета
build/collect-l1.shr (CLT1, tools/collect_export.py): 7 карточек с номером из данных (card11..card17) и 20 ос с точкой появления
(AddSpawnPointByLocatorScript) — те же сущности, что считает игра и паспорт уровня (docs/levels/L1_ПАСПОРТ.md);
pad — подкидывающие точки Гомера (блок JMP1 level.shr, tools/jumps_export.py: sb01 — на крышу школы, towerjump — верх
вышки, spring3 — к лифту АЭС и мосткам card16): ступени пути к карточкам и осам, тяга исследователя к ним. Только данные.
  --legacy   старый счёт (до Г5/П4, 01.10): осы — все локаторы w_* (23, три без точки появления), карточки — по имени
             локатора (6: локатор card13 несёт карточку card14, настоящая card13 терялась) — отрицательный контроль гейта
             tests/collect_targets/run.sh
  --out ПУТЬ другой выход (гейт), по умолчанию build/bots/targets-l1.tsv"""
import argparse, json, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/cartest')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
import routes as R


def coins(level):
    b = level.read_bytes(); po = struct.unpack_from('<I', b, 96)[0]; magic = b[po:po + 4]
    npiece, ntype, ninst, vB, iB = struct.unpack_from('<5I', b, po + 4); ct, nc = struct.unpack_from('<iI', b, po + 24)
    head = 64 if magic == b'PRP2' else 32; body = po + head
    off = body + vB + iB + 40 * npiece + 20 * ntype + 32 * ninst
    return [struct.unpack_from('<3f', b, off + 12 * i) for i in range(nc)]


def pads(level):
    """Подкидывающие точки JMP1 (формат — tools/jumps_export.py): имя, центр объёма, полуразмеры -> (имя, x y z, радиус)"""
    b = level.read_bytes(); i = b.find(b'JMP1')
    if i < 0: return []
    nz, npad = struct.unpack_from('<2I', b, i + 8); p = i + 32 + 80 * nz; out = []
    for k in range(npad):
        o = p + 96 * k; c = struct.unpack_from('<3f', b, o); h = struct.unpack_from('<3f', b, o + 48)
        out.append((b[o + 64:o + 80].split(b'\0')[0].decode(), c, max(h[0], h[2]) + .5))
    return out


def collect_pack(path):
    """CLT1 (формат — tools/collect_export.py): карточки (номер, x y z) и осы (имя локатора, x y z) — порядок пакета"""
    b = path.read_bytes()
    if b[:4] != b'CLT1': raise SystemExit(f'{path}: не CLT1')
    nc, co, nw, wo = struct.unpack_from('<4I', b, 4 + 4 * 6)
    cards = [(struct.unpack_from('<H', b, co + 32 * i + 16)[0], struct.unpack_from('<3f', b, co + 32 * i)) for i in range(nc)]
    wasps = [(b[wo + 80 * i:wo + 80 * i + 16].split(b'\0')[0].decode(), struct.unpack_from('<3f', b, wo + 80 * i + 16)) for i in range(nw)]
    return cards, wasps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--legacy', action='store_true'); ap.add_argument('--out')
    a = ap.parse_args()
    lvl = ROOT / 'build/level.shr'; G = R.G; out = []
    rj = json.loads((ROOT / 'build/sandbox/routes-l1.json').read_text())
    for r in rj['roofs']:
        x0, z0, x1, z1 = r['bbox']; out.append(('roof', 'roof%d' % r['id'], r['x'], r['y'], r['z'], 2.0, x0, z0, x1, z1))
    for l in (ROOT / 'build/sandbox/routes-l1.tsv').read_text().splitlines():
        f = l.split('\t'); lx, ly, lz = map(float, f[3].split())
        out.append(('ramp', f[0], lx, ly, lz, 4.0, 0, 0, 0, 0))
    for g in R.glass_panes(lvl): out.append(('glass', 'glass%d' % g.get('inst', g.get('i', 0)), g['x'], g['y'], g['z'], 3.0, 0, 0, 0, 0))
    for i, (x, y, z) in enumerate(coins(lvl)): out.append(('coin', 'coin%d' % i, x, y, z, 1.5, 0, 0, 0, 0))
    if not a.legacy:
        for name, c, r in pads(lvl): out.append(('pad', 'pad_' + name, *c, r, 0, 0, 0, 0))
    if a.legacy:   # старый счёт по именам локаторов (отрицательный контроль)
        for w in R.locators(G / 'art/missions/level01/wasps.p3d', lambda n, k, e: n.lower().startswith('w_')):
            out.append(('wasp', w['name'], *w['pos'], 3.0, 0, 0, 0, 0))
        seen = set()
        for f in sorted((G / 'art').glob('l1*.p3d')):
            try: loc = R.locators(f, lambda n, k, e: 'card' in n.lower())
            except Exception: continue
            for c in loc:
                if c['name'] in seen: continue
                seen.add(c['name']); out.append(('card', c['name'], *c['pos'], 2.0, 0, 0, 0, 0))
    else:          # игровые объекты пакета: имя карточки — её номер в данных, осы — только с точкой появления
        cards, wasps = collect_pack(ROOT / 'build/collect-l1.shr')
        for name, p in wasps: out.append(('wasp', name, *p, 3.0, 0, 0, 0, 0))
        for cid, p in cards: out.append(('card', 'card%d' % cid, *p, 2.0, 0, 0, 0, 0))
    dst = Path(a.out) if a.out else ROOT / 'build/bots/targets-l1.tsv'; dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(''.join('%s\t%s\t%.2f %.2f %.2f\t%.1f\t%.1f %.1f %.1f %.1f\n' % t for t in out))
    import collections; print('целей', len(out), dict(collections.Counter(t[0] for t in out)), '->', dst)


if __name__ == '__main__':
    main()
