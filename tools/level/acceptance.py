#!/usr/bin/env python3
"""Чек-лист приёмки уровня N для Роба на PSP (канон docs/КАНОН_УРОВНЯ.md §1 Ф5, §3; L1_ФИНИШ Н4): не больше 25 строк
«код места · что сделать · как в оригинале (тайм-код записи)» — из паспорта, сверки и сделанного, без ручного списка.

  python3 tools/level/acceptance.py N               -> docs/levels/LN_ПРИЁМКА.md (+ build/level/lN/acceptance.json)
  python3 tools/level/acceptance.py 1 --gate        гейт «сначала красный» (журнал build/gates/level/acceptance-lN.log)
  --runs DIR        прогоны миссионера (по умолчанию build/bots/runs/mission этой копии и основной, только чтение)
  --catalog / --gaps ФАЙЛ   подменить каталог записи / сверку (отрицательные контроли)

Откуда строки (каждая помнит источник):
  1. сверка tools/ps2ref/GAPS_LN*.md — строки таблицы статуса со словом «сделано» (в сборке, Роб не видел); тайм-коды — из
     строки «нет в порту / не так» с теми же словами (часть «без кадра» — «в записи нет»); место — миссия, которая идёт в
     записи в этот момент (хронология по каталогу CATALOG_LN.md: «Старт миссии», «Карточка миссии», механики миссий), её старт
     из паспорта -> код места (tools/place.py); у будки, костюмов, гонок, ос, машин мира — место самой вещи из паспорта;
  2. правки docs/handoff/ПРАВКИ_РОБА.md со статусом «…на PSP нет» (кроме строк, которые целиком — сверка GAPS);
  3. миссии, которые боты не проходят (последний итог каждой миссии в прогонах миссионера): «пройди на PSP»;
  4. «не сверено» сверки с тайм-кодом — «посмотри и сравни с записью» (то, что машиной не сравнить).
Одна миссия и одно место — одна строка. Гейт: ≤ 25 строк; у каждой код места = tools/place.py от точки; тайм-коды внутри
записи; миссии каталога совпадают с паспортом по названиям и идут по порядку (каталог чужого уровня -> красный)."""
import argparse, collections, json, math, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tools/level'))
MAX_LINES = 25
TC = re.compile(r'(?<![\d:])(\d{1,2}):(\d{2})(?![\d:])')
NO_FRAME = re.compile(r'без кадра|в записи нет|нет в записи')
# механика каталога -> цель миссии (единственная миссия уровня с такой целью получает время строки каталога)
OBJ_WORDS = {'follow': r'\bслежк', 'fmv': r'\bролик на тв|\bsit on the sofa', 'destroy': r'\bтаран', 'delivery': r'\bсбор на время',
             'dump': r'\bвыпав', 'buycar': r'\bмагазин машин'}


def rel(p): return str(p).replace(str(ROOT) + '/', '')


