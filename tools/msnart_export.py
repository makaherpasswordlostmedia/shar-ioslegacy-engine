#!/usr/bin/env python3
"""Маркеры цели и значки заданий миссий уровня -> build/msnart.shr (формат MSA2, viewer/msnart.c).

Только данные с диска Роба (hit-and-run-web/source/game). Что попадает: файлы, которые скрипты уровня грузят командой
LoadP3DFile (level.mfk + загрузочные mXl/mXsdl и бонусов), если в них есть
  * составные объекты-маркеры (CompositeDrawable 0x4512: carsphere, triggersphere, exclamation, kwik_mission_doorstar,
    icebuck ...): billboard-квады (BillboardQuadGroup 0x17002) и меши на суставах скелета в позе покоя;
    анимация квадов (BQG_: ширина, высота, цвет) запекается покадрово — дверная звезда двери мерцает, как в оригинале;
  * значки заданий art/frontend/dynaload/images/msnicons/* (спрайт Scrooby из плиток: tools/ui_export.decode_sprite_image).
Движок грузит запись файла в тот же момент, что оригинал (LoadP3DFile уровня — на старте уровня, миссии — на её старте),
и выгружает при старте следующей миссии.
Анимация суставов PTRN (с 28.09, пакет «Объекты уровня и миссий»): циклический клип (флаг цикла в данных) запекается
покадрово в матрицы суставов — предметы крутятся и покачиваются, «!» прыгает, доллар стоит в позе кадра 0 (его поза покоя
скелета на 0.72 м в стороне). Меши и квады хранятся в осях своего сустава, движок ставит их матрицей кадра.
Режим рисования меша — из шейдера и альфы данных (раньше меш с BLMD 1 шёл без записи глубины: закрытые предметы —
банки колы у ведёрка, пачки, постер — просвечивали сами через себя): 0 непрозрачный (BLMD 0/1, альфа текстуры и вершин
вся ~255), 1 вырезка (ATST или альфа почти только 0/255: альфа-тест + запись глубины), 2 полупрозрачный (без записи
глубины, после непрозрачных), 3 сложение (BLMD 2), 4 вычитание (BLMD 3).
Не переносится (печатается в отчёте): системы частиц составных объектов, свечения, клипы без флага цикла (стоят на кадре 0).

  python tools/msnart_export.py [--level 1] [--out build/msnart.shr]
Формат (little endian): заголовок 32 Б "MSA2", n, offTable, size; таблица n x 96 Б (путь 80 Б как в скрипте:
строчные, '/'; off, size, pad[2]); запись — блок с заголовком 32 Б (ntex, ndraw, nimg, offTex, offDraw, offImg, pad[2]),
текстуры 16 Б (u16 w, h; off; u32 psm 3 = 8888; pad), значки 48 Б (имя 32; tex; w, h пикселей картинки; pad),
объекты 64 Б (имя 32; nbill, offBill, nmesh, offMesh, njoint, nfr (кадров позы, 1 — стоит), fps, offJoint: nfr x njoint x
12 float — R по столбцам 9 + t 3, оси объекта), квады 80 Б (tex, blend, mode 0 = NOAX 1 = к камере, zwrite; центр xyz,
ось X xyz, ось Y xyz — в осях сустава; w, h, argb, nfr, offTrack, fps, dist; mode = режим | сустав << 8), дорожка nfr x 6
float (w, h, r, g, b, a). dist квада (BillboardQuad диска: у свечений и звёзд предметов −0.2..−0.62) — сдвиг вдоль луча
взгляда: отрицательный — от камеры, свечение уходит за предмет (раньше не переносился, звезда закрывала предмет; знак —
правило порта, сверить с эталоном PS2),
меши 16 Б (tex, флаги = BLMD | режим << 8 | сустав << 16, nvert, offVert), вершины 24 Б (u, v float; ABGR; x, y, z float
в осях сустава), список треугольников.
Координаты движка (z игры отзеркален, как level.shr). Текстуры 8888, степень двойки, сторона <= 64 (<= 128 у крупных).
"""
import argparse, io, os, struct, sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools')); sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tools/missions'))
from p3d import read, walk, string          # noqa: E402  (MIT)
from textures import decode_image          # noqa: E402  (MIT)
from convert import geometry               # noqa: E402  (MIT)
import mfk                                 # noqa: E402
from prp2_export import billboards         # noqa: E402
from frontend3d_export import anims, sample, argb, shaders_of   # noqa: E402
from ui_export import decode_sprite_image  # noqa: E402
import ui_export as UE                     # noqa: E402  аватар значков заданий (размер на экране, увеличитель)
import prp2_export as PX                   # noqa: E402  скелет + PTRN по кадрам (joint_poses)
from animobj_export import pose_world      # noqa: E402
from briefcards_source import builtin_paths
from p3d import Chunk                      # noqa: E402

