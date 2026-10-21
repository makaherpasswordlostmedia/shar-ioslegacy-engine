#!/bin/bash
# Гейт №PFETCH: traffic.shr и fx.shr читает загрузчик в фоне следом за COL1/PRP2; разбор на прежнем месте. Данные те же байты (сумма FNV по словам буфера = сумма файла), состояние после загрузки то же,
# порядок фаз LOADPH тот же; GAME не длиннее. Красный: файл pfetchold (читают сами) — строк PFETCH нет. Сценарий — tests/levels/start_news_resume.txt (RESUME, запись Роба только на чтение).
#   tests/levels/pfetch.sh EBOOT НАБОР      цифры мс эмулятора — ориентир (читает из кэша ОС), итог по железу
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EB=${1:?EBOOT.PBP}; PK=${2:?НАБОР}; T="$ROOT/build/gates/pfetch/$(date +%H%M%S)"; mkdir -p "$T"
P="$T/pk"; cp -cR "$PK" "$P" 2>/dev/null || cp -R "$PK" "$P"; cp "$EB" "$P/EBOOT.PBP"; trap 'rm -rf "$P"' EXIT
one() { ( SMOKE_FLAGS="$2" SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_FILEDATA="meaudio=3" SMOKE_SCN="$ROOT/tests/levels/start_news_resume.txt" SMOKE_MAXT=${MAXT:-200} tools/smoke.sh "$P" ) > "$T/$1.out" 2>&1
  D="$ROOT/$(sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' "$T/$1.out" | tail -1)"; echo "$D" > "$T/$1.dir"
  grep -E '^(LEVEL ev=load|GAME n=)' "$D/smoke.txt" | sed -E 's/ ms=[0-9]+//; s/ heap0?=[0-9]+//g; s/ t=[0-9.]+//' > "$T/$1.state"
  grep -E '^LOADPH ' "$D/smoke.txt" | awk '{print $2}' > "$T/$1.phases"; }
one red pfetchold; one green ""
python3 - "$T" "$ROOT/build/n663/pk" <<'PY'
import sys, struct, re
from pathlib import Path
T = Path(sys.argv[1]); pk = Path(sys.argv[2]); ok = True; out = []
def lines(n): return (Path((T / (n + '.dir')).read_text().strip()) / 'smoke.txt').read_text(errors='replace').splitlines()
g, r = lines('green'), lines('red')
take = [l for l in g if l.startswith('PFETCH take')]
for key, f in (('traffic.shr', pk / 'traffic.shr'), ('fx.shr', pk / 'fx.shr')):
    m = [l for l in take if 'key=%s ' % key in l]
    b = f.read_bytes(); h = 0x811C9DC5; n4 = len(b) // 4 * 4
    for w in struct.unpack('<%dI' % (n4 // 4), b[:n4]): h = ((h ^ w) * 0x01000193) & 0xffffffff
    for c in b[n4:]: h = ((h ^ c) * 0x01000193) & 0xffffffff
    want = '%08x' % h
    if not m or 'hit=1' not in m[0] or 'crc=' + want not in m[0] or 'size=%d ' % f.stat().st_size not in m[0]: ok = False; out.append('НЕТ/НЕ ТОТ ' + key + ': ' + (m[0] if m else 'строки нет'))
    else: out.append('%s: hit, sum %s == файл, %s' % (key, want, re.search(r'wait_ms=\d+', m[0])[0]))
if any(l.startswith('PFETCH') for l in r): ok = False; out.append('КРАСНЫЙ: PFETCH есть при pfetchold')
if (T / 'green.state').read_text() != (T / 'red.state').read_text(): ok = False; out.append('СОСТОЯНИЕ после загрузки не совпало (LEVEL/GAME без ms/heap)')
if (T / 'green.phases').read_text() != (T / 'red.phases').read_text(): ok = False; out.append('порядок фаз LOADPH не совпал')
def gm(L): return int(next(re.search(r' ms=(\d+)', l)[1] for l in L if l.startswith('GAME n=')))
a, b = gm(r), gm(g); out.append('GAME: прежнее %d мс, фоном %d мс (%+d)' % (a, b, b - a))
if b > a + 50: ok = False; out.append('GAME стал длиннее > 50 мс')
print('\n'.join(out)); print('PFETCH-ГЕЙТ: ' + ('PASS' if ok else 'FAIL')); sys.exit(0 if ok else 1)
PY
