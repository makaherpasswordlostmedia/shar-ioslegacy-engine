"""Правка Роба 279 (04.10: «нет музыки ни в миссии, ни в погоне»): NEW GAME -> ролик fmv1a пропущен START (кнопка держится 1 с,
как пальцем) -> в игре НЕ открывается пауза (тюнер «Pause» глушит музыку), а в погоне Hit & Run слышна тема погони: шина музыки > 0,
поток hit_run_*. Безоконный PPSSPP близнецов без звука (scen.py скилла shar-level-polish).
КРАСНЫЙ: «flag padresyncold 1» (прежний пульт после ролика) обязан упасть. python3 tests/sound/fmv_skip_music.py [EBOOT] -> 0 = PASS"""
import os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'

def scen(old):
    return '\n'.join(['flag menu', 'flag newgamefmv'] + (['flag padresyncold 1'] if old else []) +
                     ['wait 2', 'flag idle 2', 'flag demoidle 2', 'wait 6.8', 'press cross', 'wait 0.9', 'flag idle 0', 'wait 1.5',
                      'press cross', 'wait 7', 'press start 1.0', 'wait 4', 'goto 220 172 1.5708', 'wait 2', 'flag hnr 100', 'wait 8', 'end']) + '\n'

def run(name, eboot, old):
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f: f.write(scen(old)); sp = f.name
    subprocess.run([sys.executable, str(SCEN), name, sp], cwd=ROOT, env=dict(os.environ, SCEN_EBOOT=str(eboot)),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
    p = ROOT / 'build/twins/scen/full' / name / 'smoke.txt'
    return p.read_text(errors='replace') if p.exists() else ''

def judge(txt):
    m = re.search(r'MSNFMV name=fmv1a have=1 played=1 .*skipped=1 .*t=([\d.]+)', txt)
    if not m: return 'ролик не пропущен START'
    t0 = float(m.group(1))
    pz = [float(t) for t in re.findall(r'PAUSE on .*t=([\d.]+)', txt) if t0 <= float(t) <= t0 + 3]
    if pz: return f'после пропуска ролика ({t0:.1f} с) открылась пауза ({pz[0]:.1f} с)'
    ch = [l for l in txt.splitlines() if l.startswith('AUDV') and 'cur=hit_run' in l]
    if not ch: return 'погоня без темы hit_run_*'
    bad = [l for l in ch if not re.search(r'bus=0\.[1-9]|bus=1', l) or 'pause=1' in l]
    if bad: return f'тема погони в нулевую шину / в паузе: {bad[0][:120]}'
    return ''

if __name__ == '__main__':
    eb = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    red = judge(run('fmvskip_red', eb, True)); green = judge(run('fmvskip_green', eb, False))
    print(f'красный (flag padresyncold): {red or "прошёл — проверка слепая"}'); print(f'зелёный: {green or "OK — пауза не открылась, тема погони слышна"}')
    ok = bool(red) and not green
    print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
