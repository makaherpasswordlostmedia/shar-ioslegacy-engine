"""Проверки анимаций HUD — общие для хоста (tests/ui/anim.py) и эмулятора (tests/ui/anim_check.py).
Каждая функция -> список (ок, строка). Пороги — от правил viewer/ui_anim.h с запасом на шаг кадра."""
import statistics

# Кольцо Hit & Run — цвета и ритм ОРИГИНАЛА (правка Роба 241, замер 03.10; viewer/ui_anim.h п. 3 обязан с ними совпасть):
# заливка у близнеца tw_hnr_text (PCSX2, кадр без сжатия): красная 197,16,10 · синяя 16,28,147 · чёрная 0,0,0; жёлтая — Роб 28.09
# (ItemsCount Hud.pag 254,230,20). Период мигания 0.5 с половина на половину (запись PS2 8:58.75–9:07.75 и 25:57.7–26:14.7).
YELLOW, RED, BLUE, DARK = 0xff14e6fe, 0xff0a10c5, 0xff931c10, 0xff000000
HNR_RATE = 0.6          # доля круга в секунду (ui_anim.h UI_HNR_RATE) — правило порта (Роб, правка 5: «ровно заполняется»)
BLINK_HALF = 0.25       # полупериод мигания кольца и мигалки, с (оригинал)
WARN = 780              # предупреждение: шкала выше 78 (оракул b2_warn)


def pulse(samples):
    """samples: [(age, scale)] по кадрам с появления △. Пружина появления, перелёт, дыхание ±, период ~1 с, без рывков"""
    out = []
    if len(samples) < 20:
        return [(False, 'пульс: мало кадров (%d)' % len(samples))]
    first = [s for a, s in samples if a < 0.06]
    out.append((bool(first) and min(first) <= 0.7, 'появление с малого: масштаб в первые 0.06 с %s (<= 0.70)'
                % ('%.3f' % min(first) if first else 'нет кадров')))
    early = [s for a, s in samples if 0.05 <= a <= 0.5]
    out.append((bool(early) and max(early) >= 1.05, 'упругий перелёт: максимум 0.05..0.5 с %.3f (>= 1.05)' % (max(early) if early else 0)))
    late = [(a, s) for a, s in samples if a >= 1.0]
    if len(late) < 10:
        return out + [(False, 'дыхание: мало кадров после 1 с (%d)' % len(late))]
    ss = [s for _, s in late]
    out.append((max(ss) - min(ss) >= 0.12, 'дыхание: размах после 1 с %.3f (>= 0.12, правило ±8%%)' % (max(ss) - min(ss))))
    ups = [a1 for (a0, s0), (a1, s1) in zip(late, late[1:]) if s0 < 1.0 <= s1]
    per = statistics.mean([b - a for a, b in zip(ups, ups[1:])]) if len(ups) >= 2 else 0
    out.append((0.85 <= per <= 1.15, 'период дыхания %.3f с (1.0 ± 0.15; переходов вверх %d)' % (per, len(ups))))
    jerk = max(abs(s1 - s0) / max(a1 - a0, 1e-3) for (a0, s0), (a1, s1) in zip(late, late[1:]))
    out.append((jerk <= 0.75, 'плавно: скорость масштаба после 1 с до %.2f/с (<= 0.75)' % jerk))
    return out


