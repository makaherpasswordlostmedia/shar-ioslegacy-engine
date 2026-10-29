"""Правка Роба 241: tests/hnr/hud_scenario.txt в безоконном PPSSPP близнецов (без звука), разбор строк UIHNR журнала против правил
оригинала (tests/ui/anim_rules.py: покой / предупреждение выше 78 / погоня, ритм 0.25 с) и порядка «шкала 100 -> до полиции
красно-чёрное -> с полицией красно-синее, в том числе ниже 80».
    python3 tests/hnr/hud.py green|oldui|latch EBOOT  -> 0 = PASS; oldui — тот же EBOOT с прежним кодом кольца (flag uihnrtraceold)
Папки: HUD_RUN (прогоны, по умолчанию build/twins/hnr_hud), HUD_HOME (HOME эмулятора, по умолчанию build/twins/ppsspp_home)"""
import os, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get('SHAR_DATA', ROOT))
sys.path.insert(0, str(DATA / 'tools' / 'twins')); sys.path.insert(0, str(ROOT / 'tests' / 'ui'))
import common as C, port as P  # noqa: E402
import anim_rules as R  # noqa: E402


def run(name, eboot, trace, timeout=240):
    out = Path(os.environ.get('HUD_RUN', C.OUT / 'hnr_hud')); out.mkdir(parents=True, exist_ok=True)
    scn = (ROOT / 'tests/hnr/hud_scenario.txt').read_text().replace('flag TRACE', 'flag ' + trace)
    d, man = P.stage_full(out, name, scn, 5)
    (d / 'EBOOT.PBP').unlink(); shutil.copy2(eboot, d / 'EBOOT.PBP')
    home = Path(os.environ.get('HUD_HOME', C.OUT / 'ppsspp_home')); home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN),
               SDL_AUDIODRIVER='dummy')
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    with (d / 'headless.log').open('w') as log:
        pr = subprocess.Popen(['nice', '-n', '10', str(P.HEADLESS), '--graphics=software', f'--timeout={timeout}', str(d / 'EBOOT.PBP')],
                              cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT)
        P.watch_no_window(pr, timeout + 60)
    return d


def check(smoke):
    log = smoke.splitlines()
    kv = lambda l: dict(m.groups() for m in re.finditer(r'(\w+)=(\S+)', l))
    rows = [(float(d['te']), int(d['target']), int(d['shown']), int(d['light']), int(d['col'], 16), int(d['pursuit']))
            for d in (kv(l) for l in log if l.startswith('UIHNR '))]
    chk = R.hnr(rows, tol=0.06) if rows else [(False, 'нет строк UIHNR (кольцо не рисовалось)')]
    full = next((r[0] for r in rows if r[1] >= 995), None)
    alarm = next((r[0] for r in rows if r[5]), None)
    pre = [r for r in rows if full is not None and full <= r[0] < (alarm if alarm is not None else 1e9)]
    good = bool(pre) and all(r[4] in (R.RED, R.DARK) and r[3] == 2 for r in pre)
    chk.append((good and alarm is not None and 0.3 <= alarm - full <= 1.2, 'шкала 100 -> полиция через %s с; до неё кадров %d, все красно-чёрные без мигалки: %s'
                % ('%.2f' % (alarm - full) if alarm is not None and full is not None else '-', len(pre), good)))
    low = [r for r in rows if r[5] and r[1] < 800]
    chk.append((bool(low) and all(r[4] in (R.RED, R.BLUE) for r in low), 'погоня ниже 80: кадров %d, все красно-синие' % len(low)))
    chk.append(('HNR police' in smoke, 'полиция появилась (HNR police в журнале)'))
    return R.report('кольцо от шкалы игры (эмулятор)', chk)


if __name__ == '__main__':
    mode, eboot = sys.argv[1], sys.argv[2]
    d = run('hud_' + mode, eboot, 'uihnrtraceold' if mode == 'oldui' else 'uihnrtrace')
    s = (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''
    ok, text = check(s)
    print(text); print(f'{mode}: {"OK" if ok else "FAIL"} ({d})'); sys.exit(0 if ok else 1)
