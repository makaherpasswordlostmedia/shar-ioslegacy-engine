#!/usr/bin/env python3
"""Правки 269/273/276, ступень 0 — проба Media Engine (viewer/me). Гейт на Маке и в безголовом PPSSPP (без окна и звука).
Сам ME эмулятор не исполняет: то, что код живёт на ME, проверяет только PSP (тур TEST 8, tests/me/psp_test8_me.txt).
  1 Мак: задание meJobSum/meJobWord (viewer/me/mebox.h) — суммы 100 заданий бит в бит с независимым подсчётом (Python);
    одна устаревшая строка кэша (16 слов прошлого задания) меняет сумму у каждого задания.
  2 Модуль: make -C viewer/me; код, который исполняет ME (meTask, meWork, meSafeTaskMistFinish), — без $gp и syscall, вызовы
    только внутри набора; meTask выходит хвостовым переходом в meSafeTaskMistFinish со снятым кадром стека; выход в обработчик
    ME — jr на 0x883004c0 (lui 0x8830 + 0x4c0) с -567 в слове состояния.
  3 Эмулятор (EBOOT аргументом):
    A  «flag meprobe 1» -> «ME skip emu» в smoke.txt и в чёрном ящике, модуль не грузится (нет me.txt); «flag mefmv» -> ролик
       gracie сыгран (MSNFMV played=1 frames>0); END.
    N  файл nome рядом с EBOOT + «flag meprobe 2» -> «ME skip nome», нет me.txt, END.
    R  КРАСНЫЙ: «flag meprobe 2» — защита эмулятора снята, вместо модуля пустышка -> строки «ME skip emu» нет, есть
       «ME probe ok=0 err=load»: без защиты игра пошла бы грузить модуль ядра (настоящий sharme.prx в PPSSPP роняет сам
       эмулятор, rc -11, замер 04.10 07:25).
Правка 276 (пилот: смешивание звука на ME, viewer/mixdsp.h — одна функция для Мака, главного процессора и ME):
  1м Мак: tests/audio/host (dump всех звуков и дорожек, стыки петель + demo 20 с) — путь задания (задание уезжает в другую
     память, старое затирается, счёт там, итог обратно: -DMIX_JOB_COPY=1) бит в бит с прямым; КРАСНЫЙ -DMIX_JOB_RED=1 (копия не
     обновляется — как ME без сброса кэша главного) обязан разойтись
  2м Модуль: код ME (meTask, meWork и всё mix*) — без вызовов наружу; КРАСНЫЙ: сборка без -fno-tree-loop-distribute-patterns
     -mno-check-zero-division (ME_SAFE=) обязана упасть на «переход наружу memset»/«break»
  3м Эмулятор, флаг-файл meaudio рядом с EBOOT:
    G  «1» -> «ME audio skip emu», в AUDV «me=-» (в эмуляторе ME нет — звук на главном, как без файла)
    E  «3» -> конвейер с «ME» потоком на главном: AUDV «me=on≥80» до и после ролика gracie (ролик целиком — пауза ME звуку), END
    T  «4» -> «ME» молчит: «me=off:timeout@1», музыка идёт дальше (дорожка сменилась intro -> sunday_drive), ролик целиком, END
    RG КРАСНЫЙ «2» (защита эмулятора снята) + пустышка вместо sharme.prx -> «ME audio off: load:…» — без защиты игра грузила бы модуль
Правка 313 (Роб 04.10: «делегируй Media Engine прозрачные элементы, свечение, музыку»):
  1ч Мак, частицы: прежний viewer/fx.c (эталон tests/me/fx_host/fx_ref313.c) и новый (viewer/fx.c + viewer/fxdsp.c — счёт, который
     берёт ME) на стенде tests/me/fx_host/fx_host.c (900 кадров: дым и огонь машины, взрыв с биллбордами, обломки, искры, пыль,
     блёстки, спрайты; камера вплотную и спиной) — вывод побайтно один; путь задания (FX_JOB_COPY: задание уезжает в другую память)
     — тот же вывод; КРАСНЫЕ: копия не обновляется (FX_JOB_RED) и expf на 1 ulp — обязаны разойтись
  1м Мак, микшер: + схема k (ME_MEM_KERN, -DMIX_JOB_COPY=2: в «ядро» и обратно только mixJobIn/mixJobOut) бит в бит; КРАСНЫЙ — итог
     без заголовков окон потоков
  2м Модуль: код ME — замыкание вызовов от meTask по дизассемблеру: без syscall/break/teq/$gp/косвенных вызовов, только наши функции
     (me*, mix*, fxd*) и чистые функции libm.a; плавающая точка — только в fxd* и libm (звук — целые); счёт частиц у игры и у модуля —
     один машинный код (fxdsp.c.obj игры и fxdsp_me.o модуля: .text, константы, релокации — побайтно)
  3ч Эмулятор, флаг-файл mefx (служба ME общая со звуком, viewer/me/meprobe.c): «1» — «ME fx skip emu»; «3» — пустышка ME на главном:
     частицы считаются «на ME» (MEPROF mefx=on…), ролик, END; «4» — ME молчит: «off:timeout@1», частицы дальше на главном; звук «3» +
     частицы «3» со схемой k (файл mescheme) — два клиента одной службы: оба on, занятость ME не роняет игру
python3 tests/me/run.py [EBOOT] -> 0 = PASS. ME_GATE_OUT — папка гейта (по умолчанию build/gates/me); ME_GATE_PREFIX — приставка имён
сценариев (параллельные прогоны не мешают друг другу)"""
import hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'
RUNS = Path(os.environ.get('SCEN_ROOT', '/Users/USER/Downloads/shar-psp')) / 'build/twins/scen/full'
OUT = Path(os.environ.get('ME_GATE_OUT', str(ROOT / 'build/gates/me')))
PFX = os.environ.get('ME_GATE_PREFIX', '')
SHR = Path(os.environ.get('SCEN_ROOT', '/Users/USER/Downloads/shar-psp')) / 'build'   # данные (пакеты) — сборка build/ репозитория
PSPDEV = Path(os.environ.get('PSPDEV', str(ROOT / 'pspdev')))
M32 = 0xffffffff
EBOOT_PATH = ROOT / 'viewer/build/EBOOT.PBP'


