"""Обход треугольников комнаты — лицом в комнату (правка Роба 27, 28.09: «в доме Симпсонов камера местами в стене, полкадра —
стена»; видео 4:16–4:22).

Камеры комнат оригинала (рельсы и угловые StaticCam из данных, viewer/roomcam.c) стоят ЗА стенами комнаты и смотрят сквозь
них: стена, повёрнутая лицом в комнату, из-за неё не видна (отсечение изнанки). Порт рисовал комнаты двусторонними — и
камера за стеной показывала её изнанку. Обход на диске у художников «какой получился» (в школе и Kwik-E-Mart изнутри видно
треть изнанок), поэтому сторону решает видимость ИЗ КОМНАТЫ, как tools/wind.c у города:
  глаза — узлы сетки EYE_STEP по земле комнаты (COL1 комнаты), на высоте глаз Гомера EYE_H над полом, не внутри ящиков
  мебели; из каждого — куб 6 граней с глубиной (tools/roomvis.c vote). Треугольник, который изнутри видят с обеих сторон
  (мебель, листья, тонкие перегородки: меньшинство ≥ MINOR и ≥ MINOR_REL), — двусторонний (флаг 8); остальные
  поворачиваются лицом туда, откуда их видят (вершины 1 и 2 местами), и рисуются с отсечением (флаг 128 у всех кусков
  комнаты — движок включает отсечение, viewer/main.c setFlags). Невидимые изнутри (спинки полок у стен, верх шкафов) —
  двусторонние, как было: оболочкой они не бывают, а камеру сверху не подведут.
Правило порта (в данных нет флага двусторонности шейдеров; вывод — из расстановки камер за стенами), сверить с эталоном PS2.
Правка Роба 301 (04.10: «у телевизора тыльная часть пустая, как будто просто рамка»): глаза Гомера ходят только по полу, а
камеры оригинала смотрят и оттуда, куда Гомер не дойдёт: спинку телевизора дома Симпсонов (плоскость 2 треугольника по 0,66 м²
z 400,73; за ней 0,27 м до края пола) глаза видят только спереди (9–10 тыс. пикселей лицом, 0 изнанкой) — она стала односторонней,
а камера int_sh_path1 (z 402,87, кадр близнеца v17_house_cam f01000: спинка серая, сплошная) видит её изнанку — движок её
отсекал, сквозь корпус был виден ковёр. Поэтому вторая проверка — кадрами камер оригинала, как в EBOOT (viewer/roomcam.c через
tests/rooms/view_host.c, Гомер в узлах пола через CAM_STEP м): всё с обеих сторон, кто первым виден изнанкой — тот двусторонний
(tools/roomvis.c seen). Кадр, где изнанкой больше SEEN_MAX, — камера за стеной (ради неё правка 27): не в счёт.
SHR_ROOM_CAMSIDE=0 — как до правки 301."""
import os, struct, subprocess, tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EYE_STEP, EYE_H = 0.75, (0.6, 1.2, 1.8)
MINOR, MINOR_REL = 3, 0.03
F_DOUBLE, F_SHELL = 8, 128
BIN = ROOT / 'build' / 'roomvis'
CAM_STEP, SEEN_MAX, SEEN_MIN = 1.0, 0.10, 1   # правка 301: узлы пола для кадров камер; доля «изнанкой» камеры за стеной; пикселей
VIEW_W, VIEW_H = 160, 90                      # кадр 16:9, как tests/rooms/walls.py
HOST = ROOT / 'build' / 'roomcam_view'


def tool():
    src = ROOT / 'tools' / 'roomvis.c'
    if not BIN.exists() or src.stat().st_mtime > BIN.stat().st_mtime:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['cc', '-O3', '-o', str(BIN), str(src), '-lm'], check=True)
    return BIN


def view_host():
    """камеры комнат движка на Маке (viewer/roomcam.c + tests/rooms/view_host.c) -> бинарник build/roomcam_view"""
    src = [ROOT / 'tests/rooms/view_host.c', ROOT / 'viewer/roomcam.c', ROOT / 'viewer/roomcam.h']
    if not HOST.exists() or max(s_.stat().st_mtime for s_ in src) > HOST.stat().st_mtime:
        HOST.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['cc', '-std=c99', '-O2', '-I', str(ROOT / 'viewer'), str(src[0]), str(src[1]), '-lm', '-o', str(HOST)], check=True)
    return HOST


