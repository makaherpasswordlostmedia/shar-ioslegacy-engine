"""Правка 274 (04.10): на PSP Роба запись не шла — утилита отвергала параметры (SVIO op=save res=80110388, SAVE_PARAM). Причина
(факт железа, pspautotests tests/utility/savedata/secureversion.expected): запрос 1536 Б с secureVersion 0 и нулевым ключом
железо не принимает; эмулятор принимает. Движок (viewer/savemenu.c) идёт цепочкой вариантов параметров.
Гейт в безоконном PPSSPP, прогоны своим SCEN_HOME (карта эмулятора у каждого своя):
  ЗЕЛЁНЫЙ  tests/savegame/fallback/green.txt — «flag savefail 388» имитирует отказ железа прежнему набору: запись доходит до
           запасного варианта и подтверждается чтением, после «забыть» загрузка из главного меню тоже идёт цепочкой и
           возвращает тот же прогресс, замер-тур savematrix: прежний отвергнут, остальные 5 пишут/читают/удаляют, T8 не осталось
  КРАСНЫЙ  тот же сценарий + «flag saveold 1» (прежнее поведение: только первый набор) — запись проваливается, гейт обязан упасть
  ПРЕЖНИЙ  без флагов — четыре прогона tests/savegame/emu.sh (запись, загрузка, RESUME, испорченная запись) через emu_check.py
python3 tests/savegame/fallback/run.py [EBOOT]  -> 0 = PASS. GATE_OUT — папка прогонов (build/gates/savefallback),
GATE_PREFIX — префикс имён прогонов в build/twins/scen/full (svf_)"""
import os, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'
RUNS = ROOT / 'build/twins/scen/full'
OUT = Path(os.environ.get('GATE_OUT', str(ROOT / 'build/gates/savefallback'))); PFX = os.environ.get('GATE_PREFIX', 'svf_')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); import emu_check as E   # kv, first, prog, KEYS
VARS = ['std', 'sv1', 'key', 's1500', 's1480', 'noicon']


def run(name, scen, eboot, home):
    home.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(SCEN), PFX + name, str(scen)], env=dict(os.environ, SCEN_EBOOT=eboot, SCEN_HOME=str(home)),
                   capture_output=True, timeout=900)
    return RUNS / (PFX + name)


def check_green(d, home):
    log = E.lines(d); fails = []; notes = []
    if not any(l.startswith('END') for l in log): fails.append('нет END (упал / завис)')
    if not E.first(log, 'SVFAIL', code='80110388'): fails.append('флаг savefail не понят (нет SVFAIL code=80110388)')
    tr = [E.kv(l) for l in log if l.startswith('SVIO try=')]
    sv = [t for t in tr if t.get('for') == 'save']; ld = [t for t in tr if t.get('for') == 'load']
    want = [('std', '80110388'), ('sv1', '00000000')]
    if [(t.get('try'), t.get('res')) for t in sv[:2]] != want: fails.append('запись: цепочка не std(80110388) -> sv1(0): %s' % sv[:3])
    io = E.first(log, 'SVIO', op='save')
    if not io or E.kv(io).get('res') != '00000000' or E.kv(io).get('verify') != 'O' or E.kv(io).get('var') != 'sv1':
        fails.append('запись не подтверждена запасным вариантом (%s)' % io)
    if not E.first(log, 'SVMSG', key='MSG_SAVE_SUCCESSFUL'): fails.append('нет «Save Successful»')
    if [(t.get('try'), t.get('res')) for t in ld[:2]] != [('std', '80110308'), ('sv1', '00000000')]:
        fails.append('загрузка: цепочка не std(80110308) -> sv1(0): %s' % ld[:3])
    lo = E.first(log, 'SVIO', op='load')
    if not lo or E.kv(lo).get('st') != 'O' or E.kv(lo).get('var') != 'sv1': fails.append('загрузка не прошла запасным (%s)' % lo)
    mark, got = E.first(log, 'SVPROG', src='mark'), E.first(log, 'SVPROG', src='load')
    if not mark or not got or E.prog(mark) != E.prog(got): fails.append('прогресс после загрузки другой (%s / %s)' % (mark, got))
    else: notes.append('прогресс после записи и загрузки цепочкой тот же')
    mx = {E.kv(l).get('variant'): E.kv(l) for l in log if l.startswith('SVMATRIX variant=')}
    if sorted(mx) != sorted(VARS): fails.append('замер-тур: не все варианты (%s)' % sorted(mx))
    else:
        bad = [v for v in VARS[1:] if (mx[v].get('res'), mx[v].get('load'), mx[v].get('cmp'), mx[v].get('del')) != ('00000000', '00000000', 'O', '00000000')]
        if mx['std'].get('res') != '80110388': bad.append('std не отвергнут')
        if bad: fails.append('замер-тур: ' + ', '.join(bad))
        else: notes.append('замер-тур: std отвергнут, %s пишут/читают/удаляют' % '/'.join(VARS[1:]))
    if not any(l.startswith('SVMATRIX done') for l in log): fails.append('замер-тур не дошёл до конца')
    sd = home / '.ppsspp/PSP/SAVEDATA'
    if (sd / 'SLES51897T8').exists(): fails.append('тестовая запись T8 осталась на карте')
    if not (sd / 'SLES5189700' / 'DATA.BIN').exists(): fails.append('на карте нет записи слота 1')
    return fails, notes


