#!/usr/bin/env python3
"""Блик гаечного ключа как в оригинале (№803, Роб 18.10: «блинк-блинк ровно как в оригинале»): текстуры бликов из диска -> wrglow.bin рядом с EBOOT.
    python3 tools/wrglow_export.py [OUT.bin]   (по умолчанию build/wrglow.bin; данные диска — hit-and-run-web/source/game/art/wrench.p3d, только чтение)
У оригинала (art/wrench.p3d, составной рисунок wrench) под ключом три билборда сложением, все на 0,9 м дальше ключа от камеры (DIST -0.9):
  wrenchShape46 — scratch2 (звезда-«царапина» 32×32), цвет (133,38,255), ширина 5,22↔5,72; цвет мигает полный↔чёрный каждые 0,5 с (анимация BQG 61 кадр, 30 к/с);
  wrenchShape4  — glowsolid (кольцо 64×64), цвет (72,91,255), 5,24↔5,74;  wrenchShape5 — scratch2, цвет (64,70,255), 2,09↔2,29.
Числа билбордов — в движке (viewer/spritelight.h wrGlow*), сюда — только две картинки (у диска — серые на чёрном, непрозрачные: яркость в RGB).
Формат: 'WRG1', u16 число картинок (2), u16 0; на картинку u16 w, u16 h, затем w*h u32 (GE 8888: R, G, B, A по байтам). Ассеты диска не коммитить — файл в build/."""
import re, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
HRW = ROOT / 'hit-and-run-web'
if not HRW.exists(): HRW = Path.home() / 'Downloads' / 'shar-psp' / 'hit-and-run-web'
sys.path.insert(0, str(HRW / 'tools'))
import p3d, textures   # noqa: E402

NAMES = ['scratch2', 'glowsolid']

def load(path):
    root = p3d.read(path); out = {}
    for c in root.children:
        if c.id != 0x19000: continue
        m = re.search(rb'([A-Za-z0-9_]+)\.bmp', c.data)
        if not m: continue
        for k in p3d.walk(c):
            if k.id == 0x19002:
                i = k.data.find(b'P3DI'); r = textures.decode_image(k.data[i:])
                out[m.group(1).decode()] = (r[0] if isinstance(r, tuple) else r).convert('RGBA')
    return out

def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'build' / 'wrglow.bin'
    imgs = load(HRW / 'source' / 'game' / 'art' / 'wrench.p3d')
    b = bytearray(b'WRG1' + struct.pack('<2H', len(NAMES), 0))
    for n in NAMES:
        im = imgs[n]; w, h = im.size
        assert w in (16, 32, 64, 128) and h in (16, 32, 64, 128), (n, im.size)
        b += struct.pack('<2H', w, h) + im.tobytes()   # RGBA по байтам = 8888 GE
    out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(bytes(b))
    print('wrglow.bin', len(b), 'Б:', ', '.join('%s %dx%d' % (n, *imgs[n].size) for n in NAMES), '->', out)

if __name__ == '__main__':
    main()
