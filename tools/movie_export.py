"""Ролики PS2 (RMV, Radical) -> SMV1 для PSP (viewer/movie.c): кадры JPEG 480x272 + звук PCM s16 44,1 кГц стерео.
Опора: hit-and-run-web/tools/movies.py (MIT) — заголовок rmvps212, видео IPU, звук RSD (PS-ADPCM) по языкам; оба
разжимает ffmpeg (/opt/homebrew/bin/ffmpeg). Ресурсы игры не коммитить: результат только в build/movies/.

  python tools/movie_export.py --clip radlogo --out build/movies/radlogo.smv     один ролик
  python tools/movie_export.py --all [--outdir build/movies]                     все ролики интро (INTRO)
  python tools/movie_export.py --verify build/movies/radlogo.smv [--rmv RMV]     гейт: кадры = заголовку RMV, звук = видео ±1 кадр
  python tools/movie_export.py --check-rmv RMV                                   разбор RMV без записи (испорченный -> код 1)

Картинка: PAL 640x512 с SAR 16:15 = кадр 4:3 (как в movies.py: setsar 4h/3w) -> 4:3 без растяжки на всю высоту экрана
(362x272 по центру, x = 59). Правка Роба 49 (29.09, пересмотр 32): «рамка-телевизор на роликах слишком растянута; у роликов
4:3 — красивый фон по бокам, а не растянутая рамка». Правило порта (в данных оригинала широкого экрана нет): поля по бокам —
фон из той же картинки ролика: кадр, увеличенный до ширины 480 (середина по высоте), сильно размытый, приглушённый и чуть
обесцвеченный, у краёв картинки — мягкая тень; фон идёт вместе с роликом кадр в кадр. Рамки поверх нет. Один ресемплинг
картинки с исходного кадра — без потери чёткости. SMV_LAYOUT=tv — раскладка правки 32 (окно рамки-телевизора, картинка
«капельку» шире; рамку рисовал движок), SMV_LAYOUT=bars — 362x272 с чёрными полями: отрицательные контроли гейтов.
JPEG baseline 4:2:0, стандартные таблицы (аппаратный sceJpeg PSP).
Звук: дорожка языка 0 (на диске PAL все 4 дорожки побайтно одинаковы), 48 кГц -> 44,1 кГц (частота каналов sceAudio);
тихий хвост за концом видео (пик ниже -60 дБFS: у vuglogo +0,18 с, у gracie +0,56 с нулей) отрезается; после этого
звук обязан совпасть с видео ±1 кадр, иначе ошибка. Длина выравнивается ровно в кадры*1764 (44100/25).

SMV1 (little-endian): заголовок 64 Б -> индекс (кадры+1) u32 смещений кусков (последнее = размер файла) -> куски.
  0 'SMV1' | 4 u16 w, u16 h | 8 u16 fps, u16 1 | 12 u32 кадров | 16 u32 частота | 20 u16 каналов, u16 сэмплов на кадр
  24 u32 сэмплов всего | 28 u32 наибольший кусок | 32 u32 смещение индекса | 36 u32 смещение данных | 40 u16 x, u16 w картинки
  44 u32 кадров в RMV | 48 u32 флаги (1 = звук) | 52 u32 размер файла | 56 u32 crc32 индекса | 60 u32 crc32 байт 0..59
  кусок: u32 байт JPEG, u32 сэмплов PCM, JPEG (добивка до 4), PCM s16 стерео
"""
import argparse, io, os, struct, subprocess, sys, tempfile, zlib
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'hit-and-run-web/source/game/movies'
FF = '/opt/homebrew/bin/ffmpeg'
INTRO = ['vuglogo', 'foxlogo', 'gracie', 'radlogo', 'intro']   # порядок запуска оригинала: SLES_518.97 (см. viewer/movie.h)
W, H, FPS, RATE, SPF = 480, 272, 25, 44100, 44100 // 25
LAYOUT = os.environ.get('SMV_LAYOUT', 'menu')   # menu (правка 89) | ambient (правка 49) | tv (правка 32) | bars (4:3 с чёрными полями)
# Правка Роба 153 (01.10): «демо — под видео какой-то контур, потом размытое видео; убери контур». Ролик простоя идёт без
# рамки-телевизора (viewer/main.c demoMovie), поэтому картинка — 4:3 на всю высоту с фоном из того же кадра по бокам
# (ambient, правка 49), а не окно рамки меню. Контур — чёрная кайма самого demo.rmv по краям кадра PAL (замер: слева
# 5–6 px, справа 8–9, сверху 1 строка, снизу 2 из 640x512) — у интро и fmv её нет. Срезается до масштаба, поровну с каждой
# стороны (x, y px исходника; 9/640 и 7/512 — пропорция 4:3 та же). SMV_LAYOUT в окружении — для всех роликов (контроли)
CLIP_LAYOUT = {'demo': 'ambient'}
CLIP_CROP = {'demo': (9, 7)}
CROP = (0, 0)
MENU_UNDER = 3   # px: картинка заходит под рамку меню со всех сторон (стык в окне не виден)
AMB_DOWN = 4          # фон считается в 1/4 размера (120x68): размытие и приглушение, потом бикубика до 480x272 — гладко и дёшево
AMB_BLUR = 3.0        # радиус размытия фона в пикселях уменьшенного кадра (~12 px экрана)
AMB_DIM = 1.0         # яркость фона относительно картинки (правка Роба 67: не приглушать — фон сливается с краями)
AMB_SAT = 1.0         # насыщенность фона (правка 67: как у картинки)
AMB_EDGE, AMB_SHADOW = 10, 0.0    # тень у краёв картинки — нет (правка Роба 67: «зачем тень под видео»)
AMB_FEATHER = 8      # правка 67: края картинки плавно (px экрана) переходят в размытый фон того же кадра — стыка не видно
_PIC = None


