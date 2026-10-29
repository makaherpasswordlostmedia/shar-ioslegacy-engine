"""Правка Роба 335 (05.10, голосом): «Дай мне сохранение разработчика — самый нижний слот, с сегодняшней датой, назови так, чтобы
было понятно, что это dev save. Туда максимальное прохождение — всё открыто, все уровни». Гейт в безоконном PPSSPP (scen.py скилла
shar-level-polish, свой SCEN_HOME — карта эмулятора с нуля), четыре запуска игры подряд на одной карте:
  A  без флага: новая игра -> отметка прогресса (flag svmark) -> SAVE GAME -> слот 1 — обычная запись
  B  флаг-файл devsave рядом с EBOOT: при запуске слот 4 записан DEV (SVDEV boot … verify=O), в LOAD GAME слоты O,E,E,O и строка
     «DEV SAVE  LEVEL 1  дд/мм»; загрузка слота 4 -> уровень 1: m0..m6 пройдены (маска 7f), текущая m7, монеты 99999, купленное ffff,
     карточки собраны; бонусы/гонки пройдены, доступен DEV-повтор у персонажей
  C  (если есть build/levels/l2) набор уровня 2 рядом с EBOOT (SHIP_LEVELS=2): ► на строке DEV -> LEVEL 2 -> загрузка уровня 2
     (строка LEVEL n=2), m1..m6 пройдены (маска 3f), текущая m7 уровня 2
  D  без флага: запись слота 1 из прогона A читается и загружается с тем же прогрессом; DEV в слоте 4 на месте, не переписан
  КРАСНЫЙ (--red): прогон B без флага devsave — DEV нет, гейт обязан упасть
python3 tests/savegame/devsave/run.py [--red] [EBOOT]  -> 0 = PASS. GATE_OUT — папка (build/gates/devsave), GATE_PREFIX — префикс
прогонов (dvs_), GATE_SCEN_OUT — куда scen.py кладёт прогоны (по умолчанию build/twins/scen/full дерева)"""
import os, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; HERE = Path(__file__).resolve().parent
SCRIPTS = Path.home() / '.claude/skills/shar-level-polish/scripts'
OUT = Path(os.environ.get('GATE_OUT', str(ROOT / 'build/gates/devsave'))).resolve(); PFX = os.environ.get('GATE_PREFIX', 'dvs_')
DATA = Path(os.environ.get('SCEN_ROOT', '/Users/USER/Downloads/shar-psp'))
MENU_LOAD = ['flag menu', 'flag saves', 'wait 1.5'] + ['press left', 'wait 0.3'] * 4 + ['press cross', 'wait 2']
SAVE1 = (HERE.parent / 'emu_save.txt').read_text()
DEV_L1 = '\n'.join(MENU_LOAD + ['shot dvs_slots', 'press down', 'wait 0.4', 'shot dvs_devrow', 'press cross', 'wait 2.5', 'press cross',
                                'wait 7', 'flag svlog', 'press start', 'wait 1', 'shot dvs_pause', 'end']) + '\n'
DEV_L2 = '\n'.join(MENU_LOAD + ['press down', 'wait 0.4', 'press right', 'wait 0.4', 'shot dvs_devrow2', 'press cross', 'wait 2.5',
                                'press cross', 'wait 12', 'flag svlog', 'shot dvs_l2', 'end']) + '\n'
OLD = '\n'.join(MENU_LOAD + ['press cross', 'wait 2.5', 'press cross', 'wait 6', 'flag svlog', 'end']) + '\n'


def run(name, scen_text, eboot, home, devsave=None, levels=''):
    f = OUT / (name + '.txt'); f.write_text(scen_text)
    env = dict(os.environ, SCEN_EBOOT=eboot, SCEN_HOME=str(home), SHIP_LEVELS=levels)
    env.pop('SCEN_OVERRIDE', None)
    if devsave is not None:
        flag = OUT / 'devsave'; flag.write_text(devsave); env['SCEN_OVERRIDE'] = 'devsave=%s' % flag
    so = os.environ.get('GATE_SCEN_OUT')
    code = ('import sys; sys.path.insert(0, %r); import scen; from pathlib import Path; %s'
            'scen.run(%r, open(%r).read().splitlines())') % (str(SCRIPTS), 'scen.C.OUT = Path(%r); ' % so if so else '', PFX + name, str(f))
    r = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=900)
    m = re.search(r'^dir (\S+) bad', r.stdout, re.M)
    return Path(m.group(1)) if m else OUT / ('missing_' + name)


