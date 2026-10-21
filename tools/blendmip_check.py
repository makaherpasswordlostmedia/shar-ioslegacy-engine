"""Гейт: мипы «вырезок» (альфа почти только 0/255 — лестницы, решётки, перила, кресты, крона) в level.shr.

Жалоба Роба 28.09: у лестницы пожарной машины (трамплин у Kwik-E-Mart) «пропадают текстуры». Причина: texq.keep_coverage
(Ф2, SHR_SMALL_MIPS=1) масштабирует альфу уменьшенных уровней, чтобы доля пикселей над порогом альфа-теста (0x40)
была как у уровня 0. Для материала с одним альфа-тестом это верно (дерево вдали не тает), но лестница рисуется
ПОЛУПРОЗРАЧНОЙ (флаг 2: альфа-тест + смешивание), и там альфа — это непрозрачность: уровень 1 шёл с альфой x0.5
(сквозь лестницу видно красный пол кузова), мелкие уровни — с альфой <= 0x40, их режет альфа-тест: лестница
исчезает вдали и под углом (на PSP уровень выбирается по наклону текстуры на экране, docs/psp_tricks.md).
Правило (tools/texq.py load_tex blend=True): полупрозрачному материалу — мипы без масштаба покрытия (отдельная копия,
если та же картинка есть и у материала с одним альфа-тестом); материалу с одним альфа-тестом — масштаб остаётся.

Проверки по всем текстурам level.shr и всем, кто их рисует (город, машина, небо, пропы PRP1, стейтпропы и билборды SPR1):
  [1] вырезка, которую рисуют полупрозрачной: средняя альфа каждого уровня (от 2x2) = уровню 0 в пределах 0.85..1.2,
      и уровень не теряет непрозрачное целиком (есть альфа > 0x40, если она есть у уровня 0);
  [2] вырезка только с альфа-тестом (без смешивания): покрытие (> 0x40) уровней от 8x8 = уровню 0 +-0.15 —
      масштаб покрытия не выключен заодно (иначе листва и заборы вдали тают).
python tools/blendmip_check.py [build/level.shr]  -> строки нарушений, итог; код 0 PASS, 1 FAIL"""
import sys, struct
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REC = np.dtype([('bb', '<f4', 6), ('tex', '<i4'), ('flags', '<u4'), ('nv', '<u4'), ('ni', '<u4'), ('owner', '<u4'),
                ('o', '<f4', 3), ('sc', '<f4'), ('off', '<u4'), ('nf', '<u4'), ('cell', '<u4'), ('pad', '<u4', 2)])
ALPHA_REF = 64