def menu_opening():
    """окно рамки меню на 480x272 (x0, y0, x1, y1): та же сборка, что TVFrame меню и рамка роликов (tools/load_export.py tvmovie)"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import load_export as LX, ui_export as U
    bm = U.widescreen_tvframe(U.all_images()['tvframe.png'], U.DST_W, U.DST_H, U.S)
    al = np.asarray(bm)[..., 3]
    x0, x1 = LX._run(al[U.DST_H // 2] < 250, U.DST_W // 2); y0, y1 = LX._run(al[:, U.DST_W // 2] < 250, U.DST_H // 2)
    return x0, y0, x1, y1


def picture():
    """(x, y, w, h) картинки ролика в кадре 480x272. menu (правка Роба 89, 30.09): рамка меню поверх ролика — картинка 4:3
    целиком в окне рамки (по высоте окна + MENU_UNDER под рамку), без растяжки; вокруг — размытый тот же кадр.
    ambient: 4:3 на всю высоту (правка 49); tv: окно прежней рамки роликов (правка 32)."""
    global _PIC
    if LAYOUT == 'menu':
        if _PIC is None:
            x0, y0, x1, y1 = menu_opening(); h = (y1 - y0) + 2 * MENU_UNDER; h -= h % 2
            w = int(round(h * 4 / 3)); w -= w % 2; cx = (x0 + x1) // 2
            _PIC = (cx - w // 2, (y0 + y1) // 2 - h // 2, w, h)
        return _PIC
    if LAYOUT != 'tv':
        return (59, 0, 362, H)
    if _PIC is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import load_export as LX
        (x, y, w, h), st = LX.tv_picture()
        if not 1.0 <= st <= LX.TV_STRETCH_MAX: raise RmvError(f'окно рамки: растяжка картинки {st:.3f} вне 1..{LX.TV_STRETCH_MAX}')
        _PIC = (x, y, w - w % 2, h - h % 2)
    return _PIC


IMG_W = 362; IMG_X = (W - IMG_W) // 2                           # прежняя раскладка (для справки): 4:3 при высоте 272 с полями
QUALITY = 85
SILENT_DB = -60.0


class RmvError(ValueError): pass


def rmv_parse(data, name='rmv'):
    """Заголовок и дорожки RMV как в movies.py; любое несоответствие -> RmvError."""
    if len(data) < 128 or data[:8] != b'rmvps212': raise RmvError(f'{name}: не RMV (нет rmvps212)')
    w, h, frames, size, start, langs = struct.unpack_from('<HHIIII', data, 8)
    if size != len(data): raise RmvError(f'{name}: размер в заголовке {size} != файлу {len(data)}')
    if not 0 < langs <= 16 or not 0 < frames < 1 << 20 or (w, h) != (640, 512): raise RmvError(f'{name}: заголовок испорчен')
    offs = struct.unpack_from(f'<{langs}I', data, 28); sizes = struct.unpack_from(f'<{langs}I', data, 96)
    if not 128 <= start < min(offs) or offs[0] + sizes[0] > len(data) or not sizes[0]: raise RmvError(f'{name}: дорожки испорчены')
    video = data[start:min(offs)]; end = video.rfind(b'\0\0\1\xb0')
    if end < 0: raise RmvError(f'{name}: нет кадров IPU')
    video = video[:end + 4]; n = video.count(b'\0\0\1\xb0')
    if n != frames: raise RmvError(f'{name}: кадров IPU {n} != заголовку {frames}')
    return dict(w=w, h=h, frames=frames, video=video, audio=data[offs[0]:offs[0] + sizes[0]])


def run(cmd, inp=None):
    r = subprocess.run(cmd, input=inp, capture_output=True)
    if r.returncode: raise RmvError(f'ffmpeg: {r.stderr.decode(errors="replace")[-300:]}')
    return r.stdout


def use_clip(clip):
    """раскладка и срез каймы ролика (правка 153: demo — ambient без каймы); SMV_LAYOUT в окружении главнее"""
    global LAYOUT, CROP, _PIC
    lay = os.environ.get('SMV_LAYOUT') or CLIP_LAYOUT.get(clip, 'menu')
    if lay != LAYOUT: LAYOUT, _PIC = lay, None
    CROP = CLIP_CROP.get(clip, (0, 0))


def scale_vf(pw, ph):
    cx, cy = CROP
    return (f'crop=iw-{2 * cx}:ih-{2 * cy}:{cx}:{cy},' if cx or cy else '') + f'scale={pw}:{ph}:flags=lanczos+accurate_rnd+full_chroma_int'


def decode_video(rmv, tmp):
    """Все кадры RMV -> uint8 [n, h, w, 3] картинки picture() (4:3 с «капелькой» по ширине, lanczos)."""
    _, _, pw, ph = picture()
    ipu = Path(tmp) / 'v.ipu'
    ipu.write_bytes(b'ipum' + struct.pack('<IHHI', len(rmv['video']) + 16, rmv['w'], rmv['h'], rmv['frames']) + rmv['video'])
    raw = run([FF, '-v', 'error', '-i', str(ipu), '-fps_mode', 'passthrough', '-vf', scale_vf(pw, ph),
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    fr = np.frombuffer(raw, np.uint8)
    if fr.size % (pw * ph * 3): raise RmvError('ffmpeg: неполный кадр')
    return fr.reshape(-1, ph, pw, 3)


def reference_frame(clip, f):
    """Эталон для гейта в эмуляторе: кадр f ролика clip, разжатый ffmpeg из RMV, как на экране PSP (480x272, без JPEG)."""
    use_clip(clip)
    rmv = rmv_parse((SRC / f'{clip}.rmv').read_bytes(), clip)
    with tempfile.TemporaryDirectory(prefix='shar-movie-') as tmp:
        ipu = Path(tmp) / 'v.ipu'
        ipu.write_bytes(b'ipum' + struct.pack('<IHHI', len(rmv['video']) + 16, rmv['w'], rmv['h'], rmv['frames']) + rmv['video'])
        raw = run([FF, '-v', 'error', '-i', str(ipu), '-fps_mode', 'passthrough', '-vf',
                   f'select=eq(n\\,{int(f)}),' + scale_vf(picture()[2], picture()[3]),
                   '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    _, _, pw, ph = picture()
    if len(raw) != pw * ph * 3: raise RmvError(f'{clip}: нет кадра {f}')
    return frame_480(np.frombuffer(raw, np.uint8).reshape(ph, pw, 3))


def ambient(img):
    """Фон кадра 480x272 из картинки 4:3 (правка 49): картинка на ширину 480 (середина по высоте), размыта, приглушена,
    чуть обесцвечена; у краёв места картинки — мягкая тень."""
    w0, h0 = W // AMB_DOWN, W * 3 // 4 // AMB_DOWN; hc = H // AMB_DOWN
    small = Image.fromarray(img).resize((w0, h0), Image.BOX)
    y0 = (h0 - hc) // 2
    small = small.crop((0, y0, w0, y0 + hc)).filter(ImageFilter.GaussianBlur(AMB_BLUR))
    a = np.asarray(small.resize((W, H), Image.BICUBIC), np.float32)
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    a = (lum[..., None] + (a - lum[..., None]) * AMB_SAT) * AMB_DIM
    x, _, w, _ = picture(); cols = np.arange(W, dtype=np.float32)
    d = np.maximum(x - 1 - cols, cols - (x + w)); d[(cols >= x) & (cols < x + w)] = 0
    a *= (1 - AMB_SHADOW * np.clip(1 - d / AMB_EDGE, 0, 1) ** 2)[None, :, None]
    return np.clip(a + .5, 0, 255).astype(np.uint8)


def frame_480(img):   # картинка -> кадр 480x272: на своё место picture(), вокруг фон (правка 49) или чёрное
    x, y, w, h = picture(); out = ambient(img) if LAYOUT in ('ambient', 'menu') else np.zeros((H, W, 3), np.uint8)
    sy0, sx0 = max(0, -y), max(0, -x)
    bg = out.copy()
    out[max(0, y):min(H, y + h), max(0, x):min(W, x + w)] = img[sy0:sy0 + min(H, y + h) - max(0, y), sx0:sx0 + min(W, x + w) - max(0, x)]
    if LAYOUT in ('ambient', 'menu') and AMB_FEATHER > 0 and w < W:   # правка 67: мягкий стык картинки с фоном по бокам
        cols = np.arange(W, dtype=np.float32); din = np.minimum(cols - x, x + w - 1 - cols)
        al = np.clip((din + 1) / AMB_FEATHER, 0, 1)[None, :, None]
        out = (out.astype(np.float32) * al + bg.astype(np.float32) * (1 - al) + .5).astype(np.uint8)
    return out


def decode_audio(rmv, tmp):
    """Дорожка 0 -> int16 [n, 2] 44,1 кГц (ресемплер ffmpeg)."""
    rsd = Path(tmp) / 'a.rsd'; rsd.write_bytes(rmv['audio'])
    pcm = np.frombuffer(run([FF, '-v', 'error', '-i', str(rsd), '-f', 's16le', '-ac', '2', '-ar', str(RATE), '-']), '<i2')
    return pcm.reshape(-1, 2)


GAP_S, GAP_WIN_S = 0.2, 2.0   # цифровая тишина (ровно нули) не короче GAP_S в последних GAP_WIN_S видео


def digital_gap(pcm, want):
    """Начало последней полной цифровой тишины (все отсчёты 0, не короче GAP_S) в последних GAP_WIN_S до конца видео, или None"""
    lo = max(0, want - int(GAP_WIN_S * RATE)); z = np.abs(pcm[lo:want].astype(np.int32)).max(axis=1) == 0
    best, i, n = None, 0, len(z)
    while i < n:
        if z[i]:
            j = i
            while j < n and z[j]: j += 1
            if j - i >= int(GAP_S * RATE): best = lo + i
            i = j
        else: i += 1
    return best


def fit_audio(pcm, frames, name):
    """Тихий хвост за концом видео отрезать; звук = видео ±1 кадр, иначе ошибка; длина ровно frames*SPF.
    Громкий хвост за концом видео, отделённый от звука ролика полной цифровой тишиной (нули) у конца видео, — посторонний
    хвост дорожки (demo.rmv: после тишины за 0,12 с до конца видео начинается новый звук и идёт ещё 0,88 с): звук режется
    с начала этой тишины, до конца видео — тишина (правило порта, в данных нет; эталона PS2 нет)."""
    want = frames * SPF; raw = len(pcm)
    if raw > want + SPF:
        tail = np.abs(pcm[want:].astype(np.int32)).max(initial=0)
        db = 20 * np.log10(tail / 32768 + 1e-12)
        if db > SILENT_DB:
            gap = digital_gap(pcm, want)
            if gap is None: raise RmvError(f'{name}: звук длиннее видео на {(raw - want) / RATE:.2f} с и хвост не тихий ({db:.0f} дБFS)')
            pcm = np.concatenate([pcm[:gap], np.zeros((want - gap, 2), pcm.dtype)])
        pcm = pcm[:want]
    if abs(len(pcm) - want) > SPF: raise RmvError(f'{name}: звук {len(pcm) / RATE:.3f} с != видео {frames / FPS:.3f} с ±1 кадр')
    out = np.zeros((want, 2), np.int16); n = min(want, len(pcm)); out[:n] = pcm[:n]
    return out, raw


def jpeg(img):
    b = io.BytesIO(); Image.fromarray(frame_480(img)).save(b, 'JPEG', quality=QUALITY, subsampling=2, optimize=False, progressive=False)
    return b.getvalue()


def write_smv(path, jpgs, pcm, src_frames):
    n = len(jpgs); chunks = []
    for i, j in enumerate(jpgs):
        a = pcm[i * SPF:(i + 1) * SPF].tobytes()
        chunks.append(struct.pack('<II', len(j), SPF) + j + b'\0' * (-len(j) & 3) + a)
    idx_off = 64; data_off = idx_off + 4 * (n + 1); offs = [data_off]
    for c in chunks: offs.append(offs[-1] + len(c))
    index = struct.pack(f'<{n + 1}I', *offs)
    hdr = b'SMV1' + struct.pack('<HHHHIIHHIIIIHHIIII', W, H, FPS, 1, n, RATE, 2, SPF, n * SPF, max(map(len, chunks)),
                                idx_off, data_off, picture()[0], picture()[2], src_frames, 1, offs[-1], zlib.crc32(index))
    hdr += struct.pack('<I', zlib.crc32(hdr))
    assert len(hdr) == 64
    tmp = Path(str(path) + '.part'); tmp.write_bytes(hdr + index + b''.join(chunks)); tmp.replace(path)


def smv_read(path):
    """Разбор SMV1 с проверками (как в viewer/movie.c) -> (заголовок, список (jpeg, pcm))."""
    d = Path(path).read_bytes()
    if len(d) < 64 or d[:4] != b'SMV1': raise RmvError(f'{path}: не SMV1')
    f = struct.unpack_from('<HHHHIIHHIIIIHHIIII', d, 4); crc = struct.unpack_from('<I', d, 60)[0]
    if zlib.crc32(d[:60]) != crc: raise RmvError(f'{path}: crc заголовка')
    w, h, fps, den, n, rate, ch, spf, total, maxc, io_, do_, x, iw, srcn, flags, size, icrc = f
    if (w, h, fps, den, rate, ch, spf) != (W, H, FPS, 1, RATE, 2, SPF) or size != len(d) or total != n * spf: raise RmvError(f'{path}: поля заголовка')
    index = d[io_:io_ + 4 * (n + 1)]
    if zlib.crc32(index) != icrc or do_ != io_ + 4 * (n + 1): raise RmvError(f'{path}: индекс')
    offs = struct.unpack(f'<{n + 1}I', index); out = []
    if offs[0] != do_ or offs[-1] != size: raise RmvError(f'{path}: границы данных')
    for i in range(n):
        c = d[offs[i]:offs[i + 1]]; jl, pl = struct.unpack_from('<II', c)
        if len(c) > maxc or len(c) != 8 + jl + (-jl & 3) + pl * 4: raise RmvError(f'{path}: кусок {i}')
        j = c[8:8 + jl]
        if j[:2] != b'\xff\xd8' or j[-2:] != b'\xff\xd9': raise RmvError(f'{path}: кадр {i} не JPEG')
        out.append((j, np.frombuffer(c[8 + jl + (-jl & 3):], '<i2').reshape(-1, 2)))
    return dict(frames=n, src_frames=srcn, total=total, maxchunk=maxc, size=size, img_x=x, img_w=iw), out


def export(clip, out, rmv_path=None):
    use_clip(clip)
    rp = Path(rmv_path) if rmv_path else SRC / f'{clip}.rmv'
    rmv = rmv_parse(rp.read_bytes(), rp.name)
    with tempfile.TemporaryDirectory(prefix='shar-movie-') as tmp:
        frames = decode_video(rmv, tmp)
        if len(frames) != rmv['frames']: raise RmvError(f'{rp.name}: ffmpeg дал {len(frames)} кадров, в заголовке {rmv["frames"]}')
        pcm, raw = fit_audio(decode_audio(rmv, tmp), rmv['frames'], rp.name)
    jpgs = [jpeg(f) for f in frames]
    Path(out).parent.mkdir(parents=True, exist_ok=True); write_smv(out, jpgs, pcm, rmv['frames'])
    size = Path(out).stat().st_size; sec = rmv['frames'] / FPS
    print(f'{rp.stem}: {rmv["frames"]} кадров {sec:.2f} с, звук {raw / RATE:.3f} с -> {len(pcm) / RATE:.3f} с, '
          f'{size / 1e6:.2f} МБ, {size / sec / 1024:.0f} КБ/с, JPEG ср. {sum(map(len, jpgs)) / len(jpgs) / 1024:.1f} КБ, макс кусок {max(map(len, jpgs)) // 1024 + 8} КБ -> {out}')
    return size


def verify(path, rmv_path=None):
    """Гейт (а): кадров = заголовку RMV; звук = видео ±1 кадр (до выравнивания, тихий хвост отрезан); все JPEG 480x272."""
    hdr, ch = smv_read(path)
    clip = Path(path).stem; rp = Path(rmv_path) if rmv_path else SRC / f'{clip}.rmv'
    rmv = rmv_parse(rp.read_bytes(), rp.name); bad = []
    if hdr['frames'] != rmv['frames'] or len(ch) != rmv['frames']: bad.append(f'кадров {len(ch)} != RMV {rmv["frames"]}')
    with tempfile.TemporaryDirectory(prefix='shar-movie-') as tmp: pcm = decode_audio(rmv, tmp)
    try: fit_audio(pcm, rmv['frames'], rp.name)
    except RmvError as e: bad.append(str(e))
    got = sum(len(p) for _, p in ch)
    if abs(got - rmv['frames'] * SPF) > SPF: bad.append(f'звук в SMV {got / RATE:.3f} с != видео {rmv["frames"] / FPS:.3f} с')
    for i in (0, len(ch) // 2, len(ch) - 1):
        im = Image.open(io.BytesIO(ch[i][0]))
        if im.size != (W, H) or im.mode != 'RGB': bad.append(f'кадр {i}: {im.size} {im.mode}')
    line = f'{clip}: кадров {len(ch)}/{rmv["frames"]}, звук {got / RATE:.3f} с / видео {rmv["frames"] / FPS:.3f} с'
    print(('FAIL ' if bad else 'OK ') + line + ('; ' + '; '.join(bad) if bad else ''))
    return not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clip'); ap.add_argument('--out'); ap.add_argument('--rmv'); ap.add_argument('--all', action='store_true')
    ap.add_argument('--outdir', default=str(ROOT / 'build/movies')); ap.add_argument('--verify'); ap.add_argument('--check-rmv')
    a = ap.parse_args()
    try:
        if a.check_rmv:
            r = rmv_parse(Path(a.check_rmv).read_bytes(), Path(a.check_rmv).name); print(f'OK {a.check_rmv}: {r["frames"]} кадров'); return 0
        if a.verify: return 0 if verify(a.verify, a.rmv) else 1
        if a.all:
            tot = sum(export(c, Path(a.outdir) / f'{c}.smv') for c in INTRO); print(f'интро: {len(INTRO)} роликов, {tot / 1e6:.1f} МБ'); return 0
        if a.clip and a.out: export(a.clip, a.out, a.rmv); return 0
        ap.error('нужно --clip C --out F, --all, --verify F или --check-rmv F')
    except (RmvError, OSError) as e:
        print(f'ОШИБКА {e}', file=sys.stderr); return 1


if __name__ == '__main__':
    sys.exit(main())