def mix(k, i):
    x = (i * 0x9e3779b9 + k * 0x85ebca6b) & M32
    x ^= x >> 16; x = (x * 0x7feb352d) & M32; x ^= x >> 15; x = (x * 0x846ca68b) & M32; x ^= x >> 16
    return x


def fnv(words):
    s = 0x811c9dc5
    for w in words: s = ((s ^ w) * 16777619) & M32
    return s


def step_mac():
    exe = OUT / 'sum_test'
    r = subprocess.run(['cc', '-O2', '-Wall', '-o', str(exe), str(ROOT / 'tests/me/sum_test.c')], capture_output=True, text=True)
    if r.returncode: return False, 'Мак: не собрался sum_test: ' + r.stderr.strip()[:200]
    got = dict(((a, int(k)), v) for a, k, v in (l.split() for l in subprocess.run([str(exe)], capture_output=True, text=True).stdout.splitlines()))
    bad = stale_same = 0
    for k in range(1, 101):
        w = [mix(k, i) for i in range(16384)]; want = fnv(w)
        if got.get(('job', k)) != f'{want:08x}': bad += 1
        if k > 1:
            for i in range(1024, 1040): w[i] = mix(k - 1, i)
            st = fnv(w)
            if got.get(('stale', k)) != f'{st:08x}': bad += 1
            if st == want: stale_same += 1
    ok = bad == 0 and stale_same == 0
    return ok, f'Мак: 100 сумм бит в бит с Python — расхождений {bad}; устаревшая строка не меняет сумму в {stale_same} из 99'


def step_mac_mix():
    pack = Path(os.environ.get('SFX_PACK', '/Users/USER/Downloads/shar-psp/build/audio'))
    if not (pack / 'sfx.sab').exists(): return False, f'Мак, микшер: нет пакета звука {pack}'
    def run(name, flags):
        exe = OUT / f'audio_host_{name}'
        r = subprocess.run(['cc', '-O2', '-w', '-DAUDIO_HOST', *flags, '-I', str(ROOT / 'viewer'), '-o', str(exe),
                            str(ROOT / 'tests/audio/host/audio_host.c'), str(ROOT / 'viewer/audio.c'), '-lm'], capture_output=True, text=True)
        if r.returncode: return None, 'сборка: ' + r.stderr.strip()[:200]
        d = OUT / f'mix_{name}'
        if d.exists(): d.rename(d.with_name(d.name + '-previous-' + str(time.time_ns())))
        d.mkdir(parents=True)
        rd = subprocess.run([str(exe), 'dump', str(pack) + '/', str(d)], capture_output=True, text=True)
        rm = subprocess.run([str(exe), 'demo', str(pack) + '/', str(d / 'demo.wav')], capture_output=True)
        o = rd.stdout.strip()
        negative = '-DMIX_JOB_RED=1' in flags
        if not negative and (rd.returncode or rm.returncode):
            return None, f'{name}: incomplete dump/demo: {(rd.stderr or rm.stderr).strip()[:200]}'
        if not negative and any(f.stat().st_size == 0 for f in d.glob('*.raw')):
            return None, f'{name}: empty raw output'
        h = {f.name: hashlib.md5(f.read_bytes()).hexdigest() for f in sorted(d.iterdir())}
        (OUT / f'mix_{name}_hashes.json').write_text(json.dumps(
            dict(flags=flags, dump_rc=rd.returncode, demo_rc=rm.returncode,
                 dump=rd.stdout, stderr=rd.stderr, files=h), ensure_ascii=False, indent=2) + '\n')
        return h, o
    hd, od = run('direct', []); hc, oc = run('job', ['-DMIX_JOB_COPY=1']); hr, orr = run('red', ['-DMIX_JOB_COPY=1', '-DMIX_JOB_RED=1'])
    hk, ok_ = run('kern', ['-DMIX_JOB_COPY=2']); hkr, okr = run('kernred', ['-DMIX_JOB_COPY=2', '-DMIX_JOB_RED=1'])   # правка 313
    if hd is None or hc is None or hr is None or hk is None or hkr is None:
        return False, f'Мак, микшер: {od if hd is None else oc if hc is None else orr if hr is None else ok_ if hk is None else okr}'
    same = sum(1 for k in hd if hc.get(k) == hd[k]); red = sum(1 for k in hd if hr.get(k) != hd[k])
    samek = sum(1 for k in hd if hk.get(k) == hd[k]); redk = sum(1 for k in hd if hkr.get(k) != hd[k])
    ok = (len(hd) > 100 and same == len(hd) and len(hc) == len(hd) and red > len(hd) // 2 and samek == len(hd) and len(hk) == len(hd)
          and redk > 0)
    return ok, (f'Мак, микшер: путь задания бит в бит с прямым — {same}/{len(hd)} файлов (dump+demo; {od}); '
                f'КРАСНЫЙ (копия задания не обновляется) — {"пойман" if red > len(hd) // 2 else "НЕ ПОЙМАН"}: разошлось {red}/{len(hd)}; '
                f'схема k (перенос в ядро mixJobIn/mixJobOut) — {samek}/{len(hd)}; КРАСНЫЙ k (окна потоков не вернулись) — '
                f'{"пойман" if redk else "НЕ ПОЙМАН"}: разошлось {redk}/{len(hd)}')