def textures(b):
    """-> [(w, h, pal (256,4), [RGBA уровня 0..])] (формат texq/psp_export: заголовок 16 Б, палитра 1 КБ, уровни CLUT8)"""
    ntex, = struct.unpack_from('<I', b, 4); hw, hh = struct.unpack_from('<II', b, 68)
    p = 104 + hw * hh * 8; p = (p + 15) & ~15; p += hw * hh * 4; p = (p + 15) & ~15
    out = []
    for _ in range(ntex):
        w, h, nl = struct.unpack_from('<HHH', b, p); pre = b[p + 7] == 1; t4 = b[p + 6] == 4   # T4 — правка 129
        pal = np.frombuffer(b, np.uint8, 1024, p + 16).reshape(256, 4); q = p + 16 + 1024; lw, lh = w, h; lv = []
        for _ in range(nl):
            rw = max(16, (lw + 1) // 2) if t4 else (16 if pre and lw < 16 else lw); rh = (lh + 7) & ~7 if pre else lh
            a = np.frombuffer(b, np.uint8, rw * rh, q)
            a = a.reshape(rh // 8, rw // 16, 8, 16).transpose(0, 2, 1, 3).reshape(rh, rw) if pre else a.reshape(rh, rw)
            if t4: a = np.stack([a & 15, a >> 4], -1).reshape(rh, 2 * rw)
            lv.append(pal[a[:lh, :lw]]); q += rw * rh; q = (q + 15) & ~15; lw >>= 1; lh = lh >> 1 if lh > 1 else 1
        out.append((w, h, pal, lv)); p = q
    return out


def users(b):
    """tex -> {'blend': [кто], 'alpha': [кто]}: кто рисует текстуру со смешиванием / только альфа-тестом"""
    u = {}
    def add(t, blend, alpha, who):
        if t < 0: return
        d = u.setdefault(int(t), {'blend': set(), 'alpha': set()})
        if blend: d['blend'].add(who)
        elif alpha: d['alpha'].add(who)
    npc, = struct.unpack_from('<I', b, 8); toff, = struct.unpack_from('<I', b, 76)
    for r in np.frombuffer(b, REC, npc, toff):
        add(r['tex'], r['flags'] & 2, r['flags'] & 1, ('город', 'машина', 'небо')[min(int(r['owner']), 2)])
    o, = struct.unpack_from('<I', b, 96)
    if o and b[o:o + 4] in (b'PRP1', b'PRP2'):
        npiece, ntype, ninst, vb, ib = struct.unpack_from('<5I', b, o + 4)
        p = o + (64 if b[o:o + 4] == b'PRP2' else 32) + vb + ib
        for i in range(npiece):
            t, fl = struct.unpack_from('<2i', b, p + 40 * i + 16); add(t, fl & 2, fl & 1, 'проп')
        if b[o:o + 4] == b'PRP2':
            s = o + struct.unpack_from('<I', b, o + 32)[0]
            assert b[s:s + 4] == b'SPR1', 'нет SPR1'
            ntp, nin, npc2, nj, nk, nvis, nst, nev, ncall, ncol, nbill, vb2, ib2 = struct.unpack_from('<13I', b, s + 4)
            q = s + 64
            def adv(q, n): q += n; return q + (-(q - s) % 16)
            q = adv(adv(q, vb2), ib2)
            for i in range(npc2):
                t, fl = struct.unpack_from('<2i', b, q + 40 * i + 16); add(t, fl & 2, fl & 1, 'стейтпроп')
            for n in (40 * npc2, 84 * ntp, 52 * nj, 28 * nk, 4 * nvis, 80 * nst, 4 * nev, 8 * ncall, 64 * ncol): q = adv(q, n)
            for i in range(nbill):   # билборды движок рисует всегда со смешиванием (viewer/main.c)
                t, = struct.unpack_from('<i', b, q + 40 * i + 4); add(t, 1, 0, 'билборд')
    return u


def is_cutout(a0):   # то же условие, что tools/texq.py is_cutout / keep_coverage
    mid = ((a0 > 8) & (a0 < 247)).mean()
    return not (mid > .02 or a0.min() >= 128 or a0.max() < 128)


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'build' / 'level.shr'
    b = path.read_bytes(); assert b[:4] == b'SHR7', 'не SHR7'
    T = textures(b); U = users(b)
    bad1, bad2, n1, n2 = [], [], 0, 0
    for ti, (w, h, pal, lv) in enumerate(T):
        if len(lv) < 2 or ti not in U: continue
        a0 = lv[0][..., 3].astype(float)
        if not is_cutout(a0): continue
        if U[ti]['blend']:
            n1 += 1; m0 = a0.mean(); why = []
            for l in range(1, len(lv)):
                a = lv[l][..., 3].astype(float)
                if a.size < 4: continue
                r = a.mean() / max(m0, 1e-9)
                if not .85 <= r <= 1.2: why.append(f'ур.{l} непрозрачность x{r:.2f}')
                elif (a0 > ALPHA_REF).any() and not (a > ALPHA_REF).any(): why.append(f'ур.{l} пропадает под альфа-тестом')
            if why: bad1.append(f'  [1] tex {ti} {w}x{h} (полупрозрачная у: {", ".join(sorted(U[ti]["blend"]))}): ' + '; '.join(why[:3]))
        elif U[ti]['alpha']:
            n2 += 1; c0 = (a0 > ALPHA_REF).mean(); why = []
            for l in range(1, len(lv)):
                a = lv[l][..., 3]
                if a.size < 64: continue   # от 8x8: мельче доля квантуется по 1/16 и упирается в пределы поиска keep_coverage
                c = (a > ALPHA_REF).mean()
                if abs(c - c0) > .15: why.append(f'ур.{l} покрытие {c:.2f} против {c0:.2f}')
            if why: bad2.append(f'  [2] tex {ti} {w}x{h} (альфа-тест у: {", ".join(sorted(U[ti]["alpha"]))}): ' + '; '.join(why[:3]))
    for s in bad1 + bad2: print(s)
    ok = not bad1 and not bad2
    print(f'blendmip_check {path.name}: вырезок со смешиванием {n1}, нарушений {len(bad1)}; вырезок с одним альфа-тестом {n2}, '
          f'нарушений {len(bad2)} -> {"PASS" if ok else "FAIL"}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
