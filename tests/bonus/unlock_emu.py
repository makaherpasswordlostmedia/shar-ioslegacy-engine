#!/usr/bin/env python3
"""Правка Роба 421 (09.10): открытие трасс через SMOKE_HEADLESS=1 tools/smoke.sh.
Программная отрисовка без окна/звука; HOME не меняется. XDG config/data отдельные,
но PPSSPPHeadless хранит системную виртуальную карту в HOME/.ppsspp.
  new   служебная новая игра с отключённым чтением сохранений: BONUS GAME серый
        (BONUSOPEN src=none mask=00 menu=0); Cross не запускает закрытый пункт.
        Шесть карточек отмечены служебно, card17 подбирается настоящим collectStep,
        7/7 (COLLEV cards_done) -> BONUSOPEN src=cards mask=01 + снимок надписи «LEVEL CARDS COLLECTED! / New bonus game track
        unlocked!» -> пауза -> QUIT GAME -> главное меню: BONUS GAME включён -> выбор трассы: open=01, ◄ ► не уходит с трассы 1,
        flag bonustrack 2 — отказ
  dev   флаг devsave (DEV SAVE в нижнем слоте, правка 335) и «flag saves»: первое меню по самому свежему сохранению (DEV) —
        BONUSOPEN src=latest mask=7f, выбор трассы open=7f, ► проходит трассы 2..7
  devld то же + LOAD GAME -> DEV SAVE -> игра: SVPROG src=load cards=7f,7f,7f,7f,7f,7f,7f и BONUSOPEN src=load mask=7f
python3 tests/bonus/unlock_emu.py EBOOT [--red]   -> 0 = PASS. --red: только прогон new; код 0, если проверка «new: серый» упала
(красный: сборка -DBONUS_UNLOCK_OLD=1 — все трассы открыты сразу). Прогоны: build/gates/bonus_unlock/<имя>/"""
import argparse, json, os, re, shutil, struct, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; HERE = Path(__file__).resolve().parent
OUT = ROOT / 'build/gates/bonus_unlock'
STAGE = Path(os.environ.get('BONUS_STAGE', ROOT / 'build/bonus-unlock-stage')).resolve()


def cards_l1():
    """точки карточек уровня 1 из пакета collect-l1.shr (CLT1: карточки по 32 Б — x y z r id ...)"""
    b = (STAGE / 'collect-l1.shr').read_bytes(); u = struct.unpack_from('<13I', b, 4)
    out = []
    for i in range(u[6]):
        x, y, z, r, cid = struct.unpack_from('<4fH', b, u[7] + 32 * i); out.append((cid, x, y, z))
    return out


def scen_new():
    # меню: ◄ на BONUS GAME (серый) и ✕ — не входит (запись PS2 ps2_bonus_locked_accept), ► назад на NEW GAME и ✕
    s = ['flag menu', 'wait 2', 'shot u_menu', 'press left', 'wait 0.6', 'press cross', 'wait 1.5', 'shot u_menu_locked',
         'press right', 'wait 0.6', 'press cross', 'wait 12']
    # карточки 1..6 уровня 1 стоят на крышах и трамплинах (берутся прыжком машины) — служебно отмечены собранными (flag cardsset 63),
    # последняя card17 MR. SPARKLE BOX — настоящий подбор Гомером на её точке (как последняя карточка записи PS2, кадр 250)
    cid, x, y, z = [c for c in cards_l1() if c[0] == 17][0]
    s += ['flag cardsset 63', 'wait 0.5', 'foot %.2f %.2f 0 %.2f' % (x, z, y + 1.0), 'wait 1', 'shot u_card7', 'wait 3', 'shot u_unlocked',
          'wait 3', 'press start', 'wait 1', 'press up', 'wait 0.5', 'press cross', 'wait 8',
          'press left', 'wait 0.6', 'press cross', 'wait 2', 'shot u_bonus_menu', 'press right', 'wait 0.5', 'press left', 'wait 0.5',
          'flag bonustrack 2', 'wait 0.5', 'press triangle', 'wait 4', 'end']
    return '\n'.join(s) + '\n'


def scen_dev():
    s = ['flag menu', 'flag saves', 'wait 2', 'shot d_menu', 'press left', 'wait 0.6', 'press cross', 'wait 2', 'shot d_bonus_menu']
    s += ['press right', 'wait 0.4'] * 6 + ['shot d_track7', 'press triangle', 'wait 4', 'end']
    return '\n'.join(s) + '\n'


def scen_devld():   # как tests/savegame/devsave/run.py (MENU_LOAD + строка DEV + загрузка)
    s = ['flag menu', 'flag saves', 'wait 1.5'] + ['press left', 'wait 0.3'] * 4 + ['press cross', 'wait 2', 'press down', 'wait 0.4',
         'press cross', 'wait 2.5', 'press cross', 'wait 9', 'flag svlog', 'end']
    return '\n'.join(s) + '\n'


