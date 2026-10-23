#!/usr/bin/env python3
"""Ночные боты (№876): утренний отчёт по NIGHT_DIR/runs -> NIGHT_DIR/report.html + листы PNG + сводка текстом.
  python3 tools/night/night_report.py NIGHT_DIR
Исследователь: на точку (сцена P###) — выброс GE (DIAGS citydrop+listdrop+drop_car), камера в теле (CAMCLIPSTAT eye_inside),
недогруженные клетки в кадре (BB miss), медленные кадры (SLOWFRAME); подозрительные — в начало, с 4 фото. Гэги — лист 2 кадров на гэг.
Долгая игра — куча после каждой загрузки уровня (LEVEL ev=load heap/mx) по кругам: тренд вниз = утечка/дробление."""
import html, re, sys
from pathlib import Path
from PIL import Image, ImageDraw

N = Path(sys.argv[1]); R = N / 'runs'; out = []; text = []


def scenes(p):
    cur = None; S = {}
    for ln in open(p, errors='ignore'):
        if ln.startswith('SCENE '): cur = ln.split()[1]; S.setdefault(cur, {'drop': 0, 'eye': 0, 'miss': 0, 'slow': 0, 'pos': ''}); continue
        if cur is None: continue
        s = S[cur]
        if ln.startswith('DIAGS'):
            k = dict(re.findall(r'(\w+)=(\d+)', ln)); s['drop'] += int(k.get('drop_city', 0)) + int(k.get('listdrop', 0)) + int(k.get('drop_car', 0))   # №877: кольцо неба (drop_sky) не в счёт — его закрывает подстилка земли
        elif ln.startswith('SLOWFRAME'): s['slow'] += 1 if s.get('bb', 0) >= 2 else 0   # первые 2 с после телепорта — подгрузка, не в счёт
        elif ln.startswith('BB '):
            f = ln.split(); s['bb'] = s.get('bb', 0) + 1; s['pos'] = ' '.join(f[3:5]) + f' ({f[5]}, {f[7]})' if len(f) > 8 else s['pos']
            if 'miss' in f: s['miss'] = int(f[f.index('miss') + 1])   # последняя секунда точки: подгрузка после телепорта закончилась
    return S


