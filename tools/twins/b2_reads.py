#!/usr/bin/env python3
"""Близнецы · Б2: что оригинал читает с диска на маршруте (журнал чтений PCSX2 → файлы диска и архивов RCF).

  python3 tools/twins/b2_reads.py ANSWER_ID [--log EMULOG] [--recipe RECIPE.json]
      ANSWER_ID — прогон ask.py (build/ps2ref/answers/<id>/), снятый с CdvdVerboseReads = true и EnableFileLogging = true
      в своём профиле наблюдателя (журнал data/logs/emulog.txt перезаписывается каждым запуском — копируется в прогон).
Выход build/twins/b2/<id>/: reads.tsv (время игры, сектор, блоков, файлы), files.tsv (файл: байт прочитано, первое время, точка
маршрута), hops.tsv (точка: секунды, байт, МБ/с), summary.md. Время журнала PCSX2 сводится с кадрами по событиям сохранения снимков
(«Saving state to slot») — те же кадры, что shots рецепта. Журнал чтений и таблица файлов — данные, не код игры (БЛИЗНЕЦЫ §4)."""
import argparse, json, re, shutil, statistics, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import isomap

READ = re.compile(r'^\[\s*([\d.]+)\]\s+(DvdRead|CDRead|CdAudioRead): Reading Sector (\d+) \((\d+) Blocks of Size (\d+)\)')
SAVE = re.compile(r'^\[\s*([\d.]+)\]\s+OSD \[SaveStateSlot\d+\]: Saving state')


def parse_log(path):
    reads, saves = [], []
    for l in Path(path).read_text(errors='replace').splitlines():
        m = READ.match(l)
        if m: reads.append(dict(t=float(m.group(1)), kind=m.group(2), lsn=int(m.group(3)), blocks=int(m.group(4)))); continue
        m = SAVE.match(l)
        if m: saves.append(float(m.group(1)))
    return reads, saves


def align(ans, recipe, saves):
    """смещение: время журнала − t_mac трассы, по снимкам (кадр снимка → t_mac первой строки трассы не раньше кадра)"""
    rows = [l.split('\t') for l in (ans / 'trace.tsv').read_text().splitlines()]
    head, rows = rows[0], rows[1:]
    it, ir = head.index('t_mac'), head.index('rel')
    tr = [(float(r[ir]), float(r[it])) for r in rows]
    shots = sorted(int(x) for x in recipe.get('shots', []))
    d = []
    for k, s in zip(shots, saves):
        t = next((tm for rel, tm in tr if rel >= k), None)
        if t is not None: d.append(s - t)
    if not d: raise SystemExit('нет событий сохранения для сведения времени')
    off = statistics.median(d)
    return off, tr, (max(d) - min(d)) if len(d) > 1 else 0.0


def frame_at(tr, t_mac):
    best = None
    for rel, tm in tr:
        if tm <= t_mac: best = rel
        else: break
    return best if best is not None else 0


FRAMELOG = re.compile(r'^\[кадр (\d+)\]\s*\[\s*[\d.]+\]\s+(DvdRead|CDRead|CdAudioRead): Reading Sector (\d+) \((\d+) Blocks')