def hnr(rows, tol=None):
    """rows: [(t, target, shown, light, col[, alarm])] по кадрам; alarm — полиция в игре (без столбца: target >= 1000, как у
    прежнего сценария). Ровное заполнение (правило порта) и три режима оригинала (правка 241): покой — жёлтое, мигалка не
    горит; предупреждение (выше 78, без полиции) — красное/чёрное, мигалка не горит; погоня — красное/синее на любом уровне,
    мигалка в фазе (красное кольцо — кадр 0). Ритм: полупериод 0.25 с"""
    out = []
    if len(rows) < 30:
        return [(False, 'кольцо: мало кадров (%d)' % len(rows))]
    rows = [tuple(r) + ((1 if r[1] >= 1000 else 0),) if len(r) == 5 else tuple(r) for r in rows]
    back, jump = 0, 0.0
    for (t0, g0, s0, *_), (t1, g1, s1, *_) in zip(rows, rows[1:]):
        dt = max(t1 - t0, 1e-3)
        if (s1 - s0) * (g0 - s0) < 0:
            back += 1                                         # показ ушёл против шкалы
        lim = HNR_RATE * 1000 * min(dt, 0.1) + 2
        jump = max(jump, abs(s1 - s0) - lim)
    out.append((back == 0, 'монотонно: кадров против шкалы %d (0)' % back))
    out.append((jump <= 0, 'без скачков: превышение шага %s (шаг <= %.0f%%/с · dt)' % ('%.0f' % jump if jump > 0 else 'нет', HNR_RATE * 100)))
    out.append((max(r[2] for r in rows) >= 990, 'кольцо дошло до полного: максимум %d' % max(r[2] for r in rows)))
    nm = {YELLOW: 'жёлтый', RED: 'красный', BLUE: 'синий', DARK: 'чёрный'}
    cn = lambda c: nm.get(c, '%08x' % c)
    calm = [r for r in rows if not r[5] and r[1] <= WARN]
    bad = [r for r in calm if r[4] != YELLOW or r[3] != 2]
    out.append((bool(calm) and not bad, 'покой (до 78, без полиции): жёлтое, мигалка не горит — кадров %d, чужих %d%s'
                % (len(calm), len(bad), (' (первый t=%.2f %s, мигалка %d при %d)' % (bad[0][0], cn(bad[0][4]), bad[0][3], bad[0][1])) if bad else '')))
    warn = [r for r in rows if not r[5] and r[1] > WARN]
    bad = [r for r in warn if r[4] not in (RED, DARK) or r[3] != 2]
    seen = {r[4] for r in warn}
    out.append((bool(warn) and not bad and RED in seen and DARK in seen,
                'предупреждение (выше 78, без полиции): мигает красным/чёрным, мигалка не горит — кадров %d, чужих %d%s, красный %s, чёрный %s'
                % (len(warn), len(bad), (' (первый t=%.2f %s, мигалка %d при %d)' % (bad[0][0], cn(bad[0][4]), bad[0][3], bad[0][1])) if bad else '',
                   RED in seen, DARK in seen)))
    alarm = [r for r in rows if r[5]]
    bad = [r for r in alarm if r[4] not in (RED, BLUE) or r[3] != (0 if r[4] == RED else 1)]
    seen = {r[4] for r in alarm}
    low = [r for r in alarm if r[2] < 990]
    out.append((bool(alarm) and not bad and RED in seen and BLUE in seen and bool(low) and all(r[4] in (RED, BLUE) for r in low),
                'погоня: красное/синее в фазе с мигалкой и ниже полного — кадров %d (ниже полного %d), вразнобой %d%s, красный %s, синий %s'
                % (len(alarm), len(low), len(bad), (' (первый t=%.2f %s, мигалка %d)' % (bad[0][0], cn(bad[0][4]), bad[0][3])) if bad else '',
                   RED in seen, BLUE in seen)))
    dts = sorted(b[0] - a[0] for a, b in zip(rows, rows[1:]) if b[0] > a[0])
    if tol is None:
        tol = max(0.02, 1.5 * dts[len(dts) // 2]) if dts else 0.02
    for name, part in (('предупреждение', warn), ('погоня', alarm)):
        runs, cur = [], []                                    # непрерывные серии кадров режима (разрыв > 0.1 с — новая серия)
        for r in part:
            if cur and r[0] - cur[-1][0] > 0.1:
                runs.append(cur); cur = []
            cur.append(r)
        if cur:
            runs.append(cur)
        tog, gaps = [], []
        for run in runs:
            tt = [r1[0] for r0, r1 in zip(run, run[1:]) if r1[4] != r0[4]]
            tog += tt; gaps += [b - a for a, b in zip(tt, tt[1:])]
        ok = len(gaps) >= 1 and all(abs(g - BLINK_HALF) <= tol for g in gaps)
        out.append((ok, 'ритм (%s): смен %d, промежутки %s с (%.2f ± %.3f)' % (name, len(tog), ' '.join('%.3f' % g for g in gaps[:8]) or '-', BLINK_HALF, tol)))
    return out


def arc(points, tol=3.0):
    """points: [(шкала 0..100, угол конца заливки по часовой от 12 часов, градусы)] — против замера близнецов
    (b3_chase 1400/1200/1000/820, tw_v8_stand 400: 19.25->81.25, 43.29->158.75, 67.32->233.75, 88.85->298.75, 70.56->243.75)"""
    ref = {19.25: 81.25, 43.29: 158.75, 67.32: 233.75, 70.56: 243.75, 88.85: 298.75}
    out = []
    for h, a in points:
        want = ref.get(round(h, 2))
        if want is None:
            continue
        out.append((abs(a - want) <= tol, 'дуга: шкала %.1f -> %.1f° (оригинал %.1f° ± %.0f)' % (h, a, want, tol)))
    return out or [(False, 'дуга: нет точек')]


def pop_in(samples, kind):
    """samples: [(age, scale, alpha)] с показа. kind 0 — надпись (от 0.4, перелёт), 1 — рамка задания (от 0.8)"""
    if len(samples) < 5:
        return [(False, 'всплывание: мало кадров (%d)' % len(samples))]
    s0, a0 = samples[0][1], samples[0][2]
    lo = 0.55 if kind == 0 else 0.9
    out = [(s0 <= lo or a0 <= 0.25, 'вход с малого/прозрачного: масштаб %.3f, альфа %.3f (<= %.2f или альфа <= 0.25)' % (s0, a0, lo))]
    if kind == 0:
        pk = max(s for a, s, _ in samples if a <= 0.4)
        out.append((pk >= 1.03, 'перелёт при входе %.3f (>= 1.03)' % pk))
    fin = [s for a, s, _ in samples if a >= 0.4]
    out.append((bool(fin) and all(abs(s - 1) <= 0.01 for s in fin), 'встало в 1.0 после 0.4 с: %s' % ('%.3f' % fin[-1] if fin else 'нет кадров')))
    af = [al for a, _, al in samples if a >= 0.15]
    out.append((bool(af) and min(af) >= 0.99, 'непрозрачно после 0.15 с'))
    return out


def pop_out(samples):
    """samples: [(age, alpha)] со снятия, пока рисуется. Угасание: альфа убывает, промежуточных кадров >= 2, конец <= 0.25 с"""
    if not samples:
        return [(False, 'угасание: ни одного кадра после снятия (исчезло скачком)')]
    mid = [a for _, a in samples if 0.02 < a < 0.98]
    dec = all(b <= a + 1e-3 for (_, a), (_, b) in zip(samples, samples[1:]))
    return [(len(mid) >= 2 and dec, 'угасание: промежуточных кадров %d, убывает %s' % (len(mid), dec)),
            (samples[-1][0] <= 0.25, 'угасло за %.3f с (<= 0.25)' % samples[-1][0])]


def report(title, checks):
    ok = all(c for c, _ in checks)
    lines = ['%s %s' % ('OK  ' if c else 'FAIL', m) for c, m in checks]
    return ok, '%s: %s\n  %s' % (title, 'OK' if ok else 'КРАСНОЕ', '\n  '.join(lines))