def sheet(files, path, cols=4, w=240, h=136, labels=None):
    ims = [f for f in files if f.exists()]
    if not ims: return None
    rows = (len(ims) + cols - 1) // cols; im = Image.new('RGB', (cols * w, rows * (h + 14)), (20, 20, 20)); d = ImageDraw.Draw(im)
    for i, f in enumerate(ims):
        x, y = (i % cols) * w, (i // cols) * (h + 14)
        im.paste(Image.open(f).convert('RGB').resize((w, h)), (x, y + 14)); d.text((x + 3, y + 1), (labels[i] if labels else f.stem), fill=(230, 230, 230))
    im.save(path); return path.name


out.append('<h2>Исследователь</h2>')
for L in range(1, 8):
    d = R / f'explore_L{L}'
    if not (d / 'smoke.txt').exists(): out.append(f'<p>L{L}: нет журнала</p>'); continue
    S = {k: v for k, v in scenes(d / 'smoke.txt').items() if k.startswith('P')}
    bad = sorted(S.items(), key=lambda kv: -(kv[1]['drop'] + 10 * kv[1]['miss'] + kv[1]['slow']))
    flagged = [(k, v) for k, v in bad if v['drop'] or v['miss'] or v['slow'] > 2][:24]
    text.append(f'L{L}: точек {len(S)}, подозрительных {len(flagged)} (выброс GE в {sum(1 for v in S.values() if v["drop"])}, недогруженные клетки в {sum(1 for v in S.values() if v["miss"])}, медленные кадры в {sum(1 for v in S.values() if v["slow"] > 2)})')
    out.append(f'<h3>L{L}</h3><p>{html.escape(text[-1])}</p>')
    for k, v in flagged:
        i = int(k[1:]); nm = sheet([d / f'e{i:03d}_{j}.png' for j in range(4)], N / f'ex_L{L}_{k}.png')
        if nm: out.append(f'<p>{k} {html.escape(v["pos"])} · выброс {v["drop"]} · недогруз {v["miss"]} · медленных {v["slow"]}</p><img src="{nm}">')
    allf = sorted(d.glob('e*_0.png'))
    nm = sheet(allf, N / f'ex_L{L}_all.png', cols=10, w=160, h=90)
    if nm: out.append(f'<p>все точки (первое фото каждой):</p><img src="{nm}">')
out.append('<h2>Очень дальние виды (бот-репортёр)</h2>')
import numpy as np, csv, shutil
SC = Path.home() / 'Downloads/shar-psp-render-w/build/scout'
for L in range(1, 8):
    f = SC / f'l{L}.csv'
    if not f.exists(): continue
    rows = [r for r in csv.DictReader(open(f)) if r.get('px250') not in (None, '') and r.get('pieces_d250') not in (None, '')]; tot = 128 * 72
    far = np.array([(float(r['px250']) / tot) for r in rows]); far2 = np.array([(float(r['px200']) + float(r['px250'])) / tot for r in rows])
    pid = np.array([int(r['point']) for r in rows]); xs = np.array([float(r['x']) for r in rows]); zs = np.array([float(r['z']) for r in rows])
    need = far > .01; pts = np.unique(pid[need]); allp = np.unique(pid)
    zones = set((int(x // 40), int(z // 40)) for x, z in zip(xs[need], zs[need]))
    text.append(f'L{L}: мест (точек 10 м), где в каком-то направлении нужна даль 250 м: {len(pts)} из {len(allp)} ({100 * len(pts) / max(len(allp), 1):.0f}%), клеток 40 м: {len(zones)}; дальше 140 м заметно (> 1% экрана) в {100 * (far2 > .01).mean():.0f}% ракурсов')
    out.append(f'<p>{html.escape(text[-1])}</p>')
    for nm_ in (f'l{L}_dal.png', f'l{L}_load.png'):
        if (SC / nm_).exists(): shutil.copy(SC / nm_, N / nm_); out.append(f'<img src="{nm_}" style="margin-right:8px">')
out.append('<h2>Гэги</h2>')
for L in range(1, 8):
    d = R / f'gags_L{L}'
    if not (d / 'smoke.txt').exists(): continue
    names = {int(m.group(1)): (m.group(2), int(m.group(3))) for m in re.finditer(r'GAG idx=(\d+) name=(\S+) room=\S+ inst=\S+ nskin=(\d+)', (d / 'smoke.txt').read_text(errors='ignore'))}
    files, labels = [], []
    for k, (nm_, ns) in sorted(names.items()):
        if ns <= 0: continue
        for s_ in 'ab': files.append(d / f'g{k:02d}_{s_}.png'); labels.append(f'{nm_} {s_}')
    nm = sheet(files, N / f'gags_L{L}.png', cols=6, w=200, h=113, labels=labels)
    text.append(f'L{L}: гэгов с персонажами {sum(1 for v in names.values() if v[1] > 0)}')
    if nm: out.append(f'<h3>L{L}</h3><img src="{nm}">')
out.append('<h2>Долгая игра</h2>')
sk = R / 'soak' / 'smoke.txt'
if sk.exists():
    t = sk.read_text(errors='ignore'); loads = re.findall(r'LEVEL ev=load n=(\d+) .*? heap=(\d+) mx0=\d+ mx=(\d+)', t)
    end = '^END$' in t or '\nEND\n' in t
    rows = ''.join(f'<tr><td>{i + 1}</td><td>L{n}</td><td>{int(h) / 1048576:.2f}</td><td>{int(m) / 1048576:.2f}</td></tr>' for i, (n, h, m) in enumerate(loads))
    text.append(f'долгая игра: загрузок {len(loads)}, доиграла до конца: {"да" if end else "НЕТ"}; куча после загрузки, МБ: ' + ' '.join(f'{int(h) / 1048576:.1f}' for _, h, _ in loads))
    out.append(f'<p>{html.escape(text[-1])}</p><table border=1 cellpadding=3><tr><th>№</th><th>уровень</th><th>куча, МБ</th><th>крупнейший кусок, МБ</th></tr>{rows}</table>')
(N / 'report.html').write_text('<html><meta charset="utf-8"><body style="background:#111;color:#ddd;font-family:sans-serif">'
                               '<h1>Ночные боты</h1><pre>' + html.escape('\n'.join(text)) + '</pre>' + '\n'.join(out) + '</body></html>')
print('\n'.join(text)); print('отчёт:', N / 'report.html')
