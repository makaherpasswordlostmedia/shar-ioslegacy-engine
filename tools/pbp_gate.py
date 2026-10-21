#!/usr/bin/env python3
"""Гейт картинок меню PSP (XMB) и их упаковки в EBOOT.PBP (пакет «иконка игры», правка Роба 28.09 вечер).
  python tools/pbp_gate.py [--eboot viewer/build/EBOOT.PBP] [--icon build/assets/icon0.png] [--pic1 build/assets/pic1.png]
                           [--icon1 build/assets/icon1.pmf]
Проверки (код выхода 0 = OK, иначе первая строка FAIL — причина):
  ICON0 — настоящий PNG ровно 144×80 (стандарт PSP); непрозрачен целиком (нет альфы < 255 — через прозрачность XMB
          показывает свой серый фон: «серые поля»); содержимое во всю плитку, как у Tony Hawk: знак по ширине >= 85%
          плитки, поля по бокам равны (±1 px) и не больше 8 px;
  ICON0 — правка Роба 30: начало «v.0.1» и левая грань «PSP» вровень с левым краем плашки HIT&RUN (±1 px плитки);
  PIC1  — PNG ровно 480×272 (если файл есть: фон XMB необязателен); правка Роба 30: окно на обложку Роба
          (build/assets/pic1-source-rob.png, если есть) сдвинуто вправо на PIC1_SHIFT_MIN..MAX px экрана от прежнего
          (x0 = 1 px обложки при 2,03 px обложки на px экрана) — «капельку»;
  EBOOT — заголовок PBP, 8 разделов по порядку; PARAM.SFO с TITLE; раздел ICON0.PNG побайтно равен --icon, PIC1.PNG — --pic1;
  ICON1 — правка Роба 110: если есть --icon1 (tools/icon1.py), раздел ICON1.PMF побайтно равен ему; непустой раздел ICON1
          обязан пройти гейт разбора tools/icon1.py (заголовок PSMF, паки, таблицы GOP, PTS, SPS Main@2.1, 144×80, ffmpeg).
Отрицательный контроль (tools/boot_gate.sh): иконка 143×80, иконка с прозрачными углами, EBOOT со старой иконкой,
иконка без выравнивания надписей (tools/icon0.py --align none), фон без сдвига (tools/pic1.py --shift 0), EBOOT без ICON1
при build/assets/icon1.pmf, EBOOT с испорченным ICON1 (магия PSMF) — FAIL."""
import argparse, struct, sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument('--eboot', default=str(ROOT / 'viewer/build/EBOOT.PBP'))
ap.add_argument('--icon', default=str(ROOT / 'build/assets/icon0.png'))
ap.add_argument('--pic1', default=str(ROOT / 'build/assets/pic1.png'))
ap.add_argument('--cover', default=str(ROOT / 'build/assets/pic1-source-rob.png'))
ap.add_argument('--icon1', default=str(ROOT / 'build/assets/icon1.pmf'))
ap.add_argument('--snd0', default=str(ROOT / 'build/assets/snd0.at3'))
ap.add_argument('--need-snd0', action='store_true', help='правка 130: без SND0 — FAIL (когда кодировщик собран)')
a = ap.parse_args()
TITLE = 'The Simpsons Hit & Run'   # правка 146: подпись игры в XMB «как родное» (viewer/CMakeLists.txt, PARAM.SFO TITLE)
NAMES = ['PARAM.SFO', 'ICON0.PNG', 'ICON1.PMF', 'PIC0.PNG', 'PIC1.PNG', 'SND0.AT3', 'DATA.PSP', 'DATA.PSAR']
fails, lines = [], []


def png_size(b):
    if b[:8] != b'\x89PNG\r\n\x1a\n' or b[12:16] != b'IHDR':
        return None
    return struct.unpack('>II', b[16:24])


# ICON0
ib = Path(a.icon).read_bytes()
sz = png_size(ib)
lines.append(f'ICON0 {a.icon}: PNG {sz[0]}x{sz[1]}' if sz else f'ICON0 {a.icon}: не PNG')
if sz != (144, 80):
    fails.append(f'ICON0 не 144x80 ({sz})')