def step_mac_k1():
    """правка 410, К1: сброс кэша задания звука по частям (viewer/audio.c wbBuild/meKick). Модель несогласованного кэша (-DMIX_JOB_COPY=3,
    audio.c mixRunModel): ME видит только сброшенные участки, главный после ответа — свежими только их. Зелёное: dump+demo бит в бит с
    прямым счётом, «on» у ME = у главного (onbad=0), запись мимо сброса = 0 (stray=0), строк кэша на буфер в demo ≤ 50 % задания.
    Красные (каждый обязан упасть на своём числе): прежний сброс целиком ME_WB_OLD=1 — 684 строки на буфер (гейт объёма);
    ME_WB_RED=1 — П3, «on=0» замолчавшего голоса не сброшен: onbad>0 (выход при этом совпадает — замолчавший голос тих, поэтому нужен
    счётчик, а не сравнение звука); ME_WB_RED=2 — окна потоков без данных: выход расходится и stray>0"""
    pack = Path(os.environ.get('SFX_PACK', '/Users/USER/Downloads/shar-psp/build/audio'))
    if not (pack / 'sfx.sab').exists(): return False, f'Мак, К1: нет пакета звука {pack}'
    def run(name, flags):
        exe = OUT / f'k1host_{name}'
        r = subprocess.run(['cc', '-O2', '-w', '-DAUDIO_HOST', *flags, '-I', str(ROOT / 'viewer'), '-o', str(exe),
                            str(ROOT / 'tests/audio/host/audio_host.c'), str(ROOT / 'viewer/audio.c'), '-lm'], capture_output=True, text=True)
        if r.returncode: return None, 'сборка: ' + r.stderr.strip()[:200]
        d = OUT / f'k1_{name}'
        if d.exists(): d.rename(d.with_name(d.name + '-previous-' + str(time.time_ns())))
        d.mkdir(parents=True)
        rd = subprocess.run([str(exe), 'dump', str(pack) + '/', str(d)], capture_output=True, text=True)
        rm = subprocess.run([str(exe), 'demo', str(pack) + '/', str(d / 'demo.wav')], capture_output=True, text=True)
        h = {f.name: hashlib.md5(f.read_bytes()).hexdigest() for f in sorted(d.iterdir())}
        st = {}
        for k, txt in (('dump', rd.stderr), ('demo', rm.stderr)):
            m = re.search(r'WBSTAT buffers=(\d+) lines_avg=([\d.]+) full_lines=(\d+) full=(\d+) onbad=(\d+) stray=(\d+)', txt)
            st[k] = dict(zip(('buffers', 'lines', 'full_lines', 'full', 'onbad', 'stray'), map(float, m.groups()))) if m else None
        (OUT / f'k1_{name}.json').write_text(json.dumps(dict(flags=flags, stats=st, files=h), ensure_ascii=False, indent=2) + '\n')
        return h, st
    hd, _ = run('direct', [])
    res = {n: run(n, f) for n, f in (('new', ['-DMIX_JOB_COPY=3']), ('old', ['-DMIX_JOB_COPY=3', '-DME_WB_OLD=1']),
                                     ('red1', ['-DMIX_JOB_COPY=3', '-DME_WB_RED=1']), ('red2', ['-DMIX_JOB_COPY=3', '-DME_WB_RED=2']))}
    if hd is None or any(h is None or not st.get('dump') or not st.get('demo') for h, st in res.values()):
        return False, f'Мак, К1: сборка или WBSTAT не вышли {[(n, st) for n, (h, st) in res.items()]}'
    diff = {n: sum(1 for k in hd if h.get(k) != hd[k]) for n, (h, st) in res.items()}
    S = {n: st for n, (h, st) in res.items()}
    tot = lambda n, key: S[n]['dump'][key] + S[n]['demo'][key]
    nl, ol, fl = S['new']['demo']['lines'], S['old']['demo']['lines'], S['new']['demo']['full_lines']
    green = len(hd) > 100 and diff['new'] == 0 and tot('new', 'onbad') == 0 and tot('new', 'stray') == 0 and nl <= fl / 2
    red_old = ol > fl / 2
    red1 = tot('red1', 'onbad') > 0
    red2 = diff['red2'] > 0 and tot('red2', 'stray') > 0
    ok = green and red_old and red1 and red2
    return ok, (f'Мак, К1 (сброс по частям, модель несогласованного кэша): бит в бит {len(hd) - diff["new"]}/{len(hd)} файлов; '
                f'onbad={tot("new", "onbad"):.0f} stray={tot("new", "stray"):.0f}; строк на буфер demo {nl:.1f} из {fl:.0f} '
                f'(dump {S["new"]["dump"]["lines"]:.1f}); КРАСНЫЙ прежний сброс целиком — {ol:.0f} строк: {"пойман" if red_old else "НЕ ПОЙМАН"}; '
                f'КРАСНЫЙ П3 (on=0 не сброшен) — onbad={tot("red1", "onbad"):.0f}, выход разошёлся в {diff["red1"]} файлах: '
                f'{"пойман" if red1 else "НЕ ПОЙМАН"}; КРАСНЫЙ окна без данных — разошлось {diff["red2"]}/{len(hd)}, '
                f'stray={tot("red2", "stray"):.0f}: {"пойман" if red2 else "НЕ ПОЙМАН"}')


