"""Правка Роба 309 (04.10, голосом): «Обычно на PSP оно тебя переводит в контекстное меню PSP и ты там подтверждаешь создание этого
файла… В нашем случае оно просто как на PS2 такое чик, сохранилось и пошло». Запись слота — системным окном утилиты сохранения PSP
(режим SAVE с интерфейсом), загрузка — окном LOAD (viewer/savemenu.c, ST_SYSDLG). Гейт в безоконном PPSSPP, который рисует окна
утилиты (атлас PPGe, TWINS_PPGE=1) и принимает кнопки сценария в своём контроллере (строка TWPAD) — своя сборка
tools/twins/ppsspp_pad_build.sh (build/twins/bin/PPSSPPHeadlessPad; общий PPSSPPHeadless не трогается). Прогоны — своим SCEN_HOME.
  ЗЕЛЁНЫЙ  tests/savegame/dialog/green.txt — «flag svdialog»: слот 1 -> окно PSP (статус утилиты 2 — окно на экране) -> ○ (отмена:
           ничего не записано, снова слоты) -> слот 1 -> окно -> ✕ Да -> «Сохранение завершено» -> ○; запись подтверждена чтением;
           перезапись того же слота: окно «Перезаписать?» -> ← Да -> ✕ -> seq 2 подтверждена;
           своих «Saving…» / «Save Successful» нет; QUIT -> меню -> LOAD GAME -> окно «Загрузить?» -> ✕ -> тот же прогресс;
           на карте эмулятора SLES5189700 (DATA.BIN, PARAM.SFO), рядом с игрой save00.bin; полоса окна видна на снимке
  КРАСНЫЙ  тот же сценарий + «flag svquiet» (прежний тихий путь без окна) — окна нет, гейт обязан упасть
  ЗАПАСНОЙ tests/savegame/dialog/fallback.txt — «flag svdlgfail»: окно отвергает все варианты (sv1, key, s1500, s1480, noicon, окно не
           показано) -> прежний тихий путь (AUTOSAVE цепочкой + файл) и сообщение оригинала «Save Successful»
python3 tests/savegame/dialog/run.py [EBOOT]  -> 0 = PASS. GATE_HEADLESS — PPSSPPHeadless с TWPAD (по умолчанию
build/twins/bin/PPSSPPHeadlessPad), GATE_OUT — папка карт (build/gates/savedialog), GATE_PREFIX — префикс прогонов (svd_),
SCEN_OVERRIDE — как у scen.py (psave.shr=…,fsave.shr=…)"""
import os, re, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; HERE = Path(__file__).resolve().parent
SCRIPTS = Path.home() / '.claude/skills/shar-level-polish/scripts'
OUT = Path(os.environ.get('GATE_OUT', str(ROOT / 'build/gates/savedialog'))); PFX = os.environ.get('GATE_PREFIX', 'svd_')
HEADLESS = Path(os.environ.get('GATE_HEADLESS', str(ROOT / 'build/twins/bin/PPSSPPHeadlessPad')))
sys.path.insert(0, str(HERE.parent)); import emu_check as E   # kv, first, prog, lines
VARS = ['sv1', 'key', 's1500', 's1480', 'noicon']


def run(name, scen_text, eboot, home):
    import subprocess
    home.mkdir(parents=True, exist_ok=True)
    f = OUT / (name + '.txt'); f.write_text(scen_text)
    code = ('import sys; sys.path.insert(0, %r); import scen; from pathlib import Path; scen.P.HEADLESS = Path(%r); '
            'scen.run(%r, open(%r).read().splitlines())') % (str(SCRIPTS), str(HEADLESS), PFX + name, str(f))
    r = subprocess.run([sys.executable, '-c', code], env=dict(os.environ, SCEN_EBOOT=eboot, SCEN_HOME=str(home), TWINS_PPGE='1'),
                       capture_output=True, text=True, timeout=900)
    m = re.search(r'^dir (\S+) bad', r.stdout, re.M)   # папка прогона — как её напечатал scen.py (build/twins/scen/full/<имя>)
    return Path(m.group(1)) if m else OUT / ('missing_' + name)


