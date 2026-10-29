#!/usr/bin/env python3
"""Живой значок игры в меню PSP (XMB), ICON1.PMF 144×80 — правка Роба 110 (30.09 13:25): «как у Tony Hawk: в списке —
картинка-карточка (ICON0), при наведении — анимация из фрагментов демо и заставок игры, маленький размер».

Эталон — ICON1.PMF Tony Hawk's Underground 2 Remix (Europe) из образа Роба (~/_backups/shar-psp-interactions-2026-09-27/
video/tony-hawk-reference/, прочитан, в проект не копируется). Разбор эталона (30.09, агент xmb):
  заголовок PSMF 0x800 Б: 'PSMF0012' | 0x08 u32be 0x800 (начало потока) | 0x0C u32be байт потока | 0x50 u32be 0x3E (длина
  блока дальше) | 0x54 6 Б начало показа 90000 (1 с) | 0x5A 6 Б конец = 90000 + кадров*3003 | 0x60 u32be 25000 (mux rate,
  ед. 50 Б/с) | 0x64 u32be 90000 | 0x68 01 01 | 0x6A u32be 0x24 | 0x6E начало, 0x74 конец (6 Б) | 0x7A u16be 1 |
  0x7C u32be 0x12 | 0x80 u16be потоков 1 | 0x82 поток 16 Б: E0 00 21 EF (P-STD: шкала 1, 495 КБ), EP-карта 0/0,
  ширина/16 = 9, высота/16 = 5, 00 00. Открытый ffmpeg (демуксер mpeg) разжимает и эталон, и наш файл.
  Поток: MPEG-2 PS, паки по 2048 Б без набивки; у каждой GOP (30 кадров = 1 с) свой пак: заголовок пака, системный
  заголовок (18 Б, как у эталона), private_stream_2 (0xBF) — таблица кадров GOP: 01 E0, 4×u16 «в каком паке от начала
  GOP кончается кадр 0..3», u32 0, u16 длина (2 + 4N), u16 N, N×(u16 0x0080, u16 байт кадра от AUD до AUD); затем PES
  видео 0xE0 с PTS/DTS (DTS = PTS − 3003) и P-STD 61 EF. Дальше PES без заголовка; PTS — на пакете, где первый
  начинающийся кадр позже прошлого PTS на 16 кадров и больше; кадр, которому исполнилось 20 кадров от PTS, но он не
  первый в пакете, начинает новый пак (остаток — набивка 0xBE; так у эталона набивка посреди GOP); хвост GOP и файла —
  тоже набивка 0xBE. SCR — своё расписание: DTS первого кадра пака − 75000, шаг не меньше 148 тиков (2048 Б при 25000*50
  Б/с); у эталона ≈ DTS кадра на стыке со следующим паком − 80900 ± 150 — правило не снято, SCR расходится до 0,33 с.
  Видео: H.264 Main@2.1, 144×80, 29,97 к/с, CABAC, 1 опорный, без B-кадров, AUD в каждом кадре, SPS/PPS у каждого IDR,
  SEI buffering period (IDR) + pic timing (каждый кадр, pic_struct), SAR 1:1; звука в эталоне нет (музыка — SND0.AT3).
Кодирует открытый libx264 (ffmpeg из brew), пакует этот скрипт — без закрытого софта Sony (UMD Stream Composer не нужен).
Свой SEI x264 с версией кодера (user data, тип 5) выкидывается — у эталона его нет.

Правило порта (в данных оригинала значка XMB нет — вопрос Робу): монтаж --cuts из роликов диска (RMV, разжимает
tools/movie_export.py), кадр 4:3 режется по центру до 9:5 (yc — середина окна по высоте, 0..1), 25 → 29,97 к/с
повтором ближайшего кадра, склейки встык, всего кадров кратно GOP (30). По умолчанию ~5 с: заставка THE SIMPSONS с
осой (intro), розовая машина по Evergreen (demo), грузовик-монстр (demo), Гомер на диване (intro), знак HIT&RUN (demo).
Ресурсы игры не коммитить: результат только в build/assets/ (build/ в .gitignore).

  python tools/icon1.py [--out build/assets/icon1.pmf] [--cuts clip:старт:длит[:yc],...] [--crf 26] [--sheet PNG]
  python tools/icon1.py --verify build/assets/icon1.pmf [--ref ЭТАЛОН.PMF]   гейт разбора (0 = OK, иначе FAIL: причина)
  python tools/icon1.py --selftest [--ref ЭТАЛОН.PMF]    отрицательные контроли гейта: 9 испорченных PMF обязаны упасть;
      с --ref ещё гейт на эталоне Sony и перепаковка его видеопотока нашим упаковщиком: паки побайтно, кроме SCR
Пригодность проверяет Роб на PSP: PPSSPP значок XMB не играет."""
import argparse, os, re, struct, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
FF, FP = '/opt/homebrew/bin/ffmpeg', '/opt/homebrew/bin/ffprobe'
W, H = 144, 80                       # размер значка XMB (как ICON0)
FPS_N, FPS_D, TICK = 30000, 1001, 3003   # 29,97 к/с; тиков 90 кГц на кадр
PTS0, GOP = 90000, 30                # начало показа 1 с; IDR раз в секунду — как у эталона
PACK, MUX_RATE, SCR_LEAD = 2048, 25000, 75000
PTS_GAP, PTS_MAX = 16 * TICK, 20 * TICK   # PTS не чаще 16 и не реже 20 кадров (0,53–0,67 с; MPEG-PS: ≤ 0,7 с), как у эталона
PACK_TICKS = -(-PACK * 90000 // (MUX_RATE * 50))   # 148: время на пак при mux rate
SYS_HDR = bytes.fromhex('000001bb000c80c35140f07fb9e1efbde004')   # системный заголовок эталона (rate 25000, P-STD E0 495 КБ)
PSTD_EXT = bytes([0x1e, 0x61, 0xef])                                  # PES-расширение первого пакета GOP (P-STD 1/495)
# Правка Роба 188 (01.10 23:2x, «найди причину, переделай видео»): 16-с ролик (0012, P-STD 495 КБ, как Tony Hawk) PSP не показал,
# 5-с с тем же заголовком — показывает. ICON1.PMF пяти игр Sony с карты Роба (build/xmb_ref: GTA LCS 31 с 442 КБ, Tomb Raider 12 с,
# LocoRoco 12 с, Cube 8 с, NFS 2 с) — все PSMF 0014, буфер P-STD по потоку 19–251 КБ (один и тот же в заголовке PSMF, системном
# заголовке и PES), системный заголовок 80 C3 51 | 80 | F0 7F | B9 E0 kk | BD E0 08. По умолчанию — так же (ICON1_VER=0012 — прежний
# вид эталона Tony Hawk с 495 КБ); буфер — по потоку: наибольшее заполнение (паки к своему SCR минус кадры к своему DTS) x 1,25
PSMF_VER = os.environ.get('ICON1_VER', '0014').encode()


def sys_hdr(kb):
    sony = PSMF_VER == b'0014'
    return bytes.fromhex('000001bb000c80c351') + bytes([0x80 if sony else 0x40, 0xf0, 0x7f, 0xb9, 0xe0 | (kb >> 8), kb & 0xff,
                                                         0xbd, 0xe0, 0x08 if sony else 0x04])


def pstd_ext(kb):
    return bytes([0x1e, 0x60 | (kb >> 8), kb & 0xff])
# правка Роба 131 (01.10): «видео длиннее — нарезка демо-геймплея PS2, докропать, больше динамичных фрагментов».
# Конверт — проверенный образцом Tony Hawk (16 с, 218 КБ: XMB его играет): до 20 с и 230 КБ; короче 12 с — прежний
# 5-секундный значок, правка 131 не выполнена (гейт падает).
MIN_SEC, MAX_SEC, MAX_BYTES = 12.0, 20.05, 230 * 1024   # 20,05: монтаж кладётся кратно 120 кадрам — 600 кадров 29,97 = 20,02 с (правка 262)
CUTS_OLD = 'intro:17.0:1.2:0.45,demo:4.0:1.0,demo:29.6:0.9,intro:41.6:0.9:0.15,demo:60.2:1.0'   # правка 110 (отрицательный контроль)
# правка 131: --auto 16 (auto_cuts) по разбору demo.rmv — самые подвижные окна внутри одного плана, без планов с
# видоискателем «DEMO», в порядке ролика; yc — центр движения по высоте. Зашито строкой, чтобы сборка не зависела от
# порогов разбора; tools/icon1.py --check-cuts сверяет монтаж с разбором (склейки, «DEMO», движение).
# Правка Роба 262 (04.10: «превью оптимизировать, показать больше демо»): --auto 20 — 9 кусков, 19,8 с (два новых: 11,16 и 47,92),
# сжатие crf 27 — файл 208 КБ в том же конверте (≤ 230 КБ, как у Tony Hawk). Прежний монтаж 131 — CUTS_131
CUTS_131 = ('demo:4.16:2.80:0.49,demo:14.96:0.84:0.45,demo:16.20:2.68:0.43,demo:19.48:2.80:0.45,demo:25.80:2.32:0.39,'
            'demo:28.36:2.72:0.37,demo:52.24:1.40:0.53')   # tools/icon1.py --auto 16, 01.10: 7 кусков, 15,6 с
CUTS = ('demo:4.16:2.80:0.49,demo:11.16:2.32:0.50,demo:14.96:0.84:0.45,demo:16.20:2.68:0.43,demo:19.48:2.80:0.45,'
        'demo:25.80:2.32:0.39,demo:28.36:2.72:0.37,demo:47.92:2.12:0.54,demo:52.24:1.16:0.53')
SEG_MIN, SEG_MAX, EDGE = 0.8, 2.8, 0.12   # длина куска, с; отступ от склейки, с
CUT_DIFF, MOTION_MIN = 25.0, 4.0          # склейка: средняя разница кадров 40×32 (0..255); медиана движения куска не ниже
# видоискатель «DEMO» в demo.rmv (зелёные уголки рамки): прямоугольники (y0, y1, x0, x1) на кадре разбора 160×128
DEMO_L = [(13, 22, 16, 18), (12, 13, 18, 28), (12, 13, 132, 142), (15, 22, 140, 142), (105, 112, 16, 18), (112, 113, 18, 26),
          (105, 112, 140, 142), (115, 116, 134, 140)]


# ---------- кадры из роликов диска ----------
def cut_frames(clip, start, dur, yc=0.5):
    """Кадры RMV [start, start+dur) с, 4:3 → окно 9:5 по высоте yc → 144×80 RGB, 25 к/с."""
    import movie_export as ME
    rmv = ME.rmv_parse((ME.SRC / f'{clip}.rmv').read_bytes(), clip)
    a = int(round(start * 25)); b = min(rmv['frames'], int(round((start + dur) * 25)) + 1)
    ch = int(round(rmv['w'] * 16 / 15 / (W / H)))          # PAL 640×512, SAR 16:15: высота окна 9:5 во весь кадр по ширине
    y0 = int(round((rmv['h'] - ch) * min(max(yc, 0.0), 1.0)))
    with tempfile.TemporaryDirectory(prefix='shar-icon1-') as tmp:
        ipu = Path(tmp) / 'v.ipu'
        ipu.write_bytes(b'ipum' + struct.pack('<IHHI', len(rmv['video']) + 16, rmv['w'], rmv['h'], rmv['frames']) + rmv['video'])
        raw = ME.run([FF, '-v', 'error', '-i', str(ipu), '-fps_mode', 'passthrough', '-vf',
                      f'trim=start_frame={a}:end_frame={b},crop={rmv["w"]}:{ch}:0:{y0},'
                      f'scale={W}:{H}:flags=lanczos+accurate_rnd+full_chroma_int', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    fr = np.frombuffer(raw, np.uint8)
    if not fr.size or fr.size % (W * H * 3): raise SystemExit(f'icon1: {clip} {start}+{dur}: нет кадров')
    return fr.reshape(-1, H, W, 3)


def montage(cuts):
    """Склейка встык 25 → 29,97 к/с (ближайший кадр); всего кадров кратно GOP (последний отрезок подрезается/тянется)."""
    parts = []
    for c in cuts.split(','):
        f = c.split(':'); clip, st, du = f[0], float(f[1]), float(f[2]); yc = float(f[3]) if len(f) > 3 else 0.5
        src = cut_frames(clip, st, du, yc); n = int(round(du * FPS_N / FPS_D))
        parts.append([src, n]); print(f'  {clip} {st:.1f}+{du:.1f} с (yc {yc}): {len(src)} кадров 25 к/с → {n}')
    tot = sum(n for _, n in parts); parts[-1][1] += (-tot) % GOP if tot % GOP >= GOP // 2 else -(tot % GOP)
    out = []
    for src, n in parts:
        for j in range(n): out.append(src[min(len(src) - 1, int(j * FPS_D * 25 / FPS_N + 1e-9))])
    return np.stack(out)


# ---------- разбор demo.rmv (правка 131): склейки, движение, видоискатель «DEMO» ----------
def scan(clip='demo'):
    """Весь ролик кадрами 160×128 → dict: cuts (с, жёсткие склейки), motion (по кадру), demo (bool по кадру), rows.
    Склейка — средняя разница соседних кадров 40×32 > CUT_DIFF; «DEMO» — зелёные уголки DEMO_L: доля зелёных пикселей
    в уголках ≥ 0,4 и на 0,2 больше, чем вокруг них (трава вокруг тоже зелёная). Проверено на 64 с ролика: найдено
    7.2–8.9, 31.8–32.9, 37.0–39.0, 51.0–52.1, 55.4–56.1, 56.6–58.0 — как на листе кадров."""
    import movie_export as ME
    rmv = ME.rmv_parse((ME.SRC / f'{clip}.rmv').read_bytes(), clip)
    with tempfile.TemporaryDirectory(prefix='shar-icon1-') as tmp:
        ipu = Path(tmp) / 'v.ipu'
        ipu.write_bytes(b'ipum' + struct.pack('<IHHI', len(rmv['video']) + 16, rmv['w'], rmv['h'], rmv['frames']) + rmv['video'])
        raw = ME.run([FF, '-v', 'error', '-i', str(ipu), '-fps_mode', 'passthrough', '-vf', 'scale=160:128:flags=area',
                      '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    fr = np.frombuffer(raw, np.uint8).reshape(-1, 128, 160, 3).astype(np.int16)
    r, g, b = fr[..., 0], fr[..., 1], fr[..., 2]
    gd = (g > r + 40) & (g > b + 40) & (g > 90)
    m = np.zeros((128, 160), bool); ring = np.zeros((128, 160), bool)
    for y0, y1, x0, x1 in DEMO_L:
        m[y0:y1, x0:x1] = 1; ring[max(0, y0 - 4):y1 + 4, max(0, x0 - 4):x1 + 4] = 1
    ring &= ~m
    sc, rg = gd[:, m].mean(1), gd[:, ring].mean(1)
    gray = fr.mean(3)
    sm = gray.reshape(-1, 32, 4, 40, 4).mean((2, 4))
    d = np.r_[0.0, np.abs(np.diff(sm, axis=0)).mean((1, 2))]
    rows = np.abs(np.diff(gray, axis=0)).mean(2); rows = np.vstack([rows[:1], rows])   # движение по строкам (для yc)
    return dict(cuts=[i / 25 for i in np.where(d > CUT_DIFF)[0]], motion=d, demo=(sc >= 0.4) & (sc - rg >= 0.2), rows=rows, n=len(fr))


def shots(sc):
    """Планы (начало, конец, есть ли «DEMO») между склейками; план с хоть одним кадром «DEMO» — весь грязный (рамка бывает бледной)."""
    edges = [0.0] + sc['cuts'] + [sc['n'] / 25]; out = []
    for a, b in zip(edges, edges[1:]):
        if b - a > 1e-6: out.append((a, b, bool(sc['demo'][int(round(a * 25)):int(round(b * 25))].any())))
    return out


def auto_cuts(sc, total, logo_from=59.8):
    """Правило порта правки 131: в каждом чистом плане (без «DEMO», до логотипа 59,8 с) — самое подвижное окно
    SEG_MIN..SEG_MAX с (отступ EDGE от склеек); окна по убыванию движения, пока не наберётся total с; порядок — ролика.
    Логотип HIT&RUN в конце не берётся: Роб просил нарезку геймплея (решено терминалом)."""
    cand = []
    for a, b, dm in shots(sc):
        if dm or a >= logo_from: continue
        b = min(b, logo_from); L = min(SEG_MAX, b - a - 2 * EDGE)
        if L < SEG_MIN: continue
        best = None
        for st in np.arange(a + EDGE, b - EDGE - L + 1e-6, 0.04):
            i0, i1 = int(round(st * 25)), int(round((st + L) * 25))
            e = float(np.median(sc['motion'][i0 + 1:i1 + 1]))
            if best is None or e > best[0]: best = (e, st)
        e, st = best; i0, i1 = int(round(st * 25)), int(round((st + L) * 25))
        prof = sc['rows'][i0:i1].mean(0); ys = (np.arange(len(prof)) + 0.5) / len(prof)
        yc = float(np.clip((prof * ys).sum() / max(float(prof.sum()), 1e-6), 0.35, 0.65))
        cand.append((e, st, L, yc))
    cand.sort(reverse=True); pick, tot = [], 0.0
    for e, st, L, yc in cand:
        if tot >= total - 0.3 or e < MOTION_MIN: continue
        L = min(L, total - tot)
        if L < SEG_MIN: continue
        pick.append((st, L, yc, e)); tot += L
    pick.sort()
    for st, L, yc, e in pick: print(f'  кусок demo {st:.2f}+{L:.2f} с, движение {e:.1f}, yc {yc:.2f}')
    return ','.join(f'demo:{st:.2f}:{L:.2f}:{yc:.2f}' for st, L, yc, _ in pick)


def check_cuts(cuts, sc=None):
    """Гейт монтажа правки 131 (без кодирования): длина MIN_SEC..MAX_SEC; все куски из demo; ни один не пересекает
    склейку; ни одного кадра «DEMO»; медиана движения каждого куска ≥ MOTION_MIN. Возвращает список причин FAIL."""
    fails, tot = [], 0.0
    sc = sc or scan('demo')
    for c in cuts.split(','):
        f = c.split(':'); clip, st, du = f[0], float(f[1]), float(f[2]); tot += du
        if clip != 'demo': fails.append(f'кусок {c}: не из demo (правка 131 — только геймплей)'); continue
        i0, i1 = int(round(st * 25)), int(round((st + du) * 25))
        ks = [k for k in sc['cuts'] if st < k < st + du]
        if ks: fails.append(f'кусок {c}: пересекает склейку {ks[:2]}')
        nd = int(sc['demo'][i0:i1 + 1].sum())
        if nd: fails.append(f'кусок {c}: {nd} кадров с видоискателем «DEMO»')
        e = float(np.median(sc['motion'][i0 + 1:i1 + 1]))
        if e < MOTION_MIN: fails.append(f'кусок {c}: движение {e:.1f} < {MOTION_MIN} (спокойный план)')
    if not MIN_SEC <= tot <= MAX_SEC: fails.append(f'монтаж {tot:.1f} с, нужно {MIN_SEC:g}..{MAX_SEC:g} с (правка 131)')
    return fails


# ---------- H.264 (libx264) ----------
def encode(frames, crf, profile='main', level='2.1'):
    """RGB-кадры → поток H.264 Annex B: Main@2.1, без B-кадров, 1 опорный, IDR каждые 30, AUD, HRD+pic_struct SEI."""
    xp = (f'keyint={GOP}:min-keyint={GOP}:scenecut=0:bframes=0:ref=1:aud=1:nal-hrd=vbr:vbv-maxrate=768:vbv-bufsize=768:'
          f'pic-struct=1:weightp=0:force-cfr=1:crf={crf}')
    cmd = [FF, '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', f'{FPS_N}/{FPS_D}', '-i', '-',
           '-vf', 'setsar=1,format=yuv420p', '-c:v', 'libx264', '-preset', 'veryslow', '-profile:v', profile,
           '-level:v', level, '-x264-params', xp, '-f', 'h264', '-']
    r = subprocess.run(cmd, input=frames.tobytes(), capture_output=True)
    if r.returncode: raise SystemExit('icon1: x264: ' + r.stderr.decode(errors='replace')[-300:])
    return r.stdout


def nal_units(es):
    """[(начало с нулями стартового кода, тип NAL)] потока Annex B."""
    out = []
    for m in re.finditer(b'\x00\x00\x01', es):
        p = m.start(); s = p - 1 if p and es[p - 1] == 0 else p
        if p + 3 < len(es): out.append((s, es[p + 3] & 0x1f))
    return out


def split_aus(es, drop_userdata=True):
    """Поток → кадры (от AUD до AUD); SEI user data (тип 5, версия x264) выкидывается."""
    nals = nal_units(es); aus, cur = [], None
    for i, (s, t) in enumerate(nals):
        e = nals[i + 1][0] if i + 1 < len(nals) else len(es)
        if t == 9:
            if cur is not None: aus.append(bytes(cur))
            cur = bytearray()
        if cur is None: raise ValueError('поток не начинается с AUD (нужен x264 aud=1)')
        if drop_userdata and t == 6 and es[s:e].lstrip(b'\0')[2:3] == b'\x05': continue   # 01 06 | payloadType
        cur += es[s:e]
    if cur: aus.append(bytes(cur))
    return aus


# ---------- упаковка PSMF ----------
def ts5(prefix, t):
    return bytes([(prefix << 4) | ((t >> 29) & 0x0e) | 1, (t >> 22) & 0xff, ((t >> 14) & 0xfe) | 1, (t >> 7) & 0xff, ((t << 1) & 0xfe) | 1])


def pack_header(scr):
    v = 1 << 46 | ((scr >> 30) & 7) << 43 | 1 << 42 | ((scr >> 15) & 0x7fff) << 27 | 1 << 26 | (scr & 0x7fff) << 11 | 1 << 10 | 1
    return b'\0\0\x01\xba' + v.to_bytes(6, 'big') + ((MUX_RATE << 2) | 3).to_bytes(3, 'big') + b'\xf8'


def psmf_header(stream_size, frames, kb=0x1ef):
    h = bytearray(0x800); end = PTS0 + frames * TICK
    h[0:8] = b'PSMF' + PSMF_VER; struct.pack_into('>II', h, 8, 0x800, stream_size); struct.pack_into('>I', h, 0x50, 0x3e)
    h[0x54:0x5a] = PTS0.to_bytes(6, 'big'); h[0x5a:0x60] = end.to_bytes(6, 'big')
    struct.pack_into('>IIBBI', h, 0x60, MUX_RATE, 90000, 1, 1, 0x24)
    h[0x6e:0x74] = PTS0.to_bytes(6, 'big'); h[0x74:0x7a] = end.to_bytes(6, 'big')
    struct.pack_into('>HIH', h, 0x7a, 1, 0x12, 1)
    h[0x82:0x92] = bytes([0xe0, 0x00, 0x20 | (kb >> 8), kb & 0xff]) + bytes(8) + bytes([W // 16, H // 16, 0, 0])
    return bytes(h)


def mux(aus, kb=None):
    """Кадры → ICON1.PMF (заголовок PSMF + паки 2048 Б по раскладке эталона Sony); GOP — от IDR до IDR. kb — буфер P-STD, КБ:
    None — по потоку (два прохода: SCR от буфера не зависит), при ICON1_VER=0012 — 495, как у эталона Tony Hawk"""
    if kb is None:
        if PSMF_VER != b'0014': return mux(aus, 0x1ef)
        return mux(aus, pstd_need(mux(aus, 0x1ef), aus))
    SYS_HDR, PSTD_EXT = sys_hdr(kb), pstd_ext(kb)
    idr = [i for i, a in enumerate(aus) if any(t == 5 for _, t in nal_units(a))]
    if not aus or idr[:1] != [0]: raise SystemExit('icon1: поток не начинается с IDR')
    packs, last_pts = [], None
    for g, g1 in zip(idr, idr[1:] + [len(aus)]):
        gop = aus[g:g1]; data = b''.join(gop); starts = np.cumsum([0] + [len(a) for a in gop])[:-1]
        tab_len = 18 + 4 * len(gop); pos, first, gpk, ends = 0, True, [], []
        while pos < len(data):
            room = PACK - 14 - ((len(SYS_HDR) + 6 + tab_len) if first else 0) - 9   # 9: 00 00 01 E0 len 81 f2 hl
            k = int(np.searchsorted(starts, pos))                      # первый кадр, начинающийся не раньше pos
            hdr = b''
            if first:
                hdr = ts5(3, PTS0 + g * TICK) + ts5(1, PTS0 + g * TICK - TICK) + PSTD_EXT; f2 = 0xc1
            elif k < len(gop) and starts[k] < pos + room - 10 and (PTS0 + (g + k) * TICK) - last_pts >= PTS_GAP:
                hdr = ts5(3, PTS0 + (g + k) * TICK) + ts5(1, PTS0 + (g + k) * TICK - TICK); f2 = 0xc0
            else:
                f2 = 0x00
            if f2 & 0x80: last_pts = PTS0 + (g + (0 if first else k)) * TICK
            cap = room - len(hdr)
            for j in range(k, len(gop)):   # кадр, которому пора PTS (20 кадров), но он не первый в пакете, — с нового пака
                if starts[j] >= pos + cap: break
                if starts[j] > pos and PTS0 + (g + j) * TICK - last_pts >= PTS_MAX: cap = int(starts[j]) - pos; break
            pay = data[pos:pos + cap]
            left = room - len(hdr) - len(pay)
            if 0 < left < 6: hdr += b'\xff' * left; left = 0            # остаток меньше пакета-набивки — набивка в PES
            pes = b'\0\0\x01\xe0' + struct.pack('>H', 3 + len(hdr) + len(pay)) + bytes([0x81, f2, len(hdr)]) + hdr + pay
            dts_first = PTS0 + (g + max(0, int(np.searchsorted(starts, pos, 'right')) - 1)) * TICK - TICK
            body = b''
            if first: body = SYS_HDR + b'\0\0\x01\xbf' + struct.pack('>H', tab_len) + bytes(tab_len)   # таблица — после раскладки
            body += pes + ((b'\0\0\x01\xbe' + struct.pack('>H', left - 6) + b'\xff' * (left - 6)) if left else b'')
            gpk.append([dts_first, bytearray(body)]); pos += len(pay); first = False
            ends.append(pos)
        t = gpk[0][1]; o = len(SYS_HDR) + 6          # таблица GOP: после системного заголовка и 6 Б заголовка 0xBF
        t[o:o + 2] = b'\x01\xe0'
        for i in range(4):                             # в каком паке от начала GOP кончается кадр i (как у эталона)
            j = min(i, len(gop) - 1); e = starts[j] + len(gop[j])
            struct.pack_into('>H', t, o + 2 + 2 * i, next(n for n, x in enumerate(ends) if x >= e))
        struct.pack_into('>IHH', t, o + 10, 0, 2 + 4 * len(gop), len(gop))
        for i, a in enumerate(gop): struct.pack_into('>HH', t, o + 18 + 4 * i, 0x0080, len(a))
        packs += gpk
    out, scr = [], None
    for dts, body in packs:
        scr = max(0, dts - SCR_LEAD) if scr is None else max(scr + PACK_TICKS, dts - SCR_LEAD)
        p = pack_header(scr) + bytes(body)
        if len(p) != PACK: raise SystemExit(f'icon1: пак {len(out)} {len(p)} Б')
        out.append(p)
    stream = b''.join(out)
    return psmf_header(len(stream), len(aus), kb) + stream


def pstd_need(pmf, aus):
    """буфер P-STD по потоку, КБ: наибольшее (байт паков, пришедших к SCR) − (байт кадров, снятых к своему DTS), x 1,25, 16..255"""
    def scr_of(p):
        b = p[4:10]
        return ((b[0] >> 3) & 7) << 30 | (b[0] & 3) << 28 | b[1] << 20 | (b[2] >> 3) << 15 | (b[2] & 3) << 13 | b[3] << 5 | (b[4] >> 3)
    scrs = [scr_of(pmf[o:o + PACK]) for o in range(0x800, len(pmf), PACK)]
    dts = [PTS0 + i * TICK - TICK for i in range(len(aus))]; cum = np.cumsum([len(a) for a in aus])
    need = 0
    for k, t in enumerate(scrs):
        got = (k + 1) * PACK; j = int(np.searchsorted(dts, t, 'right')); used = int(cum[j - 1]) if j else 0
        need = max(need, got - used)
    return int(min(255, max(16, -(-need * 5 // 4) // 1024)))


# ---------- гейт разбора ----------
def parse(pmf):
    """Разбор PMF → (fails, lines, info). Проверяет заголовок PSMF, паки, таблицы GOP, PTS и SPS; только сами байты."""
    fails, lines = [], []
    if len(pmf) < 0x800 + PACK or pmf[:4] != b'PSMF':
        return ['нет заголовка PSMF'], lines, {}
    ver = pmf[4:8]; off, size = struct.unpack_from('>II', pmf, 8)
    lines.append(f'заголовок: {pmf[:8].decode("latin1")}, поток с {off:#x}, {size} Б (файл {len(pmf)} Б)')
    if ver not in (b'0012', b'0013', b'0014', b'0015'): fails.append(f'версия PSMF {ver}')
    if off != 0x800: fails.append(f'поток не с 0x800 ({off:#x})')
    if off + size != len(pmf): fails.append(f'размер потока в заголовке {size} != файлу {len(pmf) - off}')
    if size % PACK: fails.append(f'поток не кратен 2048 ({size})')
    t0, t1 = int.from_bytes(pmf[0x54:0x5a], 'big'), int.from_bytes(pmf[0x5a:0x60], 'big')
    ns = struct.unpack_from('>H', pmf, 0x80)[0]; st = pmf[0x82:0x92]
    lines.append(f'  показ {t0}..{t1} ({(t1 - t0) / 90000:.3f} с), потоков {ns}, поток 0: id {st[0]:#x}, {st[12] * 16}x{st[13] * 16}')
    if struct.unpack_from('>I', pmf, 0x50)[0] != 0x2e + 16 * ns: fails.append('длина блока 0x50 не сходится с числом потоков')
    if ns < 1 or st[0] != 0xe0: fails.append('нет потока видео AVC 0xE0')
    if (st[12] * 16, st[13] * 16) != (W, H): fails.append(f'размер в заголовке {st[12] * 16}x{st[13] * 16}, нужно {W}x{H}')
    if pmf[0x6e:0x7a] != pmf[0x54:0x60]: fails.append('времена 0x54/0x6E не совпадают')
    if struct.unpack_from('>I', pmf, 0x60)[0] == 0: fails.append('mux rate 0')
    es, gops, scr_prev, pts_list = bytearray(), [], -1, []
    for n in range(max(0, (len(pmf) - off) // PACK)):
        p = pmf[off + n * PACK:off + (n + 1) * PACK]
        if p[:4] != b'\0\0\x01\xba' or p[4] >> 6 != 1: fails.append(f'пак {n}: нет заголовка MPEG-2'); break
        b = p[4:10]
        scr = ((b[0] >> 3) & 7) << 30 | (b[0] & 3) << 28 | b[1] << 20 | (b[2] >> 3) << 15 | (b[2] & 3) << 13 | b[3] << 5 | b[4] >> 3
        if scr <= scr_prev: fails.append(f'пак {n}: SCR не растёт ({scr_prev} → {scr})')
        scr_prev = scr; q = 14 + (p[13] & 7)
        while q < PACK:
            if p[q:q + 3] != b'\0\0\x01': fails.append(f'пак {n}: мусор на {q}'); break
            sid = p[q + 3]; ln = struct.unpack_from('>H', p, q + 4)[0]
            if q + 6 + ln > PACK: fails.append(f'пак {n}: пакет {sid:#x} за краем пака'); break
            if sid == 0xbf:
                t = p[q + 6:q + 6 + ln]; cnt = struct.unpack_from('>H', t, 16)[0]
                if t[:2] != b'\x01\xe0' or struct.unpack_from('>H', t, 14)[0] != 2 + 4 * cnt or ln != 18 + 4 * cnt:
                    fails.append(f'пак {n}: таблица GOP испорчена')
                gops.append(dict(pack=n, es=len(es), rel=struct.unpack_from('>4H', t, 2),
                                 sizes=[struct.unpack_from('>H', t, 20 + 4 * i)[0] for i in range(cnt)]))
            elif sid == 0xe0:
                f2, hl = p[q + 7], p[q + 8]; h = p[q + 9:q + 9 + hl]
                if f2 & 0x80:
                    ts = lambda x: ((x[0] >> 1) & 7) << 30 | x[1] << 22 | (x[2] >> 1) << 15 | x[3] << 7 | x[4] >> 1
                    pts = ts(h); dts = ts(h[5:10]) if f2 & 0x40 else pts
                    pts_list.append((n, len(es), pts, dts, scr))
                es += p[q + 9 + hl:q + 6 + ln]
            elif sid not in (0xbb, 0xbe, 0xbd):
                fails.append(f'пак {n}: неожиданный поток {sid:#x}')
            q += 6 + ln
    try: aus = split_aus(bytes(es), drop_userdata=False)
    except ValueError: aus = []
    if not aus: fails.append('видеопоток не начинается с AUD'); return fails, lines, {}
    sizes = [len(a) for a in aus]; au_off = np.cumsum([0] + sizes)
    tab = [s for g in gops for s in g['sizes']]
    lines.append(f'  паков {(len(pmf) - off) // PACK}, GOP {len(gops)}, кадров {len(aus)} ({len(aus) * TICK / 90000:.2f} с), '
                 f'видео {len(es)} Б ({len(es) * 8 * 90000 / max(1, len(aus) * TICK) / 1000:.0f} кбит/с)')
    if tab != sizes: fails.append(f'таблицы GOP ({len(tab)} кадров) не совпадают с кадрами потока ({len(aus)})')
    idr = [i for i, a in enumerate(aus) if any(t == 5 for _, t in nal_units(a))]
    if any(g['es'] not in {int(au_off[i]) for i in idr} for g in gops): fails.append('таблица GOP стоит не перед IDR')
    # PTS: DTS = PTS − 3003, PTS = 90000 + кадр*3003 первого кадра, начавшегося в пакете; SCR < DTS
    for n, esoff, pts, dts, scr in pts_list:
        i = int(np.searchsorted(au_off, esoff))
        if pts != t0 + i * TICK: fails.append(f'пак {n}: PTS {pts} не у кадра {i} ({t0 + i * TICK})'); break
        if pts - dts != TICK: fails.append(f'пак {n}: PTS−DTS {pts - dts}'); break
        if scr >= dts: fails.append(f'пак {n}: SCR {scr} ≥ DTS {dts}'); break
    if t1 - t0 != len(aus) * TICK: fails.append(f'конец показа {t1} != начало + {len(aus)} кадров')
    gaps = np.diff([p for _, _, p, _, _ in pts_list] + [t1 - TICK])   # MPEG-PS: PTS не реже 0,7 с, до последнего кадра
    if len(gaps) and gaps.max() > 63000: fails.append(f'PTS реже 0,7 с (промежуток {gaps.max() / 90000:.2f} с)')
    # SPS: профиль, уровень, размер кадра
    sps = [(s, t) for s, t in nal_units(aus[0]) if t == 7]
    if not sps: fails.append('в первом кадре нет SPS')
    else:
        b = aus[0][sps[0][0]:].lstrip(b'\0')[2:5]     # 01 67 | profile_idc, constraint flags, level_idc
        prof, lvl = b[0], b[2]; lines.append(f'  H.264 профиль {prof} ({"Main" if prof == 77 else "Baseline" if prof == 66 else "?"}), уровень {lvl / 10}')
        if prof not in (66, 77): fails.append(f'профиль H.264 {prof} (нужен Main 77 или Baseline 66)')
        if lvl > 21: fails.append(f'уровень H.264 {lvl / 10} > 2.1')
    if idr[:1] != [0] or not all({7, 8} <= {t for _, t in nal_units(aus[i])} for i in idr): fails.append('IDR без SPS/PPS')
    if len(gops) != len(idr): fails.append(f'GOP-таблиц {len(gops)}, IDR {len(idr)}')
    if len(aus) * TICK / 90000 > MAX_SEC: fails.append(f'длина {len(aus) * TICK / 90000:.1f} с > {MAX_SEC} с')
    if len(aus) * TICK / 90000 < MIN_SEC: fails.append(f'длина {len(aus) * TICK / 90000:.1f} с < {MIN_SEC:g} с (правка 131: значок длиннее)')
    if len(pmf) > MAX_BYTES: fails.append(f'файл {len(pmf)} Б > {MAX_BYTES} Б («маленький размер»)')
    return fails, lines, dict(frames=len(aus), gops=gops, sizes=sizes, es=bytes(es))


def gop_rel_check(pmf, info):
    """4 номера пака в таблице GOP = пак, где кончается кадр 0..3 (считая от пака таблицы)."""
    off = 0x800; ends, es = [], 0
    for n in range((len(pmf) - off) // PACK):
        p = pmf[off + n * PACK:off + (n + 1) * PACK]; q = 14
        while q < PACK and p[q:q + 3] == b'\0\0\x01':
            ln = struct.unpack_from('>H', p, q + 4)[0]
            if p[q + 3] == 0xe0: es += ln - 3 - p[q + 8]
            q += 6 + ln
        ends.append(es)
    au_end = np.cumsum(info['sizes']); k = 0; bad = []
    for g in info['gops']:
        for i in range(min(4, len(g['sizes']))):
            last = au_end[k + i] - 1
            pk = next(n for n, e in enumerate(ends) if e > last)
            if pk - g['pack'] != g['rel'][i]: bad.append((g['pack'], i, pk - g['pack'], g['rel'][i]))
        k += len(g['sizes'])
    return bad


def ffprobe_frames(path):
    r = subprocess.run([FP, '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                        'stream=codec_name,profile,level,width,height,nb_read_frames,r_frame_rate', '-of', 'default=nw=1', str(path)],
                       capture_output=True, text=True)
    d = dict(l.split('=', 1) for l in r.stdout.split() if '=' in l)
    e = subprocess.run([FF, '-v', 'error', '-i', str(path), '-f', 'null', '-'], capture_output=True, text=True).stderr.strip()
    return d, e


def verify(path, ref=None, quiet=False):
    pmf = Path(path).read_bytes(); fails, lines, info = parse(pmf)
    if info and not fails:
        bad = gop_rel_check(pmf, info)
        if bad: fails.append(f'номера паков в таблицах GOP не сходятся: {bad[:3]}')
    if not fails:
        d, err = ffprobe_frames(path)
        lines.append(f'  ffprobe: {d.get("codec_name")} {d.get("profile")} {d.get("width")}x{d.get("height")} '
                     f'{d.get("r_frame_rate")}, кадров разжато {d.get("nb_read_frames")}')
        if err: fails.append('ffmpeg при разжатии: ' + err.splitlines()[0][:120])
        if d.get('nb_read_frames') != str(info['frames']): fails.append(f'ffmpeg разжал {d.get("nb_read_frames")} кадров из {info["frames"]}')
        if (d.get('width'), d.get('height')) != (str(W), str(H)): fails.append(f'кадр потока {d.get("width")}x{d.get("height")}')
        if d.get('r_frame_rate') != f'{FPS_N}/{FPS_D}': fails.append(f'частота {d.get("r_frame_rate")}, нужно {FPS_N}/{FPS_D}')
    if ref and Path(ref).exists():     # заголовок сверяется с эталоном Sony: всё, кроме размера и времени конца
        rb = Path(ref).read_bytes()[:0x92]; mine = bytearray(pmf[:0x92]); rr = bytearray(rb)
        for bb in (mine, rr): bb[0x0c:0x10] = bytes(4); bb[0x5a:0x60] = bytes(6); bb[0x74:0x7a] = bytes(6)
        diff = [hex(i) for i in range(0x92) if mine[i] != rr[i]]
        lines.append(f'  заголовок против эталона {Path(ref).name}: ' + ('совпадает (кроме размера и конца показа)' if not diff else f'разница в {diff[:8]}'))
        if diff: fails.append(f'заголовок PSMF отличается от эталона Sony в {diff[:8]}')
    if not quiet:
        print(('FAIL: ' + fails[0]) if fails else f'OK: ICON1.PMF {W}x{H}, {info["frames"]} кадров, {len(pmf)} Б — разбор, таблицы GOP, PTS, SPS и ffmpeg сходятся')
        print('\n'.join(lines)); [print('  - ' + f) for f in fails[1:]]
    return fails


def remux_check(ref):
    """Упаковщик на видеопотоке эталона Sony обязан повторить эталон: заголовок и паки побайтно, кроме SCR (байты 4..9 пака)."""
    rb = Path(ref).read_bytes(); _, _, info = parse(rb)
    m = mux(split_aus(info['es'], drop_userdata=False))
    n = (len(rb) - 0x800) // PACK; same = []; scr_d = []
    for k in range(min(n, (len(m) - 0x800) // PACK)):
        a, b = rb[0x800 + k * PACK:0x800 + (k + 1) * PACK], m[0x800 + k * PACK:0x800 + (k + 1) * PACK]
        if a[:4] + a[10:] == b[:4] + b[10:]: same.append(k)
        sa = lambda p: ((p[4] >> 3) & 7) << 30 | (p[4] & 3) << 28 | p[5] << 20 | (p[6] >> 3) << 15 | (p[6] & 3) << 13 | p[7] << 5 | p[8] >> 3
        scr_d.append(abs(sa(a) - sa(b)))
    heads = [g['pack'] for g in info['gops']]; heads_ok = all(k in same for k in heads)
    # правило PTS 16/20 кадров с новым паком для «просроченного» кадра повторяет и набивку посреди GOP у Sony: 108/108
    ok = len(m) == len(rb) and m[:0x800] == rb[:0x800] and heads_ok and len(same) == n
    print(f'  перепаковка потока эталона нашим упаковщиком: размер {len(m)} / {len(rb)}, заголовок '
          f'{"=" if m[:0x800] == rb[:0x800] else "≠"}, паки GOP с таблицами {"=" if heads_ok else "≠"} ({len(heads)}), '
          f'всех паков совпало без SCR {len(same)}/{n}, SCR расходится до {max(scr_d) / 90:.0f} мс')
    return ok


def selftest(good, ref):
    """Гейт обязан упасть на каждом испорченном PMF (отрицательные контроли) и пройти на хорошем и на эталоне Sony."""
    d = bytearray(Path(good).read_bytes()); res = []

    def bad(name, fn):
        b = bytearray(d); fn(b)
        with tempfile.NamedTemporaryFile(suffix='.pmf', delete=False) as f: f.write(b)
        fl = verify(f.name, quiet=True); Path(f.name).unlink()
        res.append((name, bool(fl))); print(f'  {"красный" if fl else "ЗЕЛЁНЫЙ (ошибка гейта)"}: {name} — {fl[0] if fl else ""}')
    def gop1(b):   # первая таблица GOP: размер кадра 0 +1
        o = 0x800 + 14 + len(SYS_HDR) + 6 + 20; struct.pack_into('>H', b, o, struct.unpack_from('>H', b, o)[0] + 1)
    def rel(b):
        o = 0x800 + 14 + len(SYS_HDR) + 6 + 2; struct.pack_into('>H', b, o, 7)
    def pts(b):
        o = 0x800 + 14 + len(SYS_HDR) + 6 + 18 + 4 * GOP + 9; b[o + 3] ^= 0x02
    def sps(b):   # профиль High (100) в SPS первого кадра
        i = b.find(b'\x00\x00\x00\x01\x67', 0x800); b[i + 5] = 100
    bad('магия PSMF испорчена', lambda b: b.__setitem__(slice(0, 4), b'PSMX'))
    bad('размер потока в заголовке +2048', lambda b: struct.pack_into('>I', b, 12, struct.unpack_from('>I', b, 12)[0] + PACK))
    bad('файл обрезан на пак', lambda b: b.__delitem__(slice(len(b) - PACK, len(b))))
    bad('ширина 160 в заголовке', lambda b: b.__setitem__(0x8e, 10))
    bad('размер кадра в таблице GOP', gop1)
    bad('номер пака кадра 0 в таблице GOP', rel)
    bad('PTS первого кадра сдвинут', pts)
    bad('профиль High в SPS', sps)
    global PTS_GAP; gap0 = PTS_GAP; PTS_GAP = 40 * TICK        # упаковщик с PTS раз в GOP (1 с > 0,7 с)
    sparse = mux(split_aus(parse(bytes(d))[2]['es'], drop_userdata=False)); PTS_GAP = gap0
    bad('PTS только в начале GOP (1 с)', lambda b: b.__setitem__(slice(0, len(b)), sparse))
    ok = not verify(good, ref=ref)
    if ref and Path(ref).exists():
        print('эталон Sony тем же гейтом (без лимитов длины/размера):')
        global MIN_SEC, MAX_SEC, MAX_BYTES; mn, ms, mb = MIN_SEC, MAX_SEC, MAX_BYTES; MIN_SEC, MAX_SEC, MAX_BYTES = 0.0, 60.0, 1 << 24
        ok_ref = not verify(ref); MIN_SEC, MAX_SEC, MAX_BYTES = mn, ms, mb
        ok_ref = remux_check(ref) and ok_ref
    else: ok_ref = True
    n_red = sum(r for _, r in res)
    print(('OK' if n_red == len(res) and ok and ok_ref else 'FAIL') + f': отрицательных контролей красных {n_red}/{len(res)}, хороший PMF {"зелёный" if ok else "КРАСНЫЙ"}'
          + ('' if not ref else f', эталон Sony {"зелёный" if ok_ref else "КРАСНЫЙ"}'))
    return n_red == len(res) and ok and ok_ref


def contact_sheet(frames, out):
    from PIL import Image
    idx = list(range(0, len(frames), 10)); cols = 10; rows = -(-len(idx) // cols)
    sheet = Image.new('RGB', (cols * W, rows * H))
    for k, i in enumerate(idx): sheet.paste(Image.fromarray(frames[i]), ((k % cols) * W, (k // cols) * H))
    sheet.save(out); print(f'  контактный лист (каждый 10-й кадр): {out}')


def check_pmf_cuts(pmf_path, psnr_min=26.0):
    """Гейт правки 131 на готовом PMF: монтаж из PMF.json проходит check_cuts, а разжатые кадры PMF совпадают с
    перемонтажом тех же кусков (средний PSNR ≥ psnr_min дБ) — PMF собран именно из этого монтажа."""
    import json
    jp = Path(pmf_path).with_suffix('.json')
    if not jp.exists():
        print(f'FAIL: нет {jp.name} — монтаж PMF неизвестен (собрать tools/icon1.py)'); return [f'нет {jp}']
    cuts = json.loads(jp.read_text())['cuts']
    fails = check_cuts(cuts)
    if not fails:
        ref = montage(cuts)
        raw = subprocess.run([FF, '-v', 'error', '-i', str(pmf_path), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
        got = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
        if len(got) != len(ref): fails.append(f'кадров в PMF {len(got)}, в монтаже {len(ref)}')
        else:
            mse = ((got.astype(np.float32) - ref.astype(np.float32)) ** 2).mean((1, 2, 3))
            ps = float(np.mean(10 * np.log10(255.0 ** 2 / np.maximum(mse, 1e-3))))
            print(f'  кадры PMF против перемонтажа: PSNR {ps:.1f} дБ (нужно ≥ {psnr_min:g})')
            if ps < psnr_min: fails.append(f'кадры PMF не из монтажа {jp.name} (PSNR {ps:.1f} дБ)')
    print(('FAIL: ' + fails[0]) if fails else f'OK: монтаж {jp.name} — только demo, без «DEMO» и склеек внутри кусков, подвижный, длина в {MIN_SEC:g}..{MAX_SEC:g} с; PMF из него')
    [print('  - ' + f) for f in fails[1:]]
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'build/assets/icon1.pmf'))
    ap.add_argument('--cuts', default=CUTS)
    ap.add_argument('--crf', type=float, default=27)   # правка 262: 20 с в 230 КБ (было 26 при 16 с)
    ap.add_argument('--sheet')
    ap.add_argument('--profile', default='main')   # high — только для отрицательного контроля
    ap.add_argument('--verify'); ap.add_argument('--selftest', action='store_true'); ap.add_argument('--ref')
    ap.add_argument('--auto', type=float, help='правка 131: подобрать монтаж такой длины, с, по разбору demo.rmv и напечатать')
    ap.add_argument('--check-cuts', metavar='PMF', help='правка 131: гейт монтажа PMF по его .json (склейки, «DEMO», движение, длина) '
                    'и сверка кадров PMF с перемонтажом (PSNR)')
    ap.add_argument('--check', metavar='CUTS', help='правка 131: гейт монтажа строкой (без PMF)')
    a = ap.parse_args()
    if a.verify: sys.exit(1 if verify(a.verify, a.ref) else 0)
    if a.selftest: sys.exit(0 if selftest(a.out, a.ref) else 1)
    if a.auto:
        print(auto_cuts(scan('demo'), a.auto)); sys.exit(0)
    if a.check_cuts: sys.exit(1 if check_pmf_cuts(a.check_cuts) else 0)
    if a.check:   # только монтаж строкой, без кодирования (отрицательные контроли tools/boot_gate.sh)
        f = check_cuts(a.check); print(('FAIL: ' + f[0]) if f else 'OK: монтаж годен (правка 131)'); [print('  - ' + x) for x in f[1:]]
        sys.exit(1 if f else 0)
    print(f'icon1: монтаж {a.cuts}')
    fr = montage(a.cuts)
    es = encode(fr, a.crf, a.profile, '2.1' if a.profile != 'high' else '3.0')
    aus = split_aus(es)
    if len(aus) != len(fr): raise SystemExit(f'icon1: x264 дал {len(aus)} кадров из {len(fr)}')
    pmf = mux(aus)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_bytes(pmf)
    print(f'icon1: {a.out}: {len(fr)} кадров ({len(fr) * TICK / 90000:.2f} с), {len(pmf)} Б')
    import json   # правка 131: монтаж рядом — по нему гейт --check-cuts перемонтирует и сверяет кадры
    Path(a.out).with_suffix('.json').write_text(json.dumps(dict(cuts=a.cuts, crf=a.crf, frames=len(fr), bytes=len(pmf)), ensure_ascii=False, indent=1))
    if a.sheet: contact_sheet(fr, a.sheet)
    sys.exit(1 if verify(a.out, a.ref) else 0)


if __name__ == '__main__':
    main()
