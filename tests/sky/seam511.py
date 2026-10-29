"""№511 швы неба: гейт без данных игры. Зелёный: bleed_rgb убирает чужой цвет под прозрачным и не трогает видимое и альфу;
билинейная выборка у края слоя не берёт цвет невидимого пикселя; tri_i16_clampv держит v в [0, 1] (без переноса), u сдвигает как раньше.
Красный контроль: старый путь (без bleed, v с переносом) даёт кайму и смешение через край.   python3 tests/sky/seam511.py"""
import sys, numpy as np
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import texq, uvq

def layer():   # холмы: верх непрозрачный зелёный, низ прозрачный, под прозрачным чужой серо-розовый
    a = np.zeros((16, 16, 4), np.uint8)
    a[:, :, :3] = (200, 120, 160)
    a[:11, :, :3] = (40, 120, 40); a[:11, :, 3] = 255
    return Image.fromarray(a, 'RGBA')

def lerp_row_color(img, y_edge):   # цвет билинейной выборки на границе видимого/невидимого: среднее строк y_edge-1 и y_edge
    a = np.asarray(img, np.float64)
    return (a[y_edge - 1, 0] + a[y_edge, 0]) / 2

ok = True
img = layer(); new = texq.bleed_rgb(img, 65); a0, a1 = np.asarray(img), np.asarray(new)
vis = a0[..., 3] >= 65
c1 = (a0[~vis][:, :3] != (200, 120, 160)).any()
t = (a1[vis] == a0[vis]).all() and (a1[..., 3] == a0[..., 3]).all()
fringe_old = lerp_row_color(img, 11)[:3]; fringe_new = lerp_row_color(new, 11)[:3]
good = np.abs(fringe_new - (40, 120, 40)).max() < 1e-6 and np.abs(fringe_old - (40, 120, 40)).max() > 50
print('bleed: видимое и альфа целы' if t else 'FAIL bleed трогает видимое', '| кайма до', fringe_old.round(0), 'после', fringe_new.round(0)); ok &= bool(t and good)
u = np.array([-0.01, 0.2, 0.3], np.float32); v = np.array([-0.0004, 0.5, 1.0004], np.float32)
uu, vv = uvq.tri_i16_clampv(u, v); gu, gv = uvq.ge_uv(uu, vv)
ok &= bool(gv.min() >= 0 and gv.max() <= 1.0 + 1e-9 and gu.min() >= 0)
uo, vo = uvq.tri_i16(np.array([0.5, 0.6, 0.7], np.float32), np.array([1.0, 1.0, 1.0], np.float32)); go = uvq.ge_uv(uo, vo)[1]
un, vn = uvq.tri_i16_clampv(np.array([0.5, 0.6, 0.7], np.float32), np.array([1.0, 1.0, 1.0], np.float32)); gn = uvq.ge_uv(un, vn)[1]
print('v: верхняя строка v=1: старое', go.tolist(), '(перенос на 0 при REPEAT смешает с низом), новое', gn.tolist())
ok &= bool(go.max() == 0.0 and gn.min() == 1.0)
# утечка: текстура, общая у неба и города (стекло Krusty/холмы) — у города прежняя запись, у неба своя копия с bleed
import tempfile, os
tmp = Path(tempfile.mkdtemp()); layer().save(tmp / 'g.png'); texq.TEXDIR = tmp
texq.BLEED_URLS['g.png'] = 65
c1, b1 = {}, []; city = texq.load_tex('g.png', c1, b1); sk = texq.load_tex('g.png', c1, b1, sky=True)
c2, b2 = {}, []; ref = texq.load_tex('g.png', c2, b2)
texq.BLEED_URLS.clear(); c3, b3 = {}, []; plain = texq.load_tex('g.png', c3, b3, sky=True)   # sky без регистрации = как город
leak = b1[city] != b2[ref] or city == sk or b1[sk] == b1[city] or b3[plain] != b2[ref]
print('утечка bleed в город:', 'ЕСТЬ' if leak else 'нет (город байт в байт, небо отдельной копией)'); ok &= not leak
print('ЗЕЛЁНЫЙ' if ok else 'КРАСНЫЙ'); sys.exit(0 if ok else 1)
