#!/bin/sh
# Сборка cartest на Маке: build/cartest (-O2) и build/cartest_dbg (-O2 + ASan/UBSan).
# Плюс проверка, что viewer/col.c и viewer/car.c собираются для PSP (psp-gcc -O2 -c), если есть pspdev.
set -e
D=$(cd "$(dirname "$0")" && pwd); R=$(cd "$D/../.." && pwd); B="$D/build"; mkdir -p "$B"
W="-std=c99 -Wall -Wextra -Wshadow -Wno-unused-parameter"
WL="$W -Wdouble-promotion"          # col.c/car.c: всё во float (у PSP одинарная точность)
for v in rel dbg; do
  if [ $v = rel ]; then F="-O2"; O="$B/cartest"; else F="-O2 -g -fsanitize=address,undefined -fno-omit-frame-pointer"; O="$B/cartest_dbg"; fi
  cc $WL $F -c "$R/viewer/col.c" -o "$B/col.$v.o"
  cc $WL $F -c "$R/viewer/car.c" -o "$B/car.$v.o"
  cc $W $F -o "$O" "$D/cartest.c" "$B/col.$v.o" "$B/car.$v.o" -lm
done
if [ -x "$R/pspdev/bin/psp-gcc" ]; then
  for f in col car; do
    PSPDEV="$R/pspdev" PATH="$R/pspdev/bin:$PATH" psp-gcc -std=c99 -O2 -G0 $WL -c "$R/viewer/$f.c" -o "$B/$f.psp.o"
  done
  echo "psp-gcc -O2: col.c $(wc -c < "$B/col.psp.o" | tr -d ' ') B, car.c $(wc -c < "$B/car.psp.o" | tr -d ' ') B of objects"
fi
echo "built $B/cartest $B/cartest_dbg"
cc $W -O2 -g -DCOL_DEBUG -o "$B/cartest_trace" "$D/cartest.c" "$R/viewer/col.c" "$R/viewer/car.c" -lm
cc $W -O0 -g -DCOL_DEBUG -o "$B/probe" "$D/probe.c" "$R/viewer/col.c" "$R/viewer/car.c" -lm
cc $W -O2 -o "$B/bench" "$D/bench.c" "$B/col.rel.o" "$B/car.rel.o" -lm
cc $W -O2 -DCOL_DEBUG -o "$B/bench_count" "$D/bench.c" "$R/viewer/col.c" "$R/viewer/car.c" -lm
# feel: метрики ощущения на искусственном полигоне — новая машина и старая (car_v9.c) для сравнения
cc $W -O2 -I"$R/viewer" -o "$B/feel" "$D/feel.c" "$R/viewer/col.c" "$R/viewer/car.c" -lm
if [ -f "$R/viewer/car_v9.c" ]; then
  mkdir -p "$B/v9"; cp "$R/viewer/car_v9.c" "$B/v9/car.c"; cp "$R/viewer/car_v9.h" "$B/v9/car.h"; cp "$R/viewer/col.h" "$B/v9/col.h"
  cc $W -O2 -DV9 -I"$B/v9" -o "$B/feel_v9" "$D/feel.c" "$R/viewer/col.c" "$B/v9/car.c" -lm
fi
