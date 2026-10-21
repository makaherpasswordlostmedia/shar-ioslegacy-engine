#!/usr/bin/env python3
"""Гейт Т1.2 (docs/handoff/ДВА_ТЕСТИРОВЩИКА_2026-09-28.md §3): живой город в мире ботов. Каждая часть сначала красная.
  (1) save/load/hash: самопроверка игры без экрана с трафиком (ввод дважды побайтно; сохранить -> 10 с -> загрузить -> те же 10 с);
      контроль — сборка -DBW_BREAK_TRAFFIC_LOAD=1 (загрузка не возвращает трафик) обязана упасть.
  (2) один повтор ввода — одно и то же: настоящий повтор каскадёра прямо и «как бот» (--stitch: снимок, забег, загрузка каждые 90
      кадров) дают один отпечаток мира; контроль на сломанной сборке — разные.
  (3) машина-препятствие: от спавна уровня 5 с газа по прямой, стоящая машина подложена в 30 м впереди (--plant-car);
      без трафика (BW_NO_TRAFFIC=1) бот её не видит и проезжает дальше; с трафиком — упирается (удар, событие Hit & Run).
Сверка с EBOOT в эмуляторе здесь не делается: арифметика PSP и Мака разная; порядок кадра — как main.c (tools/bots/world.c)."""
import os, re, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; B = ROOT / 'build/bots'; L = [str(ROOT / 'build/level.shr'), str(ROOT / 'build/homer.shr')]


def run(binp, *a, env=None):
    return subprocess.run([str(binp), *L, *map(str, a)], capture_output=True, text=True, env=dict(os.environ, **(env or {}))).stdout


def main():
    subprocess.run([str(ROOT / 'tools/bots/build.sh')], check=True, capture_output=True)
    subprocess.run([str(ROOT / 'tools/bots/build.sh'), '-DBW_BREAK_TRAFFIC_LOAD=1'], check=True, capture_output=True, env=dict(os.environ, BINS='game_headless', SUF='_trbroken'))
    good, bad = B / 'game_headless', B / 'game_headless_trbroken'
    out = ROOT / 'build/bots/runs/gate-t12' / time.strftime('%Y%m%d-%H%M%S'); out.mkdir(parents=True)
    L1 = []
    # (1)
    g, b = run(good, '--selftest', '--secs', 30), run(bad, '--selftest', '--secs', 30)
    tr = re.search(r'трафик в мире: машин (\d+), пешеходов (\d+), стоящих мест (\d+)', g)
    ok1 = 'RESULT: OK' in g and tr and int(tr.group(1)) > 0 and int(tr.group(3)) > 0 and 'RESULT: FAIL' in b
    L1.append(f"(1) save/load/hash: контроль (загрузка без трафика) — {'КРАСНЫЙ, расхождение поймано' if 'RESULT: FAIL' in b else 'зелёный — КОНТРОЛЬ НЕ ЛОВИТ'}; "
              f"рабочая — {'зелёный' if 'RESULT: OK' in g else 'КРАСНЫЙ'}, в мире {tr.group(0) if tr else 'трафика нет'}")
    # (2)
    reps = sorted((ROOT / 'build/bots/runs/explore').glob('*-gate/good/repro/coin*.in'), key=lambda p: -p.stat().st_mtime)
    if not reps: print('гейт Т1.2: нет повтора каскадёра (python3 tools/bots/explorer.py --gate)'); return 1
    rp = reps[0]; st = re.search(r'--start ([-0-9.e ]+) --input', rp.read_text().split('\n', 1)[0]).group(1).split()
    def fp(binp, *x): m = re.search(r'отпечаток ([0-9a-f]+)', run(binp, '--input', rp, '--start', *st, *x)); return m.group(1) if m else None
    gs, gt, bs, bt = fp(good), fp(good, '--stitch', 90), fp(bad), fp(bad, '--stitch', 90)
    ok2 = gs and gs == gt and bs != bt
    L1.append(f"(2) повтор `{rp.relative_to(ROOT)}`: контроль прямой {bs} / как бот {bt} — {'КРАСНЫЙ, разошлось' if bs != bt else 'совпало — КОНТРОЛЬ НЕ ЛОВИТ'}; "
              f"рабочая {gs} / {gt} — {'зелёный, одно и то же' if gs == gt else 'КРАСНЫЙ'}")
    # (3)
    gas = out / 'gas.in'; gas.write_text('300 200 0 0\n')
    def end(env):
        o = run(good, '--input', gas, '--plant-car', 250, 3.5, 172, 1.5708, env=env)
        x = float(re.search(r'машина ([-0-9.]+)', o).group(1)); e = re.search(r'событий (\d+)', o); return x, int(e.group(1)) if e else 0
    (xn, _), (xt, et) = end({'BW_NO_TRAFFIC': '1'}), end({})
    ok3 = xn > 262 and xt < 262 and et > 0
    L1.append(f"(3) машина-препятствие в x 250: без трафика бот доехал до x {xn:.1f} — {'КРАСНЫЙ, не видит' if xn > 262 else 'встал'}; "
              f"с трафиком — x {xt:.1f}, событий {et} — {'зелёный, упёрся' if xt < 262 and et else 'КРАСНЫЙ'}")
    ok = bool(ok1 and ok2 and ok3); L1.append(f"RESULT: {'OK' if ok else 'FAIL'}")
    (out / 'gate.txt').write_text('\n'.join(L1) + '\n'); print('\n'.join(L1)); print('->', out)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
