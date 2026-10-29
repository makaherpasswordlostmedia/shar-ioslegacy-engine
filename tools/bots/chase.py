#!/usr/bin/env python3
"""Догонялки на всех ядрах (пункт Б4): tools/bots/chase в N процессах с низким приоритетом, сводка «среднее время до поимки
по поколениям» и кластеры: вечный угол (подтверждённый 8 заходами погони), погоня застряла навсегда. Без AI и сети.
  python3 tools/bots/chase.py [--procs 2] [--gens 30] [--pop 16] [--rounds 4] [--seed 1]  -> build/bots/runs/chase/<время>/chase.md
  python3 tools/bots/chase.py --gate                                                        гейт Б4 (красный контроль, потом зелёный)
Каждый кластер проверяется повтором: build/bots/chase LEVEL HOMER ROADS --replay <файл> обязан дать тот же исход в тот же кадр.
Правила поимки и машина погони — правила бота, не игры (см. шапку tools/bots/chase.c)."""
import argparse, concurrent.futures, hashlib, json, math, os, subprocess, sys, time
from pathlib import Path
from clusterkey import cluster_key
ROOT = Path(os.environ.get('BOTS_ROOT') or Path(__file__).resolve().parents[2])   # ночь запускает замороженную копию скрипта (Т1.1)
IN = Path(os.environ.get('BOTS_IN') or ROOT / 'build')   # входы: общие build/ или замороженный комплект ночи
BIN = Path(os.environ.get('BOTS_BIN', ROOT / 'build/bots'))   # ночь играет своей копией бинарников (дневная пересборка их не трогает)
LVL, HOM, RDS = IN / 'level.shr', IN / 'homer.shr', IN / 'sandbox/roads-l1.bin'
PLANT = (219.0, 161.0, 12.0)   # узел дороги у спавна уровня 1; круг 12 м, куда погоне нельзя


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def rel(p):   # путь от корня проекта (или полный, если папка вне проекта)
    p = Path(p).resolve()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def run(binp, out, seed, gens, pop, rounds, extra=()):
    out.mkdir(parents=True, exist_ok=True)
    cmd = ['nice', '-n', '10', str(binp), str(LVL), str(HOM), str(RDS), '--gens', str(gens), '--pop', str(pop), '--rounds', str(rounds),
           '--seed', str(seed), '--out', str(out), *map(str, extra)]
    r = subprocess.run(cmd, capture_output=True, text=True); (out / 'stdout.tsv').write_text(r.stdout)
    return r.stdout


def campaign(binp, out, procs, gens, pop, rounds, seed, extra=()):
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(procs) as ex:
        outs = list(ex.map(lambda k: run(binp, out / f'p{k}', seed + k, gens, pop, rounds, extra), range(procs)))
    gen, clu, rounds_total, weak, frames = {}, {}, 0, 0, 0
    for k, o in enumerate(outs):
        for l in o.splitlines():
            f = l.split('\t')
            if f[0] == 'G': gen.setdefault(int(f[1]), []).append((float(f[2]), float(f[4])))
            elif f[0] == 'X':
                layer, obj = (int(f[7]), f[8]) if len(f) > 8 else (0, '-')   # слой и объект — Т1.1
                key = cluster_key(f[1], float(f[2]), float(f[4]), layer, obj)
                if key not in clu: clu[key] = dict(kind=f[1], x=float(f[2]), y=float(f[3]), z=float(f[4]), layer=layer, obj=obj, key=key, n=0, file=rel(out / f'p{k}' / f[6]))
                clu[key]['n'] += int(f[5])
            elif f[0] == 'S': rounds_total += int(f[1]); weak += int(f[3])
            elif f[0] == 'F': frames += int(f[1])
    for c in clu.values():
        r = subprocess.run([str(binp), str(LVL), str(HOM), str(RDS), '--replay', str(ROOT / c['file'])], capture_output=True, text=True)
        c['replay'] = r.returncode == 0
    g = [dict(gen=i, meanCatch=round(sum(a for a, _ in v) / len(v), 2), catchRate=round(sum(b for _, b in v) / len(v), 3)) for i, v in sorted(gen.items())]
    return dict(levelSha=sha(LVL), roadsSha=sha(RDS), binarySha=sha(binp), procs=procs, gens=gens, pop=pop, rounds=rounds, seed=seed, extra=list(map(str, extra)),
                wallSeconds=round(time.time() - t0, 1), roundsPlayed=rounds_total, gameMinutes=round(frames / 3600, 1), weakCorners=weak, generations=g,
                clusters=sorted(clu.values(), key=lambda c: (c['kind'], -c['n'])))