def main_root():
    """основная копия (у агентской копии build/bots пуст) — только чтение"""
    try:
        g = subprocess.run(['git', 'rev-parse', '--git-common-dir'], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        return Path(g).resolve().parent if g else ROOT
    except Exception: return ROOT


def secs(m, s): return int(m) * 60 + int(s)
def mmss(t): return f'{t // 60}:{t % 60:02d}'
def times(s): return [secs(a, b) for a, b in TC.findall(s)]
def norm(s): return re.sub(r'[^a-zа-яё0-9]+', ' ', s.lower()).strip()
def stems(s): return {w[:4] for w in norm(s).split() if len(w) >= 4}


def jac(a, b):
    A, B = stems(a), stems(b)
    return len(A & B) / max(1, len(A | B)), len(A & B)


def md_rows(path):
    """все строки markdown-таблиц файла: (заголовок раздела, [ячейки])"""
    sec, out = '', []
    for l in Path(path).read_text().splitlines():
        if l.startswith('#'): sec = l.strip('# ').strip(); continue
        if l.startswith('|') and not re.match(r'^\|\s*-', l):
            out.append((sec, [c.strip() for c in l.strip().strip('|').split('|')]))
    return out


def latest(pattern):
    fs = sorted((ROOT / 'tools/ps2ref').glob(pattern))
    return fs[-1] if fs else None


# ---------------------------------------------------------------- хронология миссий в записи (каталог)
def timeline(P, catalog, gaps):
    """-> ({миссия: начало, с}, конец записи, [проблемы]); каталог чужого уровня даёт пустые совпадения названий"""
    rows = md_rows(catalog); ms = P['missions']
    title = {norm(m['title']): m['id'] for m in ms}
    st, cards, prob = [], [], []
    for sec, c in rows:
        if len(c) < 2: continue
        if c[0] == 'Старт миссии':
            st = sorted(t[0] for t in (times(p) for p in re.split(r',\s*', c[1])) if t)
        if c[0] == 'Карточка миссии':
            for part in c[1].split(';'):
                t = times(part); nm = norm(TC.sub('', part).split('(')[0])
                if t and nm in title: cards.append((t[0], title[nm]))
                elif t and nm: prob.append(f'карточка «{nm}» {mmss(t[0])} — нет такой миссии в паспорте')
    start = {}
    for t0 in st:   # старт, за которым в минуту идёт карточка миссии с названием
        hit = [mid for tc, mid in cards if t0 <= tc <= t0 + 60]
        if hit: start.setdefault(hit[0], t0)
    for tc, mid in cards: start.setdefault(mid, tc)
    # механики каталога, которые есть только у одной миссии (слежка, ролик, таран…) -> её время
    cand = collections.defaultdict(list)
    for obj, rx in OBJ_WORDS.items():
        owners = [m['id'] for m in ms if obj in m['objs']]
        if len(owners) != 1 or owners[0] in start: continue
        cand[owners[0]] += [t for sec, c in rows if len(c) >= 2 and re.search(rx, c[0].lower()) for t in times(c[1])]
    for mid, tt in cand.items():
        if tt: start[mid] = min(tt)
    # старты без названия — сюжетным миссиям по порядку между соседями
    story = [m['id'] for m in ms if m['kind'].startswith('сюжет')]
    for t in st:
        if t in start.values() or any(abs(t - v) <= 60 for v in start.values()): continue
        prev = max((k for k in start if start[k] < t and k in story), key=lambda k: start[k], default=None)
        nxt = min((k for k in start if start[k] > t and k in story), key=lambda k: start[k], default=None)
        lo = story.index(prev) + 1 if prev else 0; hi = story.index(nxt) if nxt else len(story)
        cand = [k for k in story[lo:hi] if k not in start]
        if cand: start[cand[0]] = t
    # ещё без начала — фраза каталога или сверки «mN м:сс» (не «конец …» и не «в записи нет»)
    text = [' | '.join(c) for _, c in rows] + ([' | '.join(c) for _, c in md_rows(gaps)] if gaps and Path(gaps).exists() else [])
    for m in ms:
        if m['id'] in start: continue
        for l in text:
            for cl in re.split(r'[;,]', l):
                if re.search(rf'(?<![a-z0-9]){m["id"]}(?![0-9])', cl.lower()) and times(cl) and 'конец' not in cl and not NO_FRAME.search(cl):
                    start[m['id']] = times(cl)[0]; break
            if m['id'] in start: break
    head = Path(catalog).read_text()[:2000]
    total = max(times(head) + [max(start.values(), default=0) + 1])
    if not cards: prob.append('ни одна карточка миссии каталога не совпала с паспортом по названию')
    return dict(sorted(start.items(), key=lambda kv: kv[1])), total, prob


def mission_at(start, t, total):
    """миссия, идущая в записи в момент t: последний старт до t (конец — следующий старт)"""
    best = [(v, k) for k, v in start.items() if v <= t <= total]
    return max(best)[1] if best else None


# ---------------------------------------------------------------- источники строк
def gaps_items(gaps):
    """-> [dict(text, commit, tcs, src)]: строки статуса «сделано» + тайм-коды строки «нет / не так» с теми же словами"""
    rows = md_rows(gaps)
    ref = [c for sec, c in rows if sec.startswith(('Нет в порту', 'Есть, но не так')) and len(c) >= 3 and c[0] != '#']
    out = []
    for sec, c in rows:
        if not sec.startswith('Статус терминала') or len(c) < 2 or c[0].startswith('Пункт') or 'сделано' not in c[1]: continue
        txt = re.sub(r'^\d+(,\s*\d+)*\s+', '', c[0])
        done = next((p for p in c[1].split(';') if 'сделано' in p), c[1]).strip()
        dwords = re.sub(r'\s+', ' ', re.sub(r'сделано:?', '', done)).strip(' :')
        if dwords.startswith('(') and dwords.endswith(')') and dwords.count('(') == 1: dwords = dwords[1:-1]
        key = txt + ' ' + dwords
        # строка «нет / не так»: больше общих слов с названием пункта, потом — с названием и сделанным, потом доля
        best = max(ref, key=lambda r: (jac(txt, r[1] + ' ' + r[2])[1], jac(key, r[1] + ' ' + r[2])[1], jac(key, r[1] + ' ' + r[2])[0]), default=None)
        tcs, nofr = [], False
        if best and jac(key, best[1] + ' ' + best[2])[1] >= 1:
            cl = max(best[2].split(';'), key=lambda s: jac(key, s)[1])
            if NO_FRAME.search(cl) and jac(key, cl)[1] >= 1: nofr = True   # сделанная часть — «без кадра»: в записи её нет
            else: tcs = times(best[2])
        partial = ';' in re.sub(r'\([^()]*\)', '', c[1])   # сделано не всё («…; …» вне скобок) — в строку идёт, что именно
        out.append(dict(text=txt + (f' — {dwords}' if partial and dwords else ''), done=dwords, commit=c[2].strip('` ') if len(c) > 2 else '',
                        tcs=tcs, nofr=nofr, same=key + ' ' + (best[1] + ' ' + best[2] if best else ''), src=f"{rel(gaps)} «{txt[:40]}»"))
    return out


def short(s, n=160):
    """первая фраза (конец — «. » или «; » вне скобок) до n символов по границе слова"""
    s, depth = s.strip(), 0
    for i, ch in enumerate(s):
        depth += (ch == '(') - (ch == ')')
        if depth == 0 and ch in '.;' and (i + 1 == len(s) or s[i + 1] == ' ') and not s[max(0, i - 1)].isdigit(): s = s[:i]; break
    s = s.strip(' .;')
    return s if len(s) <= n else s[:n].rsplit(' ', 1)[0] + ' …'


def catalog_times(catalog, text):
    """тайм-коды строк каталога записи, чьё «что» делит с текстом ≥ 2 слов (латиница — от 3 букв: Hit & Run)"""
    st = lambda s: {w[:4] for w in norm(s).split() if len(w) >= 4 or (len(w) == 3 and w.isascii() and w.isalpha())}
    A = st(text)
    return sorted({t for sec, c in md_rows(catalog) if len(c) >= 2 and len(A & st(c[0])) >= 2 for t in times(c[1])})


def prav_items(prav):
    """правки «в сборке …, на PSP нет: …»; пронумерованные части «(1) … (2) …» — каждая отдельно"""
    out = []
    for sec, c in md_rows(prav):
        if len(c) < 4 or not c[0].isdigit(): continue
        m = re.search(r'в сборке.{0,60}?на PSP нет:?\s*(.*)', c[3], re.I)
        if not m: continue
        body = m.group(1).strip()
        parts = [p for p in re.split(r'\(\d+\)\s*', body) if p.strip()] if body.startswith('(1)') else [body]
        for p in parts:
            p = re.sub(r'^\d\d\.\d\d \d\d:\d\d \(EBOOT \w+\):\s*', '', p.strip())
            out.append(dict(num=int(c[0]), text=short(p), ask=c[1], src=f'ПРАВКИ_РОБА {c[0]}'))
    return out


def handoff_items():
    """ПЕРЕДАЧА_ТЕРМИНАЛА (последняя) §2 «Сделано вечером (в сборке, на PSP нет)»: пункты «- **заголовок:** текст»; пункт,
    чей коммит позже убран за флаг («за флагом» в сообщении более позднего коммита, где он назван), — не для приёмки"""
    fs = sorted((ROOT / 'docs/handoff').glob('ПЕРЕДАЧА_ТЕРМИНАЛА_*.md'))
    if not fs: return []
    txt = fs[-1].read_text(); m = re.search(r'\n## 2 ·[^\n]*\n(.*?)(?=\n## )', txt, re.S)
    if not m: return []
    out = []
    for b in re.split(r'\n- ', '\n' + m.group(1).strip()):
        b = ' '.join(b.split())
        h = re.match(r'\*\*(.+?)\*\*\s*(.*)', b)
        if not h or re.search(r'инструмент', h.group(1), re.I): continue
        head, body = h.group(1).strip(' :'), h.group(2)
        flagged = False
        for sha in re.findall(r'`([0-9a-f]{7})`', b):
            log = subprocess.run(['git', 'log', '--format=%s', f'--grep={sha}'], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout
            if 'за флагом' in log: flagged = True
        if flagged: continue
        out.append(dict(text=f'{head}: {short(body, 110)}', src=f'{rel(fs[-1])} §2 «{head[:30]}»'))
    return out


def mission_results(runs_dirs):
    """последний итог каждой миссии по прогонам миссионера (<время>/missions.md, колонки по заголовку; новые поверх старых)"""
    res = {}
    runs = sorted((r for d in runs_dirs if d.exists() for r in d.iterdir() if re.fullmatch(r'\d{8}-\d{6}', r.name)), key=lambda r: r.name)
    for run in runs:
        f = run / 'missions.md'
        if not f.exists(): continue
        col = None
        for l in f.read_text().splitlines():
            c = [x.strip() for x in l.strip().strip('|').split('|')]
            if c and c[0] == 'миссия': col = {k: i for i, k in enumerate(c)}; continue
            if col and len(c) >= len(col) and re.match(r'^(m\d|sr\d|gr\d|bm\d)\b', c[0]):
                g = lambda k: c[col[k]] if k in col else ''
                res[c[0].split()[0]] = dict(verdict=g('итог'), cls=g('класс'), why=g('почему'), secs=g('время, с'), run=run.name)
    return res


def unverified(gaps):
    return [dict(text=c[0], tcs=times(c[1]), src=f'{rel(gaps)} не сверено «{c[0][:30]}»')
            for sec, c in md_rows(gaps) if sec.startswith('Не сверено') and len(c) >= 2 and c[0] != 'Что' and times(c[1])]


# ---------------------------------------------------------------- места
def dist(a, b): return math.hypot(a[0] - b[0], a[2] - b[2])


def entity_place(P, text):
    """слова -> вещь из паспорта (точка, подпись); None — нет вещи"""
    t = text.lower(); s0 = P['start']['pos']; c = P['collect']
    if re.search(r'\bбудк|booth', t) and c['booths']:
        b = min(c['booths'], key=lambda b: dist(b['pos'], s0)); return b['pos'], f"будка {b['name']}"
    if re.search(r'\bкостюм|\bгардероб|\bвешалк|\bодежд|\bскин|shirtdollar', t) and c['skin_spots']:
        files = {x['file'] for x in c['skin_spots']}
        rs = [r for r in P['rooms'] if r['file'] in files and r['door']]
        if rs:
            r = min(rs, key=lambda r: dist(r['door']['pos'], s0)); return r['door']['pos'], f"дверь: {r['ru']}"
    if re.search(r'\bгонк|\bконус|\bворота\b', t):
        m = next((m for m in P['missions'] if m['kind'] == 'гонка' and m['start']), None)
        if m: return m['start']['pos'], m['id']
    if re.search(r'\bос[аы]\b', t) and c['wasps']:
        w = min(c['wasps'], key=lambda w: dist(w['pos'], s0)); return w['pos'], f"оса {w['name']}"
    for wc in c.get('world_cars', []):
        if re.search(r'ракетн|rocket', t) and wc['car'].startswith('rocke'): return wc['pos'], wc['car']
    return None


def line_place(P, start, total, text, tcs, look=False):
    import place
    ids = [m['id'] for m in P['missions'] if re.search(rf'(?<![a-z0-9]){m["id"]}(?![0-9])', text.lower())]
    e = entity_place(P, text)
    mid = ids[0] if ids and look else (mission_at(start, tcs[0], total) if tcs and not look else None)
    m = next((x for x in P['missions'] if x['id'] == mid and x['start']), None)
    if e and not (look and m): pos, why = e
    elif m: pos, why = m['start']['pos'], mid
    else: pos, why = P['start']['pos'], 'старт уровня'
    return dict(code=f"L{P['level']} {place.code(pos[0], pos[2])}", pos=[round(v, 1) for v in pos], why=why)


def fmt_tc(tcs, limit=4): return ', '.join(mmss(t) for t in tcs[:limit]) if tcs else 'в записи нет'


def bots_why(r):
    w = r['why'] or r['cls']
    if 'правило миссии' in w: return 'провал правилом миссии (таймер, урон)'
    return f"{r['verdict']}: {w}"


# ---------------------------------------------------------------- сборка чек-листа
def build(n, catalog=None, gaps=None, runs=None, P=None):
    catalog = Path(catalog) if catalog else ROOT / f'tools/ps2ref/CATALOG_L{n}.md'
    gaps = Path(gaps) if gaps else latest(f'GAPS_L{n}_*.md') or latest(f'GAPS_L{n}.md')
    runs = [Path(runs)] if runs else [ROOT / 'build/bots/runs/mission', main_root() / 'build/bots/runs/mission']
    start, total, prob = timeline(P, catalog, gaps) if catalog.exists() else ({}, 0, ['нет каталога записи ' + rel(catalog)])
    items = []
    res = mission_results(runs)
    for m in P['missions']:   # миссии, которые боты не проходят, — первыми: строка «пройди»
        r = res.get(m['id'])
        if not r or r['verdict'] == 'пройдена': continue
        t0 = start.get(m['id'])
        nxt = min((v for v in start.values() if t0 is not None and v > t0), default=total)
        pl = dict(code=f"L{n} {m['start']['code']}" if m['start'] else f'L{n} --', pos=m['start']['pos'] if m['start'] else None, why=m['id'])
        tm = f", таймер {m['timer']}" if m['timer'] != '—' else ''
        items.append(dict(kind='миссия', mission=m['id'], place=pl, act=f"пройди {m['id']} «{m['title'].strip()}»{tm} — у ботов {bots_why(r)}",
                          orig=f'{mmss(t0)}–{mmss(nxt)}' if t0 is not None else 'в записи нет', src=f"миссионер {r['run']}"))
    seen, nums = [], set()   # взятые «проверь»: та же вещь из другого источника не берётся
    def same(t):
        """половина слов общая (≥ 2) — или треть и начало фразы (название вещи) совпало тремя словами"""
        A, head = stems(t), stems(re.split(r'\s[—:]\s|:\s', t)[0])
        for s, title in seen:
            k = len(A & stems(s)); r = k / max(1, min(len(A), len(stems(s))))
            if k >= 2 and (r >= 0.5 or (r >= 0.3 and len(head & stems(title)) >= 3)): return True
        return False
    if gaps and gaps.exists():
        for g in gaps_items(gaps):
            seen.append((g['same'], g['text']))
            pl = line_place(P, start, total, g['text'] + ' ' + g['done'], g['tcs'])
            items.append(dict(kind='проверь', mission=pl['why'], place=pl, act=g['text'],
                              orig='в записи нет' if g['nofr'] else fmt_tc(g['tcs']), src=g['src'] + (f" {g['commit']}" if g['commit'] else '')))
    for h in handoff_items():
        if same(h['text']): continue
        seen.append((h['text'], h['text'])); nums |= set(re.findall(r'\b(\d{2,3})\b', h['text'].split(':')[0]))
        pl = line_place(P, start, total, h['text'], [])
        tc = catalog_times(catalog, h['text']) if catalog.exists() else []
        items.append(dict(kind='проверь', mission=pl['why'], place=pl, act=h['text'], orig=fmt_tc(tc), src=h['src']))
    for r in prav_items(ROOT / 'docs/handoff/ПРАВКИ_РОБА.md'):
        if str(r['num']) in nums or same(r['text']): continue   # правка уже в пункте передачи с её номером
        seen.append((r['text'], r['text']))
        pl = line_place(P, start, total, r['ask'] + ' ' + r['text'], [])
        tc = catalog_times(catalog, r['text']) if catalog.exists() else []
        items.append(dict(kind='проверь', mission=pl['why'], place=pl, act=f"{r['num']} {r['text']}", orig=fmt_tc(tc), src=r['src']))
    if gaps and gaps.exists():
        for u in unverified(gaps):
            pl = line_place(P, start, total, u['text'], u['tcs'], look=True)
            items.append(dict(kind='посмотри', mission=pl['why'], place=pl, act=u['text'][:1].lower() + u['text'][1:], orig=fmt_tc(u['tcs']), src=u['src']))
    merged, order = {}, []
    for it in items:   # одна миссия и одно место — одна строка
        key = (it['place']['code'], it['mission'])
        if key not in merged: merged[key] = dict(it, parts=[], origs=[], srcs=[]); order.append(key)
        m = merged[key]; m['parts'].append((it['kind'], it['act'])); m['srcs'].append(it['src']); m['origs'].append(it['orig'])
        if it['kind'] == 'миссия': m['kind'] = 'миссия'
    lines = []
    for k in order:
        m = merged[k]
        acts = [a for kd, a in m['parts'] if kd == 'миссия']
        for kd in ('проверь', 'посмотри'):
            got = [a for k2, a in m['parts'] if k2 == kd]
            if got: acts.append(f"{kd}: " + '; '.join(got))
        origs = [o for o in m['origs'] if o != 'в записи нет'] or ['в записи нет']
        lines.append(dict(kind=m['kind'], mission=m['mission'], place=m['place'], act='; '.join(acts),
                          orig='; '.join(dict.fromkeys(origs)), src='; '.join(m['srcs'])))
    return dict(level=n, generated=time.strftime('%Y-%m-%d %H:%M'), catalog=rel(catalog), gaps=rel(gaps) if gaps else None,
                timeline={k: mmss(v) for k, v in start.items()}, record_end=mmss(total), lines=lines, problems=prob,
                missions_bots={k: v['verdict'] for k, v in res.items()})


def verify(A, P, R):
    import place
    ls = A['lines']
    R.check(0 < len(ls) <= MAX_LINES, f'строк чек-листа {len(ls)} (≤ {MAX_LINES})')
    tot = secs(*A['record_end'].split(':'))
    for i, l in enumerate(ls, 1):
        c = l['place']['code'].split()[-1]; pos = l['place']['pos']
        R.check(pos is not None and c != '--' and place.code(pos[0], pos[2]) == c, f'строка {i}: код места {l["place"]["code"]} = tools/place.py от точки', f'{pos}')
        R.check(all(0 <= t <= tot for t in times(l['orig'])), f'строка {i}: тайм-коды внутри записи (≤ {A["record_end"]})', l['orig'])
    R.check(not A['problems'], 'каталог записи совпадает с паспортом (названия миссий)', '; '.join(A['problems'])[:200])
    story = [m['id'] for m in P['missions'] if m['kind'].startswith('сюжет')]
    seq = [k for k in A['timeline'] if k in story]
    R.check(seq == sorted(seq, key=story.index) and len(seq) >= 0.75 * len(story),
            f'хронология записи: сюжетные миссии по порядку ({len(seq)} из {len(story)})', ' '.join(f'{k} {v}' for k, v in A['timeline'].items()))


def fmt_md(A):
    L = [f"# Уровень {A['level']} · приёмка на PSP (Ф5)", '',
         f"Сгенерирован `tools/level/acceptance.py {A['level']}` {A['generated']}: паспорт, сверка `{A['gaps']}`, правки «на PSP нет», "
         f"итоги ботов. Запись оригинала — `build/ps2ref/external/yt-bziOipI4gDI.mp4` (тайм-коды по ролику, 0:00–{A['record_end']}). "
         "Код места — как на паузе внизу слева (`python tools/place.py \"L1 K9-7\"` — точка). Ответ на строку — в `ВЕРДИКТЫ.md`: «ок» или «не так: …».",
         '', '| # | код места | что сделать | как в оригинале (запись) |', '|---|---|---|---|']
    for i, l in enumerate(A['lines'], 1):
        L.append(f"| {i} | {l['place']['code']} | {l['act'].replace('|', '/')} | {l['orig']} |")
    L += ['', 'Источники: ' + '; '.join(f"{i} — {l['src']}" for i, l in enumerate(A['lines'], 1)) + '.',
          '', 'Миссии в записи (начало, по каталогу): ' + ', '.join(f'{k} {v}' for k, v in A['timeline'].items())
          + '; гонок sr1–sr3 и gr1 в записи нет.' if A['level'] == 1 else '']
    return '\n'.join(L) + '\n'


class Rep:
    def __init__(self, quiet=False): self.rows = []; self.quiet = quiet
    def check(self, ok, what, det=''):
        self.rows.append(('PASS' if ok else 'FAIL', what, det))
        if not self.quiet: print(f"  {'PASS' if ok else 'FAIL'} {what}" + (f' — {det}' if det else ''), flush=True)
        return ok
    @property
    def failed(self): return any(s == 'FAIL' for s, _, _ in self.rows)


def load_passport(n):
    import passport as PP
    js = ROOT / f'build/level/l{n}/passport.json'
    return json.loads(js.read_text()) if js.exists() else PP.collect(n)


def gate(n, runs=None):
    P = load_passport(n)
    log = ROOT / f'build/gates/level/acceptance-l{n}.log'; log.parent.mkdir(parents=True, exist_ok=True)
    tmp = ROOT / f'build/level/l{n}/gate'; tmp.mkdir(parents=True, exist_ok=True)
    other = (ROOT / f'tools/ps2ref/CATALOG_L{n}.md').read_text()
    for m in P['missions']: other = other.replace(m['title'].strip(), m['title'].strip()[::-1])   # названия чужих миссий
    (tmp / 'catalog_foreign.md').write_text(other)
    gaps = latest(f'GAPS_L{n}_*.md')
    (tmp / 'gaps_badtc.md').write_text(gaps.read_text().replace('| 2:14, 4:03', '| 72:14, 4:03'))
    cases = [('RED', 'каталог записи чужого уровня', dict(catalog=tmp / 'catalog_foreign.md')),
             ('RED', 'тайм-код за концом записи (72:14)', dict(gaps=tmp / 'gaps_badtc.md')),
             ('RED', 'чек-лист длиннее 25 строк', dict(extra=30)),
             ('RED', 'код места не от точки (испорчен)', dict(badcode=True)),
             ('GREEN', f'настоящий уровень {n}', dict())]
    lines, ok_all = [], True
    for want, what, kw in cases:
        A = build(n, catalog=kw.get('catalog'), gaps=kw.get('gaps'), runs=runs, P=P)
        if kw.get('extra'): A['lines'] = A['lines'] + [dict(A['lines'][0])] * kw['extra']
        if kw.get('badcode'): A['lines'][0] = dict(A['lines'][0], place=dict(A['lines'][0]['place'], code=f'L{n} A1-1'))
        R = Rep(quiet=True); verify(A, P, R)
        fails = [w for s, w, _ in R.rows if s == 'FAIL']
        good = (want == 'RED') == bool(fails); ok_all &= good
        s = f"{want:5} {'OK ' if good else 'BAD'} {what}: FAIL {len(fails)}" + (f" ({'; '.join(fails[:3])})" if fails else '') + f", строк {len(A['lines'])}"
        print(s, flush=True); lines.append(s)
    lines.append('RESULT: ' + ('PASS' if ok_all else 'FAIL'))
    log.write_text(time.strftime('%Y-%m-%d %H:%M') + f' acceptance.py {n} --gate\n' + '\n'.join(lines) + '\n')
    print(lines[-1], '->', rel(log))
    return 0 if ok_all else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('level', type=int)
    ap.add_argument('--gate', action='store_true'); ap.add_argument('--runs'); ap.add_argument('--catalog'); ap.add_argument('--gaps')
    ap.add_argument('--out'); ap.add_argument('--no-write', action='store_true')
    a = ap.parse_args()
    if a.gate: return gate(a.level, a.runs)
    P = load_passport(a.level)
    A = build(a.level, a.catalog, a.gaps, a.runs, P)
    R = Rep(quiet=True); verify(A, P, R)
    for s, w, d in R.rows:
        if s != 'PASS': print(f'  {s} {w} — {d}')
    if not a.no_write:
        out = Path(a.out) if a.out else ROOT / f'docs/levels/L{a.level}_ПРИЁМКА.md'
        out.parent.mkdir(parents=True, exist_ok=True); out.write_text(fmt_md(A))
        jf = ROOT / f'build/level/l{a.level}/acceptance.json'; jf.parent.mkdir(parents=True, exist_ok=True)
        jf.write_text(json.dumps(A, ensure_ascii=False, indent=1))
        print(f"чек-лист -> {rel(out)} ({len(A['lines'])} строк), данные -> {rel(jf)}")
    print('RESULT:', 'FAIL' if R.failed else 'PASS')
    return 1 if R.failed else 0


if __name__ == '__main__':
    sys.exit(main())
