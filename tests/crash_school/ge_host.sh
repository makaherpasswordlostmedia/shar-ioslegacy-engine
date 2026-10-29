#!/bin/bash
# Гейт правки 103 (повтор 01.10, «спортивная площадка у школы»): 3D после города (персонажи — skinDraw, пропы гонок и значки миссий —
# msnart) укладывается в бюджет списка GE, конец кадра — внутри массива list. На Маке, без эмулятора: настоящие viewer/skin.c и
# viewer/msnart.c с заглушками pspsdk (tests/crash_school/stub), данные диска — build/chars, build/msnart.shr. Разбор — ge_host.c.
#   tests/crash_school/ge_host.sh            зелёный: рабочая копия (обязан пройти)
#   tests/crash_school/ge_host.sh --old REF  красный: те же файлы из git REF (по умолчанию HEAD — код до правки) обязаны упасть
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
REF=""; [ "${1:-}" = --old ] && REF="${2:-HEAD}"
T="build/crash_school/ge_host${REF:+_old}"; rm -rf "$T"; mkdir -p "$T/src"
for f in skin.c skin.h msnart.c msnart.h blackbox.h main.c main_state.h gevb.c gevb.h camnear.h levlight.h; do
  if [ -n "$REF" ]; then git show "$REF:viewer/$f" > "$T/src/$f" 2>/dev/null || rm -f "$T/src/$f"
  else cp "viewer/$f" "$T/src/$f"; fi
done
ARR=$(python3 - "$T/src/main.c" "$T/src/main_state.h" <<'PY'   # длина массива list этой версии main.c, КБ (выражение с #define и sizeof)
import re, sys
s = ''.join(open(a, encoding='utf-8').read() for a in sys.argv[1:] if __import__('os').path.exists(a))   # list теперь в main_state.h
e = re.search(r'unsigned int __attribute__\(\(aligned\(64\)\)\) list\[([^\]]+)\];', s).group(1).replace('sizeof(unsigned int)', '4')
for _ in range(4):
    for k in set(re.findall(r'[A-Z_]{3,}', e)):
        m = re.search(r'#define ' + k + r' (\([^\n]*?\)|\S+)', s)
        if m: e = e.replace(k, m.group(1))
print(int(eval(e.replace('u', ''))) * 4 >> 10)
PY
)
cc -std=c11 -O2 -w -I "$T/src" -I tests/crash_school/stub tests/crash_school/ge_host.c "$T/src/skin.c" "$T/src/msnart.c" "$T/src/gevb.c" -lm \
   -o "$T/ge_host" 2> "$T/build.txt" || { echo "FAIL сборка (${REF:-рабочая копия}): $(head -3 "$T/build.txt")"; exit 2; }
echo "версия: ${REF:-рабочая копия} (массив list $ARR КБ)"
"$T/ge_host" build "$ARR"
