#!/usr/bin/env python3
"""Ночной прогон одной кнопкой (docs/handoff/LOOP_TERMINAL.md, пункт 3а): днём уровень 1, ночью Мак гоняет остальное,
утром агент читает одну сводку. Только процессор Мака: без AI и API, на PSP ничего.

По порядку; упавший шаг не мешает остальным, причина идёт строкой в сводку:
  1 уровни 2–7: tools/build_all_levels.sh 2 3 4 5 6 7 (флаги качества по умолчанию, build/level.shr не трогает)
  2 дороги каждого собранного уровня: tools/cartest/roads.py --level N --out build/sandbox/roads-lN.bin
  3 рой машин на каждом собранном уровне 2–7: sandbox_batch.py, 6 серий × 600 с × 256 машин → <ночь>/lN/
  4 регрессия уровня 1 (build/level.shr, текущий код): seed 10000–10095 → <ночь>/l1/
  5 сводка <ночь>/СВОДКА.md (+ СВОДКА.json: по ней следующая ночь считает сравнение)
<ночь> = build/sandbox/night/<ГГГГММДД-ЧЧММ>. Ограничения: до 07:00, данных ночи не больше 4 GiB, стоп при свободном
месте меньше 10 GiB, одна копия за раз (замок build/sandbox/night/night.lock).

  python3 tools/cartest/night.py                 полный прогон (кнопка: tools/cartest/Ночной прогон.command)
  python3 tools/cartest/night.py --smoke         короткий: уже собранные L1 и L3, по серии на 60 с, без сборки уровней
  --levels 3,4          только эти уровни из 2–7 (сборка и рой)
  --level-file 3=PATH   взять уровень из файла (отрицательный контроль: битый файл → в сводке «не загрузился»)
"""
import argparse
import collections
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
NIGHTS = ROOT / 'build/sandbox/night'
VENV_PY = ROOT / '.venv/bin/python'
DATA_LIMIT = 4 * 1024 ** 3
DISK_RESERVE = 10 * 1024 ** 3
KINDS = ('penetration', 'long-flight', 'blocked-review')           # проникновение, долгий полёт, остановка
KIND_RU = {'penetration': 'проникновение', 'long-flight': 'долгий полёт', 'blocked-review': 'остановка'}
# база сравнения уровня 1: долгая кампания 27.09 (build/sandbox/soaks/20260927-175304-ded22e, 462 серии), на серию
BASE_L1 = {'penetration': 36.1, 'long-flight': 36.5, 'blocked-review': 72.3, 'series': 462, 'seconds': 600,
           'source': 'build/sandbox/soaks/20260927-175304-ded22e'}
# приёмка и сравнение ночей — только естественные события (старт на дороге, start = -1), Роб 28.09; база по тем же seed —
# build/sandbox/soak-report-natural.json (tools/cartest/soak_report.py, perSeedNatural)
BASE_L1_NATURAL = ROOT / 'build/sandbox/soak-report-natural.json'


def log(msg):
    print(time.strftime('%H:%M:%S'), msg, flush=True)


def deadline_after(now):
    """Ближайшие 07:00 после старта: запуск до 07:00 — сегодня, позже — завтра."""
    d = now.replace(hour=7, minute=0, second=0, microsecond=0)
    return d if now < d else d + dt.timedelta(days=1)


def du(path):
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file()) if path.exists() else 0


