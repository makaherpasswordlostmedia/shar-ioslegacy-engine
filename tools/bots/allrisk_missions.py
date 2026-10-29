#!/usr/bin/env python3
"""Run input-driven allrisk --mode mission on L2–L7; compare packet stages to disc.

CPU only, no emulator, network, schedules or deployment. Failures are observations,
not proof that the game is defective. Replay inputs and SHA-256 inputs are retained.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools/missions'))
import mfk


def sha(p):
    return hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()


def load_runner():
    spec = importlib.util.spec_from_file_location('allrisk_runner', ROOT / 'tools/bots/allrisk.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def world_inputs(files, level):
    """Files loaded by bwData and its native audio backend, including siblings."""
    inputs = dict(files)
    folder = files['level'].parent
    inputs['interiors'] = folder / f'interiors-l{level}.bin'
    inputs['music'] = folder / 'audio/music.sap'
    inputs['sfx'] = folder / 'audio/sfx.sab'
    return inputs


def disc_objectives(source, mission, phase):
    path = ROOT / 'hit-and-run-web/source/game/scripts/missions' / source
    calls, _ = mfk.parse_file(path)
    wanted = mission + ('sd' if phase == 0 else '')
    # Extracted disc has swapped names: identify actual init by SelectMission,
    # independently of the compiler's canonical diagnostic SOURCE label.
    if not any(c.op == 'SelectMission' and c.args and str(c.args[0]).lower() == wanted for c in calls):
        candidates = []
        for candidate in sorted(path.parent.glob('*.mfk')):
            parsed, _ = mfk.parse_file(candidate)
            if any(c.op == 'SelectMission' and c.args and str(c.args[0]).lower() == wanted for c in parsed):
                candidates.append((candidate, parsed))
        if len(candidates) != 1:
            raise ValueError(f'{source}: expected one SelectMission({wanted}), found {len(candidates)}')
        path, calls = candidates[0]
    stages = []
    for call in calls:
        if call.op == 'AddStage':
            stages.append('none')
        elif call.op == 'AddObjective' and stages:
            stages[-1] = str(call.args[0]).lower()
    return stages


def catalog(binary, args):
    run = subprocess.run([str(binary), *args, '--mode', 'mission', '--catalog'],
                         cwd=ROOT, capture_output=True, text=True, check=True)
    missions, plans, sources = {}, {}, {}
    for ln in run.stdout.splitlines():
        f = ln.split('\t')
        if f[0] == 'CAT':
            missions[int(f[1])] = dict(id=f[2], flags=int(f[3]))
        elif f[0] == 'PLAN':
            plans.setdefault((int(f[1]), int(f[3])), []).append(f[5])
        elif f[0] == 'SOURCE':
            sources[(int(f[1]), int(f[2]))] = f[4]
    errors = []
    for key, objectives in plans.items():
        source = sources[key]
        if '#' in source:  # Synthetic bonus dialogue, derived by existing compiler.
            continue
        expected = disc_objectives(source, missions[key[0]]["id"], key[1])
        if expected != objectives:
            errors.append(dict(mission=key[0], phase=key[1], source=source,
                               disc=expected, packet=objectives))
    return missions, plans, errors, run.stdout


def parse_trace(text, index, plans):
    trace = []
    result = None
    for ln in text.splitlines():
        f = ln.split('\t')
        if f[0] == 'STAGE':
            phase, stage = int(f[2]), int(f[3])
            planned = plans.get((index, phase), [])
            trace.append(dict(phase=phase, stage=stage, objective=f[4],
                              position=list(map(float, f[5:8])), frame=int(f[8]),
                              matches=0 <= stage < len(planned) and planned[stage] == f[4]))
        elif f[0] == 'M':
            result = dict(id=f[2], result=f[4], reason=f[5], seconds=float(f[6]),
                          visited=int(f[9]), attempts=int(f[10]),
                          position=list(map(float, f[12:14])), collision=int(f[14]),
                          classification=f[15])
    return trace, result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--levels', default='2,3,4,5,6,7')
    ap.add_argument('--secs', type=float, default=900)
    ap.add_argument('--procs', type=int, default=3)
    ap.add_argument('--timeout', type=float, default=120, help='wall-clock budget per mission, not gameplay timer')
    ap.add_argument('--data', type=Path)
    ap.add_argument('--binary', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--report', action='store_true', help='summarize retained runtime logs without replay')
    ap.add_argument('--only', help='mission ids, e.g. m1,m2')
    ap.add_argument('--from-main', action='store_true', help='explicit checkpoint start, reported separately')
    ap.add_argument('--impossible-timer', action='store_true')
    a = ap.parse_args()
    if a.secs <= 0 or a.procs < 1:
        ap.error('secs and procs must be positive')
    mod = load_runner()
    out = a.out or ROOT / 'build/bots/missions' / dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True, exist_ok=True)
    binary = a.binary.resolve() if a.binary else (out / 'bin/allrisk').resolve()
    if not a.binary and not a.report:
        failures = mod.build(binary.parent, '')
        if failures:
            raise RuntimeError(failures)
    data = mod.data_root(a.data)
    jobs, manifest, errors = [], {str(binary): sha(binary)}, []
    for level in map(int, a.levels.split(',')):
        files = mod.level_files(data, level)
        args = [str(files[k]) for k in ('level', 'player', 'roads', 'msn')]
        for path in world_inputs(files, level).values():
            if path.exists():
                manifest[str(path)] = sha(path)
        missions, plans, bad, text = catalog(binary, args)
        (out / f'L{level}_catalog.tsv').write_text(text)
        errors.extend(dict(level=level, **item) for item in bad)
        for index, mission in missions.items():
            if mission['flags'] & 15:  # Bonus and races have their own Codex-3 task.
                continue
            if a.only and mission['id'] not in a.only.split(','):
                continue
            jobs.append((level, index, mission, args, plans))
    if not a.report:
        (out / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2))
    (out / 'disc_comparison.json').write_text(json.dumps(errors, indent=2))
    if not a.report:
        metadata = dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                        dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
                        checkpoint=a.from_main, game_seconds=a.secs, wall_budget=a.timeout,
                        search='3 generations x 8 candidate inputs; independent second driver 3 seeds',
                        wallet='derived from packet purchase costs unless explicitly overridden; starting fixture')
        (out / 'METADATA.json').write_text(json.dumps(metadata, indent=2))


    def play(job):
        level, index, mission, args, plans = job
        dest = out / f'L{level}_{mission["id"]}'
        dest.mkdir(exist_ok=True)
        cmd = [str(binary), *args, '--mode', 'mission', '--mission', str(index),
               '--secs', str(a.secs), '--out', str(dest)]
        if a.from_main:
            cmd.append('--from-main')
        if a.impossible_timer:
            cmd.append('--impossible-timer')
        if a.report:
            saved = json.loads((dest / 'result.json').read_text())
            trace, result = parse_trace((dest / 'runtime.tsv').read_text(), index, plans)
            return dict(saved, trace=trace, outcome=result, trace_ok=bool(trace) and all(t['matches'] for t in trace))
        with (dest / 'runtime.tsv').open('w') as log:
            try:
                proc = subprocess.run(['nice', '-n', '10', *cmd], cwd=ROOT, stdout=log,
                                      stderr=subprocess.STDOUT, timeout=a.timeout,
                                      env=dict(os.environ, BW_LEVEL=str(level)))
                code = proc.returncode
            except subprocess.TimeoutExpired:
                code = 'timeout'
        trace, result = parse_trace((dest / 'runtime.tsv').read_text(), index, plans)
        row = dict(level=level, index=index, mission=mission['id'], code=code,
                   trace=trace, outcome=result, replay=cmd, checkpoint=a.from_main,
                   trace_ok=bool(trace) and all(t['matches'] for t in trace))
        (dest / 'result.json').write_text(json.dumps(row, ensure_ascii=False, indent=2))
        print(f'L{level} {mission["id"]}: {result and result["result"]}; stages={len(trace)}', flush=True)
        return row

    with cf.ThreadPoolExecutor(a.procs) as ex:
        rows = list(ex.map(play, jobs))
    (out / 'result.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    lines = ['# Миссии L2–L7, ввод настоящего бота', '',
             f'Сравнение этапов пакета с диском: {len(errors)} расхождений',
             'Старт: ' + ('основная часть с чекпоинта меню' if a.from_main else 'вступление миссии'),
             'Бюджет поиска: 3 поколения × 8 вариантов ввода, второй водитель: 3 seed; это правило стенда',
             'Класс «игра» означает, что два водителя не доехали, и сам по себе не доказывает дефект',
             'Результат бота не является приёмкой игры; записи наблюдателя пункта 22 пока нет', '',
             '| Уровень | Миссия | Итог | Посещённые этапы | Место остановки | Причина |',
             '|---|---|---|---|---|---|']
    for row in rows:
        r = row['outcome'] or {}
        trace = row['trace']
        last = trace[-1] if trace else {}
        place = '--'
        if r.get('position'):
            x, z = r['position']
            # On successful missions position defaults to zero; omit misleading code.
            if r.get('result') != 'пройдена' and (x or z):
                import place as pc
                place = pc.code(x, z) if hasattr(pc, 'code') else f'{x:.1f}, {z:.1f}'
        lines.append(f'| L{row["level"]} | {row["mission"]} | {r.get("result", row["code"])} | '
                     f'{len(trace)}, последний {last.get("phase", "-")}.{last.get("stage", "-")} '
                     f'{last.get("objective", "-")} | {place} | {r.get("reason", "нет результата")} |')
    (out / 'РЕЗУЛЬТАТ.md').write_text('\n'.join(lines) + '\n')
    print(out / 'РЕЗУЛЬТАТ.md')
    return int(bool(errors) or any(not r['trace_ok'] or r['outcome'] is None for r in rows))


if __name__ == '__main__':
    raise SystemExit(main())
