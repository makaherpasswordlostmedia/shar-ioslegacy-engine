#!/usr/bin/env python3
"""Табло проекта из трёх чисел и бюджет входа (станок С0, docs/handoff/LOOP_TERMINAL.md). Числа считает только этот
скрипт из файлов; ручное число в STATE.md = отказ.
  python3 tools/tablo.py            посчитать и показать
  python3 tools/tablo.py --write    вписать в STATE.md между <!-- tablo --> и <!-- /tablo -->
  python3 tools/tablo.py --check    STATE.md совпадает с подсчётом, STATE.md <= 8 КБ, вход <= 30 КБ; иначе код 1
Числа:
  (а) открытые естественные кластеры: последняя сводка исследователя build/sandbox/explore/*/clusters.json, пока её нет —
      последняя перепись стен build/sandbox/walls/*/walls.json; кластер «открыт», если он из естественных стартов
      (старт на дороге, не менее 3 событий), вид — ошибка (прозрачная стена, дыра, застрял, провал, проникновение),
      и его ключа нет в docs/state/fixed-clusters.tsv (исправленные, их повтор стоит в гейте);
      плюс места поломок последней ночи ботов build/bots/nights/*/night.json (пункт Б5; старты только с дороги): провал Гомера,
      Гомер заперт, погоня застряла, вечный угол — связные клетки 8 м одного вида от 3 повторений (одно место = одна поломка)
  (б) эталонные клипы в допуске: X = build/ps2ref/clips/*/result.json с "inTolerance": true, N = строк в tools/ps2ref/clips.tsv
  (в) типы чанков диска без обработчика: id чанков во всех файлах уровней 1–7 (art/l[1-7]*.p3d), которых нет среди
      обработанных в docs/state/handlers.tsv (таблицу пишет --handlers по ссылкам на id в коде экспорта, дальше правится)
Бюджет входа: AGENTS.md + CLAUDE.md + STATE.md + docs/handoff/LOOP_TERMINAL.md <= 30 КБ (Роб 28.09, правило 4)."""
import argparse, collections, glob, json, os, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ENTRY = ['AGENTS.md', 'CLAUDE.md', 'STATE.md', 'docs/handoff/LOOP_TERMINAL.md']
BUDGET, STATE_MAX = 30 * 1024, 8 * 1024
BUG = {'прозрачная', 'дыра', 'застрял', 'провал', 'проникновение', 'penetration', 'long-flight', 'blocked-review'}
CODE = ['tools/%s.py' % n for n in ('psp_export', 'prp2_export', 'ui_export', 'homer_export', 'char_export', 'fx_export', 'fx_pack',
                                     'audio_export', 'sound_export', 'traffic_export')] + \
       ['hit-and-run-web/tools/%s.py' % n for n in ('convert', 'interiors', 'p3d', 'frontend', 'characters', 'audio')]   # конвейер экспорта


def latest(pattern):
    c = sorted(glob.glob(str(ROOT / pattern)), key=os.path.getmtime)
    return Path(c[-1]) if c else None


def fixed_keys():
    f = ROOT / 'docs/state/fixed-clusters.tsv'
    return {l.split('\t')[0] for l in f.read_text().splitlines() if l and not l.startswith('#')} if f.exists() else set()


def number_a():
    fx = fixed_keys(); n = None
    p = latest('build/sandbox/explore/*/clusters.json')
    if p:
        cl = json.loads(p.read_text())['clusters']
        n = sum(1 for c in cl if c.get('origin') == 'естественное' and c.get('events', 0) >= 3 and c.get('family') in BUG and c['key'] not in fx)
    else:
        p = latest('build/sandbox/walls/*/walls.json')
        if p:
            cl = json.loads(p.read_text())['clusters']
            n = sum(1 for c in cl if c.get('nNat', 0) >= 3 and c.get('family') in BUG and c.get('key', '') not in fx)
    sys.path.insert(0, str(ROOT / 'tools/bots')); from night import regions, finished_nights
    fin = finished_nights()   # только завершённые ночи (не день, не гейт, не идущая сейчас)
    nights = [p for p, _ in fin]
    if nights:
        S = fin[-1][1]
        # догонялки — только из ночей со строгой проверкой (chase.confirm >= 2: заход по следу беглеца, старты со свободных узлов,
        # 767745e / 6f008c6); в ночах до неё часть углов и «погоня застряла» признана ложной — не считаем
        boxes = [S['explore']['clusters']] + ([S['chase']['stuck'], S['chase']['corners']] if S['chase'].get('confirm', 1) >= 2 else [])
        cl = {k: c for d in boxes for k, c in d.items() if k not in fx}
        b = len(regions(cl, 3))   # места (связные клетки 8 м одного вида) от 3 повторений
        return (n or 0) + b, '%s + %s' % (p.relative_to(ROOT) if p else '-', nights[-1].relative_to(ROOT))
    return n, p


