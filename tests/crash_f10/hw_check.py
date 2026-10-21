#!/usr/bin/env python3
"""Правка 252: разбор прогона эмулятора-проверяльщика (tests/crash_f10/hw_run.py). hw_check.py РЕЖИМ ПАПКА
  route — путь F10: до END, съезд (large_car_crash F10-5), разбитая на посадке (BOOM, EJECT, CARBOOM), и НИ ОДНОГО места, где
          PSP упала бы, а PPSSPP молчит (HWSUM: FPE_*, NAN_IN, UNALIGNED, BADADDR, BREAK, STACKOVF = 0; модуль ядра sharexc
          в счёт не идёт — KMEM), сторож не видел стоянок на проходах F10 (нет BBSTALL после первой сцены f10hw)
  trap  — красный контроль правила FPU: файл fputrap (прежнее) + HW_TRAP=1 -> игра остановлена на 0/0 (HWTRAP FPE_V, нет END)
  keep  — новое правило FPU: игра до END, FPEPROBE выполнен, в smoke.txt «FPE … V…:m» (случай записан, PSP не встала)
Выход 0 — ожидание выполнено."""
import re, sys
from pathlib import Path
mode, d = sys.argv[1], Path(sys.argv[2])
smk = (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''
hw = (d / 'hwchk.txt').read_text(errors='replace') if (d / 'hwchk.txt').exists() else ''
end = bool(re.search(r'^END$', smk, re.M))
summ = re.search(r'^HWSUM (.*)$', hw, re.M)
cnt = {k: int(v) for k, v in re.findall(r'(\w+)=\d+/(\d+)', summ.group(1))} if summ else {}
trap = re.findall(r'^HWTRAP .*$', hw, re.M)
sites = [l for l in hw.splitlines() if l.startswith('HWCHK ') and 'KMEM' not in l and 'start' not in l]
stack = re.findall(r'^HWSTACK thread=(\S+) size=(\d+) used=(\d+)', hw, re.M)
bad, info = [], []
if mode == 'route':
    if not end: bad.append('сценарий не дошёл до END')
    if not summ: bad.append('нет HWSUM (проверяльщик не отработал)')
    hot = {k: v for k, v in cnt.items() if k != 'KMEM' and v}
    if hot: bad.append('места, где PSP упала бы: ' + ', '.join(f'{k} {v}' for k, v in hot.items()) + ' | ' + ' | '.join(s[:150] for s in sites[:3]))
    land = len(re.findall(r'^SFX large_car_crash crash .* L1 F10-[45]$', smk, re.M))
    if land < 2: bad.append(f'посадок на газон F10-4/5 с ударом {land} из 2')
    for ev in ('BOOM', 'EJECT', 'CARBOOM'):
        if not re.search(rf'^{ev} ', smk, re.M): bad.append(f'нет {ev} (разбитая на посадке)')
    m0 = re.search(r'^SCENE f10hw', smk, re.M)   # стоянки пролога (старт m0: служебный след 259 пишет карту по кускам) не в счёт
    if m0 and re.search(r'^BBSTALL', smk[m0.start():], re.M): bad.append('сторож видел стоянку главного потока на проходах F10')
    info.append(f'посадок {land}, BOOM/EJECT/CARBOOM есть' if not bad else '')
    calls = re.search(r'calls fpu3=(\d+) fpu2=(\d+) cmp=(\d+) mem=(\d+)', hw)
    if calls: info.append(f'операций FPU {int(calls.group(1)) + int(calls.group(2)) + int(calls.group(3)):,}, обращений к памяти {int(calls.group(4)):,}'.replace(',', ' '))
    if stack: info.append('стек: ' + ', '.join(f'{n} {int(u) // 1024}/{int(s) // 1024} КБ' for n, s, u in stack if int(u) > 2048))
elif mode == 'trap':
    if end: bad.append('игра дошла до END — ловушка FPU не сработала')
    if not any('FPE_V' in t for t in trap): bad.append('нет HWTRAP FPE_V (0/0 на ловушке)')
    info.append(trap[0][:140] if trap else '')
elif mode == 'keep':
    if not end: bad.append('сценарий не дошёл до END (игра встала)')
    if trap: bad.append('проверяльщик остановил игру: ' + trap[0][:120])
    if not re.search(r'^FPEPROBE .*keep=0', smk, re.M): bad.append('нет FPEPROBE keep=0 (проба не выполнена)')
    fpe = re.search(r'^FPE t=[\d.]+ (V\S*:\S*m\S*)', smk, re.M)
    if not fpe: bad.append('в smoke.txt нет «FPE … V…:m» — случай не записан')
    else: info.append('записано: FPE ' + fpe.group(1))
print(f'{mode}: ' + ('PASS' if not bad else 'FAIL') + (' — ' + '; '.join(x for x in info if x) if info and not bad else ''))
for b in bad: print('  -', b)
sys.exit(1 if bad else 0)
