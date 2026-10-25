#!/usr/bin/env python3
# CAMPERF (ускорение камеры, дирижёр 23.10): вердикты по двум журналам смоука (smoke.txt) — «старый» и «новый» прогон одного сценария (tests/camera/camperf_gen.py).
#   camperf.py equal OLD NEW [--tol 0.001]      траектория глаза, взгляда и ближней плоскости (строки CAMF) одинаковая, не хуже tol (1 мм); кадров поровну
#   camperf.py cost  OLD NEW [--max 0.85]       цена камеры за езду/ходьбу (строки CAMSUB: chase + safe + floor + fnear + nfr + rw, мкс на кадр) новая / старая не больше --max
#   camperf.py ... --expect fail                красный контроль: вердикт должен быть FAIL (например equal «новый против прогона с camsafeold 1» или cost «старый против старого»)
# Выход 0 — вердикт совпал с ожидаемым.
import re, sys
def camf(p):
    d = []
    for l in open(p, encoding='utf-8', errors='replace'):
        if l.startswith('CAMF '):
            m = re.search(r't=([\d.]+).*?eye=([-\d.]+),([-\d.]+),([-\d.]+) look=([-\d.]+),([-\d.]+),([-\d.]+).*? near=([-\d.]+)', l)
            if m: d.append(tuple(float(m.group(i)) for i in range(1, 9)))
    return d
def equal(a, b, tol):
    A, B = camf(a), camf(b)
    if not A or len(A) != len(B): return False, 'кадров %d и %d' % (len(A), len(B))
    mx, bad, first = 0.0, 0, None
    for i, (x, y) in enumerate(zip(A, B)):
        if abs(x[0] - y[0]) > 0.0025: return False, 'время разошлось на кадре %d (%.3f и %.3f)' % (i, x[0], y[0])
        e = max(abs(x[k] - y[k]) for k in range(1, 8)); mx = max(mx, e)
        if e > tol:
            bad += 1
            if first is None: first = (i, x[0], e)
    return bad == 0, 'кадров %d, наибольшее расхождение %.4f м, кадров больше %.4f м: %d%s' % (len(A), mx, tol, bad, '' if first is None else ', первый: кадр %d t=%.2f %.3f м' % first)
KEYS = ['chase', 'safe', 'floor', 'fnear', 'nfr', 'rw']
def cost(p):
    rows = []; mm = 0
    for l in open(p, encoding='utf-8', errors='replace'):
        if not l.startswith('CAMSUB'): continue
        d = dict(re.findall(r'(\w+)=([-\d.]+)', l))
        mm = max(mm, int(float(d.get('mm', 0))))
        if float(d['n']) >= 20: rows.append(d)
    drive = [d for d in rows if float(d['chase']) >= 50]   # езда: погоня считается; ходьба — только правило глаза
    use = drive if len(drive) >= 20 else [d for d in rows if float(d['safe']) >= 50]
    tot = sum(sum(float(d[k]) for k in KEYS) for d in use)
    return (tot / len(use) if use else 0.0), len(use), mm
def main():
    a = sys.argv[1:]; expect = 'pass'
    if '--expect' in a: i = a.index('--expect'); expect = a[i + 1]; del a[i:i + 2]
    tol, mx = 0.001, 0.85
    if '--tol' in a: i = a.index('--tol'); tol = float(a[i + 1]); del a[i:i + 2]
    if '--max' in a: i = a.index('--max'); mx = float(a[i + 1]); del a[i:i + 2]
    mode, old, new = a[0], a[1], a[2]
    if mode == 'equal': ok, msg = equal(old, new, tol)
    else:
        co, no, _ = cost(old); cn, nn, mm = cost(new)
        ok = no >= 20 and nn >= 20 and co > 0 and cn / co <= mx and mm == 0
        msg = 'камера %.0f -> %.0f мкс на кадр (%.0f %%), окон %d и %d, расхождений пакетных лучей %d, порог %.0f %%' % (co, cn, 100 * cn / co if co else 0, no, nn, mm, 100 * mx)
    verdict = 'PASS' if ok else 'FAIL'
    print('%s %s: %s' % (mode, verdict, msg))
    sys.exit(0 if (verdict == 'PASS') == (expect == 'pass') else 1)
main()
