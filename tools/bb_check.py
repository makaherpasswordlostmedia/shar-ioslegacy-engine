#!/usr/bin/env python3
"""Гейт строки чёрного ящика (viewer/main.c bbSample): правка 139(1) — строка несёт трафик «trf <машин> park <нарисовано>/<проснулось>
ped <пешеходов>»; правка 103 (01.10, самописец) — этап миссии, моделей персонажей и машин миссии, КБ рисунков msnart, кадров за
бюджетом GE и последнее действие с возрастом («msn %s mdl %d car %d art %u over %u  op %s %.1f»). Строка с худшими значениями обязана
влезать в кольцо bbRing (иначе snprintf обрежет хвост и «\\n» пропадёт), шапка файла — в буфер h функции bbCompose, а шапка и всё
кольцо — в файл фиксированной длины BB_FILE.

Формат и размеры читаются из исходника; строка собирается python-форматом с шириной полей C (%6.0f, %-7s, %u...).
  python3 tools/bb_check.py                    # viewer/main.c
  python3 tools/bb_check.py --src FILE         # другой исходник (красный контроль: main.c до правки)
  python3 tools/bb_check.py --ring 240         # подменить длину строки кольца (красный контроль: прежние 240 Б)
"""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[1]/"tools"))
from main_source import read_main
import argparse, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def define(src, name):
    m = re.search(r'#define ' + name + r' \(?([^)\n/]+)\)?', src)
    if not m: return None
    expr = m.group(1).strip()
    for k in re.findall(r'[A-Z_]+', expr):
        v = define(src, k)
        if v is None: return None
        expr = expr.replace(k, str(v))
    try: return int(eval(expr, {}, {}))
    except Exception: return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--src', default=str(ROOT / 'viewer/main.c')); ap.add_argument('--ring', type=int)
    a = ap.parse_args(); src = read_main(Path(a.src))
    m = re.search(r'static char bbRing\[BB_N\]\[(\w+)\]', src)
    ring = a.ring or (int(m.group(1)) if m and m.group(1).isdigit() else (define(src, m.group(1)) if m else 0)) or 0
    body = src[src.index('static void bbSample('):]; body = body[:body.index('\n}\n')]
    call = body[body.index('snprintf(s, sizeof bbRing[0],'):]
    fmt = ''.join(re.findall(r'"((?:[^"\\]|\\.)*)"', call[:call.index('\\n"') + 3]))
    fmt = fmt.replace('\\n', '\n')
    bad = 0
    if not re.search(r'trf %d park %d/%d ped %d', fmt): print('FAIL в строке нет полей «trf %d park %d/%d ped %d»'); bad += 1
    if not re.search(r'msn %s mdl %d car %d art %u over %u  op %s %\.1f', fmt):
        print('FAIL в строке нет полей самописца «msn %s mdl %d car %d art %u over %u  op %s %.1f» (правка 103)'); bad += 1
    # худшие значения: 5 знаков времени, код места 23 знака (pc[24]), координаты 5 знаков, счётчики 5 знаков, этап миссии 15 (bbMsn[16]),
    # действие 39 (bbOpS[40]), возраст 999.0, все экраны
    worst = {'f': [99999., -9999., -999., -9999., 31.99, 31.99, 999.0],
             's': ['MEMFAIL', 'K9-7-ABCDEFGHIJKLMNOPQRS', 'sr3.10.10-ABCDE', 'npc+ ' + 'X' * 34, 'foot ', 'room ', 'phone ', 'shop ', 'msncars'],
             'd': [7, 999, 999, 5, 93, 93, 99, 4, 6], 'u': [100, 99999, 99999, 99999, 99999, 99999, 4294967295]}
    it = {k: iter(v) for k, v in worst.items()}
    def sub(mm):
        spec, conv = mm.group(1), mm.group(2)
        if conv == '%': return '%'
        v = next(it['f' if conv == 'f' else 's' if conv == 's' else 'd' if conv == 'd' else 'u'], 0)
        return ('%' + spec + ('d' if conv == 'u' else conv)) % v
    line = re.sub(r'%([-0-9.]*)([fsdu%])', sub, fmt)
    need = len(line.encode('utf-8')) + 1
    print(f'кольцо {ring} Б, худшая строка {need} Б:\n  {line.rstrip()}')
    if need > ring: print(f'FAIL строка {need} Б не влезает в кольцо {ring} Б'); bad += 1
    # шапка файла (bbCompose; до правки 103 — bbWrite): подпись колонок не должна обрезаться
    fn = 'static int bbCompose(' if 'static int bbCompose(' in src else 'static void bbWrite('
    w = src[src.index(fn):]; w = w[:w.index('\n}\n')]
    hm = re.search(r'char h\[(\d+)\]', w); hcall = w[w.index('snprintf(h, sizeof h,'):]; hcall = hcall[:hcall.index(', head,')]
    hfmt = ''.join(re.findall(r'"((?:[^"\\]|\\.)*)"', hcall)).replace('\\n', '\n')
    hline = (hfmt.replace('%s', 'EXIT', 1).replace('%u', '99999', 1).replace('%.0f', '99999', 1)
             .replace('%s', 'Oct  1 2026', 1).replace('%s', '23:59:59', 1))
    hneed = len(hline.encode('utf-8')) + 1; hsize = int(hm.group(1)) if hm else 0
    print(f'шапка {hsize} Б, нужно {hneed} Б')
    if hneed > hsize: print(f'FAIL шапка {hneed} Б не влезает в {hsize} Б'); bad += 1
    n, f = define(src, 'BB_N'), define(src, 'BB_FILE')
    if f is not None and n is not None:   # самописец: файл фиксированной длины — шапка и всё кольцо худшими строками
        print(f'файл {f} Б, нужно {hneed - 1 + n * (need - 1) + 1} Б (шапка + {n} строк)')
        if hneed - 1 + n * (need - 1) + 1 > f: print('FAIL шапка и кольцо не влезают в файл BB_FILE'); bad += 1
    # Сторож «bbdog» (правка 103, повтор 01.10): есть, выше главного потока (0x20) по приоритету, пишет ящик без printf (dtoa
    # берёт кучу — главный поток мог встать, держа её замок), файл «STALL» при старте уходит в blackbox_prev.txt, кадры считаются
    # во всех местах, где меняются буферы экрана
    if 'bbDogThread' not in src:
        print('FAIL нет сторожа bbDogThread (ящик при зависании пишется только раз в минуту / на событии)'); bad += 1
    else:
        pm = re.search(r'sceKernelCreateThread\("bbdog", bbDogThread, (0x[0-9a-fA-F]+|\d+|[A-Z_]+),', src)
        pr = (int(pm.group(1), 0) if pm.group(1)[0].isdigit() else (define(src, pm.group(1)) or 999)) if pm else 999   # 04.10: приоритет именем (BB_DOG_PRI)
        print(f'сторож: приоритет {pr:#x} (главный поток 0x20)')
        if pr >= 0x20: print('FAIL сторож не выше главного потока по приоритету — при бесконечном цикле не проснётся'); bad += 1
        dw = src[src.index('static void bbDogWrite('):]; dw = dw[:dw.index('\n}\n')]
        if re.search(r'\b(s?n?printf|vsnprintf)\s*\(', dw): print('FAIL bbDogWrite зовёт printf (куча: dtoa)'); bad += 1
        boot = src[src.index('static void blackBoxBoot('):]; boot = boot[:boot.index('\n}\n')]
        if '"STA"' not in boot: print('FAIL blackBoxBoot не сохраняет ящик STALL в blackbox_prev.txt'); bad += 1
        if re.search(r'=\s*sceGuSwapBuffers\(\)', src): print('FAIL кадр показан мимо swapBuf — сторож его не видит'); bad += 1
        # шапка STALL худшими значениями + всё кольцо — в файл
        sh = ('STALL n=4294967295 ms=4294967295 phase=19 traffic3d beat=4294967295 op=' + 'X' * 39 + ' list=4194303K last=4194303K '
              'heap=4194303K msn=' + 'Y' * 15 + ' EBOOT Oct  1 2026 23:59:59\n')
        if f is not None and n is not None:
            print(f'файл STALL: шапка {len(sh)} Б + {n} строк -> {len(sh) + n * (need - 1) + 1} Б из {f}')
            if len(sh) + n * (need - 1) + 1 > f: print('FAIL шапка STALL и кольцо не влезают в BB_FILE'); bad += 1
    print(f'RESULT {"PASS" if not bad else "FAIL"}'); return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