class Night:
    def __init__(self, a):
        self.a = a
        self.started = dt.datetime.now()
        self.deadline = deadline_after(self.started)
        stamp = self.started.strftime('%Y%m%d-%H%M') + ('-smoke' if a.smoke else '')
        self.dir = NIGHTS / stamp
        n = 1
        while self.dir.exists():                                   # завершённое не перезаписываем
            n += 1; self.dir = NIGHTS / ('%s-%d' % (stamp, n))
        self.dir.mkdir(parents=True)
        self.levels = {}          # N -> dict(built, why, file, roads, swarm...)
        self.notes = []
        self.stopped = None       # причина остановки (07:00 / место)

    # ---- ограничения ----------------------------------------------------------------------------------------
    def budget(self):
        if self.stopped:
            return self.stopped
        if dt.datetime.now() >= self.deadline:
            self.stopped = 'не успел до 07:00'
        elif shutil.disk_usage(self.dir).free < DISK_RESERVE:
            self.stopped = 'свободного места меньше 10 GiB'
        elif du(self.dir) > DATA_LIMIT:
            self.stopped = 'данных ночи больше 4 GiB'
        return self.stopped

    def seconds_left(self):
        return max(1.0, (self.deadline - dt.datetime.now()).total_seconds())

    def run(self, cmd, name, cap):
        """Шаг отдельным процессом (своя группа), лог в <ночь>/logs/<name>.log. -> (код, последняя строка)."""
        logs = self.dir / 'logs'; logs.mkdir(exist_ok=True)
        path = logs / (name + '.log')
        timeout = min(cap, self.seconds_left())
        with path.open('w') as f:
            p = subprocess.Popen(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, start_new_session=True)

            def kill():
                os.killpg(p.pid, signal.SIGTERM)
                try:
                    p.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL); p.wait()
            try:
                code = p.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                kill(); code = None
            except BaseException:                                      # Ctrl-C / закрыли окно: дочерние не бросаем
                kill(); raise
        lines = [x for x in path.read_text(errors='replace').replace(str(ROOT) + '/', '').splitlines() if x.strip()]
        last = lines[-1].strip() if lines else ''
        if code is None:
            last = ('не успел до 07:00' if dt.datetime.now() >= self.deadline else 'превысил %d мин' % (cap // 60)) + \
                   (' (последняя строка: %s)' % last[:160] if last else '')
        return code, last

    # ---- шаги -------------------------------------------------------------------------------------------------
    def step_build(self):
        want = self.a.levels
        for n in want:
            self.levels[n] = dict(built=False, why='не собирался', file=ROOT / 'build/levels' / ('l%d' % n) / 'level.shr')
        overrides = {n: p for n, p in self.a.level_file.items()}
        if self.a.smoke:
            for n in want:
                f = overrides.get(n, self.levels[n]['file'])
                ok = Path(f).exists()
                self.levels[n].update(built=ok, file=Path(f), why='уже собран (--smoke, сборки нет)' if ok else 'нет файла ' + str(f))
            return
        todo = [n for n in want if n not in overrides]
        if todo:
            why = self.budget()
            if why:
                for n in todo:
                    self.levels[n]['why'] = why
            else:
                log('1 сборка уровней %s (tools/build_all_levels.sh)' % ' '.join(map(str, todo)))
                t0 = time.time()
                code, last = self.run(['bash', 'tools/build_all_levels.sh', *map(str, todo)], 'build', 4 * 3600)
                rep = ROOT / 'build/levels/report.txt'
                fresh = rep.exists() and rep.stat().st_mtime >= t0
                lines = rep.read_text().splitlines() if fresh else []
                for n in todo:
                    row = next((x for x in lines if x.startswith('l%d level:' % n)), None)
                    if row and row.split(':', 1)[1].strip().startswith('OK'):
                        self.levels[n].update(built=True, why='собран этой ночью')
                    elif row:
                        self.levels[n]['why'] = row.split(':', 1)[1].strip()
                    else:
                        self.levels[n]['why'] = 'сборка не дошла до уровня: ' + (last or 'код %s' % code)
                log('  сборка: %s' % ', '.join('L%d %s' % (n, 'OK' if self.levels[n]['built'] else 'нет') for n in todo))
        for n, p in overrides.items():
            self.levels[n].update(built=Path(p).exists(), file=Path(p), why='файл из --level-file')

    def step_roads(self, n, entry):
        out = ROOT / 'build/sandbox' / ('roads-l%d.bin' % n)
        if n == 1 and out.exists():
            entry['roads'] = out; return True
        why = self.budget()
        if why:
            entry['swarm'] = dict(status='пропущен', why=why); return False
        code, last = self.run([str(VENV_PY), str(HERE / 'roads.py'), '--level', str(n), '--out', str(out)], 'roads-l%d' % n, 600)
        if code != 0 or not out.exists():
            entry['swarm'] = dict(status='пропущен', why='дороги не построены: ' + last); return False
        entry['roads'] = out
        return True

    def step_swarm(self, n, entry, runs, seconds, seed, name):
        why = self.budget()
        if why:
            entry['swarm'] = dict(status='пропущен', why=why); return
        out = self.dir / name
        # уровень и дороги копией в папку ночи: днём build/level.shr пересоберут, а повтор из сводки должен совпасть
        data = self.dir / 'data'; data.mkdir(exist_ok=True)
        for key, dst in (('file', data / ('l%d.shr' % n)), ('roads', data / ('roads-l%d.bin' % n))):
            shutil.copy2(entry[key], dst); entry[key] = dst
        cmd = [sys.executable, str(HERE / 'sandbox_batch.py'), '--level', str(entry['file']), '--roads', str(entry['roads']),
               '--runs', str(runs), '--workers', str(min(6, runs)), '--seconds', str(seconds), '--cars', '256',
               '--seed', str(seed), '--emit', '600', '--out', str(out)]
        log('%s рой L%d: %d серий × %d с × 256 машин, seed %d…' % ('4' if name == 'l1' else '3', n, runs, seconds, seed))
        try:
            code, last = self.run(cmd, 'swarm-' + name, 3 * 3600)
            stopped = False
        except KeyboardInterrupt:                                      # готовые серии всё равно идут в сводку
            code, last, stopped = None, 'остановлен вручную', True
        res = out / 'results.json'
        runs_done = json.loads(res.read_text())['runs'] if res.exists() else []
        sw = dict(dir=str(out.relative_to(ROOT)), planned=runs, done=len(runs_done), seconds=seconds, seedFrom=seed)
        if code == 0:
            sw['status'] = 'OK'
        else:
            reason = last
            for lg in sorted(out.glob('seed-*.log')):                   # причина у самого бинарника роя
                t = [x for x in lg.read_text(errors='replace').splitlines() if x.strip()]
                if t and not t[-1].startswith('ticks='):
                    reason = t[-1].strip().replace(str(ROOT) + '/', ''); break
            loaded = not any(k in reason for k in ('not SHR7', 'no COL1', 'invalid', 'missing PRP2', 'zero support seeds'))
            sw['status'] = 'частично' if runs_done else ('не загрузился' if not loaded else 'упал')
            sw['why'] = reason
        if stopped:
            sw.update(status='частично' if runs_done else 'прерван', why=last)
        if runs_done:
            sw.update(analyse(runs_done, entry, out))
        entry['swarm'] = sw
        log('  L%d: %s%s' % (n, sw['status'], (' — ' + sw['why']) if sw.get('why') else ''))
        if stopped:
            raise KeyboardInterrupt

    def step_props(self, entry):
        """пункт 10а: каждый предмет уровня 1 под ударом (tools/cartest/props_sweep.py --gate), вердикты по типам"""
        why = self.budget()
        if why:
            entry['props'] = dict(status='пропущен', why=why); return
        out = self.dir / 'props-sweep.json'
        cmd = [sys.executable, str(HERE / 'props_sweep.py'), '--gate', '--level', str(entry['file']), '--out', str(out)]
        log('обход предметов L1 (props_sweep)…')
        code, last = self.run(cmd, 'props', 1800)
        if code == 0 and out.exists():
            r = json.loads(out.read_text())
            v = collections.Counter(x['verdict'] for part in ('prp1', 'spr1') for x in r[part].values())
            entry['props'] = dict(status='OK', verdicts=dict(v), file=str(out.relative_to(ROOT)))
        else:
            entry['props'] = dict(status='упал', why=last)

    # ---- сводка -----------------------------------------------------------------------------------------------
    def previous(self):
        best = None
        for d in sorted(NIGHTS.glob('*/СВОДКА.json')):
            if d.parent == self.dir or ('-smoke' in d.parent.name) != self.a.smoke:
                continue
            best = d
        return json.loads(best.read_text()) if best else None

    def summary(self):
        prev = self.previous()
        data = dict(kind='night-v2', started=self.started.isoformat(timespec='seconds'),
                    finished=dt.datetime.now().isoformat(timespec='seconds'), smoke=self.a.smoke, stopped=self.stopped,
                    dir=str(self.dir.relative_to(ROOT)), dataBytes=du(self.dir), notes=self.notes,
                    levels={str(n): {k: (str(v.relative_to(ROOT)) if isinstance(v, Path) and v.is_absolute() and v.is_relative_to(ROOT) else
                                        str(v) if isinstance(v, Path) else v) for k, v in e.items()} for n, e in sorted(self.levels.items())},
                    previous=prev and prev.get('dir'))
        tmp = self.dir / 'СВОДКА.json.tmp'; tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1)); tmp.replace(self.dir / 'СВОДКА.json')
        L = ['# Ночной прогон %s%s' % (self.started.strftime('%d.%m %H:%M'), ' · короткий (--smoke)' if self.a.smoke else ''), '',
             'Закончен %s, данных %.2f GiB, папка `%s`. %s' % (
                 dt.datetime.now().strftime('%d.%m %H:%M'), data['dataBytes'] / 1024 ** 3, data['dir'],
                 'Остановлен: ' + self.stopped + '.' if self.stopped else 'Все шаги дошли до конца.'),
             'Это наблюдения роя на процессоре Мака, не приёмка игры: принимает Роб на PSP.', '',
             'Числа на серию — только естественные события (старт на дороге); стресс-старты отдельной колонкой, в приёмку не входят.', '',
             '| Уровень | Собран | Рой | Серий | Естественные на серию: проникн. / полёт / остановка | Стресс | Покрытие, воксели | Стёкла |',
             '|---|---|---|---|---|---|---|---|']
        for n, e in sorted(self.levels.items()):
            sw = e.get('swarm', {})
            per = sw.get('perSeries', {})
            rate = ' / '.join('%.1f' % per[k] for k in KINDS) if per else '—'
            spr = sw.get('perSeriesStress', {}); srate = ' / '.join('%.1f' % spr[k] for k in KINDS) if spr else '—'
            L.append('| L%d | %s | %s | %s | %s | %s | %s | %s |' % (
                n, 'да' if e.get('built') else 'нет: ' + e.get('why', ''),
                sw.get('status', '—') + (': ' + sw['why'] if sw.get('why') else ''),
                '%d/%d' % (sw.get('done', 0), sw.get('planned', 0)) if sw.get('planned') else '—', rate, srate,
                '%.0f' % sw['coverage'] if sw.get('coverage') else '—',
                '%d/%d' % (sw['glassCovered'], sw['glassTotal']) if sw.get('glassTotal') else '—'))
        L += ['', '## Сравнение']
        for n, e in sorted(self.levels.items()):
            sw = e.get('swarm', {})
            per = sw.get('perSeries')
            if not per:
                continue
            parts = []                                                 # сравнимы только серии одной длины
            if n == 1:
                bn = json.loads(BASE_L1_NATURAL.read_text()).get('perSeedNatural', {}) if BASE_L1_NATURAL.exists() else {}
                same = [bn[str(sd)] for sd in sw.get('seeds', []) if str(sd) in bn]
                if sw['seconds'] != BASE_L1['seconds']:
                    parts.append('с базой 27.09 не сравниваю: серия %d с против %d с' % (sw['seconds'], BASE_L1['seconds']))
                elif same:                                             # те же seed в базовой кампании: разница = изменение кода
                    parts.append('база 27.09, естественные, те же %d seed: ' % len(same) + ', '.join('%s %.1f → %.1f' % (
                        KIND_RU[k], sum(e.get(k, 0) for e in same) / len(same), per[k]) for k in KINDS))
            ps = prev and prev.get('kind') == 'night-v2' and prev.get('levels', {}).get(str(n), {}).get('swarm', {})
            pp = ps and ps.get('seconds') == sw['seconds'] and ps.get('perSeries')
            parts.append(('прошлая ночь: ' + ', '.join('%s %.1f → %.1f' % (KIND_RU[k], pp[k], per[k]) for k in KINDS))
                         if pp else 'прошлой ночи для сравнения нет')
            L.append('- L%d: %s' % (n, '; '.join(parts)))
        L += ['', '## Топ-5 мест по уровням (сетка 8 м; повтор: бинарник и данные из папки пакета, тот же seed, весь флот)']
        for n, e in sorted(self.levels.items()):
            top = e.get('swarm', {}).get('top')
            if not top:
                continue
            L.append('- **L%d**' % n)
            for t in top:
                L.append('  - (%.0f, %.0f): %d событий (%s); повтор: seed %d, машина %d, tick %d, %s `%s`' % (
                    t['x'], t['z'], t['count'], ', '.join('%s %d' % (KIND_RU[k], v) for k, v in t['kinds'].items()),
                    t['seed'], t['car'], t['tick'], KIND_RU[t['kind']], t['replay']))
        pr = self.levels.get(1, {}).get('props')
        if pr:
            L += ['', '## Предметы L1 под ударом (пункт 10а)', '- %s%s' % (pr['status'], (': ' + ', '.join('%s %d' % kv for kv in pr['verdicts'].items()) + ', `' + pr['file'] + '`')
                                                              if pr.get('verdicts') else (' — ' + pr.get('why', '')))]
        if self.notes:
            L += ['', '## Заметки'] + ['- ' + x for x in self.notes]
        (self.dir / 'СВОДКА.md').write_text('\n'.join(L) + '\n')
        return self.dir / 'СВОДКА.md'