else:
    im = Image.open(a.icon); rgba = np.asarray(im.convert('RGBA')).astype(int)
    tr = int((rgba[..., 3] < 255).sum())
    lines.append(f'  режим {im.mode}, прозрачных пикселей {tr}')
    if tr:
        fails.append(f'ICON0: {tr} прозрачных пикселей — XMB покажет сквозь них серый фон')
    bgc = np.median(np.concatenate([rgba[0, :, :3], rgba[-1, :, :3], rgba[:, 0, :3], rgba[:, -1, :3]]), axis=0)   # фон плитки по краю
    ink = np.abs(rgba[..., :3] - bgc).max(axis=2) > 40
    xs = np.where(ink.any(axis=0))[0]; ys = np.where(ink.any(axis=1))[0]
    if not len(xs):
        fails.append('ICON0: плитка пустая')
    else:
        l, r, t, b = xs.min(), 143 - xs.max(), ys.min(), 79 - ys.max(); w = xs.max() - xs.min() + 1
        lines.append(f'  содержимое {w}x{ys.max() - ys.min() + 1} ({w / 144:.0%} ширины), поля: слева {l}, справа {r}, сверху {t}, снизу {b}')
        if w < .85 * 144: fails.append(f'ICON0: знак занимает {w / 144:.0%} ширины (< 85%)')
        if abs(int(l) - int(r)) > 1: fails.append(f'ICON0: поля по бокам не равны ({l} и {r})')
        if max(l, r) > 8: fails.append(f'ICON0: поле по бокам {max(l, r)} px (> 8)')
        # правка Роба 30: «v.0.1» и «PSP» от левого края плашки HIT&RUN
        c = rgba[..., :3]; g = (c[..., 1] > c[..., 0] + 30) & (c[..., 1] > c[..., 2] + 10)
        gy, gx = np.where(g)
        if not len(gx):
            fails.append('ICON0: нет зелёной плашки HIT&RUN')
        else:
            px0, py0, py1 = gx.min(), gy.min(), gy.max()
            gray = ink & (np.abs(c[..., 0] - c[..., 1]) < 24) & (np.abs(c[..., 1] - c[..., 2]) < 24)

            def left(y0, y1):   # самая правая группа серой краски в полосе (зазор ≥ 3 px), её левый край
                cols = np.where(gray[y0:y1, px0 - 2:].any(0))[0]
                if not len(cols): return None
                st = cols[-1]
                for cc in cols[::-1]:
                    if st - cc > 3: break
                    st = cc
                return int(st + px0 - 2)
            # правка Роба 146 (01.10): «убрать надпись версии и PSP, только логотип на чёрном» — над плашкой HIT&RUN
            # и под ней (правее её левого края) нет светлой серой краски (там стояли «v.0.1» и «PSP»; знак — цветной)
            lit = gray & (c.max(axis=2) > 90)
            n_ver, n_psp = int(lit[:max(1, py0 - 1), px0:].sum()), int(lit[py1 + 2:, px0:].sum())
            lines.append(f'  правка 146: светлой серой краски над плашкой {n_ver} px, под плашкой {n_psp} px (нужно 0 — без «v.0.1» и «PSP»)')
            if n_ver or n_psp:
                fails.append(f'ICON0: остались надписи «v.0.1»/«PSP» ({n_ver} и {n_psp} px серой краски) — правка Роба 146')
    # правка 146: ICON0 — ровно логотип из карточки Роба (tools/icon0.py render(), --text none), сверка с источником
    src0 = ROOT / 'build/assets/icon0-source-rob.png'
    if src0.exists():
        sys.path.insert(0, str(ROOT / 'tools')); import icon0
        ref0 = np.asarray(icon0.render(src0, log=lambda *_: None), np.float32)
        e0 = float(np.abs(np.asarray(Image.open(a.icon).convert('RGB'), np.float32) - ref0).mean())
        lines.append(f'  сверка с карточкой Роба (только логотип): средняя разница {e0:.2f} (нужно ≤ 0,5)')
        if e0 > 0.5: fails.append(f'ICON0 не равен логотипу из карточки Роба {src0.name} без надписей (разница {e0:.1f}) — правка 146')