def check_file(d, home):   # 274 страховка файлом: утилита отвергла ВСЁ («saveutiloff 1») — запись и загрузка идут файлом save00.bin
    log = E.lines(d); fails = []
    if not any(l.startswith('END') for l in log): fails.append('нет END (упал / завис)')
    if not E.first(log, 'SVUTILOFF', on='1'): fails.append('флаг saveutiloff не понят')
    fs = E.first(log, 'SVFILE', op='save')
    if not fs or E.kv(fs).get('res') != '0': fails.append('файл не записан (%s)' % fs)
    io = E.first(log, 'SVIO', op='save')
    if not io or E.kv(io).get('verify') != 'O' or E.kv(io).get('var') != 'file': fails.append('запись не подтверждена файлом (%s)' % io)
    if not E.first(log, 'SVMSG', key='MSG_SAVE_SUCCESSFUL'): fails.append('нет «Save Successful»')
    lo = E.first(log, 'SVIO', op='load')
    if not lo or E.kv(lo).get('st') != 'O': fails.append('загрузка файлом не прошла (%s)' % lo)
    mark, got = E.first(log, 'SVPROG', src='mark'), E.first(log, 'SVPROG', src='load')
    if not mark or not got or E.prog(mark) != E.prog(got): fails.append('прогресс после загрузки другой (%s / %s)' % (mark, got))
    if not (d / 'save00.bin').exists(): fails.append('нет файла save00.bin рядом с игрой')
    return fails


def std_runs(eboot, tag):   # прежние сценарии tests/savegame/emu_*.txt без флагов, одна карта на четыре прогона
    home = OUT / ('home_std_' + tag)
    if home.exists(): shutil.rmtree(home)
    d1 = run('std_%s_1' % tag, ROOT / 'tests/savegame/emu_save.txt', eboot, home)
    d2 = run('std_%s_2' % tag, ROOT / 'tests/savegame/emu_load.txt', eboot, home)
    d3 = run('std_%s_3' % tag, ROOT / 'tests/savegame/emu_resume.txt', eboot, home)
    f = home / '.ppsspp/PSP/SAVEDATA/SLES5189700/DATA.BIN'
    if f.exists():   # порча: байты в середине файла (как emu.sh)
        b = bytearray(f.read_bytes()); n = len(b)
        for i in range(n // 3, n // 3 + 24): b[i] ^= 0x5a
        f.write_bytes(bytes(b))
    d4 = run('std_%s_4' % tag, ROOT / 'tests/savegame/emu_corrupt.txt', eboot, home)
    r = subprocess.run([sys.executable, str(ROOT / 'tests/savegame/emu_check.py'), str(d1), str(d2), str(d3), str(d4)],
                       capture_output=True, text=True)
    gone = not f.exists()
    return r.returncode == 0 and gone, r.stdout.strip().splitlines()[0] if r.stdout.strip() else r.stderr.strip()[-200:], gone


if __name__ == '__main__':
    eb = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'viewer/build/EBOOT.PBP')
    OUT.mkdir(parents=True, exist_ok=True)
    green = HERE / 'green.txt'; red = OUT / 'red.txt'
    red.write_text(''.join(l + ('flag saveold 1\n' if l.strip() == 'flag svmark' else '') for l in green.read_text().splitlines(True)))
    hg, hr = OUT / 'home_green', OUT / 'home_red'
    for h in (hg, hr):
        if h.exists(): shutil.rmtree(h)
    dg = run('green', green, eb, hg); fg, ng = check_green(dg, hg)
    dr = run('red', red, eb, hr); fr, _ = check_green(dr, hr)
    rio = E.first(E.lines(dr), 'SVIO', op='save')
    fgt, frt = OUT / 'file_green.txt', OUT / 'file_red.txt'   # 274: утилита отвергает всё -> страховка файлом; красный — без файла
    body = [l for l in green.read_text().splitlines(True) if not l.startswith('flag savefail') and not l.startswith('flag savematrix')]
    fgt.write_text(''.join(l + ('flag saveutiloff 1\n' if l.strip() == 'flag svmark' else '') for l in body))
    frt.write_text(''.join(l + ('flag saveutiloff 1\nflag savefileoff 1\n' if l.strip() == 'flag svmark' else '') for l in body))
    hf, hfr = OUT / 'home_file', OUT / 'home_file_red'
    for h in (hf, hfr):
        if h.exists(): shutil.rmtree(h)
    dfg = run('file_green', fgt, eb, hf); ffg = check_file(dfg, hf)
    dfr = run('file_red', frt, eb, hfr); ffr = check_file(dfr, hfr)
    ok_std, std_msg, gone = std_runs(eb, 'nf')
    print('ЗЕЛЁНЫЙ (savefail 388):', 'OK — ' + '; '.join(ng) if not fg else 'FAIL — ' + '; '.join(fg))
    print('КРАСНЫЙ (savefail 388 + saveold 1):', ('пойман — ' if fr else 'НЕ ПОЙМАН — ') + (rio or 'нет SVIO op=save'))
    print('ПРЕЖНИЙ (без флагов, emu_save/load/resume/corrupt):', std_msg, '' if gone else '; испорченная запись осталась')
    print('ФАЙЛ (утилита отвергла всё):', 'OK — записано и загружено файлом save00.bin, прогресс тот же' if not ffg else 'FAIL — ' + '; '.join(ffg))
    print('КРАСНЫЙ ФАЙЛА (+ savefileoff 1):', ('пойман — ' + ffr[0]) if ffr else 'НЕ ПОЙМАН')
    print('прогоны:', dg.name, dr.name, dfg.name, dfr.name, PFX + 'std_nf_1..4')
    ok = not fg and bool(fr) and ok_std and not ffg and bool(ffr)
    print('PASS: отказ прежнего набора -> запасной вариант пишет и читает; красный пойман; без флагов как раньше' if ok else
          'FAIL (зелёный %s, красный пойман %s, прежний %s)' % (not fg, bool(fr), ok_std))
    sys.exit(0 if ok else 1)
