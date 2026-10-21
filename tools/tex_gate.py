#!/usr/bin/env python3
"""Гейт правки Роба 129 (текстуры уровня: память и «золотая середина» вывесок), только файлы, на Маке.

  (а) обход секции текстур по правилу строки движка (viewer/main.c texRowBytes: T8 — ширина, в swizzle не меньше 16 Б;
      T4 — полширины, не меньше 16 Б; высота в swizzle кратна 8) обязан закончиться ровно на tableOff (@76)
  (б) картинка та же: уровень 0 каждой записи, построенной без потерь (исходник диска в пределе размера и <= 256 цветов),
      после снятия swizzle и полубайтов (младший — левый тексел) побайтно равен PNG диска (источник — level.shr.texsrc.json)
  (в) память: секция текстур не больше --budget-mb (по умолчанию 3.75 МБ; до правки 129 — 4.20)
  (г) вывески: записи из TEX_CAP256_SIGN (tools/psp_export.py) — длинная сторона не больше SIGN_CAP; небо и фон
      (TEX_CAP256_SKY) остаются 256 (их не трогаем: закон 1)
Подброски (обязаны дать КРАСНОЕ): --swap-nibbles (полубайты наоборот), --t8-rows (строка T4 как у T8).
    python tools/tex_gate.py build/level.shr [--old OLD.shr] [--budget-mb 3.75] [--swap-nibbles] [--t8-rows]
"""
import sys, json, struct, argparse
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import texq  # noqa: E402

SIGN = ('textures/613596a3df666840a734.png', 'textures/2f9eba2961ee2932bcf9.png', 'textures/020948d017434d037b00.png',
        'textures/0c3ef8f9ed6afa467bf9.png', 'textures/e3a9ff751e5b9e72872f.png')   # = psp_export.TEX_CAP256_SIGN
SKY = ('textures/a7a9b8ac41248b5e9546.png', 'textures/68f3567d2aa80fb31ee6.png', 'textures/a44b975c13f87db7f865.png')
SIGN_CAP = 128


