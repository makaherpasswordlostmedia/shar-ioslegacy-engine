#!/bin/bash
# Гейт защиты от кэша карты ARK-4 (правки 252/259): tests/msio/host.c — модель общего кэша по смещению, два потока, два файла.
# Красный: -DMSIO_OLD (прямое чтение) обязан поймать чужие байты; зелёный: viewer/msio.c — ноль.
set -u; cd "$(dirname "$0")/../.."; mkdir -p build/msio
cc -std=c99 -O1 -Wall -pthread -DMSIO_OLD tests/msio/host.c -o build/msio/host_old || exit 2
cc -std=c99 -O1 -Wall -pthread tests/msio/host.c -o build/msio/host || exit 2
red=0; if build/msio/host_old > build/msio/red.txt; then echo "КРАСНЫЙ НЕ ПОЙМАН: прямое чтение без чужих байтов ($(head -1 build/msio/red.txt))"
else echo "красный (MSIO_OLD): $(head -1 build/msio/red.txt)"; red=1; fi
if build/msio/host > build/msio/green.txt; then echo "зелёный: $(head -1 build/msio/green.txt)"; g=1; else echo "НЕ ЗЕЛЁНЫЙ: $(head -1 build/msio/green.txt)"; g=0; fi
# №741: вложенная запись журнала из чтения (кадр экрана загрузки) — прежний замок (MSIO_NEST_OLD) виснет, новый проходит
cc -std=c99 -O1 -Wall -pthread -DMSIO_NEST_OLD=1 tests/msio/host.c -o build/msio/host_nest_old || exit 2
nr=0; if build/msio/host nest > build/msio/nest.txt; then echo "зелёный №741: $(head -1 build/msio/nest.txt)"; ng=1; else echo "НЕ ЗЕЛЁНЫЙ №741: $(head -1 build/msio/nest.txt)"; ng=0; fi
if build/msio/host_nest_old nest > build/msio/nest_old.txt; then echo "КРАСНЫЙ №741 НЕ ПОЙМАН: $(head -1 build/msio/nest_old.txt)"; else echo "красный №741 (MSIO_NEST_OLD): $(head -1 build/msio/nest_old.txt)"; nr=1; fi
[ $red = 1 ] && [ $g = 1 ] && [ $ng = 1 ] && [ $nr = 1 ] && { echo "PASS"; exit 0; }; echo "FAIL"; exit 1
