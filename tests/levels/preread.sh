#!/bin/bash
# Гейт №PREREAD: резидентную часть level.shr читает загрузчик, пока газета влетает (раньше 0,9 с мёртвого времени до чтения). Байты буфера = файл (сумма по словам), состояние после загрузки (LEVEL ev=load / GAME без ms/heap)
# и порядок фаз LOADPH те же, GAME не длиннее. Красный: файл prereadold (читает главный) — строки PREREAD start нет, use=0. Сценарий — tests/levels/ab_pfetch_on.txt (RESUME, запись Роба только на чтение).
#   tests/levels/preread.sh EBOOT НАБОР      цифры мс эмулятора — ориентир (чтение из кэша ОС), итог по железу
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EB=${1:?EBOOT.PBP}; PK=${2:?НАБОР}; T="$ROOT/build/gates/preread/$(date +%H%M%S)"; mkdir -p "$T"
P="$T/pk"; cp -cR "$PK" "$P" 2>/dev/null || cp -R "$PK" "$P"; cp "$EB" "$P/EBOOT.PBP"; trap 'rm -rf "$P"' EXIT
one() { ( SMOKE_FLAGS="$2" SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_FILEDATA="meaudio=3" SMOKE_SCN="$ROOT/tests/levels/ab_pfetch_on.txt" SMOKE_MAXT=${MAXT:-200} tools/smoke.sh "$P" ) > "$T/$1.out" 2>&1
  D="$ROOT/$(sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' "$T/$1.out" | tail -1)"; echo "$D" > "$T/$1.dir"
  grep -E '^(LEVEL ev=load|GAME n=)' "$D/smoke.txt" | sed -E 's/ ms=[0-9]+//; s/ heap0?=[0-9]+//g; s/ t=[0-9.]+//' > "$T/$1.state"
  grep -E '^LOADPH ' "$D/smoke.txt" | awk '{print $2}' > "$T/$1.phases"; }
one red prereadold; one green ""; one sum prereadsum    # sum: те же условия + служебная сумма буфера (считает 10 МБ — в замер времени не входит)
python3 - "$T" "$P/level.shr" <<'PY'
import sys, struct, re
from pathlib import Path
T = Path(sys.argv[1]); lvl = Path(sys.argv[2]); ok = True; out = []
def lines(n): return (Path((T / (n + '.dir')).read_text().strip()) / 'smoke.txt').read_text(errors='replace').splitlines()
g, r, sm = lines('green'), lines('red'), lines('sum')
if not any(l.startswith('PREREAD start') for l in g): ok = False; out.append('ЗЕЛЁНЫЙ: PREREAD start нет')
u = [l for l in g if l.startswith('PREREAD use=')]
if not u or 'use=1' not in u[0]: ok = False; out.append('ЗЕЛЁНЫЙ: PREREAD use=1 нет: ' + (u[0] if u else '-'))
else: out.append('зелёный: ' + u[0])
if any(l.startswith('PREREAD start') for l in r) or any('use=1' in l for l in r if l.startswith('PREREAD use=')): ok = False; out.append('КРАСНЫЙ: PREREAD есть при prereadold')
s = [l for l in sm if l.startswith('PREREAD sum')]
if not s: ok = False; out.append('сумма буфера не залогирована')
else:
    m = re.search(r'off=(\d+) size=(\d+) sum=([0-9a-f]{8})', s[0]); off, size, got = int(m[1]), int(m[2]), m[3]
    b = lvl.read_bytes()[off:off + size]; h = 0x811C9DC5; n4 = len(b) // 4 * 4
    for w in struct.unpack('<%dI' % (n4 // 4), b[:n4]): h = ((h ^ w) * 0x01000193) & 0xffffffff
    for c in b[n4:]: h = ((h ^ c) * 0x01000193) & 0xffffffff
    if '%08x' % h != got: ok = False; out.append('БАЙТЫ НЕ СОВПАЛИ: буфер %s, файл %08x' % (got, h))
    else: out.append('байты: буфер == файл [%d..%d), сумма %s' % (off, off + size, got))
if (T / 'green.state').read_text() != (T / 'red.state').read_text(): ok = False; out.append('СОСТОЯНИЕ после загрузки не совпало')
if (T / 'green.phases').read_text() != (T / 'red.phases').read_text(): ok = False; out.append('порядок фаз LOADPH не совпал')
def gm(L): return int(next(re.search(r' ms=(\d+)', l)[1] for l in L if l.startswith('GAME n=')))
a, b = gm(r), gm(g); out.append('GAME: прежнее %d мс, предчтение %d мс (%+d)' % (a, b, b - a))
if b > a + 50: ok = False; out.append('GAME стал длиннее > 50 мс')
print('\n'.join(out)); print('PREREAD-ГЕЙТ: ' + ('PASS' if ok else 'FAIL')); sys.exit(0 if ok else 1)
PY
