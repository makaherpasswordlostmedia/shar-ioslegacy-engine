#!/usr/bin/env python3
"""Запись ввода PCSX2 (.p2m2) из нашего сценария (станок С2): ввод клипа — файлом, не нажатиями в окно.
Формат PCSX2 2.x (Recording/InputRecordingFile): заголовок 561 байт (u8 версия 1, эмулятор 50, автор 255, игра 255), u32 кадров,
u32 откатов, u8 «старт из сохранения»; дальше на кадр 2 порта × 18 байт: 2 байта кнопок (0 — нажата; первый: SELECT L3 R3 START
UP RIGHT DOWN LEFT с младшего бита, второй: L2 R2 L1 R1 △ ○ ✕ □), стики RX RY LX LY (0–255, 127 центр), 12 байт силы нажатия
(→ ← ↑ ↓ △ ○ ✕ □ L1 R1 L2 R2). Старт из сохранения: рядом файл <имя>.p2m2_SaveState.p2s (его грузит сам PCSX2).
  python3 tools/ps2ref/p2m2.py OUT.p2m2 SCRIPT [--state STATE.p2s]
SCRIPT: строки «кадров кнопки [lx ly]», кнопки через +: x o s t (✕ ○ □ △) l1 r1 l2 r2 up down left right start select или -;
lx ly — стик от -1 до 1 (вправо/вниз +)."""
import shutil, struct, sys
from pathlib import Path

D1 = dict(select=0, l3=1, r3=2, start=3, up=4, right=5, down=6, left=7)
D2 = dict(l2=0, r2=1, l1=2, r1=3, t=4, o=5, x=6, s=7)
PRESS = ['right', 'left', 'up', 'down', 't', 'o', 'x', 's', 'l1', 'r1', 'l2', 'r2']


def pad(buttons, lx=0.0, ly=0.0):
    b1 = b2 = 0xFF
    for b in buttons:
        if b in D1: b1 &= ~(1 << D1[b])
        elif b in D2: b2 &= ~(1 << D2[b])
        else: raise ValueError('кнопка %r' % b)
    st = lambda v: 127 if v == 0 else max(0, min(255, int(round(127.5 + v * 127.5))))
    return bytes([b1 & 0xFF, b2 & 0xFF, 127, 127, st(lx), st(ly)] + [255 if k in buttons else 0 for k in PRESS])


IDLE = pad([])


def write(out, frames, game='The Simpsons - Hit & Run', state=None):
    """frames: список 18-байтовых состояний порта 1 (порт 2 пустой)."""
    h = struct.pack('<B50s255s255s', 1, b'PCSX2-2.6.3', b'shar-psp tools/ps2ref/p2m2.py', game.encode())
    body = b''.join(f + IDLE for f in frames)
    Path(out).write_bytes(h + struct.pack('<IIB', len(frames), 0, 1 if state else 0) + body)
    if state: shutil.copy(state, str(out) + '_SaveState.p2s')


def parse(text):
    fr = []
    for l in text.splitlines():
        l = l.split('#')[0].split()
        if not l: continue
        n, bs = int(l[0]), [] if l[1] == '-' else l[1].split('+')
        lx, ly = (float(l[2]), float(l[3])) if len(l) >= 4 else (0.0, 0.0)
        fr += [pad(bs, lx, ly)] * n
    return fr


def main():
    a = sys.argv[1:]
    if len(a) < 2: print(__doc__); return 2
    st = a[a.index('--state') + 1] if '--state' in a else None
    fr = parse(Path(a[1]).read_text()); write(a[0], fr, state=st)
    print(a[0], len(fr), 'кадров', '(из сохранения %s)' % st if st else '')
    return 0


if __name__ == '__main__':
    sys.exit(main())