def run(name, eboot, scen, devsave=False, timeout=600):
    # All native runs use the authorized runner. Keep every attempt in a new
    # directory; XDG config/data are separate (the system memstick is shared).
    d = Path(tempfile.mkdtemp(prefix=name + '-', dir=OUT))
    subprocess.run(['cp', '-c', '-R', str(STAGE) + '/.', str(d)], check=True)
    shutil.copyfile(eboot, d / 'EBOOT.PBP')
    scenario = d / 'scenario.txt'; scenario.write_text(scen)
    env = dict(os.environ, SMOKE_HEADLESS='1', SMOKE_SCN=str(scenario), SMOKE_BALLAST='5', SMOKE_MAXT=str(timeout))
    env['SMOKE_FLAGS'] = 'devsave' if devsave else ''
    result = subprocess.run([str(ROOT / 'tools/smoke.sh'), str(d)], cwd=ROOT, env=env, capture_output=True, text=True)
    output = result.stdout + result.stderr
    (d / 'runner.log').write_text(output)
    match = re.search(r'отчёт: (.*?)/summary\.txt', output)
    if not match: return d, 'no smoke report; raw rc=%s' % result.returncode
    native = ROOT / match[1]
    (d / 'native.json').write_text(json.dumps({'path': str(native), 'raw_rc': result.returncode}, indent=2) + '\n')
    log = lines(native)
    bad = []
    if not any(l.startswith('END ') or l == 'END' for l in log): bad.append('no native END')
    for l in log:
        values = kv(l)
        for key in ('readerr', 'allocfail', 'geskip', 'memfail', 'gebad'):
            if key in values and float(values[key]) != 0: bad.append('%s=%s' % (key, values[key]))
    # The raw summary remains an artifact. This gate verifies unlock behavior;
    # menu-only STAT frames=0 is not a gameplay frame-rate measurement.
    return native, '; '.join(bad) if bad else None


def lines(d):
    p = d / 'smoke.txt'
    return p.read_text(errors='replace').splitlines() if p.exists() else []


def kv(l): return dict(re.findall(r'(\w+)=(\S+)', l))


def rows(log, pre, **want): return [l for l in log if l.startswith(pre + ' ') and all(kv(l).get(k) == v for k, v in want.items())]


def check_new(d, bad):
    log = lines(d); f = []; notes = []
    b0 = rows(log, 'BONUSOPEN')
    first = b0[0] if b0 else None
    menu0 = rows(log, 'MENU', n='1')
    if not first or kv(first).get('src') != 'none' or kv(first).get('mask') != '00' or kv(first).get('menu') != '0':
        f.append('new.grey: в начале BONUS GAME не серый (%s)' % first)
    else: notes.append('новая игра: BONUS GAME серый, трасс 0')
    ent = [l for l in log if l.startswith('BONUS ev=menu')]
    t_game = next((float(kv(l)['t']) for l in log if l.startswith('GAME ')), None)
    if t_game is None: f.append('new.game: игра не началась (нет строки GAME)')
    elif any(float(kv(l)['t']) < t_game for l in ent): f.append('new.grey: выбор бонус-игры открылся до сбора карточек')
    got = rows(log, 'COLLEV card', name='card17'); done = rows(log, 'COLLEV cards_done')
    if not got or kv(got[0]).get('cards') != '7/7' or not done: f.append('new.cards: card17 7/7 и cards_done — %s / %s' % (got[:1], done[:1]))
    else: notes.append('уровень 1: 7/7 последним подбором card17 (COLLEV card, cards_done)')
    if ent and any(float(kv(l)['t']) < t_game for l in ent if t_game is not None) or [l for l in log if l.startswith('MENUSEL key=cross') and t_game is not None and float(kv(l)['t']) < t_game and
                                                                                        kv(l).get('act') not in ('-1', kv(menu0[0]).get('new') if menu0 else None)]:
        f.append('new.grey: ✕ на сером BONUS GAME что-то запустил')
    six = [l for l in b0 if kv(l).get('src') == 'cards']
    if not six or kv(six[0]).get('mask') != '01' or kv(six[0]).get('changed') != '1' or kv(six[0]).get('menu') != '1':
        f.append('new.unlock: после 7/7 трасса 1 не открылась (%s)' % (six[0] if six else 'нет BONUSOPEN src=cards'))
    else: notes.append('7/7 -> открыта трасса 1 (mask 01)')
    pre = [l for l in b0 if kv(l).get('mask') not in ('00', None) and (not done or float(kv(l)['t']) < float(kv(done[0])['t']))]
    if pre: f.append('new.unlock: трасса открылась раньше последней карточки (%s)' % pre[0])
    m2 = rows(log, 'MENU', n='2')
    if not m2: f.append('new.back: главное меню после QUIT GAME не открылось')
    if not ent or kv(ent[0]).get('open') != '01' or kv(ent[0]).get('track') != '1':
        f.append('new.select: выбор трасс не open=01 track=1 (%s)' % (ent[0] if ent else 'нет BONUS ev=menu'))
    else: notes.append('BONUS GAME включён, выбор трасс: открыта только 1')
    tr = [l for l in log if l.startswith('BONUS ev=track')]
    steps = [kv(l) for l in tr if 'd' in kv(l)]
    if len(steps) < 2 or any(s.get('track') != '1' for s in steps): f.append('new.select: ◄ ► ушли с трассы 1 (%s)' % steps)
    ref = [kv(l) for l in tr if kv(l).get('want') == '2']
    if not ref or ref[0].get('refused') != '1' or ref[0].get('track') != '1': f.append('new.select: закрытая трасса 2 выбрана (%s)' % ref)
    else: notes.append('◄ ► и flag bonustrack 2 не выбирают закрытые')
    if bad: f.append('new: прогон эмулятора: %s' % bad)
    return f, notes, menu0