def lines(d):
    p = d / 'smoke.txt'
    return p.read_text(errors='replace').splitlines() if p.exists() else []


def kv(l): return dict(re.findall(r'(\w+)=(\S+)', l))


def first(log, pre, **want):
    for l in log:
        if l.startswith(pre) and all(kv(l).get(k) == v for k, v in want.items()): return l
    return None


def prog(log, src):
    l = first(log, 'SVPROG', src=src)
    return re.sub(r' t=\S+$', '', l.split(' ', 2)[2]) if l else None


def disc_dev_mask(level):
    # Independent original MFK order; final story/transition remain open by the existing port rule.
    sys.path.insert(0, str(ROOT / 'tools'))
    from missions.mfk import parse
    calls, _ = parse((DATA / f'hit-and-run-web/source/game/scripts/missions/level0{level}/level.mfk').read_text(errors='replace'))
    rows = [(c.op, str(c.args[0])) for c in calls if c.op in ('AddMission', 'AddBonusMission')]
    return sum(1 << i for i, (op, mid) in enumerate(rows) if (op == 'AddBonusMission' and (DATA / f'hit-and-run-web/source/game/scripts/missions/level0{level}/{mid}i.mfk').is_file()) or (op == 'AddMission' and mid not in ('m7', 'm8')))


def disc_dev_gag_mask(level):
    sys.path.insert(0, str(ROOT / 'tools'))
    from missions.mfk import parse
    calls, _ = parse((DATA / f'hit-and-run-web/source/game/scripts/missions/level0{level}/level.mfk').read_text(errors='replace'))
    idx = -1; mask = 0
    for c in calls:
        if c.op == 'GagBegin': idx += 1
        if c.op == 'GagSetCoins' and int(c.args[0]) > 0: mask |= 1 << idx
    return mask


