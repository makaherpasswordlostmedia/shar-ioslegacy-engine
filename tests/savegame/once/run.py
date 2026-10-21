"""Правка Роба 334 (05.10, голосом): «Ящики и монеты не возобновляются на уровне в оригинале: если я их собрал и сохранился, они не
должны потом появляться опять на том же месте, иначе буду бесконечно ящики получать». Разовые предметы — стейтпропы с монетами
(stateprops.h spOnce): в игре не возвращаются «вне вида», в записи помнятся по уровню (хвост DATA.BIN, savegame.h SvOnce).
Гейт в безоконном PPSSPP (scen.py), своя карта эмулятора на каждую пару прогонов:
  ЗЕЛЁНЫЙ  ingame.txt — таран ящика 30 даёт монеты; 8 с за 200 м и снова таран того же места — кошелёк не растёт;
           save.txt — таран -> SAVE слот 1 -> QUIT -> LOAD -> таран: ящика нет (SVONCE op=apply restored>=1), кошелёк тот же;
           resume.txt — новый запуск, RESUME GAME -> таран: кошелёк тот же
  КРАСНЫЙ  те же сценарии + «flag svonceold» (прежнее: ящик возвращается, в запись не идёт) — кошелёк растёт, гейт обязан упасть
python3 tests/savegame/once/run.py [EBOOT]  -> 0 = PASS. GATE_OUT — папка карт (build/gates/saveonce), GATE_PREFIX — префикс
прогонов в build/twins/scen/full (svo_)"""
import os, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; HERE = Path(__file__).resolve().parent
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'
RUNS = Path(os.environ.get('SCEN_ROOT', '/Users/USER/Downloads/shar-psp')) / 'build/twins/scen/full'
OUT = Path(os.environ.get('GATE_OUT', str(ROOT / 'build/gates/saveonce'))); PFX = os.environ.get('GATE_PREFIX', 'svo_')
sys.path.insert(0, str(HERE.parent)); import emu_check as E   # kv, first, lines


def run(name, scen, eboot, home):
    home.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(SCEN), PFX + name, str(scen)], env=dict(os.environ, SCEN_EBOOT=eboot, SCEN_HOME=str(home)),
                   capture_output=True, timeout=900)
    return RUNS / (PFX + name)


def coins(log, src='now'):
    return [int(E.kv(l).get('coins', -1)) for l in log if l.startswith('SVPROG ') and E.kv(l).get('src') == src]


def check_ingame(d):
    log = E.lines(d); f = []
    if not any(l.startswith('END') for l in log): f.append('нет END (упал / завис)')
    c = coins(log)   # старт, в машине, после тарана 1, после возврата и тарана 2
    if len(c) < 4: return f + ['нет строк кошелька (%s)' % c], c
    if c[2] <= c[1]: f.append('таран ящика не дал монет (%d -> %d) — сценарий не дошёл до ящика' % (c[1], c[2]))
    if c[3] != c[2]: f.append('ящик вернулся: второй таран того же места дал %+d монет' % (c[3] - c[2]))
    return f, c


def check_save(d):
    log = E.lines(d); f = []
    if not any(l.startswith('END') for l in log): f.append('нет END (упал / завис)')
    io = E.first(log, 'SVIO', op='save')
    if not io or E.kv(io).get('verify') != 'O': f.append('запись не подтверждена (%s)' % io)
    c, ld = coins(log), coins(log, 'load')
    ap = E.first(log, 'SVONCE', op='apply')
    if len(c) < 3 or not ld: return f + ['нет строк кошелька (now %s, load %s)' % (c, ld)], c + ld
    before = c[0]   # после тарана, до записи
    if before <= 7: f.append('таран ящика не дал монет (%d)' % before)
    if ld[0] != before: f.append('кошелёк после загрузки другой (%d -> %d)' % (before, ld[0]))
    if not ap or int(E.kv(ap).get('restored', 0)) < 1: f.append('разбитый ящик не восстановлен из записи (%s)' % ap)
    if c[-1] != before: f.append('после загрузки ящик снова на месте: таран дал %+d монет' % (c[-1] - before))
    return f, [before, ld[0], c[-1]]


def check_resume(d, want):
    log = E.lines(d); f = []
    if not any(l.startswith('END') for l in log): f.append('нет END (упал / завис)')
    c, ld = coins(log), coins(log, 'load')
    ap = E.first(log, 'SVONCE', op='apply')
    if not c or not ld: return f + ['нет строк кошелька'], c
    if ld[0] != want: f.append('RESUME: кошелёк %d, записан %d' % (ld[0], want))
    if not ap or int(E.kv(ap).get('restored', 0)) < 1: f.append('RESUME: разбитый ящик не восстановлен (%s)' % ap)
    if c[-1] != ld[0]: f.append('после RESUME ящик снова на месте: таран дал %+d монет' % (c[-1] - ld[0]))
    return f, [ld[0], c[-1]]


def red_text(src):   # прежнее поведение — флаг сразу после начала игры (до тарана) и после RESUME
    out, done = [], False
    for l in src.read_text().splitlines(True):
        out.append(l)
        if not done and l.strip() == 'wait 5': out.append('flag svonceold\n'); done = True
    return ''.join(out)


def suite(eb, tag, red):
    home_a, home_b = OUT / ('home_%s_a' % tag), OUT / ('home_%s_b' % tag)
    for h in (home_a, home_b):
        if h.exists(): shutil.rmtree(h)
    sc = {}
    for n in ('ingame', 'save', 'resume'):
        p = HERE / (n + '.txt')
        if red: p2 = OUT / ('%s_%s.txt' % (tag, n)); p2.write_text(red_text(p)); p = p2
        sc[n] = p
    d1 = run('%s_ingame' % tag, sc['ingame'], eb, home_a)
    d2 = run('%s_save' % tag, sc['save'], eb, home_b)
    d3 = run('%s_resume' % tag, sc['resume'], eb, home_b)
    f1, c1 = check_ingame(d1); f2, c2 = check_save(d2); f3, c3 = check_resume(d3, c2[0] if c2 else -1)
    return f1, f2, f3, (c1, c2, c3), (d1, d2, d3)


if __name__ == '__main__':
    eb = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'viewer/build/EBOOT.PBP')
    OUT.mkdir(parents=True, exist_ok=True)
    g = suite(eb, 'green', False); r = suite(eb, 'red', True)
    names = ('в игре (уехал и вернулся)', 'запись и загрузка', 'новый запуск, RESUME')
    ok = not any(g[:3]); caught = all(r[:3])
    for i, n in enumerate(names):
        print('ЗЕЛЁНЫЙ %-28s %s  кошелёк %s' % (n, 'OK' if not g[i] else 'FAIL — ' + '; '.join(g[i]), g[3][i]))
    for i, n in enumerate(names):
        print('КРАСНЫЙ %-28s %s  кошелёк %s' % (n, ('пойман — ' + '; '.join(r[i])) if r[i] else 'НЕ ПОЙМАН', r[3][i]))
    print('прогоны:', ' '.join(str(d.name) for d in g[4] + r[4]))
    print('PASS' if ok and caught else 'FAIL', '— зелёный %s, красный пойман %d/3' % ('OK' if ok else 'FAIL', sum(1 for x in r[:3] if x)))
    sys.exit(0 if ok and caught else 1)