def step_mac_bbcpu():
    """правка 410, шаг 0: доля потока BBCPU (viewer/bbcpu.h). Новый расчёт: норма 5 % без событий, смена уровня (runClocks меньше базы,
    числа T3 smoke.txt:5024) — 0 и событие, 103 % — 100 и событие. КРАСНЫЙ BBCPU_OLD=1 обязан дать ровно 815353985/815354014 тура T3"""
    def run(old):
        exe = OUT / f'bbcpu_{old}'
        r = subprocess.run(['cc', '-O2', '-Wall', '-I', str(ROOT / 'viewer'), f'-DBBCPU_OLD={old}', '-o', str(exe), str(ROOT / 'tests/me/bbcpu_host.c')],
                           capture_output=True, text=True)
        if r.returncode: return None
        return {l.split()[0]: l.split()[1:] for l in subprocess.run([str(exe)], capture_output=True, text=True).stdout.splitlines()}
    n, o = run(0), run(1)
    if not n or not o: return False, 'Мак, BBCPU: не собрался tests/me/bbcpu_host.c'
    green = n['norm'] == ['0', '0'] and n['T3mix'] == ['0', '1'] and n['T3io'] == ['0', '1'] and n['after'] == ['4', '0'] and n['over'] == ['100', '2']
    red = o['T3mix'][0] == '815353985' and o['T3io'][0] == '815354014'
    return green and red, (f'Мак, BBCPU: смена уровня — доля {n["T3mix"][0]}/{n["T3io"][0]} событие {n["T3mix"][1]}, следующая секунда {n["after"][0]} %, '
                           f'103 % -> {n["over"][0]} событие {n["over"][1]}: {"ok" if green else "ПРОВАЛ"}; КРАСНЫЙ прежний расчёт — '
                           f'{o["T3mix"][0]}/{o["T3io"][0]} (тур T3: 815353985/815354014): {"пойман" if red else "НЕ ПОЙМАН"}')


def step_mac_fx():
    """правка 313: частицы — прежний fx.c (эталон) и новый с fxdsp.c (счёт ME) на одном стенде — вывод побайтно один"""
    pack = SHR / 'fx.shr'
    if not pack.exists(): return False, f'Мак, частицы: нет пакета {pack}'
    H = ROOT / 'tests/me/fx_host'; V = ROOT / 'viewer'
    def run(name, srcs, flags):
        exe = OUT / f'fx_{name}'; txt = OUT / f'fx_{name}.txt'
        # №391 is checked separately against road normals; retain the old explosion for this migration equivalence oracle
        r = subprocess.run(['cc', '-O2', '-ffp-contract=off', '-w', '-I', str(H), '-I', str(V), '-DFXD_EXPF=expf', '-DFX_BOOM_OLD=1', *flags, '-o', str(exe),
                            str(H / 'fx_host.c'), *map(str, srcs), '-lm'], capture_output=True, text=True)
        if r.returncode: return None, 'сборка ' + name + ': ' + r.stderr.strip()[:200]
        o = subprocess.run([str(exe), str(pack), str(txt), '900'], capture_output=True, text=True)
        if o.returncode or not txt.exists(): return None, f'запуск {name}: rc {o.returncode}'
        return txt.read_bytes(), o.stdout.strip()
    new = [V / 'fx.c', V / 'fxdsp.c']
    ref, oref = run('ref', [H / 'fx_ref313.c'], [])
    cur, ocur = run('new', new, [])
    cp, ocp = run('copy', new, ['-DFX_JOB_COPY=1', '-DFX_JOB_RED=0'])
    rc, orc = run('copyred', new, ['-DFX_JOB_COPY=1', '-DFX_JOB_RED=1'])
    ru, oru = run('ulpred', new, ['-include', str(H / 'ulp.h'), '-UFXD_EXPF', '-DFXD_EXPF=fxhExpfUlp'])
    for x, m in ((ref, oref), (cur, ocur), (cp, ocp), (rc, orc), (ru, oru)):
        if x is None: return False, 'Мак, частицы: ' + m
    lines = ref.decode().splitlines()
    draws = sum(1 for l in lines if l.startswith('D ')); skips = sum(int(re.search(r'skip=(\d+)', l).group(1)) for l in lines if l.startswith('F '))
    adds = sum(1 for l in lines if l.startswith('D b=0,10,10')); subs = sum(1 for l in lines if l.startswith('D b=2,10,10'))
    ok = cur == ref and cp == ref and rc != ref and ru != ref and draws > 1000 and skips > 0 and adds > 0 and subs > 0
    nd = lambda a: sum(1 for x, y in zip(a.decode().splitlines(), lines) if x != y)
    return ok, (f'Мак, частицы: новый fx.c+fxdsp.c и прежний — {"побайтно один" if cur == ref else f"РАЗНЫЕ ({nd(cur)} строк)"} '
                f'({ocur}; команд рисования {draws}: сложение {adds}, вычитание {subs}; пропусков бюджета ближней заливки {skips}); '
                f'путь задания — {"тот же" if cp == ref else "РАЗНЫЙ"}; КРАСНЫЕ: копия не обновляется — '
                f'{"поймана" if rc != ref else "НЕ ПОЙМАНА"} ({nd(rc)} строк), expf на 1 ulp — {"пойман" if ru != ref else "НЕ ПОЙМАН"} ({nd(ru)} строк)')


