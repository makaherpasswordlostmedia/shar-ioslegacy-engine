#!/usr/bin/env python3
"""Правка 103 (вылет у спортивной площадки школы): разбор прогона tests/crash_school/run.sh.
  check.py OUT_DIR   (build/smoke/<время>/: smoke.txt, ppsspp.log, blackbox.txt)
Провал, если хоть одно:
  - сценарий не дошёл до END (эмулятор упал или игра зависла);
  - в журнале PPSSPP то, что эмулятор молча пропускает, а PSP на нём падает и выключается: обращение по плохому адресу
    («Bad memory access», «Invalid address»), переход на плохой адрес («Jump to invalid address»), ловушка процессора
    («BREAK!» — деление на ноль и __builtin_trap: break 7 в коде движка), неизвестная команда GE;
  - отказ памяти / клетка без памяти / ошибка чтения / пропуск кусков из-за полного списка GE / битый адрес для GE (строки STAT);
  - модель персонажа или машины миссии не загрузилась (MSNNPC load-fail, MCR bad);
  - свободная куча ниже резерва движка 3 МБ (MEMLOW) или наибольший свободный кусок меньше 1 МБ;
  - пик списка GE выше 90 % (230 КБ из 256) или конец кадра за пределом списка (GELIST over — правка 103, хвост кадра);
  - самописец: ящик на карте реже раза в 3 с, в строках нет последнего действия и этапа миссии, модель персонажа или машины
    миссии читается с карты без действия npc+ / car+ перед чтением;
  - сторож (сценарий с «flag freeze N»): зависание главного потока не записано — нет BBSTALL phase=gesync с шапкой STALL или
    строки «op stall gesync_<мс>» в ящике после того, как кадры пошли (BBOP stall).
Красный контроль — прогон прежнего EBOOT d3e33a24 (HEAD 7a2f832: игра как в 7dec8b30 на PSP, отличие — только заставка 148/149)
по маршруту площадки: build/smoke/20261001-111628 — FAIL 3 (ящик 3 раза за 122 с, нет op/msn, чтение модели без npc+).
Выход 0 — зелёный."""
import re, sys
from pathlib import Path

out = Path(sys.argv[1])
smk = (out / 'smoke.txt').read_text(errors='replace') if (out / 'smoke.txt').exists() else ''
bad = []
if not re.search(r'^END$', smk, re.M):
    last = [l for l in smk.splitlines() if l and l[0].isdigit()][-1:] or ['—']
    bad.append(f'сценарий не дошёл до END (вылет или зависание); последняя строка: {last[0][:120]}')
logp = out / 'ppsspp.log'
if not logp.exists():
    bad.append('нет ppsspp.log (журнал эмулятора не записан — проверка адресов не сделана)')
else:
    pat = re.compile(r'Bad memory access|Invalid address|invalid address|Jump to invalid|BREAK!|Unknown GE command|BAD GE|'
                     r'DL PC = .* WTF|Unknown instruction|Unimplemented', re.I)
    hits = []
    with open(logp, errors='replace') as f:          # журнал — сотни МБ: построчно
        for l in f:
            if pat.search(l):
                hits.append(l.strip())
                if len(hits) > 50: break
    if hits:
        bad.append(f'журнал PPSSPP: {len(hits)}{"+" if len(hits) > 50 else ""} мест, на которых PSP падает (эмулятор пропустил), первые: '
                   + ' | '.join(h[-110:] for h in hits[:3]))
stats = {}
for l in smk.splitlines():
    if not l.startswith('STAT '): continue
    f = l.split(); sc = f[1]; kv = {}
    for i in range(2, len(f) - 1):
        if re.fullmatch(r'[a-z]+', f[i]) and re.fullmatch(r'-?[0-9.]+', f[i + 1]): kv[f[i]] = float(f[i + 1])
    stats[sc] = kv
heap_min = min((v['heapmin'] for v in stats.values() if 0 < v.get('heapmin', 1e9) < 1e8), default=None)
blk_min = min((v['blkmin'] for v in stats.values() if 0 < v.get('blkmin', -1) < 1e8), default=None)
ge_peak = max((v.get('gepeak', 0) for v in stats.values()), default=0)
for sc, v in stats.items():
    for k, what in (('memfail', 'отказов памяти'), ('allocfail', 'клеток без памяти'), ('readerr', 'ошибок чтения'),
                    ('geskip', 'пропусков кусков (список GE полон)'), ('gebad', 'битых адресов для GE')):
        if v.get(k, 0) > 0: bad.append(f'сцена {sc}: {what} {v[k]:.0f}')
if heap_min is not None and heap_min < 3.0: bad.append(f'MEMLOW: свободная куча {heap_min:.2f} МБ < резерва 3 МБ')
if blk_min is not None and blk_min < 1.0: bad.append(f'наибольший свободный кусок {blk_min:.2f} МБ < 1 МБ')
if ge_peak > 230: bad.append(f'пик списка GE {ge_peak:.0f} КБ > 90 %')
for l in re.findall(r'^(?:MSNNPC load-fail|MCR bad|GELIST over)[^\n]*', smk, re.M)[:3]:
    bad.append(l[:120])
