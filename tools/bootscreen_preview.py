#!/usr/bin/env python3
"""Превью загрузочного экрана (пункт Л): собирает tools/bootscreen_preview.c (тот же код, что на PSP) и пишет
build/ui_shots/boot/boot_1x.gif, boot_2x.gif, boot_end.png, boot_end_2x.png (со знаками build/bootmarks.bin, правка 127)."""
import subprocess
from pathlib import Path
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]; out = ROOT / 'build/ui_shots/boot'; out.mkdir(parents=True, exist_ok=True)
subprocess.run(['cc', '-std=c99', '-O1', '-I', str(ROOT / 'viewer'), str(ROOT / 'tools/bootscreen_preview.c'), '-o', str(ROOT / 'build/bootscreen_preview')], check=True)
raw = subprocess.run([str(ROOT / 'build/bootscreen_preview'), str(ROOT / 'build/bootmarks.bin')], capture_output=True, check=True).stdout
N = 480 * 272 * 3; fr = [Image.frombytes('RGB', (480, 272), raw[i:i + N]) for i in range(0, len(raw), N)]
fr2 = fr[::2]   # GIF: 30 кадров в секунду
fr2[0].save(out / 'boot_1x.gif', save_all=True, append_images=fr2[1:], duration=33, loop=0)
big = [f.resize((960, 544), Image.NEAREST) for f in fr2]
big[0].save(out / 'boot_2x.gif', save_all=True, append_images=big[1:], duration=33, loop=0)
fr[-1].save(out / 'boot_end.png'); fr[-1].resize((960, 544), Image.NEAREST).save(out / 'boot_end_2x.png')
print('кадров', len(fr), '->', out)