def cam_views(cam_tab, ncam, TR, BX, step=CAM_STEP):
    """кадры камер оригинала, как в EBOOT: таблица камер блоба RMG1 (tools/interior_export.py cam_table с началом 128), Гомер в
    узлах пола -> (M, 8) глаз, цель, вертикальный FOV, 16:9 (только узлы в триггере какой-нибудь камеры)"""
    feet = floor_points(TR, BX, step)
    if not ncam or not len(feet): return np.zeros((0, 8), np.float32)
    blob = bytearray(128); struct.pack_into('<2I', blob, 120, 128, ncam); blob += cam_tab; blob += b'\0' * (-len(blob) % 16)
    shg = b'SHG1' + struct.pack('<3I', 1, 1, 0) + struct.pack('<32sII8x', b'R', 64, len(blob)) + bytes(blob)
    d = Path(tempfile.mkdtemp(prefix='roomcam_')); (d / 'r.bin').write_bytes(shg)
    req = ''.join(f'R {x:.4f} {y:.4f} {z:.4f}\n' for x, y, z in feet)
    out = subprocess.run([str(view_host()), str(d / 'r.bin')], input=req, capture_output=True, text=True, check=True).stdout
    V = [[float(v) for v in l.split()[8:14]] + [float(l.split()[7]), VIEW_W / VIEW_H] for l in out.splitlines()
         if l.startswith('VIEW ') and l.split()[5] != '-1']
    return np.array(V, np.float32).reshape(-1, 8)


def seen(T, drawn2, V):
    """T (N,3,3) в обходе для движка, drawn2 — рисуется с обеих сторон, V — кадры (cam_views) -> (пикселей изнанкой по
    треугольникам в кадрах «в счёт», пикселей изнанкой по кадрам)"""
    d = Path(tempfile.mkdtemp(prefix='roomseen_'))
    write_tris(d / 't.bin', T, np.asarray(drawn2, np.uint8))
    with open(d / 'v.bin', 'wb') as f: f.write(struct.pack('<I', len(V))); f.write(np.asarray(V, '<f4').tobytes())
    subprocess.run([str(tool()), 'seen', str(d / 't.bin'), str(d / 'v.bin'), str(d / 'o.bin'), '--w', str(VIEW_W), '--h', str(VIEW_H),
                    '--max', str(SEEN_MAX)], check=True)
    o = np.frombuffer((d / 'o.bin').read_bytes(), '<u4')
    return o[:len(T)].astype(np.int64), o[len(T):].astype(np.int64)


def floor_points(TR, BX, step=EYE_STEP):
    """узлы сетки по земле комнаты (нижняя опора в точке), без мест внутри ящиков мебели -> (N, 3) ноги"""
    g = TR[TR[:, 3, 1] > .7][:, :3]
    if not len(g): return np.zeros((0, 3))
    lo, hi = g.reshape(-1, 3).min(0), g.reshape(-1, 3).max(0)
    X, Z = np.meshgrid(np.arange(lo[0] + step / 2, hi[0], step), np.arange(lo[2] + step / 2, hi[2], step))
    X, Z = X.ravel(), Z.ravel(); Y = np.full(len(X), np.inf)
    for (ax, ay, az), (bx, by, bz), (cx, cy, cz) in g:
        d = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
        if abs(d) < 1e-9: continue
        w1 = ((bz - cz) * (X - cx) + (cx - bx) * (Z - cz)) / d; w2 = ((cz - az) * (X - cx) + (ax - cx) * (Z - cz)) / d; w3 = 1 - w1 - w2
        m = (w1 >= -1e-6) & (w2 >= -1e-6) & (w3 >= -1e-6)
        Y[m] = np.minimum(Y[m], (w1 * ay + w2 * by + w3 * cy)[m])
    P = np.c_[X, Y, Z][np.isfinite(Y)]
    if len(BX) and len(P):
        ok = np.ones(len(P), bool)
        for b in BX:   # ноги (на 0.5 м над полом) в ящике мебели с запасом 0.3 м — Гомер там не стоит
            c, A, h = b[:3], b[3:12].reshape(3, 3), b[12:15]
            dd = (P + np.array([0, .5, 0]) - c) @ A.T
            ok &= ~(np.abs(dd) <= h + .3).all(1)
        P = P[ok]
    return P


