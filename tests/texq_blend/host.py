"""Нативный тест tools/texq.py: мипы «вырезки» для полупрозрачного материала (лестница пожарной машины, 28.09).
Синтетические картинки во временной папке (ресурсы игры не нужны):
  лестница 32x32 — альфа только 0/255 (вырезка), материал со смешиванием и материал с одним альфа-тестом;
  мягкая альфа (не вырезка) — одна общая запись для обоих материалов.
Ожидание: копия для смешивания держит непрозрачность каждого уровня как у уровня 0 (x0.85..1.2) и не исчезает под
альфа-тестом (есть альфа > 0x40); копия для альфа-теста — с масштабом покрытия (keep_coverage, средняя альфа уровня 1
заметно ниже); у не-вырезки одна запись.
.venv/bin/python tests/texq_blend/host.py          -> PASS/FAIL
.venv/bin/python tests/texq_blend/host.py --legacy -> отрицательный контроль: экспортёр как до 28.09 (материал со смешиванием
                                               получает ту же запись, что и альфа-тест) — обязан FAIL"""
import sys, struct, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import texq

LEGACY = '--legacy' in sys.argv
texq.CAP, texq.CLUT4, texq.PRESWIZZLE, texq.SMALL_MIPS = 128, False, True, True   # как psp_export с SHR_SMALL_MIPS=1
tmp = Path(tempfile.mkdtemp()); texq.TEXDIR = tmp; (tmp / 'textures').mkdir()
a = np.zeros((32, 32, 4), np.uint8); a[..., :3] = (205, 210, 182)
a[:, :5, 3] = a[:, 27:, 3] = 255; a[::8, :, 3] = a[1::8, :, 3] = 255              # две рейки и ступени
Image.fromarray(a, 'RGBA').save(tmp / 'textures/ladder.png')
s = np.zeros((32, 32, 4), np.uint8); s[..., :3] = 90; s[..., 3] = np.linspace(0, 200, 32).astype(np.uint8)[None, :]
Image.fromarray(s, 'RGBA').save(tmp / 'textures/soft.png')


def levels_alpha(rec):
    w, h, nl = struct.unpack_from('<HHH', rec, 0); pal = np.frombuffer(rec, np.uint8, 1024, 16).reshape(256, 4)
    p, lw, lh, out = 16 + 1024, w, h, []
    for _ in range(nl):
        rw = 16 if lw < 16 else lw; rh = (lh + 7) & ~7
        idx = np.frombuffer(rec, np.uint8, rw * rh, p).reshape(rh // 8, rw // 16, 8, 16).transpose(0, 2, 1, 3).reshape(rh, rw)
        out.append(pal[idx[:lh, :lw]][..., 3].astype(float)); p += rw * rh; p = (p + 15) & ~15; lw >>= 1; lh = max(1, lh >> 1)
    return out


def load(url, cache, blob, blend):
    return texq.load_tex(url, cache, blob) if LEGACY else texq.load_tex(url, cache, blob, blend=blend)


cache, blob, bad = {}, [], []
ia = load('textures/ladder.png', cache, blob, False)     # материал с одним альфа-тестом
ib = load('textures/ladder.png', cache, blob, True)      # полупрозрачный материал (флаг 2)
LA, LB = levels_alpha(blob[ia]), levels_alpha(blob[ib])
m0 = LB[0].mean()
for l, al in enumerate(LB[1:], 1):
    if al.size < 4: continue
    r = al.mean() / m0
    if not .85 <= r <= 1.2: bad.append(f'смешивание: уровень {l} непрозрачность x{r:.2f}')
    elif not (al > texq.ALPHA_REF).any(): bad.append(f'смешивание: уровень {l} пропадает под альфа-тестом')
if not LA[1].mean() / LA[0].mean() < .8: bad.append(f'альфа-тест: масштаб покрытия пропал (x{LA[1].mean() / LA[0].mean():.2f})')
isoft = load('textures/soft.png', cache, blob, True); isoft2 = load('textures/soft.png', cache, blob, False)
if isoft != isoft2: bad.append('не-вырезка получила вторую запись')
print('записи: вырезка альфа-тест %d, смешивание %d; не-вырезка %d/%d; уровень 1 средняя альфа: альфа-тест %.0f, смешивание %.0f '
      '(уровень 0 %.0f)' % (ia, ib, isoft, isoft2, LA[1].mean(), LB[1].mean(), m0))
for b in bad: print('  ' + b)
print('texq_blend:', 'FAIL' if bad else 'PASS', '(legacy)' if LEGACY else '')
sys.exit(1 if bad else 0)