# PIC1
pb = Path(a.pic1).read_bytes() if Path(a.pic1).exists() else None
if pb is not None:
    ps = png_size(pb); lines.append(f'PIC1 {a.pic1}: PNG {ps}')
    if ps != (480, 272): fails.append(f'PIC1 не 480x272 ({ps})')
    elif Path(a.cover).exists():   # правка Роба 132: фон перерисовывается по pic1.json из обложки и сверяется с PNG
        import json; sys.path.insert(0, str(ROOT / 'tools')); import pic1 as P1
        jp = Path(a.pic1).with_suffix('.json')
        if not jp.exists():
            fails.append(f'PIC1: нет {jp.name} (параметры фона tools/pic1.py)')
        else:
            meta = json.loads(jp.read_text()); bx0 = meta['box']
            ref1 = np.asarray(P1.render(a.cover, meta['zoom'], bx0[0], bx0[1], meta['dim'], meta.get('fill', 'dark'), meta.get('feather', P1.FEATHER)), np.float32)
            e1 = float(np.abs(np.asarray(Image.open(a.pic1).convert('RGB'), np.float32) - ref1).mean())
            mg = P1.marge_on_screen(meta)
            lines.append(f'  перерисовка по {jp.name} из обложки: разница {e1:.2f} (≤ 2); масштаб {meta["zoom"]:g} (правка 204: окно обрезки Роба); '
                         f'Мардж на экране x {mg[0]:.0f}..{mg[2]:.0f}, y {mg[1]:.0f}..{mg[3]:.0f} (x ≥ {P1.ICONS_X1}, целиком в кадре)')
            if e1 > 2: fails.append(f'PIC1 не совпадает с обложкой Роба по {jp.name} (разница {e1:.1f})')
            elif meta.get('rob_crop') or True:   # правка Роба 204 (03.10 12:1x): «вот я тебе сам обрезал, подставь вот так» — PIC1 = его обрезка
                rc = ROOT / P1.ROB_CROP
                if not rc.exists(): fails.append(f'PIC1: нет обрезки Роба {P1.ROB_CROP} (правка 204)')
                else:
                    from PIL import ImageEnhance
                    rob = Image.open(rc).convert('RGBA'); bg = Image.new('RGBA', rob.size, P1.FILL_DARK + (255,)); bg.alpha_composite(rob)
                    kk = rob.width / 480; hh = 272 * kk; top = (rob.height - hh) / 2
                    ref = ImageEnhance.Brightness(bg.convert('RGB').resize((480, 272), Image.LANCZOS, box=(0, top, rob.width, top + hh))).enhance(meta['dim'])
                    e2 = float(np.abs(np.asarray(Image.open(a.pic1).convert('RGB'), np.float32) - np.asarray(ref, np.float32)).mean())
                    lines.append(f'  обрезка Роба {rc.name}: разница с PIC1 {e2:.2f} (≤ 4, правка 204)')
                    if e2 > 4: fails.append(f'PIC1 не совпадает с обрезкой Роба {rc.name} (разница {e2:.1f}) — правка 204 «подставь вот так»')
                    elif bx0[2] < P1.HAND_X + 2: fails.append(f'PIC1: рука Гомера обрезана (окно до {bx0[2]:.0f}), правка 204')
            if mg[1] < 0 or mg[3] > 272 or mg[2] > 480: fails.append(f'PIC1: Мардж не целиком в кадре ({[round(v) for v in mg]}), правка Роба 132')
    else:
        lines.append(f'  обложки {a.cover} нет — сдвиг фона не проверен')
# EBOOT
d = Path(a.eboot).read_bytes()
if d[:4] != b'\0PBP':
    fails.append('EBOOT: нет заголовка PBP')