def analyse(runs, entry, out):
    """Числа на серию, покрытие, стёкла и топ-5 мест (сетка 8 м по XZ) с повтором из этой же папки пакета."""
    n = len(runs)
    cnt, stress = collections.Counter(), collections.Counter()
    cells = collections.defaultdict(lambda: dict(count=0, kinds=collections.Counter(), ev=None))
    for r in runs:
        for e in r.get('review', []):
            if e['kind'] not in KINDS:
                continue
            if e.get('start', -1) >= 0:                                # стресс-старт: отдельно, не в приёмку и не в топ
                stress[e['kind']] += 1; continue
            cnt[e['kind']] += 1
            x, y, z = e['xyz']
            c = cells[(int(x // 8), int(z // 8))]
            c['count'] += 1; c['kinds'][e['kind']] += 1
            if c['ev'] is None:
                c['ev'] = dict(e, seed=r['seed'])
    per = {k: cnt[k] / n for k in KINDS}; perS = {k: stress[k] / n for k in KINDS}
    top = []
    for (cx, cz), c in sorted(cells.items(), key=lambda kv: -kv[1]['count'])[:5]:
        e = c['ev']
        replay = '%s/swarm --level %s --roads %s --cars 256 --seed %d --ticks %d --emit 1' % (
            out.relative_to(ROOT), Path(entry['file']).relative_to(ROOT), Path(entry['roads']).relative_to(ROOT), e['seed'], e['tick'] + 60)
        top.append(dict(x=cx * 8 + 4, z=cz * 8 + 4, count=c['count'], kinds=dict(c['kinds']), seed=e['seed'], car=e['car'],
                        tick=e['tick'], kind=e['kind'], replay=replay))
    fin = [r['final'] for r in runs]
    return dict(perSeries=per, perSeriesStress=perS, origin='естественные: старт на дороге', allEvents=dict(cnt), stressEvents=dict(stress), seeds=sorted(r['seed'] for r in runs), coverage=sum(f['coverage'] for f in fin) / n,
                glassCovered=max(f.get('glassCovered', 0) for f in fin), glassTotal=max(f.get('glassTotal', 0) for f in fin),
                top=top)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--levels', default=None, help='уровни из 2–7 через запятую')
    ap.add_argument('--level-file', action='append', default=[], help='N=PATH')
    a = ap.parse_args()
    a.levels = [int(x) for x in a.levels.split(',')] if a.levels else ([3] if a.smoke else [2, 3, 4, 5, 6, 7])
    if any(n not in range(2, 8) for n in a.levels):
        ap.error('--levels: только 2..7 (уровень 1 идёт регрессией)')
    lf = {}
    for x in a.level_file:
        n, p = x.split('=', 1); lf[int(n)] = Path(p).resolve()
    a.level_file = lf
    NIGHTS.mkdir(parents=True, exist_ok=True)
    lock = (NIGHTS / 'night.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('ночной прогон уже идёт (замок build/sandbox/night/night.lock), вторую копию не запускаю'); return 1
    night = Night(a)

    def interrupted(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted); signal.signal(signal.SIGHUP, interrupted)
    log('ночной прогон → %s (до %s)' % (night.dir.relative_to(ROOT), night.deadline.strftime('%d.%m %H:%M')))
    try:
        night.step_build()
        for n in a.levels:
            e = night.levels[n]
            if not e.get('built'):
                e['swarm'] = dict(status='пропущен', why='уровень не собран'); continue
            if night.step_roads(n, e):
                night.step_swarm(n, e, 1 if a.smoke else 6, 60 if a.smoke else 600, 100, 'l%d' % n)
        l1 = dict(built=(ROOT / 'build/level.shr').exists(), why='дневной build/level.shr', file=lf.get(1, ROOT / 'build/level.shr'))
        night.levels[1] = l1
        if l1['built'] and night.step_roads(1, l1):
            night.step_swarm(1, l1, 1 if a.smoke else 96, 60 if a.smoke else 600, 10000, 'l1')
        if l1['built']:
            night.step_props(l1)
    except KeyboardInterrupt:
        night.stopped = 'остановлен вручную'
    except Exception as ex:                                           # сводка пишется всегда
        night.notes.append('сбой ночного скрипта: %r' % ex)
    finally:
        path = night.summary()
    log('сводка: %s' % path.relative_to(ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
