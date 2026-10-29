"""Правка 345 в EBOOT (безоконный PPSSPP без звука, ~/.claude/skills/shar-level-polish/scripts/scen.py): атмосфера Kwik-E-Mart,
реплика водителя на ✕ Continue карточки миссии и на выходе из машины. Сценарий: Гомер пешком у двери Kwik-E-Mart, △ — в магазин
(строка ROOMAMB room=KwikEMart amb=amb_room_small_01), △ у выхода — на улицу (ROOMAMB room=- amb=<улица>); дальше m0: разговор с
Мардж, ✕ на карточке (MSN say mstart w_mstart_hom_*), 8 раз сел/вышел (SAY goc на каждом выходе, хотя бы одна реплика w_goc_hom_*;
шанс 0,5 — вероятность ни одной за 8 выходов 0,4 %). КРАСНЫЙ: «flag pcsayold 1» + «flag roomambold 1» — как до правки.
  python3 tests/sound/pcsay_emu.py [EBOOT]  (SCEN_OVERRIDE — свой звуковой пакет: audio/music.sap=…,audio/sfx.sab=…) -> 0 = PASS"""
import os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'
DATA = Path(os.environ.get('SCEN_ROOT', '/Users/USER/Downloads/shar-psp'))

def scen(old):
    L = ['scene start', 'wait 3'] + (['flag pcsayold 1', 'flag roomambold 1'] if old else [])
    L += ['foot 213.9 299 0 5.2', 'wait 1.5', 'press up 0.8', 'press circle 0.8', 'wait 1.2', 'press triangle', 'wait 4',   # в Kwik-E-Mart
          'foot 499.43 305.25 0 -19.5', 'wait 0.5', 'press triangle', 'wait 3']                                               # на улицу
    L += ['flag msn', 'wait 3', 'flag msngo', 'wait 0.5', 'press triangle', 'wait 14', 'press cross', 'wait 3', 'flag msngo', 'wait 1']
    for _ in range(8): L += ['press triangle', 'wait 4', 'press triangle', 'wait 4']   # сел — вышел
    return '\n'.join(L + ['end']) + '\n'

def run(name, eboot, old):
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f: f.write(scen(old)); sp = f.name
    subprocess.run([sys.executable, str(SCEN), name, sp], cwd=DATA, env=dict(os.environ, SCEN_EBOOT=str(eboot)),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=900)
    p = DATA / 'build/twins/scen/full' / name / 'smoke.txt'
    return p.read_text(errors='replace') if p.exists() else ''

def facts(txt):
    ra = re.findall(r'^ROOMAMB room=(\S+) amb=(\S+)', txt, re.M)
    ms = re.findall(r'^MSN say mstart (\S+)', txt, re.M)
    goc = re.findall(r'^SAY goc (\S+)', txt, re.M)
    return ra, ms, goc

def judge(txt):
    if 'END' not in txt.split(): return 'сценарий не дошёл до END'
    ra, ms, goc = facts(txt); bad = []
    kw = [a for r, a in ra if r == 'KwikEMart']; out = [a for r, a in ra if r == '-']
    if kw != ['amb_room_small_01']: bad.append(f'в Kwik-E-Mart атмосфера {kw or "нет строки ROOMAMB"}')
    if not out or out[0] in ('amb_room_small_01', '-'): bad.append(f'после выхода атмосфера {out or "нет строки"}')
    if not ms or not all(m.startswith('w_mstart_hom_') for m in ms): bad.append(f'реплика старта миссии: {ms or "нет"}')
    named = [g for g in goc if g.startswith('w_goc_hom_')]
    if len(goc) < 6 or not named: bad.append(f'выходов из машины {len(goc)}, реплик w_goc_hom_ {len(named)}')
    gic = re.findall(r'^SAY gic (\S+)', txt, re.M)
    if len(gic) < 6 or not any(g.startswith('w_gic_hom_') for g in gic):
        bad.append(f'посадок {len(gic)}, реплик W_GIC нет или неполный сценарий')
    return '; '.join(bad)

if __name__ == '__main__':
    eb = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    t_red, t_green = run('a345_pcsay_red', eb, True), run('a345_pcsay_green', eb, False)
    for nm, t in (('красный', t_red), ('зелёный', t_green)):
        ra, ms, goc = facts(t); print(f'{nm}: ROOMAMB {ra}; mstart {ms}; goc {goc}')
    red, green = judge(t_red), judge(t_green)
    print(f'красный (flag pcsayold, roomambold): {red or "прошёл — проверка слепая"}'); print(f'зелёный: {green or "OK"}')
    ok = bool(red) and not green
    print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