# Самописец (правка 103, 01.10): после вылета на карте должно остаться, что было в последние секунды и что грузилось.
#  - ящик на карте пишется не реже раза в 3 с (шапка «RUN n=<записей> t=<секунд игры>»; прежний ящик — раз в минуту);
#  - в строках ящика — последнее действие («op …») и этап миссии;
#  - каждой загрузке модели персонажа и машины миссии предшествует действие («BBOP npc+ имя» / «BBOP car+ имя» в smoke.txt —
#    ящик ушёл на карту ДО чтения).
bbp = out / 'blackbox.txt'
bbt = bbp.read_text(errors='replace') if bbp.exists() else ''
hm = re.match(r'(RUN|EXIT) n=(\d+) t=(\d+)', bbt)
bb_note = 'нет blackbox.txt'
if not hm:
    bad.append('самописец: нет blackbox.txt с шапкой RUN/EXIT')
else:
    nw, tt = int(hm.group(2)), int(hm.group(3)); bb_note = f'ящик: {nw} записей за {tt} с'
    if tt >= 20 and nw * 3 < tt: bad.append(f'самописец: ящик на карте {nw} раз за {tt} с (раз в {tt / max(nw, 1):.0f} с) — после вылета нет последних секунд')
    rows = [l for l in bbt.splitlines() if re.match(r'\s*\d+ ', l)]
    if rows and not all(' op ' in l and ' msn ' in l for l in rows[-5:]):
        bad.append('самописец: в строках ящика нет последнего действия и этапа миссии («op …», «msn …»)')
# Сторож «bbdog» (правка 103, повтор 01.10): сценарий с «flag freeze N» — главный поток стоит N с там, где ждёт GE (как зависший
# список). Сторож обязан сам записать ящик «STALL … phase=gesync» (шапка — в строке BBSTALL head=…), а когда кадры пошли — строка
# «op stall gesync_<мс>» в кольце ящика. У прежнего ящика сторожа нет: при зависании на карте только запись минутной давности
scnp = out / 'scenario.txt'
scn = scnp.read_text(errors='replace') if scnp.exists() else ''
if re.search(r'^flag freeze', scn, re.M):
    st = re.search(r'^BBSTALL phase=(\S+) ms=(\d+) n=\d+ t=\S+ head=(.*)$', smk, re.M)
    if not st:
        bad.append('сторож: после «flag freeze» нет BBSTALL — зависание главного потока ящик не записал')
    else:
        if st.group(1) != 'gesync' or int(st.group(2)) < 5000:
            bad.append(f'сторож: {st.group(0)[:100]} — ждали phase=gesync, ms >= 5000')
        if not re.match(r'STALL n=\d+ ms=\d+ phase=\d+ gesync ', st.group(3)):
            bad.append(f'сторож: шапка ящика при зависании не «STALL … phase=… gesync»: {st.group(3)[:90]}')
    # строка «op stall …» ушла в кольцо ящика (кольцо — последние ~40 с, к концу прогона её вытесняет: смотрим журнал действий bbOp)
    if not re.search(r'^BBOP stall gesync_\d+ ', smk, re.M):
        bad.append('сторож: главный поток ожил, а строки «op stall gesync_<мс>» в ящик не ушло (нет BBOP stall)')
ops = [(m.start(), m.group(1), m.group(2)) for m in re.finditer(r'^BBOP (npc\+|car\+) (\S+)', smk, re.M)]
for m in re.finditer(r'^(MSNNPC load|MCR load) (\S+)', smk, re.M):
    want = 'npc+' if m.group(1).startswith('MSNNPC') else 'car+'
    if not any(p < m.start() and o == want and a.lower() == m.group(2).lower() for p, o, a in ops):
        bad.append(f'самописец: «{m.group(0)}» без действия {want} {m.group(2)} перед чтением (ящик на карте его не назовёт)'); break
trims = len(re.findall(r'^MEMTRIM', smk, re.M)); retries = len(re.findall(r'^CELLRETRY', smk, re.M))
npc = re.findall(r'^MSNNPC (load|drop|load-fail) (\S+)', smk, re.M)
mcr = re.findall(r'^MCR load (\S+)', smk, re.M)
tut = re.findall(r'^TUTORIAL on ev=(\S+)', smk, re.M)
ballast = re.search(r'ballast (\d+) MB', smk)
slow = re.search(r'slowio (\d+) KB/s', smk)
print(f'сцен {len(stats)}, балласт {ballast.group(1) if ballast else "?"} МБ, куча мин {heap_min if heap_min is not None else "?"} МБ, '
      f'кусок мин {blk_min if blk_min is not None else "?"} МБ, GE пик {ge_peak:.0f} КБ, MEMTRIM {trims}, CELLRETRY {retries}, '
      f'модели персонажей: {", ".join(a + " " + b for a, b in npc[:8]) or "-"}; машины миссий: {", ".join(mcr[:4]) or "-"}; '
      f'подсказки Барта: {", ".join(tut[:6]) or "-"}; {bb_note}, действий в журнале {len(re.findall(r"^BBOP ", smk, re.M))}')
for b in bad: print('FAIL', b)
print('RESULT', 'FAIL' if bad else 'PASS')
sys.exit(1 if bad else 0)