GAME = ROOT / 'hit-and-run-web/source/game'
F4 = np.diag([1., 1., -1., 1.])
MAXTEX = 64
# Правка Роба 166 (01.10: «над телефонными будками крутятся синие трубки — ты их не загрузил»): level.mfk всех уровней грузит
# LoadP3DFile("art\cards.p3d"); в нём, кроме карточки (её рисует пакет коллекции, tools/collect_export.py), составные объекты
# phone_icon (синяя трубка: меш, свечения BQG, PTRN 121 кадр по кругу — крутится и качается) и phone_icon_shadow (голубой круг
# на земле под будкой, BQG дышит 3.1–3.5 м). Движок рисует их над каждой будкой уровня (viewer/main.c, как shirtdollar)
PICK = {'art/cards.p3d': ('phone_icon', 'phone_icon_shadow'),
        # перепись миссий 04.10: эффект подбора SetCollectibleEffect("wrench_collect") — 321 вызов на уровнях 1–7 (искры при въезде в сферу
        # цели); его квады wrench_collectShape* — здесь, частицы wrench_collect2Shape — в fx.shr (tools/fx_export.py). Рисует движок
        # (props.item_collected — помощник «эффекты»); level.mfk всех уровней грузит art/wrench.p3d — запись живёт весь уровень
        'art/wrench.p3d': ('wrench_collect',)}


def norm(p): return p.replace('\\', '/').lower()


def pow2(n):
    k = 1
    while k < n: k *= 2
    return k


def tex_bytes(img, cap=MAXTEX):
    """PIL RGBA -> (w, h, bytes 8888 ABGR-порядок байт R,G,B,A), степень двойки <= cap, пропорции как есть"""
    w, h = img.size
    tw, th = min(pow2(w), cap), min(pow2(h), cap)
    img = img.convert('RGBA').resize((tw, th), Image.LANCZOS)
    return tw, th, img.tobytes()


def load_scripts(level):
    d = GAME / f'scripts/missions/level{level:02d}'
    files = []
    for f in sorted(d.glob('*.mfk')):
        n = f.name.lower()
        if n == 'level.mfk' or n.endswith('l.mfk'):      # level.mfk + загрузочные (mXl, mXsdl, sr1l ...)
            files.append(f)
    out = []
    for f in files:
        calls, _ = mfk.parse_file(f)
        for c in calls:
            if c.op == 'LoadP3DFile' and c.args:
                p = norm(str(c.args[0]))
                if p not in out: out.append(p)
    return out


def presentation_paths(level):
    """картинки брифинга миссий (SetPresentationBitmap в скриптах миссий уровня)"""
    out = []
    for f in sorted((GAME / f'scripts/missions/level{level:02d}').glob('*.mfk')):
        calls, _ = mfk.parse_file(f)
        for c in calls:
            if c.op == 'SetPresentationBitmap' and c.args:
                p = norm(str(c.args[0]))
                if p not in out: out.append(p)
    # 423: original-disc built-ins are selected by the bonus giver, absent from MFK SetPresentationBitmap.
    # BRIEFCARDS_423_OLD=1 keeps the former package for the actual missing-image red control.
    if not os.environ.get('BRIEFCARDS_423_OLD'):
        for p in builtin_paths():
            if ('/misxx_' in p or '/mis%02d_' % level in p) and p not in out: out.append(p)
    return out


def textures_of(root):
    out = {}
    for c in root.children:
        if c.id != 0x19000: continue
        name = string(c.data)[0].lower()
        try:
            im = next(v for v in c.children if v.id == 0x19001); raw = next(v for v in im.children if v.id == 0x19002).data[4:]
            out[name] = decode_image(raw)
        except (StopIteration, ValueError):
            pass
    return out