def band(png, y0=2, y1=20):   # средняя яркость полосы вверху снимка (там PPSSPP рисует строку окна «Save» / «Load»)
    from PIL import Image
    import numpy as np
    a = np.asarray(Image.open(png).convert('RGB'), dtype=float)[y0:y1, :480]
    return float(a.mean())


def check_green(d, home):
    log = E.lines(d); fails, notes = [], []
    if not any(l.startswith('END') for l in log): fails.append('нет END (упал / завис)')
    if not E.first(log, 'SVDLGMODE', on='1', src='flag'): fails.append('флаг svdialog не понят')
    dl = [E.kv(l) for l in log if l.startswith('SVDLG op=')]
    sv = [x for x in dl if x.get('op') == 'save']; ld = [x for x in dl if x.get('op') == 'load']
    vis = lambda x: int(x.get('vis', '0')) > 0
    if len(sv) < 2 or not vis(sv[0]) or sv[0].get('res') != '00000001':
        fails.append('отмена в окне: нет окна со статусом «на экране» и ответом «отмена» (%s)' % sv[:1])
    else: notes.append('окно на экране %s кадров, ○ — отмена' % sv[0]['vis'])
    i_cancel = next((i for i, l in enumerate(log) if l.startswith('SVIO op=save') and 'res=cancel' in l), -1)
    if i_cancel < 0: fails.append('после отмены нет SVIO op=save res=cancel')
    elif any(l.startswith(('SVFILE op=save', 'SVIO op=save slot=0 res=0')) for l in log[:i_cancel]): fails.append('отмена, а запись была')
    if len(sv) < 2 or not vis(sv[1]) or sv[1].get('res') != '00000000' or sv[1].get('try') not in VARS:
        fails.append('запись окном не прошла (%s)' % sv[1:2])
    else: notes.append('запись окном: вариант %s, окно %s кадров, фон %s' % (sv[1]['try'], sv[1]['vis'], sv[1].get('bg')))
    io = next((E.kv(l) for l in log if l.startswith('SVIO op=save') and 'res=cancel' not in l), None)
    if not io or io.get('res') != '00000000' or io.get('verify') != 'O' or io.get('dlg') != '1':
        fails.append('запись окном не подтверждена чтением (%s)' % io)
    ios = [E.kv(l) for l in log if l.startswith('SVIO op=save') and 'res=cancel' not in l]   # перезапись: окно «Перезаписать?»
    if len(sv) < 3 or not vis(sv[2]) or sv[2].get('res') != '00000000' or len(ios) < 2 or ios[1].get('verify') != 'O' \
            or ios[1].get('dlg') != '1' or ios[1].get('seq') != '2':
        fails.append('перезапись слота окном не прошла (%s / %s)' % (sv[2:3], ios[1:2]))
    else: notes.append('перезапись окном (seq 2) подтверждена')
    for key in ('MSG_SAVING_GAME_(PS2)', 'MSG_SAVE_SUCCESSFUL', 'MSG_SAVE_CONFIRM_OVERWRITE_(PS2)'):
        if E.first(log, 'SVMSG', key=key): fails.append('при окне PSP — своё сообщение %s (два подтверждения подряд)' % key)
    if not ld or not vis(ld[0]) or ld[0].get('res') != '00000000': fails.append('загрузка окном не прошла (%s)' % ld[:1])
    lo = next((E.kv(l) for l in log if l.startswith('SVIO op=load')), None)
    if not lo or lo.get('st') != 'O' or lo.get('dlg') != '1': fails.append('загрузка окном не подтверждена (%s)' % lo)
    mark, got = E.first(log, 'SVPROG', src='mark'), E.first(log, 'SVPROG', src='load')
    if not mark or not got or E.prog(mark) != E.prog(got): fails.append('прогресс после загрузки другой (%s / %s)' % (mark, got))
    else: notes.append('прогресс после записи и загрузки окном тот же')
    if not any(l.startswith('TWPAD 4000') for l in log): fails.append('✕ сценария не дошёл до окна (нет TWPAD 4000)')
    sd = home / '.ppsspp/PSP/SAVEDATA/SLES5189700'
    if not (sd / 'DATA.BIN').exists() or not (sd / 'PARAM.SFO').exists(): fails.append('на карте нет SLES5189700/DATA.BIN, PARAM.SFO')
    if not (d / 'save00.bin').exists(): fails.append('нет страховки save00.bin рядом с игрой')
    try:
        b0, b1 = band(d / 'd_slots.png'), band(d / 'd_confirm.png')
        if abs(b1 - b0) < 6: fails.append('на снимке d_confirm нет полосы окна (яркость %.1f -> %.1f)' % (b0, b1))
        else: notes.append('полоса окна на снимке: яркость %.1f -> %.1f' % (b0, b1))
    except OSError as e: fails.append('снимков нет (%s)' % e)
    return fails, notes