def write(out, res, title):
    (out / 'chase.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    g = res['generations']; corners = [c for c in res['clusters'] if c['kind'] == 'eternal_corner']; stuck = [c for c in res['clusters'] if c['kind'] == 'pursuer_stuck']
    L = [f'# {title}', '', f"{res['procs']} процессов, {res['gens']} поколений × {res['pop']} × {res['rounds']} раунда; {res['roundsPlayed']} раундов по 60 с "
         f"({res['gameMinutes']} мин игры) за {res['wallSeconds'] / 60:.1f} мин; уровень {res['levelSha']}, бинарник {res['binarySha']}",
         f"Время беглеца до поимки (среднее, не больше 60 с): поколение 0 — {g[0]['meanCatch']}, последнее — {g[-1]['meanCatch']}; доля поимок {g[0]['catchRate']} -> {g[-1]['catchRate']}. "
         f"Подтверждённых вечных углов {len(corners)}, опровергнуто подтверждением {res['weakCorners']}; погоня застряла: {len(stuck)} мест", '',
         '| что | место | раз | повтор |', '|---|---|---|---|'] + [
         f"| {c['kind']} | {c['x']:.0f} {c['y']:.1f} {c['z']:.0f} | {c['n']} | {'тот же исход' if c['replay'] else 'РАЗОШЁЛСЯ'} `{c['file']}` |" for c in corners + stuck[:15]]
    (out / 'chase.md').write_text('\n'.join(L) + '\n')
    return L


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--procs', type=int, default=2); ap.add_argument('--gens', type=int, default=30); ap.add_argument('--pop', type=int, default=16)
    ap.add_argument('--rounds', type=int, default=4); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--gate', action='store_true'); ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    if not os.environ.get('BOTS_NO_BUILD'): subprocess.run([str(ROOT / 'tools/bots/build.sh')], check=True, capture_output=True)   # ночь собирает один раз сама
    os.environ['BW_FRAMES'] = '1'
    stamp = time.strftime('%Y%m%d-%H%M%S'); out = a.out or ROOT / 'build/bots/runs/chase' / (stamp + ('-gate' if a.gate else '')); out.mkdir(parents=True, exist_ok=True)
    good = BIN / 'chase'
    if not a.gate:
        res = campaign(good, out, a.procs, a.gens, a.pop, a.rounds, a.seed); L = write(out, res, f'Догонялки {stamp}')
        print('\n'.join(L[2:4])); print('->', out / 'chase.md'); return 0
    px, pz, pr = PLANT; region = ('--region', px, pz, 120); plant = ('--plant-corner', px, pz, pr)
    def near(res): return [c for c in res['clusters'] if c['kind'] == 'eternal_corner' and math.hypot(c['x'] - px, c['z'] - pz) < pr + 4]
    def verdict(planted, control):
        why = []
        if not near(planted): why.append('подложенный угол не пойман')
        if near(control): why.append('угол у центра без подложенного (ложное срабатывание)')
        bad = [c for r in (planted, control) for c in r['clusters'] if not c['replay']]
        if bad: why.append(f'повторов разошлось {len(bad)}')
        return why
    # (1) контроль: детектор сломан нарочно (-DCHASE_BREAK_DETECT=1) -> подложенный угол не ловится -> красный
    env = dict(os.environ, BINS='chase', SUF='_broken')
    subprocess.run([str(ROOT / 'tools/bots/build.sh'), '-DCHASE_BREAK_DETECT=1'], check=True, capture_output=True, env=env)
    brk = ROOT / 'build/bots/chase_broken'
    wb = verdict(campaign(brk, out / 'broken-planted', 1, 10, 16, 3, 11, region + plant), campaign(brk, out / 'broken-control', 1, 10, 16, 3, 11, region))
    # (2) рабочая сборка: с подложенным углом и без него, те же seed
    P = campaign(good, out / 'planted', 1, 10, 16, 3, 11, region + plant); C = campaign(good, out / 'control', 1, 10, 16, 3, 11, region)
    wg = verdict(P, C); write(out / 'planted', P, f'Гейт Б4 {stamp}, подложенный угол'); write(out / 'control', C, f'Гейт Б4 {stamp}, без подложенного')
    np_ = near(P); where = ', '.join('%.0f %.0f' % (c['x'], c['z']) for c in np_)
    lines = [f"контроль (детектор сломан): {'КРАСНЫЙ — ' + '; '.join(wb) if wb else 'зелёный — ГЕЙТ НЕ ЛОВИТ'}",
             f"рабочая сборка: {'КРАСНЫЙ — ' + '; '.join(wg) if wg else 'зелёный'}; подложенный угол пойман "
             f"{'у ' + where if np_ else 'нет'}; без подложенного углов {len([c for c in C['clusters'] if c['kind'] == 'eternal_corner'])} (вдали от центра)",
             f"RESULT: {'OK' if wb and not wg else 'FAIL'}"]
    (out / 'gate.txt').write_text('\n'.join(lines) + '\n'); print('\n'.join(lines)); print('->', out)
    return 0 if wb and not wg else 1


if __name__ == '__main__':
    sys.exit(main())