def main():
    red = '--red' in sys.argv; args = [a for a in sys.argv[1:] if a != '--red']
    eboot = args[0] if args else str(DATA / 'build/EBOOT.PBP')
    OUT.mkdir(parents=True, exist_ok=True)
    home = OUT / ('home_red' if red else 'home'); shutil.rmtree(home, ignore_errors=True)
    fails, notes = [], []
    # A: обычная запись в слот 1
    a = run('a_save1', SAVE1, eboot, home); la = lines(a)
    if not first(la, 'SVIO op=save', slot='0', verify='O'): fails.append('A: запись слота 1 не подтверждена (%s)' % a)
    markp = prog(la, 'mark')
    # B: флаг devsave -> слот 4 DEV, загрузка уровня 1
    b = run('b_dev', DEV_L1, eboot, home, devsave=None if red else ''); lb = lines(b)
    boot = first(lb, 'SVDEV boot')
    if not boot or kv(boot).get('verify') != 'O': fails.append('B: при запуске DEV в слот 4 не записан (%s)' % (boot or 'нет строки SVDEV boot'))
    else: notes.append('DEV записан при запуске: %s' % ' '.join('%s=%s' % (k, kv(boot)[k]) for k in ('res', 'file', 'verify', 'date', 'ms')))
    if not first(lb, 'SVOPEN mode=load', slots='O,E,E,O'): fails.append('B: в LOAD GAME слоты не O,E,E,O')
    if not first(lb, 'SVDEV load', slot='3', level='1'): fails.append('B: загрузка слота 4 не DEV (нет SVDEV load slot=3 level=1)')
    pb = first(lb, 'SVPROG', src='load'); k = kv(pb) if pb else {}
    # правка 350 (05.10): DEV — «полностью пройденный уровень»: все карточки, осы и гэги уровня собраны (main.c saveApply, SVDEV collect)
    want = dict(level='1', msn='%08x' % disc_dev_mask(1), story='7', coins='99999', owned='ffff', cards='7f,0,0,0,0,0,0')
    bad = {x: k.get(x) for x in want if k.get(x) != want[x]}
    if bad: fails.append('B: прогресс после загрузки DEV не тот: %s (ждём %s)' % (bad, want))
    else: notes.append('уровень 1 после DEV: полный DEV-прогресс (m0..m6 и бонусы), текущая m7, монеты 99999, купленное ffff, карточки 7/7')
    col = first(lb, 'SVDEV collect', level='1'); kc_ = kv(col) if col else {}
    nw, ng = int(kc_.get('wasps', '0')), int(kc_.get('gags', '0'))
    if not col or kc_.get('cards') != '7f/7' or nw < 1 or ng < 1 or k.get('wasps') != '%x' % ((1 << nw) - 1) or ng != disc_dev_gag_mask(1).bit_count() or k.get('gags') != '%x' % disc_dev_gag_mask(1):
        fails.append('B: DEV не собрал уровень целиком (правка 350): %s; SVPROG wasps=%s gags=%s' % (col, k.get('wasps'), k.get('gags')))
    else: notes.append('собрано по DEV: карточки 7/7, осы %d/%d, гэги %d/%d' % (nw, nw, ng, ng))
    if not red:   # красный правки 350: flag devcollold 1 — только миссии и покупки, карточек 0
        e = run('e_devcollold', DEV_L1.replace('flag menu\n', 'flag menu\nflag devcollold 1\n', 1), eboot, home, devsave=''); le = lines(e)
        pe = first(le, 'SVPROG', src='load'); ke = kv(pe) if pe else {}
        if ke.get('cards') != '0,0,0,0,0,0,0' or first(le, 'SVDEV collect'): fails.append('B: красный 350 (devcollold) не пойман: %s' % pe)
        else: notes.append('красный 350 (devcollold): карточек 0 — пойман')
    if not first(lb, 'MSN mission m7'): fails.append('B: миссия m7 не стала текущей')
    # C: уровень 2 (набор build/levels/l2)
    if (DATA / 'build/levels/l2/level.shr').exists() and not red:
        c = run('c_dev_l2', DEV_L2, eboot, home, devsave='', levels='2'); lc = lines(c)
        lv = first(lc, 'LEVEL ev=load'); pc = first(lc, 'SVPROG', src='load'); kc = kv(pc) if pc else {}
        if not first(lc, 'SVDEV pick', level='2'): fails.append('C: ► на строке DEV не выбрал уровень 2')
        if not lv or kv(lv).get('n') != '2': fails.append('C: уровень 2 не загрузился (%s)' % lv)
        elif kc.get('level') != '2' or kc.get('msn') != '%08x' % disc_dev_mask(2) or kc.get('story') != '6' or kc.get('cards') != '0,7f,0,0,0,0,0':
            fails.append('C: прогресс уровня 2 не тот: %s' % pc)
        else: notes.append('уровень 2 по DEV: загружен за %s мс, полный DEV-прогресс (m1..m6 и бонусы), текущая m7 (%s)' % (kv(lv).get('ms'),
                           ((first(lc, 'MSN mission m7') or '').split('"') + ['', ''])[1]))
        if first(lc, 'SVDEV boot', skip='same') is None: fails.append('C: DEV того же дня переписан (ждём skip=same)')
    elif not red: notes.append('уровень 2: набора build/levels/l2 нет — прогон C пропущен')
    # D: прежняя запись слота 1 читается, DEV на месте
    if not red:
        d = run('d_old', OLD, eboot, home); ld = lines(d)
        if not first(ld, 'SVSCAN', slots='O,E,E,O'): fails.append('D: после прогонов слоты не O,E,E,O')
        if first(ld, 'SVDEV boot'): fails.append('D: без флага DEV переписан')
        pd = prog(ld, 'load')
        if not markp or not pd or re.sub(r' story=\S+ phase=\S+ stage=\S+', '', markp) != re.sub(r' story=\S+ phase=\S+ stage=\S+', '', pd):
            fails.append('D: запись слота 1 загрузилась не с тем прогрессом: было %s, стало %s' % (markp, pd))
        else: notes.append('прежняя запись слота 1 загружена с тем же прогрессом')
    print(('FAIL: ' + '; '.join(fails)) if fails else 'PASS: ' + '; '.join(notes))
    print('прогоны: %s' % OUT)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