def objdump_funcs(elf):
    txt = subprocess.run([str(PSPDEV / 'bin/psp-objdump'), '-d', '--no-show-raw-insn', str(elf)], capture_output=True, text=True).stdout
    funcs, cur = {}, None
    for ln in txt.splitlines():
        m = re.match(r'^[0-9a-f]+ <([\w.]+)>:$', ln)
        if m: cur = m.group(1); funcs[cur] = []; continue
        m = re.match(r'^\s+([0-9a-f]+):\s+(\S+)\s*(.*)$', ln)
        if m and cur: funcs[cur].append((int(m.group(1), 16), m.group(2), m.group(3).strip()))
        elif not ln.strip(): cur = None
    return funcs


# правка 313: код ME — замыкание вызовов от meTask. Свои функции: me*, mix* (звук — только целые), fxd* (частицы — плавающая точка);
# чистые функции libm.a (тот же машинный код, что у игры); __math_oflowf/__math_uflowf — свои, без errno (viewer/me/sharme.c)
LIBM_OK = {'cosf', 'sinf', 'atan2f', '__ieee754_atan2f', 'atanf', 'fabsf', 'fminf', '__fpclassifyf', '__ieee754_expf', '__ieee754_rem_pio2f',
           '__kernel_rem_pio2f', '__kernel_sinf', '__kernel_cosf', 'floorf', 'scalbnf', '__math_oflowf', '__math_uflowf', 'meXflowf'}


def me_closure(F, root='meTask'):
    seen, st = [], [root]
    while st:
        f = st.pop()
        if f in seen: continue
        seen.append(f)
        for a, op, arg in F.get(f, []):
            if op in ('jal', 'j'):
                t = re.search(r'<([\w.]+)(\+0x[0-9a-f]+)?>', arg)
                if t and t.group(1) != f: st.append(t.group(1))
    return seen


def me_code_errs(F, root='meTask', finish='meSafeTaskMistFinish'):
    ME = me_closure(F, root); errs = []
    for f in (root, 'meWork', finish):
        if f not in ME: errs.append(f'нет функции {f}')
    for f in ME:
        if f not in F: errs.append(f'переход наружу: {f}'); continue
        own = f.startswith(('me', 'mix', 'fxd')) or f in LIBM_OK
        if not own: errs.append(f'переход наружу: {f}')
        fp_ok = f.startswith('fxd') or f in LIBM_OK
        for a, op, arg in F[f]:
            if op in ('syscall', 'break', 'teq', 'tne', 'tge', 'tlt', 'tgeu', 'tltu'): errs.append(f'{f}: {op}')
            if re.search(r'\bgp\b', arg): errs.append(f'{f}: $gp ({op} {arg})')
            if op in ('jal', 'j'):
                t = re.search(r'<([\w.]+)(\+0x[0-9a-f]+)?>', arg)
                if t and t.group(1) in ('memset', 'memcpy'): errs.append(f'{f}: переход наружу {op} {arg}')
            if op == 'jalr': errs.append(f'{f}: косвенный вызов {arg}')
            if not fp_ok and (op.endswith('.s') or op.endswith('.w') or op.startswith('cvt') or op in ('mtc1', 'mfc1', 'lwc1', 'swc1')):
                errs.append(f'{f}: команда FPU {op}')   # правка 276: звук на ME — только целые (FPU ME, может быть, выключен)
    return ME, errs


def fx_same_code(eboot):
    """правка 313: счёт частиц у игры (fxdsp.c.obj) и у модуля (fxdsp_me.o) — один машинный код: .text, константы, релокации"""
    g = Path(eboot).parent / 'CMakeFiles/sharview.dir/fxdsp.c.obj'; m = ROOT / 'viewer/me/fxdsp_me.o'
    if not g.exists() or not m.exists(): return False, f'нет {g.name if not g.exists() else m.name}'
    def sect(o, s):
        b = OUT / f'_{o.stem}{s}.bin'; b.unlink(missing_ok=True)
        subprocess.run([str(PSPDEV / 'bin/psp-objcopy'), '-O', 'binary', '-j', s, str(o), str(b)], capture_output=True)
        return b.read_bytes() if b.exists() else b''
    def rel(o):
        t = subprocess.run([str(PSPDEV / 'bin/psp-objdump'), '-dr', '--no-show-raw-insn', str(o)], capture_output=True, text=True).stdout
        return [l for l in t.splitlines()[3:]]
    tg, tm = sect(g, '.text'), sect(m, '.text'); cg, cm = sect(g, '.rodata.cst4'), sect(m, '.rodata.cst4')
    same = tg == tm and cg == cm and len(tg) > 1000 and rel(g) == rel(m)
    return same, f'.text {len(tg)} Б {"=" if tg == tm else "≠"}, константы {len(cg)} Б {"=" if cg == cm else "≠"}, релокации {"=" if rel(g) == rel(m) else "≠"}'