def number_b():
    plan = ROOT / 'tools/ps2ref/clips.tsv'
    N = sum(1 for l in plan.read_text().splitlines() if l.strip() and not l.startswith('#')) if plan.exists() else 0
    names = [l.split('\t')[0] for l in plan.read_text().splitlines() if l.strip() and not l.startswith('#')] if plan.exists() else []
    X = 0
    for nm in names:   # только клипы плана (служебные t0, t1 не в счёт)
        r = ROOT / 'build/ps2ref/clips' / nm / 'result.json'
        try: X += bool(json.loads(r.read_text()).get('inTolerance'))
        except Exception: pass
    return X, N


def disk_ids():
    """id чанков в файлах уровней 1–7 (кэш по размеру и времени файла)"""
    sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
    art = ROOT / 'hit-and-run-web/source/game/art'
    files = sorted(p for p in art.glob('l*.p3d') if re.match(r'l[1-7]', p.name))
    cache_f = ROOT / 'build/state/chunk-ids.json'; cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    ids = collections.Counter(); changed = False
    for f in files:
        st = f.stat(); key = '%s:%d:%d' % (f.name, st.st_size, int(st.st_mtime))
        if key not in cache:
            from p3d import read
            got = collections.Counter()
            def walk(c):
                got[c.id] += 1
                for k in c.children: walk(k)
            walk(read(f)); cache[key] = {hex(k): v for k, v in got.items()}; changed = True
        for k, v in cache[key].items(): ids[k] += v
    if changed:
        cache_f.parent.mkdir(parents=True, exist_ok=True); cache_f.write_text(json.dumps(cache))
    return ids, len(files)


def handlers():
    f = ROOT / 'docs/state/handlers.tsv'
    out = {}
    if f.exists():
        for l in f.read_text().splitlines():
            if l and not l.startswith('#'):
                p = l.split('\t'); out[p[0].lower()] = p[1] if len(p) > 1 else ''
    return out


def write_handlers(ids):
    """начальная таблица: id считается обработанным, если он упомянут в коде экспорта (файл:строка первой ссылки)"""
    refs = {}
    for c in CODE:
        p = ROOT / c
        if not p.exists(): continue
        for i, l in enumerate(p.read_text(errors='replace').splitlines(), 1):
            for m in re.finditer(r'0x[0-9a-fA-F]{5,8}\b', l):
                refs.setdefault(hex(int(m.group(0), 16)), '%s:%d' % (c, i))
    L = ['# id чанка\tстатус (обработчик файл:строка / проигнорировано: причина / нет)\tвстречается раз на уровнях 1–7',
         '# сгенерировано tools/tablo.py --handlers по ссылкам на id в коде экспорта; дальше правится руками по делу']
    for k, v in sorted(ids.items(), key=lambda kv: -kv[1]):
        L.append('%s\t%s\t%d' % (k, ('обработчик ' + refs[k]) if k in refs else 'нет', v))
    f = ROOT / 'docs/state/handlers.tsv'; f.parent.mkdir(parents=True, exist_ok=True); f.write_text('\n'.join(L) + '\n')
    return f


def number_c():
    ids, nf = disk_ids(); h = handlers()
    return sum(1 for k in ids if not h.get(k, 'нет').startswith(('обработчик', 'проигнорировано'))), len(ids), nf, ids


