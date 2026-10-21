#!/usr/bin/env python3
"""Сравнение двух туров с PSP построчно по сценам: что выросло, что упало.
  python3 tools/tour_compare.py ТУР_А ТУР_Б [--out файл.md]      (А — база, Б — новый; сцены сопоставляются по имени без префикса T19_/T20_/…)
Берёт из smoke.txt: STAT (p95/пропуски), RBLD (мс по подсистемам), PHSEC (сборка списка, ожидание GE/vblank, разбивка x_*), PHDRAW (вызовы/ктрисы по подсистемам),
RFAST (дальность, ктрисы, вызовы, смены текстур), PHSUB, PBPROF (если есть), CAMCLIPSTAT, LOADREAD, LEVEL (время загрузки уровня). Первые 2 с сцены отброшены (settle)."""
import re, sys, argparse
from collections import defaultdict
from pathlib import Path


def kv(ln):
    d = {}
    for k, v in re.findall(r'(\w+)=([^\s]+)', ln): d.setdefault(k, v)   # первое вхождение (в PHDRAW после «kw:» повторяются те же имена)
    return d


def fl(x):
    try: return float(str(x).split('/')[0])
    except Exception: return None


def parse(d):
    L = (Path(d) / 'smoke.txt').read_text(errors='replace').splitlines()
    sc_t0 = {}; stat = {}; rows = defaultdict(lambda: defaultdict(list)); loads = []; levels = []; cam = defaultdict(lambda: [0, 0, 0, 0]); pbp = defaultdict(list)
    cur = None; gg = []; xcity = []
    for ln in L:
        if ln.startswith('SCENE '):
            p = ln.split(); cur = p[1]; sc_t0[cur] = float(p[2])
        elif ln.startswith('STAT '):
            p = ln.split(); k = dict(zip(p[2::2], p[3::2]))
            if k.get('frames', '0') != '0': stat[p[1]] = k
        elif ln.startswith(('RBLD ', 'PHSEC ', 'PHDRAW ', 'PHSUB ', 'RFAST ')):
            k = kv(ln); n = k.get('sc') or k.get('scene'); t = fl(k.get('t')) if k.get('t') else None
            if not n or n not in sc_t0 or (t is not None and t < sc_t0[n] + 2.0): continue
            tag = ln.split()[0]
            if tag == 'PHSEC' and 'x_city' in k and t is not None: xcity.append((t, n, fl(k['x_city'])))
            if tag == 'PHDRAW':   # city=612/39.2/96: вызовы/ктрисы/привязки
                for key in ('city', 'car3d', 'npc', 'trf', 'mcr', 'props', 'fx'):
                    v = k.get(key)
                    if v and '/' in v:
                        a = v.split('/'); rows[n][f'draw_{key}_calls'].append(float(a[0])); rows[n][f'draw_{key}_ktris'].append(float(a[1]))
            else:
                for key, v in k.items():
                    if key in ('t', 'sc', 'scene', 'n', 'old', 'name'): continue
                    f = fl(v)
                    if f is not None: rows[n][f'{tag}.{key}'].append(f)
        elif ln.startswith('CAMCLIPSTAT '):
            k = kv(ln); n = None
            t = fl(k.get('t'))
            for s, t0 in sorted(sc_t0.items(), key=lambda x: x[1]):
                if t0 <= (t or 0) - 0.5: n = s
            if n:
                c = cam[n]; c[0] += fl(k.get('eye_inside')) or 0; c[1] += fl(k.get('near03')) or 0; c[2] = max(c[2], fl(k.get('clip_pieces_max')) or 0); c[3] += fl(k.get('wall_vox')) or 0
        elif ln.startswith('GGSTAT '):
            k = kv(ln); gg.append((fl(k.get('t')), fl(k.get('frames')), fl(k.get('ggOn'))))
        elif ln.startswith('PBPROF '):
            pbp[cur].append(ln)
        elif ln.startswith('LOADREAD '):
            k = kv(ln); loads.append((fl(k.get('t')), fl(k.get('ms')), fl(k.get('frames')), fl(k.get('skip'))))
        elif ln.startswith('LEVEL ') and 'ev=load' in ln:
            k = kv(ln); levels.append((int(fl(k.get('n'))), fl(k.get('ms')), fl(k.get('t')), fl(k.get('heap'))))
    return sc_t0, stat, rows, loads, levels, cam, pbp, gg, xcity


