#!/usr/bin/env python3
"""Монета-спрайт (Роб 17.10): кадры оборота из Blender (tools/coin/coin_blender.py или сцена SHAR_coin.blend) -> гифка без фона для просмотра
и лента кадров для игры coinspr.bin (кладётся рядом с EBOOT; viewer/coinspr.h).
    python3 tools/coin/coin_pack.py FRAMES_DIR OUT_DIR [--half 0.3441] [--cy 0.3186] [--spin 3.0]
coinspr.bin: заголовок 32 Б ('CSP1', w, h, уровней, кадров, столбцов, строк, сторона кадра — u16; половина кадра в метрах, центр по высоте от низа монеты,
кадров в секунду — f32; запас) -> палитра 256 x RGBA (индекс 0 — прозрачный) -> уровни CLUT8 в swizzle (блоки 16 Б x 8 строк, как GE)."""
import argparse, math, struct
from pathlib import Path
import numpy as np
from PIL import Image

def swz(a):   # PSP swizzle 8 бит: блоки 16 x 8, строка блоков подряд
    h, w = a.shape; return a.reshape(h // 8, 8, w // 16, 16).transpose(0, 2, 1, 3).reshape(-1).tobytes()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('frames'); ap.add_argument('out'); ap.add_argument('--half', type=float, default=.3441)
    ap.add_argument('--cy', type=float, default=.3186); ap.add_argument('--spin', type=float, default=3.0); ap.add_argument('--px', type=int, default=64); ap.add_argument('--bin', help='только coinspr.bin по этому пути (tools/ship_rules.txt), без гифки и листа')
    # №829 (ключ крупнее и без «лесенки»): --page — лента страницами 512 × 512 (кадр 128: 4 × 4 на странице, 32 кадра — 2 страницы; GE не берёт
    # картинку больше 512), --soft — палитра с полупрозрачным краем (207 непрозрачных цветов + 48 цветов края с альфой + прозрачный 0)
    ap.add_argument('--page', action='store_true'); ap.add_argument('--soft', action='store_true')
    A = ap.parse_args(); out = Path(A.out); out.mkdir(parents=True, exist_ok=True)
    if A.page: return main_pages(A, out)
    fs = sorted(Path(A.frames).glob('f_*.png')); N = len(fs); fr = [Image.open(f).convert('RGBA') for f in fs]
    fps = N * A.spin / (2 * math.pi)
    # гифка для Роба: 128 px, прозрачный фон (край — порог альфы 50 %), петля
    g = []
    for im in fr:
        a = np.asarray(im); q = im.convert('RGB').quantize(255, method=Image.Quantize.MEDIANCUT); idx = np.asarray(q).astype(np.uint8) + 1
        idx[a[..., 3] < 128] = 0; pal = [0, 0, 0] + q.getpalette()[:255 * 3]; p = Image.fromarray(idx, 'P'); p.putpalette(pal); g.append(p)
    if not A.bin: g[0].save(out / 'coin_spin.gif', save_all=True, append_images=g[1:], duration=int(round(1000 / fps)), loop=0, transparency=0, disposal=2)
    # лента кадров: 8 столбцов, кадр PX (уровень 0) и PX/2 (уровень 1), края кадра — 1 тексел запаса прозрачный
    cols = 8; rows = (N + cols - 1) // cols; PX = A.px; W, H = cols * PX, rows * PX
    def sheet(px):
        s = Image.new('RGBA', (cols * px, rows * px), (0, 0, 0, 0))
        for k, im in enumerate(fr): s.paste(im.resize((px, px), Image.LANCZOS), ((k % cols) * px, (k // cols) * px))
        return s
    L0, L1 = sheet(PX), sheet(PX // 2)
    both = Image.new('RGBA', (W, H + H // 2)); both.paste(L0, (0, 0)); both.paste(L1, (0, H))
    rgb = Image.new('RGB', both.size, (0, 0, 0)); rgb.paste(both.convert('RGB')); al = np.asarray(both)[..., 3]
    q = rgb.quantize(255, method=Image.Quantize.MEDIANCUT); idx = np.asarray(q).astype(np.uint8) + 1; idx[al < 96] = 0
    pal = np.zeros((256, 4), np.uint8); pp = np.array(q.getpalette()[:255 * 3], np.uint8).reshape(-1, 3); pal[1:1 + len(pp), :3] = pp; pal[1:, 3] = 255
    # прозрачный индекс 0 — цвет края монеты (средний цвет непрозрачных текселей у прозрачных), альфа 0: фильтрация на силуэте не подмешивает чёрное (проверка 17.10)
    op = al >= 96; tr = ~op; near = np.zeros_like(tr)
    near[1:] |= tr[:-1]; near[:-1] |= tr[1:]; near[:, 1:] |= tr[:, :-1]; near[:, :-1] |= tr[:, 1:]   # сосед — прозрачный
    edge = op & near
    rgb_ = np.asarray(both.convert('RGB'))
    if edge.any(): pal[0, :3] = rgb_[edge].mean(0).round().astype(np.uint8)
    i0, i1 = idx[:H, :W], idx[H:, :W // 2]
    hdr = b'CSP1' + struct.pack('<8H', W, H, 2, N, cols, rows, PX, 0) + struct.pack('<3f', A.half, A.cy, fps)
    hdr += b'\0' * (32 - len(hdr))
    data = hdr + pal.tobytes() + swz(i0) + swz(i1)
    if A.bin: Path(A.bin).write_bytes(data); print(f'coinspr.bin -> {A.bin}, {len(data)} Б'); return
    (out / 'coinspr.bin').write_bytes(data)
    prev = Image.fromarray(pal[idx.astype(int)], 'RGBA'); bg = Image.new('RGBA', prev.size, (60, 70, 60, 255)); bg.alpha_composite(prev); bg.save(out / 'coinspr_preview.png')
    print(f'кадров {N}, {fps:.1f} к/с; гифка {out / "coin_spin.gif"}; лента {W}x{H} + {W // 2}x{H // 2}, файл {len(data)} Б')

def main_pages(A, out):
    """Лента страницами 512 × 512: заголовок CSP1 (pad = число страниц), палитра, на каждую страницу — уровень 0 (512 × 512) и 1 (256 × 256) в swizzle."""
    fs = sorted(Path(A.frames).glob('f_*.png')); N = len(fs); fr = [Image.open(f).convert('RGBA') for f in fs]
    fps = N * A.spin / (2 * math.pi); PX = A.px; cols = 512 // PX; per = cols * cols; pages = (N + per - 1) // per
    def page(p, px):
        s = Image.new('RGBA', (cols * px, cols * px), (0, 0, 0, 0))
        for k in range(per):
            i = p * per + k
            if i < N: s.paste(fr[i] if px == PX else fr[i].resize((px, px), Image.LANCZOS), ((k % cols) * px, (k // cols) * px))
        return s
    L = [(page(p, PX), page(p, PX // 2)) for p in range(pages)]
    allp = Image.new('RGBA', (512, pages * (512 + 256)), (0, 0, 0, 0)); y = 0
    for l0, l1 in L: allp.paste(l0, (0, y)); allp.paste(l1, (0, y + 512)); y += 768
    a = np.asarray(allp).astype(np.int32); al = a[..., 3]; idx = np.zeros(al.shape, np.uint8); pal = np.zeros((256, 4), np.uint8)
    op = al >= 250; part = (al >= 8) & ~op
    rgb = a[..., :3].astype(np.uint8).copy(); rgb[~op] = rgb[op].mean(0).round().astype(np.uint8)   # прозрачное и край не тянут палитру тела
    q = Image.fromarray(rgb, 'RGB').quantize(207 if A.soft else 255, method=Image.Quantize.MEDIANCUT); qi = np.asarray(q).astype(np.uint8)
    pp = np.array(q.getpalette()[:(207 if A.soft else 255) * 3], np.uint8).reshape(-1, 3); pal[1:1 + len(pp), :3] = pp; pal[1:1 + len(pp), 3] = 255
    idx[op] = qi[op] + 1
    if A.soft and part.any():   # край: свои 48 цветов с альфой (октодерево по RGBA только краевых текселей)
        e = a.astype(np.uint8).copy(); e[~part] = a[part][0].astype(np.uint8)
        qe = Image.fromarray(e, 'RGBA').quantize(48, method=Image.Quantize.FASTOCTREE); qei = np.asarray(qe).astype(np.uint8)
        pe = np.array(qe.getpalette('RGBA')[:48 * 4], np.uint8).reshape(-1, 4); pal[208:208 + len(pe)] = pe; idx[part] = qei[part] + 208
    elif part.any(): idx[part & (al >= 96)] = qi[part & (al >= 96)] + 1
    near = np.zeros_like(op); tr = ~op
    near[1:] |= tr[:-1]; near[:-1] |= tr[1:]; near[:, 1:] |= tr[:, :-1]; near[:, :-1] |= tr[:, 1:]
    edge = op & near
    if edge.any(): pal[0, :3] = a[edge][:, :3].mean(0).round().astype(np.uint8)   # прозрачный 0 — цвет края: фильтрация не подмешивает чёрное
    hdr = b'CSP1' + struct.pack('<8H', 512, 512, 2, N, cols, cols, PX, pages) + struct.pack('<3f', A.half, A.cy, fps); hdr += b'\0' * (32 - len(hdr))
    data = bytearray(hdr + pal.tobytes()); y = 0
    for _ in range(pages): data += swz(idx[y:y + 512, :512]) + swz(idx[y + 512:y + 768, :256]); y += 768
    Path(A.bin or out / 'coinspr.bin').write_bytes(bytes(data))
    prev = Image.fromarray(pal[idx.astype(int)], 'RGBA'); bg = Image.new('RGBA', prev.size, (60, 70, 60, 255)); bg.alpha_composite(prev); bg.save(out / 'pages_preview.png')
    print(f'страниц {pages} по 512x512 (кадр {PX}, {cols}x{cols}), кадров {N}, {fps:.1f} к/с, край {"мягкий" if A.soft else "резкий"}, файл {len(data)} Б -> {A.bin or out / "coinspr.bin"}')

if __name__ == '__main__': main()
