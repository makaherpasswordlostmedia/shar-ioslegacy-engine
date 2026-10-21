#!/usr/bin/env python3
"""Строка кода по вылету (аудит ведущего 01.10 22:35): ловушка viewer/kexc (sharexc.prx) пишет «CRASH … off_epc=… off_ra=… trace …»
хвостом blackbox.txt / blackbox_prev.txt и в crash.txt. EBOOT — PRX (ELF слинкован с нуля), поэтому смещения от базы модуля
идут в psp-addr2line как есть. ELF выпуска: build/crash/elf/<первые 8 знаков SHA-256 EBOOT>.elf (кладёт tools/ship.sh).
  python3 tools/crash_addr.py ФАЙЛ_ИЛИ_ПАПКА [--elf ELF]     # папка: crash.txt, blackbox_prev.txt, blackbox.txt
"""
import argparse, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EXC = {0: 'прерывание', 1: 'TLB mod', 2: 'TLB load', 3: 'TLB store', 4: 'адрес чтения (невыровнен/плохой)',
       5: 'адрес записи (невыровнен/плохой)', 6: 'шина команд', 7: 'шина данных', 8: 'syscall', 9: 'break (trap)',
       10: 'неизвестная команда', 11: 'сопроцессор', 12: 'переполнение', 13: 'trap', 15: 'FPU'}

def crash_line(p):
    files = [p] if p.is_file() else [p / n for n in ('crash.txt', 'blackbox_prev.txt', 'blackbox.txt', 'crash_prev.txt')]
    for f in files:
        if f.exists():
            m = [l for l in f.read_text(errors='replace').splitlines() if l.startswith('CRASH ')]
            if m: return f, m[-1]
    return None, None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('path'); ap.add_argument('--elf'); a = ap.parse_args()
    f, line = crash_line(Path(a.path))
    if not line: print('FAIL нет строки CRASH (ловушка не стояла — смотри «kexc N» в шапке ящика — или вылета не было)'); return 1
    kv = dict(re.findall(r'(\w+)=(\S+)', line.split(' trace')[0])); tr = line.split(' trace')[1].split() if ' trace' in line else []
    elf = a.elf
    if not elf:
        hd = re.search(r'EBOOT .*', (f.parent / 'blackbox.txt').read_text(errors='replace')) if (f.parent / 'blackbox.txt').exists() else None
        cands = sorted((ROOT / 'build/crash/elf').glob('*.elf'), key=lambda x: x.stat().st_mtime)
        if not cands: print('FAIL нет ELF выпуска в build/crash/elf (укажи --elf)'); return 1
        elf = str(cands[-1]); print(f'ELF: {elf} (последний; для точности укажи --elf ELF того EBOOT)')
    exc = int(kv.get('exc', '-1'))
    print(f'{f.name}: исключение {exc} ({EXC.get(exc, "?")}), поток {kv.get("thread")}, адрес ошибки {kv.get("badv")}, база {kv.get("base")}')
    a2l = str(ROOT / 'pspdev/bin/psp-addr2line')
    for name, off in [('epc', kv.get('off_epc')), ('ra', kv.get('off_ra'))] + [(f'вызов{i}', t) for i, t in enumerate(tr)]:
        if not off: continue
        out = subprocess.run([a2l, '-e', elf, '-f', '-C', '-i', '-p', '0x' + off], capture_output=True, text=True).stdout.strip()
        print(f'  {name:7} +{off}  {out}')
    return 0

if __name__ == '__main__': sys.exit(main())