else:
    off = list(struct.unpack_from('<8I', d, 8)) + [len(d)]
    if off != sorted(off) or off[0] != 40: fails.append(f'EBOOT: разделы не по порядку {off}')
    parts = {n: d[off[i]:off[i + 1]] for i, n in enumerate(NAMES)}
    lines.append('EBOOT ' + a.eboot + ': ' + ', '.join(f'{n} {len(p)}' for n, p in parts.items() if n != 'DATA.PSAR'))
    sfo = parts['PARAM.SFO']
    if sfo[:4] != b'\0PSF':
        fails.append('EBOOT: PARAM.SFO испорчен')
    else:
        kt, dt, n = struct.unpack_from('<III', sfo, 8); kv = {}
        for i in range(n):
            ko, fmt, ln, mx, do = struct.unpack_from('<HHIII', sfo, 20 + 16 * i)
            k = sfo[kt + ko:sfo.index(b'\0', kt + ko)].decode()
            v = sfo[dt + do:dt + do + ln]
            kv[k] = v.rstrip(b'\0').decode('utf-8', 'replace') if fmt != 0x0404 else struct.unpack('<I', v[:4])[0]
        lines.append(f'  PARAM.SFO TITLE="{kv.get("TITLE")}" CATEGORY={kv.get("CATEGORY")}')
        if not kv.get('TITLE'): fails.append('EBOOT: в PARAM.SFO нет TITLE')
        elif kv.get('TITLE') != TITLE: fails.append(f'EBOOT: подпись в XMB «{kv.get("TITLE")}», нужно «{TITLE}» (правка 146, как родное)')
    if parts['ICON0.PNG'] != ib:
        fails.append(f'EBOOT: ICON0.PNG в EBOOT ({len(parts["ICON0.PNG"])} Б) не равен {a.icon} ({len(ib)} Б) — пересобрать EBOOT')
    else:
        lines.append('  ICON0.PNG в EBOOT = файлу побайтно')
    if pb is not None:
        if parts['PIC1.PNG'] != pb: fails.append(f'EBOOT: PIC1.PNG в EBOOT не равен {a.pic1}')
        else: lines.append('  PIC1.PNG в EBOOT = файлу побайтно')
    # правка Роба 110: живой значок ICON1.PMF (tools/icon1.py) — побайтно файлу и гейт разбора PSMF
    i1 = Path(a.icon1).read_bytes() if Path(a.icon1).exists() else None; sec = parts['ICON1.PMF']
    if i1 is not None and sec != i1:
        fails.append(f'EBOOT: ICON1.PMF в EBOOT ({len(sec)} Б) не равен {a.icon1} ({len(i1)} Б) — пересобрать EBOOT')
    if sec:
        sys.path.insert(0, str(ROOT / 'tools')); import icon1, tempfile
        with tempfile.NamedTemporaryFile(suffix='.pmf', delete=False) as f: f.write(sec)
        f1 = icon1.verify(f.name, quiet=True); Path(f.name).unlink()
        if f1: fails.append('EBOOT: ICON1.PMF не проходит гейт tools/icon1.py: ' + f1[0])
        else: lines.append(f'  ICON1.PMF в EBOOT {len(sec)} Б' + (' = файлу побайтно' if sec == i1 else '') + ', гейт PSMF (tools/icon1.py) OK')
    else:
        lines.append('  ICON1.PMF нет (build/assets/icon1.pmf не собран — tools/icon1.py): значок в XMB без анимации')
    # правка Роба 130: музыка XMB SND0.AT3 (tools/snd0.py) — раздел побайтно файлу и гейт формата (RIFF WAVE ATRAC3/AT3+)
    s0 = Path(a.snd0).read_bytes() if Path(a.snd0).exists() else None; ssec = parts['SND0.AT3']
    if s0 is None and a.need_snd0:
        fails.append(f'SND0: нет {a.snd0} — музыка XMB не собрана (tools/snd0.py, нужен кодировщик ATRAC3 atracdenc), правка 130')
    if s0 is not None and ssec != s0:
        fails.append(f'EBOOT: SND0.AT3 в EBOOT ({len(ssec)} Б) не равен {a.snd0} ({len(s0)} Б) — пересобрать EBOOT')
    if ssec:
        sys.path.insert(0, str(ROOT / 'tools')); import snd0
        f0, info0 = snd0.verify_bytes(ssec)
        if f0: fails.append('EBOOT: SND0.AT3 не проходит гейт tools/snd0.py: ' + f0[0])
        else: lines.append(f'  SND0.AT3 в EBOOT {len(ssec)} Б' + (' = файлу побайтно' if ssec == s0 else '') + f', {info0}')
    else:
        lines.append('  SND0.AT3 нет: в XMB без музыки' + (' (build/assets/snd0.at3 не собран — tools/snd0.py)' if s0 is None else ''))
if fails:
    print('FAIL: ' + fails[0]); print('\n'.join(lines)); [print('  - ' + f) for f in fails[1:]]; sys.exit(1)
print('OK: ICON0 144x80 непрозрачна во всю плитку, PIC1 480x272, обе внутри EBOOT побайтно; ICON1 — строка ниже'); print('\n'.join(lines))