def skeleton_world(sk):
    """суставы в позе покоя -> [мировая строчная 4x4 в осях движка]"""
    W = []
    for j in sk.children:
        if j.id != 0x4501: continue
        _, p = string(j.data); par, = struct.unpack_from('<I', j.data, p)
        L = np.frombuffer(j.data, '<f4', 16, p + 24).reshape(4, 4).astype(np.float64)
        W.append(L @ W[par] if W and par < len(W) else L)
    return [F4 @ M @ F4 for M in W]


class Entry:
    def __init__(self):
        self.tex = []; self.texidx = {}; self.imgs = []; self.draws = []; self.skipped = []

    def add_tex(self, key, img, cap=MAXTEX):
        if key in self.texidx: return self.texidx[key]
        self.texidx[key] = len(self.tex); self.tex.append(tex_bytes(img, cap)); return self.texidx[key]

    def pack(self):
        blob = bytearray(32)
        def align():
            while len(blob) % 16: blob.append(0)
        align(); offTex = len(blob); blob += bytes(16 * len(self.tex))
        align(); offImg = len(blob); blob += bytes(48 * len(self.imgs))
        align(); offDraw = len(blob); blob += bytes(64 * len(self.draws))
        for i, (w, h, px) in enumerate(self.tex):
            align(); o = len(blob); blob += px
            struct.pack_into('<HHII4x', blob, offTex + 16 * i, w, h, o, 3)
        for i, (name, t, w, h, *top) in enumerate(self.imgs):   # pad записи = верх значка в углу + 1 (0 — движок считает сам)
            struct.pack_into('<32sIIII', blob, offImg + 48 * i, name.encode()[:31], t, w, h, top[0] + 1 if top and top[0] is not None else 0)
        for i, d in enumerate(self.draws):
            align(); ob = len(blob); blob += bytes(80 * len(d['bills']))
            for k, b in enumerate(d['bills']):
                align(); otr = len(blob)
                for row in b['track']: blob += struct.pack('<6f', *row)
                struct.pack_into('<4I3f3f3f2fIIIff', blob, ob + 80 * k, b['tex'], b['blend'], b['mode'] | (b['joint'] << 8), b['zwrite'],
                                 *b['c'], *b['ax'], *b['ay'], b['w'], b['h'], b['argb'], len(b['track']), otr, b['fps'], b['dist'])
            align(); om = len(blob); blob += bytes(16 * len(d['meshes']))
            shared = {}   # один список вершин на несколько мешей (экземпляры пропов гонки) — в пакете один раз
            for k, m in enumerate(d['meshes']):
                ov = shared.get(id(m['verts']))
                if ov is None:
                    align(); ov = len(blob); shared[id(m['verts'])] = ov
                    for (u, v, c, x, y, z) in m['verts']: blob += struct.pack('<2fI3f', u, v, c, x, y, z)
                struct.pack_into('<4I', blob, om + 16 * k, m['tex'] & 0xFFFFFFFF, m['blend'] | (m['mode'] << 8) | (m['joint'] << 16), len(m['verts']), ov)   # -1 — без текстуры (движок: ti >= ntex)
            align(); oj = len(blob)
            for M in d['frames']: blob += np.asarray(M, '<f4').tobytes()
            struct.pack_into('<32s4I2IfI', blob, offDraw + 64 * i, d['name'].encode()[:31], len(d['bills']), ob, len(d['meshes']), om,
                             d['njoint'], len(d['frames']) // max(d['njoint'], 1), d['fps'], oj)
        align()
        struct.pack_into('<6I', blob, 0, len(self.tex), len(self.draws), len(self.imgs), offTex, offDraw, offImg)
        return bytes(blob)


def draw_mode(blm, atst, img, vert_amin):
    """режим рисования меша из данных: 0 непрозрачный, 1 вырезка (альфа-тест + глубина), 2 полупрозрачный, 3 сложение,
    4 вычитание. BLMD 1 с альфой текстуры и вершин ~255 — непрозрачный (смешивание ничего не даёт, а без записи глубины
    закрытый предмет просвечивает сам через себя); альфа почти только 0/255 — вырезка."""
    if blm == 2: return 3
    if blm == 3: return 4
    a = np.asarray(img.convert('RGBA'))[..., 3] if img is not None else np.full((1, 1), 255, np.uint8)
    solid = a.min() >= 250 and vert_amin >= 250
    cut = float(((a > 8) & (a < 247)).mean()) < 0.05 and vert_amin >= 250
    if blm == 1: return 0 if solid else (1 if cut else 2)
    return 1 if (atst and not solid) else 0


# Роб 17.10 вечер: значок задания в углу (после пузыря) ставится по ВЕРХУ СВОЕГО РИСУНКА — отступ у каждого свой, кольца в одно место НЕ сводить
# (memory feedback_shar_icon_custom_top). Все 150 msnicons просмотрены глазами: над кольцом у многих главное — голова (манекен digest, обезьяна),
# вывеска (Krusty Burger, Kwik-E-Mart, кладбище), сам предмет (бензопила, $ над футболкой) — это верх, он виден целиком. Уточнения:
#  · невидимые полупрозрачные пиксели не верх (Ralph: альфа ≤ 45 на 7 px выше рисунка — кольцо опускалось на 10 px) → верх = первая строка, где
#    хотя бы 2 пикселя с альфой ≥ 128;
#  · тонкая мелочь над корпусом — не верх (ICON_MINOR: антенна радио, антенна дома Симпсонов, соломинка стакана) → верх = первая строка шире
#    ICON_MINOR_W px; мелочь при этом может уйти за край экрана.
# Значение — в поле pad записи картинки (верх + 1), движок viewer/ui.c берёт его вместо своего счёта по альфе 32. ICON_TOP_OLD=1 — прежнее (0)
ICON_TOP = os.environ.get('ICON_TOP_OLD') != '1'
ICON_MINOR = {'radio', 'kbmeal', 'simpsons'}
ICON_MINOR_W = 6


def icon_top(im, stem):
    if not ICON_TOP: return None
    import numpy as np
    a = np.asarray(im.convert('RGBA'))[..., 3]
    need = ICON_MINOR_W if stem in ICON_MINOR else 2
    rows = np.nonzero((a >= 128).sum(1) >= need)[0]
    return int(rows.min()) if len(rows) else None


def export_file(path, box=(MAXTEX, MAXTEX), only=None):
    """only — имена составных объектов, которые берём из файла (None — все): из art/cards.p3d только значок будки"""
    root = read(GAME / path)
    e = Entry()
    # значки заданий (msnicons) и картинки брифинга (mis01_00): спрайт Scrooby из плиток, в холст box (степень двойки)
    # Значок задания (msnicons) — ровно размера аватара HUD на экране PSP (Роб 28.09, правка 22: аватар = высота пузыря;
    # tools/ui_export.py avatar_fit / avatar_ext_px), своим увеличителем ui_export.resample: движок рисует его 1:1, без растяжки
    ext = UE.avatar_ext_px() if 'msnicons/' in norm(str(path)) else None
    for c in root.children:
        if c.id == 0x19005:
            name, im = decode_sprite_image(c)
            name = name.rsplit('.', 1)[0]
            w, h = im.size
            if ext and (w, h) == UE.avatar_circle('msn')[1]:
                cw, ch = int(ext[0]), int(ext[1]); bx = (1 << (cw - 1).bit_length(), 1 << (ch - 1).bit_length())
                canvas = Image.new('RGBA', bx, (0, 0, 0, 0)); canvas.paste(UE.resample(im, cw, ch), (0, 0))
                t = len(e.tex); e.tex.append((bx[0], bx[1], canvas.tobytes())); e.imgs.append((name, t, cw, ch, icon_top(canvas.crop((0, 0, cw, ch)), Path(str(path)).stem.lower())))
                continue
            s = min(1., box[0] / w, box[1] / h); cw, ch = max(1, round(w * s)), max(1, round(h * s))
            canvas = Image.new('RGBA', box, (0, 0, 0, 0)); canvas.paste(im.resize((cw, ch), Image.LANCZOS), (0, 0))
            t = len(e.tex); e.tex.append((box[0], box[1], canvas.tobytes())); e.imgs.append((name, t, cw, ch))
    # правка 122 (сверка 30.09, запись PS2 2:13, 2:20, 4:03): зелёные стрелки навигации на дороге — наборы квадов 0x3F0000C файла
    # местности (l1_terra.p3d: darrow — езда, текстура darrow.tga; warrow — пешком, warrow.tga), скелет того же имени; группа квадов
    # «<имя>NShape» стоит на суставе N. Собираются как составной объект: группы квадов на суставах, PTRN_<имя> и BQG_ — как у маркеров
    sets = []
    for c in root.children:
        if c.id != 0x3F0000C: continue
        nm_, _ = string(c.data); els = []
        for g in c.children:
            if g.id != 0x17002: continue
            gn, _ = string(g.data, 4)
            if gn.startswith(nm_) and gn.endswith('Shape') and gn[len(nm_):-5].isdigit():
                els.append(Chunk(0x4516, bytes([len(gn)]) + gn.encode('latin1') + struct.pack('<2I', 0, int(gn[len(nm_):-5])), []))
        if els: sets.append((c, Chunk(0x4512, bytes([len(nm_)]) + nm_.encode('latin1') + bytes([len(nm_)]) + nm_.encode('latin1'), [Chunk(0, b'', els)])))
    comps = [c for c in root.children if c.id == 0x4512] + [cd for _, cd in sets]
    if only is not None: comps = [c for c in comps if string(c.data)[0] in only]
    if not comps: return e
    texs = textures_of(root); shaders = shaders_of(root); A = anims(root)
    bbs = billboards(root)
    for c, _ in sets: bbs.update(billboards(c))
    meshes = {string(c.data)[0]: c for c in root.children if c.id == 0x10000}
    skels = {string(c.data)[0]: c for c in root.children if c.id == 0x4500}
    def shader_tex(sh):
        s = shaders.get(sh, {}); tn = s.get('TEX', '')
        if tn not in texs: return -1, s
        return e.add_tex(tn, texs[tn]), s
    for cd in comps:
        cname, p = string(cd.data); skn, _ = string(cd.data, p)
        sk = skels.get(skn)
        J = skeleton_world(sk) if sk is not None else [np.eye(4)]
        # поза по кадрам: скелет + PTRN этого рисунка; цикл из данных — все кадры, иначе кадр 0 (стоит)
        frames, fps, joints = [], 30., None
        if sk is not None:
            an = [c for c in root.children if c.id == 0x121000 and string(c.data, 4)[0] in ('PTRN_' + cname, 'PTRN_' + skn)]
            loop = 0
            for c in an:
                _, q = string(c.data, 4)
                if c.data[q:q + 4] == b'PTRN': loop = struct.unpack_from('<ffI', c.data, q + 4)[2]
            try:
                joints, keys, nfr, ntrack, fps = PX.joint_poses(Chunk(0, b'', [sk] + an))
                for f in (range(nfr) if (ntrack and loop and nfr > 1) else [0]):
                    for M in pose_world(joints, keys, ntrack, f):
                        frames.append(np.r_[M[:3, :3].T.reshape(-1), M[:3, 3]])   # R по столбцам (как stateprops.c)
            except (ValueError, IndexError) as ex:
                e.skipped.append(f'{cname}: поза по кадрам не собрана ({ex}), поза покоя'); joints = None
        if joints is None:
            frames = [np.r_[M[:3, :3].reshape(-1), M[3, :3]] for M in J]   # строчная (F4 M F4): R^T по строкам = R по столбцам
        nj = len(J) if joints is None else len(joints)
        d = dict(name=cname, bills=[], meshes=[], frames=frames, njoint=nj, fps=float(fps or 30.))
        for lst in cd.children:
            for el in lst.children:
                if el.id == 0x4518:
                    e.skipped.append(f'{cname}: частицы {string(el.data)[0]}'); continue
                if el.id != 0x4516: continue
                dn, p = string(el.data); _, joint = struct.unpack_from('<2I', el.data, p)
                M = J[joint] if joint < len(J) else np.eye(4)
                if dn in bbs:
                    g = bbs[dn]; t, s = shader_tex(g['shader'])
                    an = A.get('BQG_' + dn); ch = an[3].get(dn, {}) if an else {}
                    for (mode, tq, col, w, h, dist) in g['quads']:
                        rows, fps = [], 30.
                        if an and ch:
                            _, nfr, fps, _ = an
                            for f in range(max(1, nfr)):
                                ww = sample(*ch['WDT'], f)[0] if 'WDT' in ch else w
                                hh = sample(*ch['HGT'], f)[0] if 'HGT' in ch else h
                                cc = sample(*ch['CLR'], f) if 'CLR' in ch else argb(col)
                                rows.append((ww, hh, *[float(x) for x in cc]))
                        else:
                            rows.append((w, h, *[float(x) for x in argb(col)]))
                        # в осях сустава: движок ставит центр и оси (NOAX) матрицей сустава кадра
                        d['bills'].append(dict(tex=t, blend=int(s.get('BLMD', 0)), mode=0 if mode.startswith('NOAX') else 1,
                                               zwrite=int(g['zwrite']), c=np.asarray(tq, np.float64), ax=np.r_[1., 0, 0], ay=np.r_[0., 1, 0],
                                               w=w, h=h, argb=col, track=rows, fps=float(fps), joint=min(joint, nj - 1), dist=float(dist)))
                elif dn in meshes:
                    for pg in meshes[dn].children:
                        if pg.id != 0x10002: continue
                        sh, parts = geometry(pg)
                        t, s = shader_tex(sh)
                        verts, amin = [], 255
                        for part in parts:
                            P = part['position']; n = len(P)
                            UV = part.get('uv', np.zeros((n, 2))); C = part.get('color', np.ones((n, 3))); Al = part.get('alpha', np.ones((n, 1)))
                            for i in part['indices']:
                                r, g_, b = (np.clip(C[i], 0, 1) * 255).astype(int); a = int(np.clip(Al[i][0], 0, 1) * 255); amin = min(amin, a)
                                verts.append((float(UV[i][0]), float(UV[i][1]), (a << 24) | (b << 16) | (g_ << 8) | r, *[float(x) for x in P[i][:3]]))
                        if verts:
                            blm = int(s.get('BLMD', 0) or 0)
                            d['meshes'].append(dict(tex=t, blend=blm, verts=verts, joint=min(joint, nj - 1),
                                                    mode=draw_mode(blm, int(s.get('ATST', 0) or 0), texs.get(s.get('TEX', '')), amin)))
                else:
                    e.skipped.append(f'{cname}: нет {dn}')
        if d['bills'] or d['meshes']: e.draws.append(d)
    return e


def race_props_paths(level):
    """файлы пропов уличных гонок уровня: StreetRacePropsLoad("l1_sr1p.p3d;") в скриптах миссий -> art/l1_sr1p.p3d"""
    out = []
    for f in sorted((GAME / f'scripts/missions/level{level:02d}').glob('*.mfk')):
        calls, _ = mfk.parse_file(f)
        for c in calls:
            if c.op == 'StreetRacePropsLoad' and c.args:
                for nm in str(c.args[0]).replace(':', ';').split(';'):
                    nm = nm.strip()
                    if nm and ('art/' + nm.lower()) not in out: out.append('art/' + nm.lower())
    return out


def export_race_props(path):
    """Правка 122 (сверка 30.09): пропы уличной гонки (l1_srNp.p3d) — шины и отбойники трассы (InstancedStaticEntity 0x3F00009),
    стартовая линия (InstancedStaticPhysics 0x3F0000A): меш один, экземпляры — суставы рисунка «<файл>» (кадр 0 = мировые матрицы
    экземпляров, как у inst_list); вершины общие (pack). Заборы трассы FenceWrapper 0x3F00007 -> список (ax, az, bx, bz, nx, nz)
    в осях движка (z отражён). Не переносится: анимированные шевроны 0x3F0000E"""
    root = read(GAME / path); e = Entry()
    texs = textures_of(root); shaders = shaders_of(root)
    d = dict(name=Path(path).stem.lower(), bills=[], meshes=[], frames=[], njoint=0, fps=30.)
    for ent in root.children:
        if ent.id == 0x3F0000E: e.skipped.append(f'{string(ent.data)[0]}: анимированный объект'); continue
        if ent.id not in (0x3F00009, 0x3F0000A): continue
        geo = [c for c in ent.children if c.id == 0x10000]; insts = PX.inst_list(ent)
        if not geo or not insts: continue
        groups = []
        for pg in geo[0].children:
            if pg.id != 0x10002: continue
            sh, parts = geometry(pg)
            sd = shaders.get(sh, {}); tn = sd.get('TEX', '')
            t = e.add_tex(tn, texs[tn]) if tn in texs else -1
            verts, amin = [], 255
            for part in parts:
                P = part['position']; n = len(P)
                UV = part.get('uv', np.zeros((n, 2))); C = part.get('color', np.ones((n, 3))); Al = part.get('alpha', np.ones((n, 1)))
                for i in part['indices']:
                    r, g_, b = (np.clip(C[i], 0, 1) * 255).astype(int); a = int(np.clip(Al[i][0], 0, 1) * 255); amin = min(amin, a)
                    verts.append((float(UV[i][0]), float(UV[i][1]), (a << 24) | (b << 16) | (g_ << 8) | r, *[float(x) for x in P[i][:3]]))
            if verts:
                blm = int(sd.get('BLMD', 0) or 0)
                groups.append((t, blm, draw_mode(blm, int(sd.get('ATST', 0) or 0), texs.get(tn), amin), verts))
        for _, M in insts:
            j = len(d['frames']); d['frames'].append(np.r_[M[:3, :3].reshape(-1), M[3, :3]])
            for (t, blm, mode, verts) in groups: d['meshes'].append(dict(tex=t, blend=blm, verts=verts, joint=j, mode=mode))
    # Перепись миссий 04.10: тем же StreetRacePropsLoad сценарий ставит не только пропы трасс. L1 m7 (m7i.mfk: «used here to load
    # power plant door to block the shortcut») грузит l1m7door.p3d — ворота АЭС: меши StaticEntity 0x3F00000 в координатах мира и
    # коробка столкновения StaticPhys 0x3F00001 (CollisionOBBoxVolume). Раньше не переносились — ворот не было, срезка открыта.
    # Меш: вершины от центра своего куска (convert.geometry уже отдаёт z отражённым, как у мира — ср. рамку 0x10003 диска: z 292.97…301.03,
    # меш −301.03…−292.97), сустав — тождественный поворот + центр (по нему отсечение дальше 70 м)
    for ent in root.children:
        if ent.id != 0x3F00000: continue
        groups, allp = [], []
        for geo in (c for c in ent.children if c.id == 0x10000):
            for pg in geo.children:
                if pg.id != 0x10002: continue
                sh, parts = geometry(pg)
                sd = shaders.get(sh, {}); tn = sd.get('TEX', '')
                t = e.add_tex(tn, texs[tn]) if tn in texs else -1
                verts, amin = [], 255
                for part in parts:
                    P = part['position']; n = len(P)
                    UV = part.get('uv', np.zeros((n, 2))); C = part.get('color', np.ones((n, 3))); Al = part.get('alpha', np.ones((n, 1)))
                    for i in part['indices']:
                        r, g_, b = (np.clip(C[i], 0, 1) * 255).astype(int); a = int(np.clip(Al[i][0], 0, 1) * 255); amin = min(amin, a)
                        verts.append([float(UV[i][0]), float(UV[i][1]), (a << 24) | (b << 16) | (g_ << 8) | r, float(P[i][0]), float(P[i][1]), float(P[i][2])])
                        allp.append(P[i][:3])
                if verts:
                    blm = int(sd.get('BLMD', 0) or 0)
                    groups.append((t, blm, draw_mode(blm, int(sd.get('ATST', 0) or 0), texs.get(tn), amin), verts))
        if not groups: continue
        cx, cy, cz = (np.min(allp, 0) + np.max(allp, 0)) / 2
        j = len(d['frames']); d['frames'].append(np.r_[1., 0, 0, 0, 1., 0, 0, 0, 1., cx, cy, cz])
        for (t, blm, mode, verts) in groups:
            d['meshes'].append(dict(tex=t, blend=blm, joint=j, mode=mode,
                                    verts=[(u, v, c, x - cx, y - cy, z - cz) for (u, v, c, x, y, z) in verts]))
    d['njoint'] = len(d['frames'])
    if d['meshes']: e.draws.append(d)
    fences = []
    # коробки столкновения StaticPhys (ворота l1m7door) -> четыре забора по периметру в плоскости XZ (нормали наружу), как FenceWrapper
    for ent in root.children:
        if ent.id != 0x3F00001: continue
        for ob in (k for k in walk(ent) if k.id == 0x7010004 and len(k.data) >= 12):
            vec = [np.array(struct.unpack_from('<3f', v.data)) for v in ob.children if v.id == 0x7010007 and len(v.data) >= 12]
            if len(vec) < 4: continue
            half = struct.unpack_from('<3f', ob.data); c0, axes = vec[0], vec[1:4]
            hor = sorted(range(3), key=lambda k: abs(axes[k][1]))[:2]   # две оси, ближе всего к горизонтали
            u, w = axes[hor[0]] * half[hor[0]], axes[hor[1]] * half[hor[1]]
            corners = [c0 + u + w, c0 - u + w, c0 - u - w, c0 + u - w]
            for k in range(4):
                A, B = corners[k], corners[(k + 1) % 4]
                mid = (A + B) / 2 - c0; nrm = np.array([mid[0], mid[2]]); nl = np.hypot(*nrm) or 1.
                fences.append((float(A[0]), float(-A[2]), float(B[0]), float(-B[2]), float(nrm[0] / nl), float(-nrm[1] / nl)))
    for c in root.children:
        if c.id != 0x3F00007: continue
        for f in c.children:
            if f.id == 0x3000000 and len(f.data) >= 36:
                ax, _, az, bx, _, bz, nx, _, nz = struct.unpack_from('<9f', f.data)
                fences.append((ax, -az, bx, -bz, nx, -nz))
    return e, fences


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--level', type=int, default=1); ap.add_argument('--out', default=str(ROOT / 'build/msnart.shr'))
    ap.add_argument('--fences', help='только заборы трасс уличных гонок (RFN1) в этот файл — racefence.bin (tools/ship_rules.txt)')
    a = ap.parse_args()
    if a.fences:   # RFN1 · n · [имя 32 · заборов · (ax az bx bz nx nz)] — viewer/msn_view.c raceFences
        rf = bytearray(); nrf = 0
        for rp in race_props_paths(a.level):
            if not (GAME / rp).exists(): continue
            _, fences = export_race_props(rp)
            rf += struct.pack('<32sI', Path(rp).stem.lower().encode()[:31], len(fences)); nrf += 1
            for fz in fences: rf += struct.pack('<6f', *fz)
            print(f'  {rp}: заборов {len(fences)}')
        Path(a.fences).parent.mkdir(parents=True, exist_ok=True); Path(a.fences).write_bytes(b'RFN1' + struct.pack('<I', nrf) + bytes(rf))
        print(f'{a.fences}: трасс {nrf}'); return
    entries = []
    for p in presentation_paths(a.level):   # брифинг: грузится по SetPresentationBitmap (256 x 128: на PSP ~224 x 116)
        if not (GAME / p).exists(): print(f'  нет на диске: {p}'); continue
        e = export_file(p, (256, 128))
        if e.imgs: entries.append((p, e.pack())); print(f'  {p}: брифинг {e.imgs[0][0]} {e.imgs[0][2]}x{e.imgs[0][3]}')
    for rp in race_props_paths(a.level):   # пропы уличных гонок (шины, отбойники, старт); заборы — отдельно (--fences)
        if not (GAME / rp).exists(): print(f'  нет на диске: {rp}'); continue
        e, fences = export_race_props(rp)
        if e.draws: entries.append((rp, e.pack())); print(f'  {rp}: пропы гонки, экземпляров {e.draws[0]["njoint"]}, мешей {len(e.draws[0]["meshes"])}, текстур {len(e.tex)}, заборов {len(fences)}')
        for sk in e.skipped: print(f'      не перенесено: {sk}')
    ta = f'art/l{a.level}_terra.p3d'   # стрелки навигации на дороге (darrow, warrow) — в местности уровня, движок грузит запись на старте
    if (GAME / ta).exists():
        e = export_file(ta)
        if e.draws: entries.append((ta, e.pack())); print(f'  {ta}: стрелки {", ".join(d["name"] for d in e.draws)}, текстур {len(e.tex)}')
    for p in load_scripts(a.level):
        if not (GAME / p).exists():
            print(f'  нет на диске: {p}'); continue
        if not (p.startswith('art/missions/') or p.startswith('art/frontend/dynaload/images/msnicons/') or p in PICK): continue
        e = export_file(p, only=PICK.get(p))
        if not e.draws and not e.imgs: continue
        blob = e.pack(); entries.append((p, blob))
        print(f'  {p}: объектов {len(e.draws)} ({", ".join(d["name"] for d in e.draws)}), значков {len(e.imgs)}, текстур {len(e.tex)}, {len(blob)} Б')
        for s in e.skipped: print(f'      не перенесено: {s}')
    out = bytearray(32); offTable = 32; out += bytes(96 * len(entries))
    for i, (p, blob) in enumerate(entries):
        while len(out) % 16: out.append(0)
        o = len(out); out += blob
        struct.pack_into('<80sII8x', out, offTable + 96 * i, p.encode()[:79], o, len(blob))
    struct.pack_into('<4sIII', out, 0, b'MSA2', len(entries), offTable, len(out))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_bytes(out)
    print(f'{a.out}: {len(entries)} файлов, {len(out)} Б')


if __name__ == '__main__':
    main()