def number_d():
    """(г) открытые правки Роба: строки docs/handoff/ПРАВКИ_РОБА.md, чей статус не «на PSP» и не «принято» (28.09: наблюдения
    Роба жили в передачах и не доходили до очереди — теперь каждое сразу строка списка, а табло держит их на виду)"""
    f = ROOT / 'docs/handoff/ПРАВКИ_РОБА.md'
    if not f.exists(): return 0, 0
    # 03.10 (аудит B): номера с буквой (164б) — тоже строки; «\|» внутри ячейки — не граница колонки
    rows = [re.split(r'(?<!\\)\|', l) for l in f.read_text().splitlines() if re.match(r'^\| *\d+[а-яa-z]? *\|', l)]
    # закрыта: статус НАЧИНАЕТСЯ с «на PSP» (не «на PSP нет»), «закрыто», «принято», «подтверждено», «сверено», «на Маке»
    # (инструмент, не игра) или ссылается на другую строку («= правка N», «см. N»); и в статусе нет метки открытого
    # (30.09, аудит ведущего §2.8: частичная — открыта; 03.10, аудит B: «на PSP» в середине статуса строку не закрывает)
    shut = re.compile(r'^(на PSP(?! нет)|закрыто|принято|подтверждено|сверено|на Маке|= правк|см\. \d)')
    still = re.compile(r'Открыт|открыт|в работе|не найден|ждём|ждёт|осталось|не сделан|не сверен|вопрос В\d')
    done = sum(1 for r in rows if len(r) > 4 and shut.match(r[4].strip()) and not still.search(r[4]))
    return len(rows) - done, len(rows)


def compute():
    a, pa = number_a(); x, n = number_b(); c, nid, nf, _ = number_c(); d, dOf = number_d()
    return dict(a=a, aSrc=(pa if isinstance(pa, str) else str(pa.relative_to(ROOT))) if pa else None, b='%d/%d' % (x, n), c=c, cOf=nid, files=nf,
                d=d, dOf=dOf)


def block(t):
    return ('<!-- tablo -->\n| табло (tools/tablo.py) | число | откуда |\n|---|---|---|\n'
            '| (а) открытые естественные кластеры | %s | %s |\n| (б) эталонные клипы в допуске | %s | build/ps2ref/clips, план tools/ps2ref/clips.tsv |\n'
            '| (в) типы чанков диска без обработчика | %d из %d | %d файлов уровней 1–7, docs/state/handlers.tsv |\n'
            '| (г) правки Роба открыты (не на PSP) | %d из %d | docs/handoff/ПРАВКИ_РОБА.md — брать раньше очереди |\n<!-- /tablo -->') % (
        '—' if t['a'] is None else t['a'], t['aSrc'] or 'сводки исследователя ещё нет', t['b'], t['c'], t['cOf'], t['files'], t['d'], t['dOf'])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--write', action='store_true'); ap.add_argument('--check', action='store_true'); ap.add_argument('--handlers', action='store_true')
    a = ap.parse_args()
    if a.handlers:
        ids, _ = disk_ids(); print('->', write_handlers(ids))
    t = compute(); b = block(t)
    print('табло: (а) %s  (б) %s  (в) %d из %d  (г) %d из %d' % ('—' if t['a'] is None else t['a'], t['b'], t['c'], t['cOf'], t['d'], t['dOf']))
    st = ROOT / 'STATE.md'
    if a.write:
        s = st.read_text() if st.exists() else ''
        s = re.sub(r'<!-- tablo -->.*?<!-- /tablo -->', lambda m: b, s, flags=re.S) if '<!-- tablo -->' in s else s + '\n' + b + '\n'
        st.write_text(s); print('-> STATE.md')
    sizes = {f: (ROOT / f).stat().st_size if (ROOT / f).exists() else 0 for f in ENTRY}
    total = sum(sizes.values())
    print('вход: ' + ' + '.join('%s %.1f' % (f.split('/')[-1], v / 1024) for f, v in sizes.items()) + ' = %.1f КБ (предел 30)' % (total / 1024))
    if a.check:
        errs = []
        if not st.exists(): errs.append('нет STATE.md')
        else:
            s = st.read_text(); m = re.search(r'<!-- tablo -->.*?<!-- /tablo -->', s, flags=re.S)
            if not m: errs.append('в STATE.md нет блока табло')
            elif m.group(0) != b: errs.append('табло в STATE.md не совпадает с подсчётом (ручное число?)')
            if sizes['STATE.md'] > STATE_MAX: errs.append('STATE.md %.1f КБ > 8' % (sizes['STATE.md'] / 1024))
        if total > BUDGET: errs.append('вход %.1f КБ > 30' % (total / 1024))
        print('проверка: ' + ('; '.join(errs) + ' -> FAIL' if errs else 'OK'))
        return 1 if errs else 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
