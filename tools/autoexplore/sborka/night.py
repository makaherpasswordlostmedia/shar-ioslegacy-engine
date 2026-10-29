#!/usr/bin/env python3
"""Автоисследователь: ночной запуск по расписанию (полоса Сборка3). Только процессор Мака, 8 процессов из 10, без эмулятора, звука и окон.
Берёт последний пакет build/final-<время> (без -release), раздаёт полосам задания и по ходу склеивает находки в кластеры и пишет частичный отчёт.

Контракт полосы (tools/autoexplore/<полоса>/run.sh, исполняемый):
    run.sh УРОВЕНЬ SEED ПАПКА_ПАКЕТА ВЫХОД.tsv ДО_КОГДА_EPOCH
  пишет находки в ВЫХОД.tsv (одна строка на находку: уровень x y z тип вес seed кадр описание, табуляция), останавливается к ДО_КОГДА_EPOCH,
  код возврата 0 — прогон завершён (пустой TSV — «ничего не нашёл»). Полосы без run.sh пропускаются (в отчёте помечены «не подключена»).
  python3 tools/autoexplore/sborka/night.py [--data ПАКЕТ] [--procs 8] [--until 06:30] [--seeds 3] [--levels 1,2,3,4,5,6,7] [--job-timeout 1500] [--dry] [--out DIR]
Прерванный запуск продолжается: готовые задания (есть .done) не повторяются. Итоги: build/autoexplore/<дата>/ (clusters.tsv, ОТЧЁТ_АВТОИССЛЕДОВАТЕЛЬ_<дата>.md, findings/, logs/)."""
import argparse, concurrent.futures as cf, datetime as dt, glob, os, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HOME = Path.home() / 'Downloads'
lock = threading.Lock()


def say(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)


def latest_package():
    best = None
    for tree in (ROOT, HOME / 'shar-psp'):
        for d in glob.glob(str(tree / 'build' / 'final-2*')):
            p = Path(d)
            if p.is_dir() and not d.endswith('-release') and (p / 'EBOOT.PBP').exists():
                if best is None or p.stat().st_mtime > best.stat().st_mtime: best = p
    return best


def lanes_of(roots):
    res = {}
    for r in roots:
        for rs in sorted(glob.glob(str(Path(r) / 'tools' / 'autoexplore' / '*' / 'run.sh'))):
            lane = Path(rs).parent.name
            if lane != 'sborka' and os.access(rs, os.X_OK): res.setdefault(lane, rs)
    return res


def until_epoch(s):
    h, m = map(int, s.split(':')); now = dt.datetime.now(); t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if t <= now: t += dt.timedelta(days=1)
    return t.timestamp()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--data'); ap.add_argument('--procs', type=int, default=8); ap.add_argument('--until', default='06:30')
    ap.add_argument('--seeds', type=int, default=3); ap.add_argument('--levels', default='1,2,3,4,5,6,7'); ap.add_argument('--job-timeout', type=int, default=1500)
    ap.add_argument('--dry', action='store_true'); ap.add_argument('--out'); ap.add_argument('--root', action='append', default=[])
    a = ap.parse_args()
    pkg = Path(a.data) if a.data else latest_package()
    if not pkg or not pkg.is_dir(): sys.exit('нет пакета build/final-* (собрать final-build или указать --data)')
    roots = [Path(r) for r in a.root] or [ROOT]
    lanes = lanes_of(roots)
    date = (dt.datetime.now() + dt.timedelta(hours=12)).date().isoformat();   # ночь с 11 на 12-е — отчёт 12-го
    out = Path(a.out) if a.out else ROOT / 'build' / 'autoexplore' / date
    (out / 'findings').mkdir(parents=True, exist_ok=True); (out / 'logs').mkdir(exist_ok=True)
    levels = [int(x) for x in a.levels.split(',')]; seeds = list(range(1, a.seeds + 1)); until = until_epoch(a.until)
    jobs = [(lane, lv, sd) for lv in levels for sd in seeds for lane in lanes]
    say(f'пакет {pkg.name}; полос подключено {len(lanes)}: {", ".join(lanes) or "—"}; заданий {len(jobs)}; процессов {a.procs}; до {a.until}')
    (out / 'plan.txt').write_text(f'пакет {pkg}\nполосы {", ".join(lanes) or "нет"}\nзаданий {len(jobs)}\n')
    if a.dry: return
    if not lanes:
        sys.exit('ни одна полоса не подключила tools/autoexplore/<полоса>/run.sh: запускать нечего (отчёт по готовым TSV: cluster.py)')
    last_report = [0.0]

    def refresh(force=False):
        with lock:
            if not force and time.time() - last_report[0] < 120: return
            last_report[0] = time.time()
            subprocess.run([sys.executable, str(HERE / 'cluster.py'), '--root', str(out.parent.parent.parent)]
                           + ['--out', str(out), '--date', date, '--build', pkg.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def run(job):
        lane, lv, sd = job; tag = f'{lane}_L{lv}_s{sd}'; tsv = out / 'findings' / f'{tag}.tsv'; done = out / 'findings' / f'{tag}.done'
        if done.exists(): return tag, 'готово ранее'
        if time.time() >= until: return tag, 'пропущено: ночь кончилась'
        t0 = time.time()
        try:
            r = subprocess.run([lanes[lane], str(lv), str(sd), str(pkg), str(tsv), str(int(until))], stdout=open(out / 'logs' / f'{tag}.log', 'w'), stderr=subprocess.STDOUT,
                               timeout=min(a.job_timeout, max(60, until - time.time())))
            st = f'код {r.returncode}'
            if r.returncode == 0: done.write_text(f'{time.time() - t0:.0f} c\n')
        except subprocess.TimeoutExpired: st = 'остановлено по времени'
        refresh()
        return tag, st

    with cf.ThreadPoolExecutor(a.procs) as ex:
        for tag, st in ex.map(run, jobs): say(tag, st)
    refresh(True); rep = out / f'ОТЧЁТ_АВТОИССЛЕДОВАТЕЛЬ_{date}.md'; say('итог:', rep)
    main_handoff = HOME / 'shar-psp' / 'docs' / 'handoff'   # утренний отчёт кладётся рядом с остальными разборами основного дерева
    if rep.exists() and main_handoff.is_dir() and not a.out:   # с --out (пробные запуски) в основное дерево ничего не копируется
        import shutil; shutil.copyfile(rep, main_handoff / rep.name); say('скопирован в', main_handoff / rep.name)


if __name__ == '__main__': main()