def check_dev(d, bad):
    log = lines(d); f = []; notes = []
    if not rows(log, 'SVDEV boot'): f.append('dev: DEV SAVE при запуске не записан (нет SVDEV boot)')
    b = rows(log, 'BONUSOPEN', src='latest')
    if not b or kv(b[0]).get('mask') != '7f' or kv(b[0]).get('menu') != '1': f.append('dev.menu: первое меню не 7f (%s)' % (b[0] if b else 'нет'))
    else: notes.append('DEV SAVE: в главном меню открыты все 7 трасс')
    ent = [l for l in log if l.startswith('BONUS ev=menu')]
    if not ent or kv(ent[0]).get('open') != '7f': f.append('dev.select: выбор не open=7f (%s)' % (ent[0] if ent else 'нет'))
    seen = [kv(l).get('track') for l in log if l.startswith('BONUS ev=track d=1')]
    if seen != ['2', '3', '4', '5', '6', '7']: f.append('dev.select: ► прошёл трассы %s (ждём 2..7)' % seen)
    else: notes.append('► проходит трассы 2..7')
    if bad: f.append('dev: прогон эмулятора: %s' % bad)
    return f, notes


def check_devld(d, bad):
    log = lines(d); f = []; notes = []
    if not rows(log, 'SVDEV load', slot='3'): f.append('devld: DEV SAVE не загружен (нет SVDEV load slot=3)')
    p = rows(log, 'SVPROG', src='load'); k = kv(p[0]) if p else {}
    if k.get('cards') != '7f,7f,7f,7f,7f,7f,7f': f.append('devld: карточки после загрузки DEV не все уровни (%s)' % (p[0] if p else 'нет SVPROG'))
    else: notes.append('DEV загружен: карточки всех 7 уровней 7/7')
    b = rows(log, 'BONUSOPEN', src='load')
    if not b or kv(b[0]).get('mask') != '7f': f.append('devld: в игре трассы не 7f (%s)' % (b[0] if b else 'нет BONUSOPEN src=load'))
    else: notes.append('в игре из DEV открыты все 7 трасс')
    if bad: f.append('devld: прогон эмулятора: %s' % bad)
    return f, notes


def main():
    global STAGE
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('eboot',nargs='?',type=Path,default=ROOT/'viewer/build/EBOOT.PBP')
    ap.add_argument('--red',action='store_true'); ap.add_argument('--stage',type=Path,default=STAGE)
    args=ap.parse_args(); red=args.red; STAGE=args.stage.resolve(); eboot=args.eboot.resolve()
    if not eboot.is_file() or not (STAGE/'collect-l1.shr').is_file():
        ap.error('НЕТ ДАННЫХ: actual EBOOT and stage/collect-l1.shr required')
    OUT.mkdir(parents=True, exist_ok=True)
    pf = 'red_' if red else ''
    d, bad = run(pf + 'new', eboot, scen_new()); fails, notes, _ = check_new(d, bad)
    print('прогон new: %s' % d)
    if red:
        grey = [x for x in fails if x.startswith('new.grey')]
        print(('RED CAUGHT: ' + '; '.join(grey)) if grey else 'RED NOT CAUGHT: ' + '; '.join(notes))
        return 0 if grey else 1
    d2, bad2 = run('dev', eboot, scen_dev(), devsave=True); f2, n2 = check_dev(d2, bad2); print('прогон dev: %s' % d2)
    d3, bad3 = run('devld', eboot, scen_devld(), devsave=True); f3, n3 = check_devld(d3, bad3); print('прогон devld: %s' % d3)
    fails += f2 + f3; notes += n2 + n3
    print(('FAIL: ' + '; '.join(fails)) if fails else 'PASS: ' + '; '.join(notes))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
