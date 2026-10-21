#!/bin/bash
# Гейт стенда PSPLink (этап С.1 аудита 30.09): сначала красное, потом зелёное.
#   tests/psplink/gate.sh [DIR с EBOOT, по умолчанию viewer/build]
# Красное: падающая игра (crash.txt) -> стенд обязан вернуть 10 «ВЫЛЕТ», зависшая (hang.txt) -> 11 «ЗАВИСАНИЕ ИГРЫ».
# Зелёное: обычный прогон (idle.txt) -> 0 (или 1, если провалены проверки сцен smoke_report — стенд при этом исправен).
# PSP: PSPLink запущен, кабель подключён. Итог — последняя строка вывода
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
E="${1:-$ROOT/viewer/build}"
run() { "$ROOT/tools/psplink_run.sh" --dir "$E" --label "gate-$1" "$ROOT/tests/psplink/$1.txt" > "$ROOT/build/psp-logs/.gate-$1.out" 2>&1; echo $?; }
mkdir -p "$ROOT/build/psp-logs"
c=$(run crash); echo "crash: код $c (нужно 10) · $(grep -m1 '' "$(tail -1 "$ROOT/build/psp-logs/.gate-crash.out" | sed 's/^итог: //; s#^#'"$ROOT"'/#')" 2>/dev/null)"
h=$(run hang);  echo "hang:  код $h (нужно 11) · $(grep -m1 '' "$(tail -1 "$ROOT/build/psp-logs/.gate-hang.out" | sed 's/^итог: //; s#^#'"$ROOT"'/#')" 2>/dev/null)"
i=$(run idle);  echo "idle:  код $i (нужно 0 или 1) · $(grep -m1 '' "$(tail -1 "$ROOT/build/psp-logs/.gate-idle.out" | sed 's/^итог: //; s#^#'"$ROOT"'/#')" 2>/dev/null)"
if [ "$c" = 10 ] && [ "$h" = 11 ] && { [ "$i" = 0 ] || [ "$i" = 1 ]; }; then echo "ГЕЙТ СТЕНДА: OK (вылет и зависание пойманы, обычный прогон дошёл до END)"; exit 0; fi
echo "ГЕЙТ СТЕНДА: ПРОВАЛ"; exit 1
