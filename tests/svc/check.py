#!/usr/bin/env python3
"""Разбор прогона tests/svc/scenario.txt (tools/smoke.sh): правки Роба 42 и 44.

    python tests/svc/check.py build/smoke/<время>

Зелёный, если в режиме игрока (строка «SVC mode svc=0»):
  L+R+△   — обычный △: Гомер вышел из машины (CARV №2 onfoot=1), служебного полёта нет (нигде fly=1)
  R+SELECT — служебный счётчик не включился (нигде hud=1); SELECT в машине — RESET CAR (строка «SVC reset select»)
  ○        — тормоз и задний ход, как в раскладке оригинала: после газа X скорость v1 > 3 м/с, после 2 с ○ — v2 < 1 м/с
Причина провала — первой строкой, код 1."""
import sys
from pathlib import Path


def kv(line):
    return dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)


def main():
    out = Path(sys.argv[1]); log = (out / 'smoke.txt').read_text().splitlines()
    fails, notes = [], []
    mode = [kv(l) for l in log if l.startswith('SVC mode')]
    if not mode: fails.append('нет строки «SVC mode» (движок не знает flag player — старая сборка?)')
    elif mode[0].get('svc') != '0': fails.append(f"режим не игрока: svc={mode[0].get('svc')}")
    st = [kv(l) for l in log if l.startswith('SVC state')]
    if any(s.get('fly') == '1' for s in st): fails.append('служебный полёт включился (L+R+△ у игрока)')
    if any(s.get('hud') == '1' for s in st): fails.append('служебный счётчик включился (R+SELECT у игрока)')
    if not any(l.startswith('SVC reset select') for l in log): fails.append('SELECT в машине не сделал RESET CAR (раскладка оригинала)')
    cv = [kv(l) for l in log if l.startswith('CARV')]
    notes.append('CARV: ' + '; '.join(f"v={c.get('v')} пешком={c.get('onfoot')} полёт={c.get('fly')}" for c in cv))
    if len(cv) < 5: fails.append(f'строк CARV {len(cv)} из 5 (сценарий не дошёл)')
    else:
        if cv[0].get('onfoot') != '0': fails.append('старт не за рулём')
        if cv[1].get('onfoot') != '1' or cv[1].get('fly') != '0': fails.append(f"L+R+△ не вывел Гомера из машины как обычный △ (onfoot={cv[1].get('onfoot')} fly={cv[1].get('fly')})")
        if cv[2].get('onfoot') != '0': fails.append('△ не посадил Гомера обратно')
        v1, v2 = float(cv[3]['v']), float(cv[4]['v'])
        if v1 <= 3.0: fails.append(f'газ X не разогнал машину (v1 {v1:.2f} м/с)')
        elif v2 >= 1.0: fails.append(f'○ не тормозит: после газа {v1:.2f} м/с, после 2 с ○ {v2:.2f} м/с')
    print('FAIL: ' + fails[0] if fails else 'PASS: режим игрока без служебных кнопок; ○ — тормоз/назад; SELECT — RESET CAR')
    for f in fails[1:]: print('  ещё: ' + f)
    for n in notes: print('  ' + n)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
