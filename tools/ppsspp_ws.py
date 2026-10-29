#!/usr/bin/env python3
"""Минимальный websocket-клиент отладчика PPSSPP (только stdlib). Использование из Python:
   c = WS(port); c.call('game.status'); c.call('gpu.record.dump'); c.close()"""
import socket, base64, os, struct, json, time


class WS:
    def __init__(self, port, host='127.0.0.1', path='/debugger', tries=60):
        for _ in range(tries):
            try:
                self.s = socket.create_connection((host, port), timeout=5); break
            except OSError:
                time.sleep(0.5)
        else:
            raise SystemExit('нет соединения с отладчиком')
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(('GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                        'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n' % (path, host, port, key)).encode())
        r = b''
        while b'\r\n\r\n' not in r: r += self.s.recv(1)
        assert b' 101 ' in r.split(b'\r\n')[0], r
        self.buf = b''; self.t = 0

    def _read(self, n):
        while len(self.buf) < n:
            c = self.s.recv(65536)
            if not c: raise EOFError
            self.buf += c
        o, self.buf = self.buf[:n], self.buf[n:]
        return o

    def send(self, obj):
        p = json.dumps(obj).encode(); m = os.urandom(4)
        h = b'\x81'
        if len(p) < 126: h += bytes([0x80 | len(p)])
        elif len(p) < 65536: h += bytes([0x80 | 126]) + struct.pack('>H', len(p))
        else: h += bytes([0x80 | 127]) + struct.pack('>Q', len(p))
        self.s.sendall(h + m + bytes(b ^ m[i % 4] for i, b in enumerate(p)))

    def recv(self, timeout=30):
        self.s.settimeout(timeout)
        msg = b''
        while True:
            b0, b1 = self._read(2)
            n = b1 & 0x7F
            if n == 126: n = struct.unpack('>H', self._read(2))[0]
            elif n == 127: n = struct.unpack('>Q', self._read(8))[0]
            pl = self._read(n)
            op = b0 & 0x0F
            if op == 9: continue
            if op == 8: raise EOFError
            msg += pl
            if b0 & 0x80:
                return json.loads(msg.decode('utf8', 'replace')) if op == 1 else msg

    def call(self, event, timeout=60, **kw):
        self.t += 1; t = self.t
        self.send(dict(event=event, ticket=str(t), **kw))
        while True:
            r = self.recv(timeout)
            if isinstance(r, dict) and r.get('ticket') == str(t): return r

    def close(self):
        try: self.s.close()
        except OSError: pass
