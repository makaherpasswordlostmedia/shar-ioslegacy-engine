"""№627: прогон tests/hnr/busted_ps2.txt (шаблон — bust_freeroam.py) в безоконном PPSSPP близнецов (без звука), разбор журнала:
есть арест (HNR busted), нет провала миссии (MSN failed), есть строка «штраф без провала». python3 ... ИМЯ EBOOT -> 0 = PASS"""
import os, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'twins'))
import common as C, port as P

def run(name, eboot, scen='busted_ps2', timeout=180):
    out = C.OUT / 'busted_ps2'; out.mkdir(parents=True, exist_ok=True)
    d, man = P.stage_full(out, name, (ROOT / f'tests/hnr/{scen}.txt').read_text(), 5)
    (d / 'EBOOT.PBP').unlink(); shutil.copy2(eboot, d / 'EBOOT.PBP')
    home = C.OUT / 'ppsspp_home'; home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN))
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    with (d / 'headless.log').open('w') as log:
        pr = subprocess.Popen(['nice', '-n', '10', str(P.HEADLESS), '--graphics=software', f'--timeout={timeout}', str(d / 'EBOOT.PBP')],
                              cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT)
        P.watch_no_window(pr, timeout + 60)
    return d

def smoke(d): return (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''

if __name__ == '__main__':
    name, eb = sys.argv[1], sys.argv[2]; err = []
    sa = smoke(run(name + '_pol', eb, 'busted_ps2'))   # A: полиция, Гомер пешком
    m = re.search(r'BUSTED arrest police_after=(\d+) t=([\d.]+)', sa); v = re.search(r'BUSTED vanish t=([\d.]+)', sa)
    if 'HNR busted' not in sa or not m: err.append('A: ареста нет (полиция не появилась?)')
    else:
        if int(m.group(1)) < 1: err.append(f'A: полицейская убрана в момент ареста (police_after={m.group(1)})')
        if not v: err.append('A: нет шага «полицейская и карточка пропали»')
        elif not 1.3 <= float(v.group(1)) - float(m.group(2)) <= 1.7: err.append(f'A: исчезла через {float(v.group(1)) - float(m.group(2)):.2f} с (нужно 1,5)')
    sb = smoke(run(name + '_car', eb, 'busted_ps2_car'))   # B: в машине — затемнение и перенос
    ar = re.search(r'BUSTED arrest police_after=\d+ t=([\d.]+)', sb)   # шкала после штрафа 5, спад до 0 за ~3 с
    if ar:
        t0 = float(ar.group(1)); hv = [(float(t), float(h)) for t, h in re.findall(r'HNRV t=([\d.]+) heat=([\d.]+)', sb) if float(t) >= t0 - 0.05]
        early = [h for t, h in hv if t - t0 <= 1.0]; late = [h for t, h in hv if 3.2 <= t - t0 <= 4.5]
        if not early or max(early) < 0.03: err.append(f'шкала после штрафа сразу 0 (нужно 5 ед.): {early}')
        if not late or max(late) > 0.001: err.append(f'шкала через 3,2 с не 0: {late}')
    v = re.search(r'BUSTED vanish t=([\d.]+)', sb); f = re.search(r'BUSTED fade=(\d) placed=(\d) t=([\d.]+)', sb)
    if not f or f.group(1) != '1' or f.group(2) != '1': err.append(f'B: нет затемнения с переносом ({f.group(0) if f else "строки нет"})')
    elif v and not 0.2 <= float(f.group(3)) - float(v.group(1)) <= 1.6: err.append(f'B: затемнение через {float(f.group(3)) - float(v.group(1)):.2f} с после исчезновения')
    print(f'{name}: {"OK" if not err else "FAIL: " + "; ".join(err)}'); sys.exit(1 if err else 0)