def check_fallback(d, home):
    log = E.lines(d); fails = []
    if not any(l.startswith('END') for l in log): fails.append('нет END (упал / завис)')
    if not E.first(log, 'SVDLGFAIL', on='1'): fails.append('флаг svdlgfail не понят')
    sv = [E.kv(l) for l in log if l.startswith('SVDLG op=save')]
    if [x.get('try') for x in sv] != VARS or any(x.get('res') != '80110388' or x.get('vis') != '0' for x in sv):
        fails.append('окно: не все варианты отвергнуты без показа (%s)' % [(x.get('try'), x.get('res'), x.get('vis')) for x in sv])
    if not E.first(log, 'SVDLGQUIET', op='save'): fails.append('нет перехода на тихий путь (SVDLGQUIET)')
    io = E.first(log, 'SVIO', op='save')
    if not io or E.kv(io).get('verify') != 'O' or E.kv(io).get('dlg') != '0': fails.append('тихая запись не подтверждена (%s)' % io)
    if not E.first(log, 'SVMSG', key='MSG_SAVE_SUCCESSFUL'): fails.append('нет «Save Successful» оригинала')
    if not (home / '.ppsspp/PSP/SAVEDATA/SLES5189700/DATA.BIN').exists() and not (d / 'save00.bin').exists():
        fails.append('записи нет ни на карте, ни файлом')
    return fails


if __name__ == '__main__':
    eb = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'viewer/build/EBOOT.PBP')
    if not HEADLESS.exists():
        print('FAIL: нет %s — собрать tools/twins/ppsspp_pad_build.sh (PPSSPPHeadless с кнопками в окнах утилиты)' % HEADLESS); sys.exit(1)
    OUT.mkdir(parents=True, exist_ok=True)
    green = (HERE / 'green.txt').read_text()
    red = ''.join(l + ('flag svquiet\n' if l.strip() == 'flag svdialog' else '') for l in green.splitlines(True))
    homes = {k: OUT / ('home_' + k) for k in ('green', 'red', 'fallback')}
    for h in homes.values():
        if h.exists(): shutil.rmtree(h)
    dg = run('green', green, eb, homes['green']); fg, ng = check_green(dg, homes['green'])
    dr = run('red', red, eb, homes['red']); fr, _ = check_green(dr, homes['red'])
    df = run('fallback', (HERE / 'fallback.txt').read_text(), eb, homes['fallback']); ff = check_fallback(df, homes['fallback'])
    print('ЗЕЛЁНЫЙ (окно PSP):', 'OK — ' + '; '.join(ng) if not fg else 'FAIL — ' + '; '.join(fg))
    print('КРАСНЫЙ (+ svquiet, прежний путь без окна):', ('пойман — ' + '; '.join(fr[:3])) if fr else 'НЕ ПОЙМАН')
    print('ЗАПАСНОЙ (окно отвергло все варианты):', 'OK — тихий путь записал, «Save Successful»' if not ff else 'FAIL — ' + '; '.join(ff))
    print('прогоны:', dg.name, dr.name, df.name, '; снимки окна:', ', '.join(str(dg / (n + '.png')) for n in ('d_confirm', 'd_done', 'd_load_ask')))
    ok = not fg and bool(fr) and not ff
    print('PASS: окно PSP подтверждает запись и загрузку, данные те же; красный пойман; запасной путь жив' if ok else
          'FAIL (зелёный %s, красный пойман %s, запасной %s)' % (not fg, bool(fr), not ff))
    sys.exit(0 if ok else 1)
