#!/usr/bin/env python3
"""Близнецы: проба «машина с курсом на линию» у заданных точек (забор, стена) на оригинале, кадры по одному.
  python3 tools/twins/fence_probe.py --level 1 --out fence_x ID:X:Z:ЙАУ [ID:X:Z:ЙАУ ...]   (X, Z — оси ПОРТА; ЙАУ — курс оригинала в градусах: 0 = +z, 90 = +x, 180 = -z)
Ставит машину в точку на верхнюю опору (--top) или нижнюю, 2,5 с покоя, 2 с газа с заданным курсом; результат build/twins/<out>/l<N>/orig.jsonl,
sessions/*/trace.tsv (кадр, проба, фаза, x y z курс v vy cx cy cz ...). PLACEMENT_LOCKSTEP=1 даёт строку на кадр. Всё через tools/twins/placement.py (run_orig),
курс ставится как «B-проход» (+90 к фиктивному A), поэтому у пробы курс = заданный. Точки без опоры и внутри объёмов пропускаются."""
import sys, os, math, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import placement as PL, common as C

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--level', type=int, default=1); ap.add_argument('--out', required=True)
    ap.add_argument('--top', action='store_true', help='верхняя опора (крыша, площадка) вместо нижней'); ap.add_argument('--gas', type=float, default=2.0)
    ap.add_argument('pts', nargs='+'); a = ap.parse_args()
    P = []
    for t in a.pts:
        i, x, z, yw = t.split(':'); P.append((i, float(x), float(z), float(yw)))
    lv = a.level; src = C.OUT / 'placement' / f'l{lv}'; dst = C.OUT / a.out / f'l{lv}'; dst.mkdir(parents=True, exist_ok=True)
    skip = ('orig.jsonl', 'plan.json', 'points.tsv', 'sessions', 'port.jsonl', 'compare.tsv', 'trials.tsv', 'summary.json')
    for n in os.listdir(src):
        if n in skip or n.startswith('compare') or n.startswith('plan'): continue
        if not (dst / n).exists(): (dst / n).symlink_to(src / n)
    PL.out_dir = lambda level: C.OUT / a.out / f'l{level}'
    pr, _ = PL.light(lv, 'probe', [f'{i} {x:.3f} {z:.3f}' for i, x, z, _ in P]); RI = PL.RegionIndex(lv)
    rows, ok, recs = [], [], []
    for (i, x, z, yw), p in zip(P, pr):
        L = p['layers']
        if not L: print(i, 'нет опоры'); continue
        li = 0 if a.top else len(L) - 1; y, ny, mat, d0, d90, obj = L[li]
        if ny < 0.5 or min(d0, d90) > 0.8: print(i, 'пропуск (наклон/внутри объёма)', ny, d0, d90); continue
        regs = sorted(RI.near(x, z)); layer = len(L) - 1 - li
        rows.append(f"{i}\tprobe\t{x}\t{y}\t{z}\t{PL.code(x, z)}\t{layer}\t{len(L)}\t{','.join(regs) or '-'}\t{d0:.2f}\t{d90:.2f}\t{obj}\tfence_probe")
        ok.append(i); recs.append(dict(id=i + '_A', point=i, before=dict(yaw=math.radians(yw - 90)), version=PL.VERSION))
    (dst / 'points.tsv').write_text('# fence_probe\nid\tвид\tx\ty\tz\tклетка\tслой\tопор\tрегионы\tглубина0\tглубина90\tобъект\tисточник\n' + '\n'.join(rows) + '\n')
    with open(dst / 'orig.jsonl', 'w') as f:
        for r in recs: f.write(json.dumps(r) + '\n')
    PL.orig_records = lambda level: [json.loads(l) for l in open(dst / 'orig.jsonl')]
    PL.GAS_S = a.gas
    print('точки', ok); PL.run_orig(lv, None, per=3, only=set(ok))

if __name__ == '__main__':
    main()