def step_module():
    env = dict(os.environ, PSPDEV=str(PSPDEV), PATH=f'{PSPDEV}/bin:' + os.environ.get('PATH', ''))
    elf, prx = ROOT / 'viewer/me/sharme.elf', ROOT / 'viewer/me/sharme.prx'
    # КРАСНЫЙ (правка 276): без ME_SAFE компилятор превращает обнуление суммы в вызов memset и ставит ловушку деления на 0
    r = subprocess.run(['make', '-B', '-C', str(ROOT / 'viewer/me'), 'ME_SAFE='], capture_output=True, text=True, env=env)
    red_errs = me_code_errs(objdump_funcs(elf))[1] if not r.returncode else ['не собрался']
    red = any('memset' in e or 'break' in e for e in red_errs)
    r = subprocess.run(['make', '-B', '-C', str(ROOT / 'viewer/me')], capture_output=True, text=True, env=env)
    if r.returncode or not prx.exists(): return False, 'модуль: make -C viewer/me не собрал sharme.prx: ' + (r.stderr or r.stdout).strip()[-300:]
    F = objdump_funcs(elf); ME, errs = me_code_errs(F)
    game = objdump_funcs(EBOOT_PATH.parent / 'sharview')
    _, user_errs = me_code_errs(game, 'meGameTask', 'meGameFinish')
    errs.extend('user ME: ' + e for e in user_errs)
    if not red: errs.append('КРАСНЫЙ НЕ ПОЙМАН: сборка без ME_SAFE прошла проверку кода ME')
    fs, fm = fx_same_code(EBOOT_PATH)
    if not fs: errs.append('счёт частиц у игры и модуля — разный машинный код: ' + fm)
    t = F.get('meTask', [])
    push = [i for i, (_, op, arg) in enumerate(t) if op == 'addiu' and arg.startswith('sp,sp,-')]
    for i, (_, op, arg) in enumerate(t):
        if op == 'j' and '<meSafeTaskMistFinish>' in arg:
            after_push = any(p < i for p in push)
            popped = any(o == 'addiu' and re.match(r'sp,sp,\d+$', g) for _, o, g in t[max(0, i - 1):i + 2])
            if after_push and not popped: errs.append('meTask: выход в meSafeTaskMistFinish без снятия кадра стека')
    fin = ' '.join(f'{op} {arg}' for _, op, arg in F.get('meSafeTaskMistFinish', []))
    if not (re.search(r'lui \w+,0x8830', fin) and re.search(r'addiu \w+,\w+,1216', fin) and '-567' in fin and 'jr' in fin):
        errs.append('meSafeTaskMistFinish: нет перехода на 0x883004c0 с -567')
    if errs: return False, 'модуль: ' + '; '.join(errs[:6])
    n = sum(len(F[f]) for f in ME if f in F)
    lib = sorted(f for f in ME if f in LIBM_OK)
    return True, (f'модуль: sharme.prx {prx.stat().st_size} Б; код ME ({len(ME)} функций, {n} команд, из них libm: {len(lib)}) — без $gp/syscall/'
                  f'ловушек/внешних вызовов, FPU только в fxd*/libm, кадр снят, выход 0x883004c0; счёт частиц игры и модуля — один код ({fm}); '
                  f'КРАСНЫЙ без ME_SAFE пойман: {red_errs[0]}')