def row_bytes(t4, pre, lw, t8rows=False):
    if t4 and not t8rows: return max(16, (lw + 1) // 2)
    return 16 if pre and lw < 16 else lw


def walk(b, t8rows=False):
    """-> (записи [(off, w, h, levels, t4, pre, [(off, lw, lh, rb, rows)])], конец секции, tableOff, начало секции)"""
    ntex, = struct.unpack_from('<I', b, 4); hw, hh = struct.unpack_from('<II', b, 68); toff, = struct.unpack_from('<I', b, 76)
    p = 104 + hw * hh * 8; p = (p + 15) & ~15; p += hw * hh * 4; p = (p + 15) & ~15; start = p
    recs = []
    for _ in range(ntex):
        if p + 16 + 1024 > len(b): break   # обход уехал за файл (неверное правило строки) — (а) покажет КРАСНОЕ
        w, h, nl = struct.unpack_from('<HHH', b, p); t4, pre = b[p + 6] == 4, b[p + 7] == 1
        q = p + 16 + 1024; lw, lh = w, h; lv = []
        for _ in range(nl):
            rb = row_bytes(t4, pre, lw, t8rows); rows = (lh + 7) & ~7 if pre else lh
            lv.append((q, lw, lh, rb, rows)); q += rb * rows; q = (q + 15) & ~15; lw >>= 1; lh = lh >> 1 if lh > 1 else 1
        recs.append((p, w, h, nl, t4, pre, lv)); p = q
    return recs, p, toff, start


def level0(b, rec, swap=False):
    p, w, h, nl, t4, pre, lv = rec
    q, lw, lh, rb, rows = lv[0]
    a = np.frombuffer(b, np.uint8, rb * rows, q)
    a = a.reshape(rows // 8, rb // 16, 8, 16).transpose(0, 2, 1, 3).reshape(rows, rb) if pre else a.reshape(rows, rb)
    if t4:
        lo, hi = (a >> 4, a & 15) if swap else (a & 15, a >> 4)
        a = np.stack([lo, hi], -1).reshape(rows, 2 * rb)
    pal = np.frombuffer(b, np.uint8, 1024, p + 16).reshape(256, 4)
    return pal[a[:lh, :lw]]


def expected(url, cap):
    """уровень 0, как его строит texq (размер — target_size); None — запись с потерями по построению (уменьшена или > 256 цветов)"""
    img = Image.open(texq.TEXDIR / url).convert('RGBA')
    w, h = texq.target_size(*img.size, cap)
    if (w, h) != img.size: return None
    px = np.asarray(img, np.uint8)
    if len(np.unique(px.reshape(-1, 4).view('<u4'))) > 256: return None
    return px


def section_mb(path):
    b = Path(path).read_bytes(); recs, end, toff, start = walk(b)
    return (end - start) / 2**20, recs, b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('shr'); ap.add_argument('--old'); ap.add_argument('--budget-mb', type=float, default=3.75)
    ap.add_argument('--swap-nibbles', action='store_true'); ap.add_argument('--t8-rows', action='store_true')
    a = ap.parse_args()
    b = Path(a.shr).read_bytes(); fails = 0
    recs, end, toff, start = walk(b, a.t8_rows)
    ok = end == toff
    n4 = sum(r[4] for r in recs)
    print('%s (а) обход: %d записей (T4 %d), конец %d, tableOff %d' % ('OK' if ok else 'КРАСНОЕ', len(recs), n4, end, toff, ))
    fails += not ok
    if not ok:   # дальше сверять нечего: смещения уехали
        print('FAIL'); return 1
    src = json.loads(Path(a.shr + '.texsrc.json').read_text()) if Path(a.shr + '.texsrc.json').exists() else None
    if not src:
        print('КРАСНОЕ (б) нет %s.texsrc.json (экспорт до правки 129)' % a.shr); fails += 1
    else:
        caps = src.get('caps', {}); cap = src.get('cap', 128); same = diff = lossy = 0; bad = []
        for i, rec in enumerate(recs):
            s = src['tex'][i] if i < len(src['tex']) else None
            if not s: lossy += 1; continue
            e = expected(s['url'], caps.get(s['url'], cap))
            if e is None or e.shape[:2] != (rec[2], rec[1]): lossy += 1; continue
            if np.array_equal(level0(b, rec, a.swap_nibbles), e): same += 1
            else: diff += 1; bad.append((i, 'T4' if rec[4] else 'T8', s['url']))
        print('%s (б) картинка: уровень 0 побайтно как диск — %d, отличается %d, с потерями по построению (не сверяются) %d%s'
              % ('OK' if not diff else 'КРАСНОЕ', same, diff, lossy, ('; первые: %s' % bad[:3]) if bad else ''))
        fails += diff > 0
        sz = {s['url']: (r[1], r[2]) for s, r in zip(src['tex'], recs) if s}
        sg = [(u[-24:-4], sz[u]) for u in SIGN if u in sz]; sk = [(u[-24:-4], sz[u]) for u in SKY if u in sz]
        okg = all(max(v) <= SIGN_CAP for _, v in sg) and all(max(v) == 256 for _, v in sk)
        print('%s (г) вывески %s (<= %d), небо и фон %s (= 256)' % ('OK' if okg else 'КРАСНОЕ', [v for _, v in sg], SIGN_CAP, [v for _, v in sk]))
        fails += not okg
    mb = (end - start) / 2**20
    line = '%s (в) память: секция текстур %.2f МБ (предел %.2f)' % ('OK' if mb <= a.budget_mb else 'КРАСНОЕ', mb, a.budget_mb)
    if a.old:
        omb, orecs, _ = section_mb(a.old)
        line += '; было %.2f МБ -> освобождено %.2f МБ ОЗУ (текстуры уровня живут в куче, не во VRAM)' % (omb, omb - mb)
    print(line); fails += mb > a.budget_mb
    print('FAIL' if fails else 'PASS')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
