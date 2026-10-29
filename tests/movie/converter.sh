#!/bin/bash
# Гейт (а) интро: конвертер роликов tools/movie_export.py на Маке.
#   tests/movie/converter.sh [DIR]   DIR = где лежат *.smv (по умолчанию build/movies)
# 1) каждый ролик интро: кадров в SMV = заголовку RMV, звук = видео ±1 кадр, кадры JPEG 480x272 (--verify)
# 2) испорченные входы обязаны дать ошибку: RMV усечён, число кадров в заголовке +1, нет конца последнего кадра IPU,
#    SMV чужого ролика под этим именем, байт заголовка SMV, байт индекса SMV, громкий хвост звука за концом видео
# Красное: tests/movie/converter.sh DIR_С_ЧУЖИМИ_ФАЙЛАМИ (например, radlogo.smv = копия gracie.smv) -> FAIL.
set -u; cd "$(dirname "$0")/../.."
DIR="${1:-build/movies}"; PY=.venv/bin/python; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fail=0; ok() { echo "  ok   $1"; }; bad() { echo "  FAIL $1"; fail=1; }
for c in vuglogo foxlogo gracie radlogo intro; do
  if out=$($PY tools/movie_export.py --verify "$DIR/$c.smv" 2>&1); then ok "$out"; else bad "$c: $out"; fi
done
R=hit-and-run-web/source/game/movies/radlogo.rmv
head -c 1000000 "$R" > "$T/trunc.rmv"
$PY - "$R" "$T" <<'EOF'
import sys, struct
from pathlib import Path
d = bytearray(Path(sys.argv[1]).read_bytes()); t = Path(sys.argv[2])
f = bytearray(d); struct.pack_into('<I', f, 12, struct.unpack_from('<I', f, 12)[0] + 1); (t / 'frames.rmv').write_bytes(f)
f = bytearray(d); s = struct.unpack_from('<I', f, 20)[0]; o = min(struct.unpack_from('<4I', f, 28))
e = f.rfind(b'\0\0\1\xb0', s, o); f[e:e + 4] = b'\0\0\1\xb1'; (t / 'noend.rmv').write_bytes(f)
EOF
for b in trunc frames noend; do
  if $PY tools/movie_export.py --check-rmv "$T/$b.rmv" >/dev/null 2>&1; then bad "испорченный RMV ($b) принят"; else ok "испорченный RMV ($b) отвергнут"; fi
done
cp "$DIR/gracie.smv" "$T/radlogo.smv"
if $PY tools/movie_export.py --verify "$T/radlogo.smv" >/dev/null 2>&1; then bad "чужой SMV принят"; else ok "чужой SMV отвергнут"; fi
for at in 30 200; do   # 30 — поле кадров заголовка (crc), 200 — индекс (crc индекса)
  cp "$DIR/radlogo.smv" "$T/radlogo.smv"; printf '\x55' | dd of="$T/radlogo.smv" bs=1 seek=$at conv=notrunc 2>/dev/null
  if $PY tools/movie_export.py --verify "$T/radlogo.smv" >/dev/null 2>&1; then bad "битый SMV (байт $at) принят"; else ok "битый SMV (байт $at) отвергнут"; fi
done
if $PY -c "
import sys, numpy as np; sys.path.insert(0, 'tools'); import movie_export as m
pcm = np.full((m.SPF * 30, 2), 7, np.int16); pcm[m.SPF * 25:] = 3000   # 20 кадров видео, звук на 10 кадров длиннее и громкий (без цифровой тишины: хвост не отделён)
try: m.fit_audio(pcm, 20, 'loud'); sys.exit(1)
except m.RmvError: pass
pcm[m.SPF * 20:] = 0; m.fit_audio(pcm, 20, 'quiet')                  # тот же хвост в тишине — отрезается
"; then ok "громкий хвост звука отвергнут, тихий отрезан"; else bad "проверка хвоста звука"; fi
[ $fail = 0 ] && echo "movie converter: PASS" || echo "movie converter: FAIL"
exit $fail
