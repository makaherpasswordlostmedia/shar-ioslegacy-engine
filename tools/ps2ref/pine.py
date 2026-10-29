#!/usr/bin/env python3
"""Клиент PINE для PCSX2 (станок С2): чтение/запись памяти EE, сохранить/загрузить состояние по слоту, статус, название игры.
Только собственные профили: PS2REF_SLOT=28121..28123, по умолчанию 28121; личный слот 28011 запрещён.
Протокол: запрос = u32 длина (вместе с собой) + u8 код + аргументы (little-endian); ответ = u32 длина + u8 итог (0 — ок) + данные.
  python3 tools/ps2ref/pine.py status            версия, статус, игра
  python3 tools/ps2ref/pine.py read ADDR [N]     N байт с адреса (hex)
Библиотекой: from pine import Pine; p = Pine(); p.r32(addr), p.rf(addr), p.read(addr, n), p.load(slot);
запись (О3): p.w8/w16/w32/w64(addr, v), p.wf(addr, float); сокет закрывать всегда: p.close() (убитый клиент роняет PCSX2)."""
import os, socket, struct, sys, time

MSG = dict(r8=0, r16=1, r32=2, r64=3, w8=4, w16=5, w32=6, w64=7, version=8, save=9, load=0xA, title=0xB, id=0xC, uuid=0xD, gamever=0xE, status=0xF)
STATUS = {0: 'идёт', 1: 'пауза', 2: 'выключен'}


class Pine:
    def __init__(self, slot=None, timeout=5.0):
        slot = int(os.environ.get('PS2REF_SLOT', '28121')) if slot is None else slot
        if slot not in (28121, 28122, 28123):
            raise ValueError('only isolated observer PINE slots 28121..28123 are allowed')
        tmp = os.environ.get('TMPDIR', '/tmp')
        path = os.path.join(tmp, 'pcsx2.sock') if slot == 28011 else os.path.join(tmp, 'pcsx2.sock.%d' % slot)
        self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); self.s.settimeout(timeout); self.s.connect(path)

    def _recv(self, n):
        b = b''
        while len(b) < n:
            c = self.s.recv(n - len(b))
            if not c: raise ConnectionError('PINE: сокет закрыт')
            b += c
        return b

    def call(self, code, args=b''):
        self.s.sendall(struct.pack('<IB', 5 + len(args), code) + args)
        n, = struct.unpack('<I', self._recv(4)); body = self._recv(n - 4)
        if body[0] != 0: raise IOError('PINE: отказ на код %d' % code)
        return body[1:]

    def batch(self, calls):   # несколько чтений одним пакетом (одна точка во времени эмуляции, насколько даёт PCSX2)
        req = b''.join(struct.pack('<B', c) + a for c, a in calls)
        self.s.sendall(struct.pack('<I', 4 + len(req)) + req)
        n, = struct.unpack('<I', self._recv(4)); body = self._recv(n - 4)
        if body[0] != 0: raise IOError('PINE: отказ в пакете')
        return body[1:]

    def read(self, addr, n):   # по 8 байт одним пакетом
        calls = [(MSG['r64'], struct.pack('<I', addr + k)) for k in range(0, n, 8)]
        out = b''
        for i in range(0, len(calls), 256): out += self.batch(calls[i:i + 256])
        return out[:n]

    def r32(self, a): return struct.unpack('<I', self.call(MSG['r32'], struct.pack('<I', a)))[0]
    def rf(self, a): return struct.unpack('<f', self.call(MSG['r32'], struct.pack('<I', a)))[0]
    def w8(self, a, v): self.call(MSG['w8'], struct.pack('<IB', a, v & 0xFF))
    def w16(self, a, v): self.call(MSG['w16'], struct.pack('<IH', a, v & 0xFFFF))
    def w32(self, a, v): self.call(MSG['w32'], struct.pack('<II', a, v & 0xFFFFFFFF))
    def w64(self, a, v): self.call(MSG['w64'], struct.pack('<IQ', a, v & 0xFFFFFFFFFFFFFFFF))
    def wf(self, a, x): self.w32(a, struct.unpack('<I', struct.pack('<f', x))[0])   # float через w32 (О3)
    def close(self): self.s.close()
    def string(self, code): d = self.call(code); n, = struct.unpack('<I', d[:4]); return d[4:4 + n].rstrip(b'\0').decode('utf-8', 'replace')
    def version(self): return self.string(MSG['version'])
    def title(self): return self.string(MSG['title'])
    def gameid(self): return self.string(MSG['id'])
    def status(self): return STATUS.get(struct.unpack('<I', self.call(MSG['status']))[0], '?')
    def save(self, slot): self.call(MSG['save'], struct.pack('<B', slot))
    def load(self, slot): self.call(MSG['load'], struct.pack('<B', slot))


def main():
    a = sys.argv[1:] or ['status']; p = Pine()
    if a[0] == 'status': print('PINE:', p.version(), '|', p.status(), '|', p.title(), p.gameid())
    elif a[0] == 'read': d = p.read(int(a[1], 16), int(a[2]) if len(a) > 2 else 64); print(d.hex(' ', 4))
    return 0


if __name__ == '__main__':
    sys.exit(main())