def write_tris(path, T, flags=None, side=None):
    n = len(T)
    with open(path, 'wb') as f:
        f.write(struct.pack('<I', n)); f.write(np.asarray(T, '<f4').reshape(-1).tobytes())
        f.write((np.zeros(n, np.uint8) if flags is None else np.asarray(flags, np.uint8)).tobytes())
        f.write((np.zeros(n, np.int8) if side is None else np.asarray(side, np.int8)).tobytes())


def vote(T, eyes, res=96):
    """T (N,3,3), eyes (M,3) -> front, back: пикселей лицом / изнанкой к глазам (tools/roomvis.c vote)"""
    d = Path(tempfile.mkdtemp(prefix='roomvis_'))
    write_tris(d / 't.bin', T)
    with open(d / 'e.bin', 'wb') as f: f.write(struct.pack('<I', len(eyes))); f.write(np.asarray(eyes, '<f4').reshape(-1).tobytes())
    subprocess.run([str(tool()), 'vote', str(d / 't.bin'), str(d / 'e.bin'), str(d / 'o.bin'), '--res', str(res)], check=True)
    o = np.frombuffer((d / 'o.bin').read_bytes(), '<u4').reshape(2, -1)
    return o[0].astype(np.int64), o[1].astype(np.int64)


def eyes_of(TR, BX):
    feet = floor_points(TR, BX)
    return np.concatenate([feet + np.array([0, h, 0]) for h in EYE_H]) if len(feet) else np.zeros((0, 3))


def decide(front, back):
    """-> flip (N,) — развернуть; double (N,) — двусторонний; seen (N,) — видим изнутри"""
    tot = front + back; mn = np.minimum(front, back)
    seen = tot > 0
    double = ((mn >= MINOR) & (mn >= MINOR_REL * tot)) | ~seen   # невидимые изнутри — как до правки, с обеих сторон
    flip = ~double & (back > front)
    return flip, double, seen


def orient_prims(prims, TR, BX, cams=None):
    """prims [(tex, flags, P (3n,3), UV (3n,2), C (3n,))] -> те же с обходом лицом в комнату, двусторонние — отдельными
    примитивами с флагом 8; всем флаг 128 (рисовать с отсечением). cams — (таблица камер с началом 128, число) для второй
    проверки кадрами камер оригинала (правка 301). Возврат (новые prims, сводка)"""
    if not prims: return prims, {}
    T = np.concatenate([p[2].reshape(-1, 3, 3) for p in prims]).astype(np.float64)
    eyes = eyes_of(TR, BX)
    if not len(eyes): return prims, dict(eyes=0)
    front, back = vote(T, eyes)
    flip, double, vis = decide(front, back)
    cam = {}
    if cams and cams[1] and os.environ.get('SHR_ROOM_CAMSIDE', '1') != '0':   # правка 301: что камеры оригинала видят изнанкой
        To = T.copy(); To[flip] = To[flip][:, [0, 2, 1]]
        V = cam_views(cams[0], cams[1], TR, BX)
        if len(V):
            acc, pv = seen(To, double, V)
            add = ~double & (acc >= SEEN_MIN); double = double | add; flip = flip & ~add
            cam = dict(cam_views=len(V), cam_skipped=int((pv > SEEN_MAX * VIEW_W * VIEW_H).sum()), cam_double=int(add.sum()))
    out, k = [], 0
    for t, fl, P, UV, C in prims:
        n = len(P) // 3; f, d = flip[k:k + n], double[k:k + n]; k += n
        P, UV, C = P.reshape(n, 3, 3).copy(), UV.reshape(n, 3, 2).copy(), C.reshape(n, 3).copy()
        for arr in (P, UV, C): arr[f] = arr[f][:, [0, 2, 1]]
        for sel, extra in ((~d, 0), (d, F_DOUBLE)):
            if sel.any(): out.append((t, fl | F_SHELL | extra, P[sel].reshape(-1, 3), UV[sel].reshape(-1, 2), C[sel].reshape(-1)))
    return out, dict(eyes=len(eyes), tris=len(T), flipped=int(flip.sum()), double=int(double.sum()), unseen=int((~vis).sum()), **cam)