def base(n): return n.split('_', 1)[1] if '_' in n else n


def mean(a): return sum(a) / len(a) if a else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('a'); ap.add_argument('b'); ap.add_argument('--out'); a = ap.parse_args()
    A = parse(a.a); B = parse(a.b)
    ma = {base(n): n for n in A[1]}; mb = {base(n): n for n in B[1]}
    common = [b for b in mb if b in ma]
    out = [f'# Сравнение туров · А (база) {Path(a.a).name} ↔ Б {Path(a.b).name}', '', f'Сцен у А: {len(ma)}, у Б: {len(mb)}, общих по имени: {len(common)}. Первые 2 с каждой сцены отброшены. Дельта = Б − А.', '']
    out += ['## 1. Время кадра по сценам', '', '| сцена | p95 А → Б | дельта | пропуски % А → Б | кадров А/Б |', '|---|---|---|---|---|']
    for b in common:
        sa, sb = A[1][ma[b]], B[1][mb[b]]
        pa, pb = fl(sa['p95']), fl(sb['p95']); fa, fb = fl(sa['frames']), fl(sb['frames'])
        out.append(f'| {b} | {pa:.1f} → {pb:.1f} | {pb - pa:+.1f} | {100 * fl(sa["missed"]) / fa:.1f} → {100 * fl(sb["missed"]) / fb:.1f} | {fa:.0f}/{fb:.0f} |')
    keys = [('RBLD.city', 'city'), ('RBLD.props', 'props'), ('RBLD.fx', 'fx'), ('RBLD.car', 'car'), ('RBLD.npc', 'npc'), ('RBLD.trf', 'trf'), ('RBLD.mcr', 'mcr'), ('RBLD.ui', 'ui'),
            ('RBLD.drawpiece', 'drawpiece/кадр'), ('PHSEC.build', 'сборка списка'), ('PHSEC.gesync', 'ждём GE'), ('PHSEC.vbl', 'ждём vblank'), ('RFAST.dd', 'дальность, м'),
            ('RFAST.ktris', 'ктрисы'), ('RFAST.draws', 'вызовы'), ('RFAST.binds', 'смены текстур'), ('RFAST.work_ms', 'работа кадра')]
    out += ['', '## 2. Подсистемы, среднее по сцене (мс на кадр, где не сказано иное): А → Б (дельта), показаны только сдвиги больше 0,5 / 5 %', '']
    summary = defaultdict(list)
    for b in common:
        ra, rb = A[2][ma[b]], B[2][mb[b]]
        diffs = []
        for key, nm in keys:
            xa, xb = mean(ra.get(key, [])), mean(rb.get(key, []))
            if xa is None or xb is None: continue
            d = xb - xa; summary[nm].append(d)
            if abs(d) >= max(0.5, 0.05 * abs(xa)) or (key == 'RFAST.dd' and abs(d) >= 5) or (key in ('RFAST.ktris', 'RFAST.draws', 'RFAST.binds', 'RBLD.drawpiece') and abs(d) >= 0.08 * abs(xa)):
                diffs.append(f'{nm} {xa:.1f}→{xb:.1f} ({d:+.1f})')
        out.append(f'- **{b}**: ' + ('; '.join(diffs) if diffs else 'без заметных сдвигов'))
    out += ['', '### Среднее изменение по всем общим сценам', '', '| подсистема | среднее Δ | сцен выросло | сцен упало |', '|---|---|---|---|']
    for key, nm in keys:
        v = summary.get(nm)
        if v: out.append(f'| {nm} | {sum(v) / len(v):+.2f} | {sum(1 for x in v if x > 0.05)} | {sum(1 for x in v if x < -0.05)} |')
    # PHDRAW
    dk = ['city', 'props', 'fx', 'car3d', 'trf']
    out += ['', '## 3. Вызовы и ктрисы по подсистемам (PHDRAW), среднее по общим сценам: А → Б', '', '| подсистема | вызовы | ктрисы |', '|---|---|---|']
    for k in dk:
        ca = [mean(A[2][ma[b]].get(f'draw_{k}_calls', [])) for b in common]; cb = [mean(B[2][mb[b]].get(f'draw_{k}_calls', [])) for b in common]
        ta = [mean(A[2][ma[b]].get(f'draw_{k}_ktris', [])) for b in common]; tb = [mean(B[2][mb[b]].get(f'draw_{k}_ktris', [])) for b in common]
        f = lambda x: mean([y for y in x if y is not None])
        out.append(f'| {k} | {f(ca):.0f} → {f(cb):.0f} | {f(ta):.1f} → {f(tb):.1f} |')
    # CAMCLIPSTAT
    out += ['', '## 4. Камера (CAMCLIPSTAT), сумма кадров по сцене: Б (у А строки не было)', '', '| сцена | глаз в ящике | ближе 0,3 м к ящику | макс. кусков под плоскостью | wall_vox |', '|---|---|---|---|---|']
    for b in common:
        c = B[5].get(mb[b])
        if c and (c[0] or c[1] or c[3]): out.append(f'| {b} | {c[0]:.0f} | {c[1]:.0f} | {c[2]:.0f} | {c[3]:.0f} |')
    # ggOn: срез города на CPU для всего кадра (ближняя плоскость < NEAR_Z); доля кадров по сцене и цена x_city внутри одного тура
    out += ['', '## 4б. ggOn (срез города на CPU): доля кадров по сцене, А → Б', '', '| сцена | ggOn А, % | ggOn Б, % |', '|---|---|---|']
    def gshare(X, names, key):
        r = {}
        for t, fr, on in X[7]:
            n = None
            for s0, t0 in X[0].items():
                if t0 <= (t or 0) - 0.5 and (n is None or t0 > X[0][n]): n = s0
            if n and t >= X[0][n] + 2.0: c = r.setdefault(base(n), [0.0, 0.0]); c[0] += fr; c[1] += on
        return r
    ga, gb = gshare(A, ma, 0), gshare(B, mb, 0)
    for b in common:
        xa, xb = ga.get(b), gb.get(b)
        f = lambda x: f'{100 * x[1] / x[0]:.0f}' if x and x[0] else '—'
        if (xa and xa[1]) or (xb and xb[1]): out.append(f'| {b} | {f(xa)} | {f(xb)} |')
    for nm, X in (('А', A), ('Б', B)):
        gmap = {round(t, 1): (on, fr) for t, fr, on in X[7]}; on_, off_ = [], []
        for t, n, c in X[8]:
            if n not in X[0] or t < X[0][n] + 2.0: continue
            g = None
            for dt in (0, .1, -.1, .2, -.2):
                g = gmap.get(round(t + dt, 1)) or g
                if g: break
            if not g or g[1] <= 0: continue
            if g[0] / g[1] >= 0.9: on_.append(c)
            elif g[0] == 0: off_.append(c)
        if on_ and off_: out.append(f'\nТур {nm}: x_city в секундах с ggOn ≥ 90 % кадров — {sum(on_) / len(on_):.1f} мс ({len(on_)} с), без ggOn — {sum(off_) / len(off_):.1f} мс ({len(off_)} с)')
    # загрузка уровня
    out += ['', '## 5. Загрузка уровня (LEVEL ev=load, мс) и чтение под газетой (LOADREAD)', '', '| уровень | А, мс | Б, мс | дельта |', '|---|---|---|---|']
    la = {n: ms for n, ms, t, h in A[4]}; lb = {n: ms for n, ms, t, h in B[4]}
    for n in sorted(set(la) | set(lb)):
        x, y = la.get(n), lb.get(n)
        out.append(f'| {n} | {x if x is not None else "—"} | {y if y is not None else "—"} | {(y - x):+.0f} |' if x is not None and y is not None else f'| {n} | {x if x is not None else "—"} | {y if y is not None else "—"} | — |')
    out += ['', '| LOADREAD (газета при смене уровня и старте) | А: мс (кадров, пропущено) | Б: мс (кадров, пропущено) |', '|---|---|---|']
    for i in range(max(len(A[3]), len(B[3]))):
        ra = A[3][i] if i < len(A[3]) else None; rb = B[3][i] if i < len(B[3]) else None
        fmt = lambda r: f'{r[1]:.0f} ({r[2]:.0f}, {r[3]:.0f}) t={r[0]:.0f}' if r else '—'
        out.append(f'| #{i + 1} | {fmt(ra)} | {fmt(rb)} |')
    txt = '\n'.join(out) + '\n'
    Path(a.out).write_text(txt) if a.out else print(txt)


if __name__ == '__main__':
    main()