def from_drive(run_dir, hops=None):
    """журнал drive.py (pcsx2-twins -lockstep, --cdvd): строки «[кадр N] … DvdRead …» — кадр точный, без сведения по времени"""
    run_dir = Path(run_dir); reads = []
    for l in (run_dir / 'log.txt').read_text(errors='replace').splitlines():
        m = FRAMELOG.match(l)
        if m: reads.append(dict(frame=int(m.group(1)), lsn=int(m.group(3)), blocks=int(m.group(4))))
    files = isomap.diskmap(); out = C.OUT / 'b2' / run_dir.name; out.mkdir(parents=True, exist_ok=True)
    pos = {}
    if (run_dir / 'drive.tsv').exists():
        for l in (run_dir / 'drive.tsv').read_text().splitlines()[1:]:
            f = l.split('\t'); pos[int(f[0])] = (float(f[1]), float(f[3]))
    def where(fr):
        k = max((q for q in pos if q <= fr), default=None)
        return f'({pos[k][0]:.0f}, {pos[k][1]:.0f})' if k is not None else '?'
    per_file = defaultdict(lambda: dict(bytes=0, first=None, hop=None, reads=0))
    with (out / 'reads.tsv').open('w') as fo:
        fo.write('кадр\tс\tсектор\tблоков\tфайлы\n')
        for r in reads:
            st, en = r['lsn'] * isomap.SEC, (r['lsn'] + r['blocks']) * isomap.SEC; hit = isomap.files_in(files, st, en)
            for f in hit:
                pf = per_file[f['path']]; pf['bytes'] += min(en, f['end']) - max(st, f['start']); pf['reads'] += 1
                if pf['first'] is None: pf['first'] = r['frame']; pf['hop'] = where(r['frame'])
            fo.write(f"{r['frame']}\t{r['frame'] / 50:.2f}\t{r['lsn']}\t{r['blocks']}\t{' | '.join(f['path'] for f in hit) or '-'}\n")
    size = {f['path']: f['end'] - f['start'] for f in files}
    with (out / 'files.tsv').open('w') as fo:
        fo.write('файл\tпрочитано байт\tразмер\tчтений\tпервый кадр\tточка маршрута\n')
        for p, v in sorted(per_file.items(), key=lambda kv: kv[1]['first']):
            fo.write(f"{p}\t{v['bytes']}\t{size.get(p, 0)}\t{v['reads']}\t{v['first']}\t{v['hop']}\n")
    tot = sum(v['bytes'] for v in per_file.values()); dur = (reads[-1]['frame'] - reads[0]['frame']) / 50 if reads else 1
    print(f'чтений {len(reads)}, файлов {len(per_file)}, {tot / 1048576:.1f} МБ за {dur:.0f} с игры → {out.relative_to(C.DATA)}')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('id'); ap.add_argument('--log'); ap.add_argument('--recipe'); ap.add_argument('--drive', action='store_true')
    a = ap.parse_args()
    if a.drive: from_drive(C.OUT / 'o4' / a.id); return 0
    ans = C.DATA / 'build/ps2ref/answers' / a.id
    log = Path(a.log) if a.log else ans / 'emulog.txt'
    if not log.exists():
        src = C.DATA / 'build/ps2ref/profiles/observer1/data/logs/emulog.txt'
        shutil.copy2(src, log)
    rp = Path(a.recipe) if a.recipe else Path(json.loads((ans / 'report.json').read_text())['recipe'])
    if not rp.is_absolute(): rp = C.DATA / rp
    recipe = json.loads(rp.read_text())
    reads, saves = parse_log(log)
    if not reads: raise SystemExit(f'{log}: строк чтения нет — CdvdVerboseReads выключен?')
    off, tr, spread = align(ans, recipe, saves)
    files = isomap.diskmap()
    hops = recipe.get('hops') or [dict(name='весь прогон', at=0)]
    out = C.OUT / 'b2' / a.id; out.mkdir(parents=True, exist_ok=True)
    per_file = defaultdict(lambda: dict(bytes=0, first=None, hop=None, reads=0))
    per_hop = defaultdict(int)
    with (out / 'reads.tsv').open('w') as fo:
        fo.write('кадр\tс\tсектор\tблоков\tфайлы\n')
        for r in reads:
            rel = frame_at(tr, r['t'] - off)
            hop = max((h for h in hops if h['at'] <= rel), key=lambda h: h['at'], default=None)
            hname = hop['name'] if hop else 'до маршрута'
            start, end = r['lsn'] * isomap.SEC, (r['lsn'] + r['blocks']) * isomap.SEC
            hit = isomap.files_in(files, start, end)
            for f in hit:
                ov = min(end, f['end']) - max(start, f['start'])
                pf = per_file[f['path']]; pf['bytes'] += ov; pf['reads'] += 1
                if pf['first'] is None: pf['first'] = rel; pf['hop'] = hname
            per_hop[hname] += end - start
            fo.write(f"{rel}\t{rel / 50:.2f}\t{r['lsn']}\t{r['blocks']}\t{' | '.join(f['path'] for f in hit) or '-'}\n")
    with (out / 'files.tsv').open('w') as fo:
        fo.write('файл\tпрочитано байт\tразмер\tчтений\tпервый кадр\tточка маршрута\n')
        size = {f['path']: f['end'] - f['start'] for f in files}
        for p, v in sorted(per_file.items(), key=lambda kv: kv[1]['first']):
            fo.write(f"{p}\t{v['bytes']}\t{size.get(p, 0)}\t{v['reads']}\t{v['first']}\t{v['hop']}\n")
    order = ['до маршрута'] + [h['name'] for h in hops]
    with (out / 'hops.tsv').open('w') as fo:
        fo.write('точка\tбайт\tМБ\n')
        for h in order:
            if h in per_hop: fo.write(f"{h}\t{per_hop[h]}\t{per_hop[h] / 1048576:.2f}\n")
    total = sum(per_hop.values()); dur = (max(r['t'] for r in reads) - min(r['t'] for r in reads)) or 1
    groups = defaultdict(int)
    for p, v in per_file.items(): groups[p.split(':')[0] + (':' + p.split(':')[1].split('/')[0] if ':' in p else '')] += v['bytes']
    L = [f'# Б2 · чтения диска оригинала · {a.id}', '',
         f'Время (date): {C.clock()} · журнал {log.name} · строк чтения {len(reads)} · сведение времени по {len(saves)} снимкам '
         f'(смещение {off:.2f} с, разброс {spread:.2f} с)', '',
         f'Всего прочитано {total / 1048576:.1f} МБ за {dur:.0f} с журнала ({total / 1048576 / dur:.2f} МБ/с в среднем); файлов {len(per_file)}', '',
         '| что | МБ |', '|---|---|'] + [f'| {g} | {b / 1048576:.2f} |' for g, b in sorted(groups.items(), key=lambda kv: -kv[1])[:20]] + ['']
    (out / 'summary.md').write_text('\n'.join(L) + '\n')
    print('\n'.join(L[:5]))
    print(f'→ {out.relative_to(C.DATA)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
