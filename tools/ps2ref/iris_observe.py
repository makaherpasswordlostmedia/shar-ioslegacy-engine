#!/usr/bin/env python3
"""Н2.3 · ирис «кружок к центру»: iris.p3d (диск) против покадрового замера записи оригинала.

Запись: внешняя, YouTube bziOipI4gDI (PS2, 60 кадров/с, без комментария) — не наш PCSX2, ввода нет.
Меряем радиус круга по самой широкой освещённой строке 4:3-картинки (в долях высоты), центр, тёмную паузу.
Проверки против данных: порядок, прямая (не плавная), симметрия, темп. Каждая проверка сначала падает на синтетике.
  python3 tools/ps2ref/iris_observe.py [--video ...] [--out build/ps2ref/iris]
"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
VIDEO = ROOT / 'build/ps2ref/external/yt-bziOipI4gDI.mp4'
DATA = ROOT / 'build/ps2ref/data/data.json'
W, H, X0, X1 = 960, 540, 120, 840          # 16:9 кадр, 4:3 картинка 720x540 в центре
HALF_DIAG = float(np.hypot(360, 270) / 540)  # 0.8333: круг такого радиуса закрывает весь экран
LIT, DARK = 28, 22                          # чёрный у YouTube ≈ 16
MIN_N = 12


def raw(video, args, pix='gray'):
    return subprocess.run(['ffmpeg', '-v', 'error', *args[:-1], '-i', str(video), '-vf', args[-1],
                           '-f', 'rawvideo', '-pix_fmt', pix, '-'], capture_output=True, check=True).stdout


def find_events(video):
    """Тёмные куски ≥0.5 с, у которых по краям картинка — круг по центру (иначе это затемнение сцены)."""
    b = raw(video, ['fps=4,scale=160:90'])
    m = np.frombuffer(b, np.uint8).reshape(-1, 90, 160)[:, :, 22:138].astype(float).mean((1, 2))
    ev, i = [], 0
    while i < len(m):
        j = i
        while j < len(m) and m[j] < DARK: j += 1
        if j - i >= 2: ev.append(i / 4)
        i = max(j, i + 1)
    return ev


def measure(video, t):
    b = raw(video, ['-ss', str(t - 1.0), '-t', '5.5', f'scale={W}:{H}'])
    f = np.frombuffer(b, np.uint8).reshape(-1, H, W)[:, :, X0:X1] > LIT
    rows = []
    for i, m in enumerate(f):
        n = int(m.sum())
        if n < 20: rows.append((i, 'dark', 0.0, None, None)); continue
        if n > 0.97 * m.size: rows.append((i, 'full', None, None, None)); continue
        cy = int(np.argmax(m.sum(1))); xs = np.nonzero(m[cy])[0]
        if xs.min() == 0 or xs.max() == m.shape[1] - 1: rows.append((i, 'clip', None, None, cy / 540)); continue
        # круг ли это: доля освещённого в описанном квадрате ≈ π/4
        r = (xs.max() - xs.min() + 1) / 2; cx = (xs.min() + xs.max()) / 2
        box = m[max(0, int(cy - r)):int(cy + r) + 1, int(cx - r):int(cx + r) + 1]
        fill = box.mean() if box.size else 0
        rows.append((i, 'disc' if abs(fill - np.pi / 4) < 0.08 else 'other', r / 540, cx / 720, cy / 540))
    return rows


def phases(rows):
    """Разбить на закрытие/открытие; оставить только кадры с новым значением (повторы — просадка частоты игры)."""
    d = [(i, r) for i, k, r, _, _ in rows if k == 'disc']
    if len(d) < 8: return None
    i = np.array([a for a, _ in d], float); r = np.array([b for _, b in d])
    g = int(np.argmax(np.diff(i)))
    out = []
    for ii, rr in ((i[:g + 1], r[:g + 1]), (i[g + 1:], r[g + 1:])):
        keep = np.r_[True, np.diff(rr) != 0]; out.append((ii[keep], rr[keep]))
    dark = int(i[g + 1] - i[g] - 1)
    return out, dark


def fit(ii, rr):
    t = ii / 60.0
    lin = np.polyfit(t, rr, 1); rl = rr - np.polyval(lin, t)
    # плавная альтернатива: smoothstep по тому же отрезку
    u = (t - t[0]) / max(t[-1] - t[0], 1e-9); s = u * u * (3 - 2 * u)
    A = np.c_[s, np.ones_like(s)]; cs, *_ = np.linalg.lstsq(A, rr, rcond=None); rs = rr - A @ cs
    return dict(slope=float(lin[0]), rms_linear=float(np.sqrt((rl ** 2).mean())), rms_smooth=float(np.sqrt((rs ** 2).mean())), n=len(ii))


def data_model():
    d = json.loads(DATA.read_text())
    a = next(x for x in d['animations'] if x['name'] == 'EXP_p3dGroup1' and x['source'].endswith('iris.p3d'))
    c = next(c for c in a['channels'] if c['id'] == '0x121100')
    f = next(x for x in d['files'] if x['path'].endswith('iris.p3d'))
    return dict(keys=c['keys'], values=c['values'], fps=a['fps'], frames=a['frames'], source=f['path'], sha256=f['sha256'])


def judge(ev, model):
    """ev: список {close, open, dark, centre}. Возвращает проверки как bool."""
    k, v, fps = model['keys'], model['values'], model['fps']
    close_T = (k[1] - k[0]) / fps; open_T = (k[3] - k[2]) / fps
    # фаза из <12 различимых кадров не судится (пример: 849.5 с — магазин Гила темнеет вместе с ирисом, край ниже порога)
    cl = [e['close'] for e in ev if e['close']['n'] >= MIN_N]; op = [e['open'] for e in ev if e['open']['n'] >= MIN_N]
    order = all(c['slope'] < 0 for c in cl) and all(o['slope'] > 0 for o in op) and v[0] > v[1] and v[3] > v[2]
    linear = all(x['rms_linear'] < 0.02 and x['rms_linear'] < x['rms_smooth'] for x in cl + op)
    ratio = np.median([-c['slope'] for c in cl]) / np.median([o['slope'] for o in op])
    symmetric = abs(ratio - close_T / open_T) < 0.05
    # масштаб 1 закрывает экран (видно целиком до сжатия) ⇒ радиус при 1 ≥ HALF_DIAG ⇒ закрытие ≥ HALF_DIAG/скорость
    min_close = HALF_DIAG / np.median([-c['slope'] for c in cl])
    tempo = min_close <= close_T * 1.15
    centred = all(abs(e['centre'][0] - 0.5) < 0.01 and abs(e['centre'][1] - 0.5) < 0.01 for e in ev)
    return dict(judged_phases=len(cl) + len(op), skipped_phases=2 * len(ev) - len(cl) - len(op), order=bool(order), linear=bool(linear), symmetric=bool(symmetric), tempo_matches_data=bool(tempo), centred=bool(centred),
                close_nominal_s=close_T, close_observed_min_s=float(min_close), tempo_ratio=float(min_close / close_T), slope_ratio=float(ratio))


def synth(kind, slope=1.29):
    """Синтетическое событие в формате замера: нужно, чтобы каждая проверка умела падать и проходить."""
    def seg(sign, ease=False):
        t = np.arange(31) / 60.0; u = t / t[-1]
        r = (HALF_DIAG * 0.8) * ((u * u * (3 - 2 * u)) if ease else u)
        rr = r if sign > 0 else r[::-1]
        return fit(np.arange(31, dtype=float), rr * (slope * t[-1] / (HALF_DIAG * 0.8)))
    c, o = seg(-1, kind == 'smooth'), seg(+1, kind == 'smooth')
    if kind == 'reversed': c, o = o, c
    return dict(close=c, open=o, dark=100, centre=(0.5, 0.5))


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--video', type=Path, default=VIDEO)
    p.add_argument('--out', type=Path, default=ROOT / 'build/ps2ref/iris'); a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True); model = data_model()

    # 1. Гейт умеет падать: синтетика с заведомо неверной формой/порядком, и умеет проходить темп из данных
    k = model['keys']; nominal_slope = HALF_DIAG / ((k[1] - k[0]) / model['fps'])
    red = dict(smooth_fails_linear=not judge([synth('smooth')], model)['linear'],
               reversed_fails_order=not judge([synth('reversed')], model)['order'],
               nominal_tempo_passes=judge([synth('linear', nominal_slope)], model)['tempo_matches_data'],
               half_tempo_fails=not judge([synth('linear', nominal_slope / 2)], model)['tempo_matches_data'],
               linear_passes_linear=judge([synth('linear')], model)['linear'])
    for kk, ok in red.items(): print(('RED/GREEN control OK ' if ok else 'CONTROL BROKEN ') + kk)
    if not all(red.values()): sys.exit('FAIL: контроль гейта не сработал')

    # 2. Замер оригинала
    evs, tsv = [], ['event_s\tframe\tkind\tradius_h\tcentre_x\tcentre_y']
    for t in find_events(a.video):
        rows = measure(a.video, t); ph = phases(rows)
        if ph is None: continue
        (ci, cr), (oi, orr), dark = ph[0][0], ph[0][1], ph[1]
        if len(ci) < 8 or len(oi) < 8: continue
        cen = [(x, y) for _, kd, _, x, y in rows if kd == 'disc']
        evs.append(dict(t=t, close=fit(ci, cr), open=fit(oi, orr), dark=dark,
                        centre=tuple(np.median(np.array(cen), 0).round(4).tolist())))
        tsv += [f'{t}\t{i}\t{kd}\t{"" if r is None else round(r, 4)}\t{"" if x is None else round(x, 4)}\t{"" if y is None else round(y, 4)}'
                for i, kd, r, x, y in rows]
    if len(evs) < 3: sys.exit(f'FAIL: найдено событий ириса {len(evs)} < 3')
    res = judge(evs, model)
    (a.out / 'iris.tsv').write_text('\n'.join(tsv) + '\n')
    rep = dict(video=str(a.video.relative_to(ROOT)), video_sha256=hashlib.sha256(a.video.read_bytes()).hexdigest(),
               source='YouTube bziOipI4gDI, PS2, 60 fps; внешняя запись, ввода нет', model=model, events=evs, checks=res, controls=red)
    (a.out / 'report.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False) + '\n')
    for e in evs:
        print(f"{e['t']:7.2f}s close {e['close']['slope']:+.3f} h/s rms {e['close']['rms_linear']:.4f} | open {e['open']['slope']:+.3f} rms {e['open']['rms_linear']:.4f} | dark {e['dark']} f | centre {e['centre']}")
    print('CHECKS', json.dumps(res, ensure_ascii=False))
    print('RESULT: порядок/прямая/симметрия/центр', 'PASS' if all(res[x] for x in ('order', 'linear', 'symmetric', 'centred')) else 'FAIL',
          '· темп против данных', 'PASS' if res['tempo_matches_data'] else f"FAIL (закрытие ≥{res['close_observed_min_s']:.3f} с против {res['close_nominal_s']:.3f} с в данных)")


if __name__ == '__main__':
    main()
