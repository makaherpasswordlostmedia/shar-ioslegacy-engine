# Модель спуска дальности после ✕ в L3 sr3 (разбор тура 12): работа кадра = 12 + 38*(dd/250)^3 мс (подогнана под строки тура: 250 м -> 50 мс, 175 м -> 24 мс).
# Старый спуск 20 м/с и новый (до 3,5 x при превышении бюджета, DD_DOWN_K = 6 мс). Считаются секунды после ✕ и число кадров дольше 33,3 мс.
import sys
BASE, TGT, FLOOR = 250.0, 31.2, 150.0
def run(fast, secs=12.0):
    sc, avg, t, bad, last_bad = 1.0, 50.0, 0.0, 0, 0.0
    while t < secs:
        work = 12 + 38 * (sc) ** 3
        per = 1 / 30 if work <= 33.3 else (2 / 30 if work < 66.6 else 3 / 30)   # период вывода: 30 к/с, при пропуске 15 к/с и т.д.
        dt = per
        avg += (work - avg) * .08
        rate = 20.0 * (min(3.5, 1 + max(0, avg - TGT) / 6.0) if fast else 1.0)
        if avg > TGT + .3: sc -= rate * dt / BASE
        elif avg < TGT - 2.5: sc += 6.0 * dt / BASE
        sc = max(FLOOR / BASE, min(1.0, sc))
        if work > 33.3: bad += 1; last_bad = t
        t += dt
    return bad, last_bad, sc * BASE
for name, f in (('старый 20 м/с', False), ('новый до 70 м/с', True)):
    b, lb, d = run(f); print(f'{name}: кадров дольше 33,3 мс {b}, последний на {lb:.1f} с, дальность в конце {d:.0f} м')
o, n = run(False), run(True)
ok = n[0] < o[0] and n[2] >= 150 and abs(n[2] - o[2]) < 25
print('OK' if ok else 'FAIL'); sys.exit(0 if ok else 1)