def scen(name, lines, eboot, override):
    name = PFX + name
    OUT.mkdir(parents=True, exist_ok=True); p = OUT / f'{name}.txt'; p.write_text('\n'.join(lines + ['end']) + '\n')
    env = dict(os.environ, SCEN_EBOOT=str(eboot), SCEN_HOME=str(OUT / ('home_' + name)), SCEN_OVERRIDE=','.join(override))
    r = subprocess.run([sys.executable, str(SCEN), name, str(p)], env=env, capture_output=True, text=True, timeout=1200)
    d = RUNS / name; smk = (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''
    bb = (d / 'blackbox.txt').read_text(errors='replace') if (d / 'blackbox.txt').exists() else ''
    rc = re.search(r' rc (-?\d+)', r.stdout); return d, smk, bb, int(rc.group(1)) if rc else None


def me_lines(smk): return [l for l in smk.splitlines() if l.startswith('ME ')]


def step_emu(eboot):
    prx = ROOT / 'viewer/me/sharme.prx'; dummy = OUT / 'dummy.prx'; nome = OUT / 'nome'
    OUT.mkdir(parents=True, exist_ok=True); dummy.write_bytes(b'not a module\n'); nome.write_text('')
    res, ok = [], True
    head = ['scene me-gate', 'wait 4']
    d, smk, bb, rc = scen('me-probe-gA', head + ['flag meprobe 1', 'wait 1', 'flag mefmv 1', 'wait 15'], eboot, [f'sharme.prx={prx}'])
    L = me_lines(smk); fmv = re.search(r'MSNFMV name=gracie have=1 played=1 frames=(\d+) shown=(\d+)', smk)
    a = L[:1] == ['ME skip emu'] and 'NOTE    ME skip emu' in bb and not (d / 'me.txt').exists() and fmv and int(fmv.group(1)) > 0 and 'END' in smk
    ok &= bool(a); res.append(f'A {"ok" if a else "ПРОВАЛ"}: {L[:2]} ящик={"да" if "ME skip emu" in bb else "нет"} me.txt={(d / "me.txt").exists()} '
                              f'ролик={fmv.group(0) if fmv else "нет"} END={"END" in smk} rc={rc}')
    d, smk, bb, rc = scen('me-probe-gN', head + ['flag meprobe 2', 'wait 1'], eboot, [f'sharme.prx={prx}', f'nome={nome}'])
    L = me_lines(smk); n = L[:1] == ['ME skip nome'] and not (d / 'me.txt').exists() and 'END' in smk
    ok &= n; res.append(f'N {"ok" if n else "ПРОВАЛ"}: {L[:1]} me.txt={(d / "me.txt").exists()} END={"END" in smk} rc={rc}')
    d, smk, bb, rc = scen('me-probe-gR', head + ['flag meprobe 2', 'wait 1'], eboot, [f'sharme.prx={dummy}'])
    L = me_lines(smk); red = bool(L) and L[0] != 'ME skip emu' and L[0].startswith('ME probe ok=0 err=load')
    ok &= red; res.append(f'R красный {"пойман" if red else "НЕ ПОЙМАН"}: {L[:1]} (без защиты эмулятора — загрузка модуля)')
    # правка 276: флаг-файл meaudio
    def mea(name, content, extra, lines):
        f = OUT / f'meaudio_{name}'; f.write_text(content)
        d, smk, bb, rc = scen(name, head + lines, eboot, [f'meaudio={f}'] + extra)
        A = [l for l in smk.splitlines() if l.startswith('ME audio')]
        aud = re.findall(r'^AUDV t=([\d.]+) .*?cur=(\S+) .*? me=(\S+)', smk, re.M)
        fmv = re.search(r'MSNFMV name=gracie have=1 played=1 frames=(\d+) shown=(\d+)', smk)
        return d, smk, bb, rc, A, aud, fmv
    mov = ['flag mefmv 1', 'wait 15']
    d, smk, bb, rc, A, aud, fmv = mea('me-audio-gG', '1', [f'sharme.prx={prx}'], ['wait 2'])
    g = A[:1] == ['ME audio skip emu'] and bool(aud) and all(m == '-' for _, _, m in aud) and 'END' in smk
    ok &= g; res.append(f'G {"ok" if g else "ПРОВАЛ"}: {A[:1]} AUDV me={sorted(set(m for _, _, m in aud))} END={"END" in smk} rc={rc}')
    d, smk, bb, rc, A, aud, fmv = mea('me-audio-gE', '3', [], mov)
    tf = float(re.search(r'MSNFMV .* t=([\d.]+)', smk).group(1)) if fmv else 0
    before = [int(m[2:].split('/')[0]) for t, _, m in aud if float(t) < tf - 0.5 and m.startswith('on')]
    after = [int(m[2:].split('/')[0]) for t, _, m in aud if float(t) > tf + 1.5 and m.startswith('on')]
    e = (bool(A) and A[0].startswith('ME audio on fake mute=0') and 'audio=on' in A[0] and fmv and fmv.group(1) == fmv.group(2) and int(fmv.group(1)) > 100 and
         len(before) >= 3 and min(before) >= 80 and len(after) >= 3 and min(after) >= 80 and 'END' in smk and 'meon' in bb)
    ok &= bool(e); res.append(f'E {"ok" if e else "ПРОВАЛ"}: {A[:1]} заданий/с до ролика {before[:4]} после {after[:4]} ролик={fmv.group(0)[:60] if fmv else "нет"} '
                              f'ящик «meon»={"да" if "meon" in bb else "нет"} END={"END" in smk} rc={rc}')
    d, smk, bb, rc, A, aud, fmv = mea('me-audio-gT', '4', [], mov)
    curs = [c for _, c, _ in aud]
    t_ = (bool(A) and A[0].startswith('ME audio on fake mute=1') and bool(aud) and all(m == 'off:timeout@1' for _, _, m in aud) and
          'sunday_drive' in curs and fmv and fmv.group(1) == fmv.group(2) and 'END' in smk and 'meoff:timeout@1' in bb)
    ok &= bool(t_); res.append(f'T {"ok" if t_ else "ПРОВАЛ"}: {A[:1]} AUDV me={sorted(set(m for _, _, m in aud))} дорожки={sorted(set(curs))} '
                               f'ролик={"целиком" if fmv and fmv.group(1) == fmv.group(2) else "нет"} END={"END" in smk} rc={rc}')
    d, smk, bb, rc, A, aud, fmv = mea('me-audio-gR', '2', [f'sharme.prx={dummy}'], ['wait 2'])
    rg = bool(A) and A[0].startswith('ME audio off: load') and 'END' in smk
    ok &= rg; res.append(f'RG красный {"пойман" if rg else "НЕ ПОЙМАН"}: {A[:1]} (без защиты эмулятора — загрузка модуля) END={"END" in smk}')
    # правка 313: флаг-файл mefx — частицы и свечение на ME (служба общая со звуком)
    fxl = ['flag meprof 1', 'goto 246 -180 1.5708', 'wait 2', 'flag testdmg 0.95', 'flag autostraight 6', 'wait 8', 'flag stop',
           'flag testboom', 'wait 8']
    def mfx(name, files, lines):
        ov = []
        for k, v in files.items(): f = OUT / f'{k}_{name}'; f.write_text(v); ov.append(f'{k}={f}')
        d, smk, bb, rc = scen(name, head + lines, eboot, ov)
        F = [l for l in smk.splitlines() if l.startswith('ME fx') or l.startswith('ME audio')]
        mp = re.findall(r'^MEPROF t=([\d.]+) .*? fx=(\d+)/(\d+) .*? mefx=(\S+)', smk, re.M)
        aud = re.findall(r'^AUDV t=([\d.]+) .*? me=(\S+)', smk, re.M)
        return smk, rc, F, mp, aud
    smk, rc, F, mp, aud = mfx('me-fx-gG', {'mefx': '1'}, fxl)
    g = any(l == 'ME fx skip emu' for l in F) and bool(mp) and all(m == '-' for *_, m in mp) and max(int(x[1]) for x in mp) > 20 and 'END' in smk
    ok &= g; res.append(f'FG {"ok" if g else "ПРОВАЛ"}: {F[:1]} MEPROF mefx={sorted(set(m for *_, m in mp))} частиц до {max([int(x[2]) for x in mp] or [0])} END={"END" in smk} rc={rc}')
    smk, rc, F, mp, aud = mfx('me-fx-gE', {'mefx': '3', 'mescheme': 'b'}, fxl + mov)
    on = [int(re.match(r'on(\d+)/', m).group(1)) for *_, m in mp if m.startswith('on')]
    fmv = re.search(r'MSNFMV name=gracie have=1 played=1 frames=(\d+) shown=(\d+)', smk)
    e = (any(l.startswith('ME fx on fake mute=0 scheme=1') and 'fx=on' in l for l in F) and len(on) >= 5 and on[-1] > 200 and
         max(int(x[1]) for x in mp) > 20 and fmv and fmv.group(1) == fmv.group(2) and 'END' in smk)
    ok &= bool(e); res.append(f'FE {"ok" if e else "ПРОВАЛ"}: {F[:1]} заданий частиц на «ME» {on[:1]}…{on[-1:]} частиц до {max([int(x[2]) for x in mp] or [0])} '
                              f'ролик={"целиком" if fmv and fmv.group(1) == fmv.group(2) else "нет"} END={"END" in smk} rc={rc}')
    smk, rc, F, mp, aud = mfx('me-fx-gT', {'mefx': '4'}, fxl)
    st = sorted(set(m for *_, m in mp)); after = [int(x[1]) for x in mp if x[3].startswith('off:timeout')]
    t_ = (any(l.startswith('ME fx on fake mute=1') for l in F) and any(m.startswith('off:timeout@1') for m in st) and after and max(after) > 20 and 'END' in smk)
    ok &= bool(t_); res.append(f'FT {"ok" if t_ else "ПРОВАЛ"}: {F[:1]} MEPROF mefx={st} частиц после молчания ME до {max(after or [0])} END={"END" in smk} rc={rc}')
    smk, rc, F, mp, aud = mfx('me-fx-gK', {'mefx': '3', 'meaudio': '3', 'mescheme': 'k'}, fxl)
    on = [int(re.match(r'on(\d+)/', m).group(1)) for *_, m in mp if m.startswith('on')]; am = [m for _, m in aud if m.startswith('on')]
    k_ = (any(l.startswith('ME audio on fake') and 'scheme=3' in l for l in F) and any(l.startswith('ME fx on') for l in F) and len(on) >= 5
          and len(am) >= 5 and 'END' in smk)
    ok &= bool(k_); res.append(f'FK {"ok" if k_ else "ПРОВАЛ"}: звук и частицы одной службой (схема k): {F[:2]} частиц на «ME» {on[-1:]} AUDV me={am[-1:]} END={"END" in smk} rc={rc}')
    smk, rc, F, mp, aud = mfx('me-fx-gU', {'mefx': '3', 'mescheme': 'u'}, fxl)
    on = [int(re.match(r'on(\d+)/', m).group(1)) for *_, m in mp if m.startswith('on')]
    u_ = any(l.startswith('ME fx on fake mute=0 scheme=0') for l in F) and len(on) >= 5 and 'END' in smk
    ok &= bool(u_); res.append(f'FU {"ok" if u_ else "ПРОВАЛ"}: схема u (ящик в памяти игры): {F[:1]} заданий {on[-1:]} END={"END" in smk} rc={rc}')
    return ok, res


if __name__ == '__main__':
    sys.stdout.reconfigure(line_buffering=True)   # облако 05.10: строки шагов — сразу (на Маке в трубе вывод копился до конца)
    print('шаги: 1 Мак (суммы, микшер, частицы), 2 модуль, 3 эмулятор (PPSSPP, данные игры). Очередь ME без PSP — tests/me/queue.sh')
    args = [a for a in sys.argv[1:] if a != '--mac']
    eb = Path(args[0] if args else str(ROOT / 'viewer/build/EBOOT.PBP')).resolve()
    EBOOT_PATH = eb
    OUT.mkdir(parents=True, exist_ok=True)
    ok1, m1 = step_mac(); print(m1)
    ok1m, m1m = step_mac_mix(); print(m1m); ok1 = ok1 and ok1m
    ok1k, m1k = step_mac_k1(); print(m1k); ok1 = ok1 and ok1k   # правка 410, К1
    ok1b, m1b = step_mac_bbcpu(); print(m1b); ok1 = ok1 and ok1b   # правка 410, шаг 0
    if '--mac' in sys.argv:   # правка 410: только шаги Мака (эмулятор — через tools/smoke.sh SMOKE_HEADLESS=1)
        ok1f, m1f = step_mac_fx(); print(m1f); ok1 = ok1 and ok1f
        print('Мак: ' + ('PASS' if ok1 else 'FAIL')); sys.exit(0 if ok1 else 1)
    ok1f, m1f = step_mac_fx(); print(m1f); ok1 = ok1 and ok1f   # правка 313
    ok2, m2 = step_module(); print(m2)
    ok3, m3 = step_emu(eb)
    for l in m3: print(l)
    ok = ok1 and ok2 and ok3
    print(f'EBOOT {eb.name} {__import__("hashlib").sha256(eb.read_bytes()).hexdigest()[:8]}: ' + ('PASS' if ok else 'FAIL'))
    sys.exit(0 if ok else 1)
