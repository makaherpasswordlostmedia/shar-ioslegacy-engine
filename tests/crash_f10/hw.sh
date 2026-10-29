#!/bin/bash
# Правка 252 (03.10): зависание ВСЕЙ PSP у особняка L1 F10-4/F10-5 после съезда с 12–13 м (01.10 22:26 и 03.10 15:06; звук
# пропал, сторож молчит, ловушки sharexc тогда ещё не было), эмулятор не повторяет. Гейт в эмуляторе-проверяльщике «как железо»
# (tools/twins/ppsspp_hwcheck_build.sh): он ловит то, что PPSSPP прощает, а PSP — нет (ловушки FPU, невыровненный доступ,
# плохой адрес, break, дно стека).
#  A route  — путь F10 (route_hw.txt: целая и разбитая на посадке): ни одного такого места; до END; BOOM/EJECT/CARBOOM
#  B trap   — красный контроль правила FPU: служебный файл fputrap (прежнее: ловушки V/Z/O как у PSP) + HW_TRAP=1 — «flag fpeprobe»
#             (0/0 в главном потоке) останавливает игру (HWTRAP FPE_V), как встала бы PSP
#  C keep   — новое (viewer/fpuguard.h): без fputrap та же проба — игра до END, случай в smoke.txt и ящике («FPE … V:m»)
# tests/crash_f10/hw.sh [EBOOT]   EBOOT по умолчанию viewer/build/EBOOT.PBP. FPU_GATE_OLD=1 — шаг C тоже с fputrap (красный: FAIL)
# HW_ROUTE=0 — без шага A (он ~3–4 мин интерпретатора). Выход 0 — зелёный.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EB="$(cd "$(dirname "${1:-viewer/build/EBOOT.PBP}")" && pwd)/$(basename "${1:-viewer/build/EBOOT.PBP}")"
[ -f "$EB" ] || { echo "FAIL: нет $EB"; exit 2; }
PY="${PY:-python3}"; H="${SCEN_HOME:-$ROOT/build/crash_f10/home}"; mkdir -p "$H"
run() {   # имя сценарий [переменные…] -> папка прогона (нет проверяльщика или прогона — пустая строка, шаг FAIL)
  local nm=$1 sc=$2; shift 2
  local d; d=$(env SCEN_ROOT="$ROOT" SCEN_HOME="$H" SCEN_EBOOT="$EB" "$@" "$PY" tests/crash_f10/hw_run.py "$nm" "$sc" 2>"$H/$nm.err" | tail -1)
  [ -d "$d" ] && echo "$d" || { echo "FAIL: прогон $nm не состоялся: $(tail -1 "$H/$nm.err")" >&2; echo /nonexistent; }
}
fail=0
if [ "${HW_ROUTE:-1}" != 0 ]; then
  d=$(run f10hw_route tests/crash_f10/route_hw.txt); "$PY" tests/crash_f10/hw_check.py route "$d" || fail=1
fi
d=$(run f10hw_trap tests/crash_f10/fpe_probe.txt SCEN_OVERRIDE=fputrap=/dev/null HW_TRAP=1 HW_TIMEOUT=600)
"$PY" tests/crash_f10/hw_check.py trap "$d" || fail=1
if [ "${FPU_GATE_OLD:-0}" = 1 ]; then k=(SCEN_OVERRIDE=fputrap=/dev/null); else k=(); fi
d=$(run f10hw_keep tests/crash_f10/fpe_probe.txt ${k[@]+"${k[@]}"} HW_TRAP=1 HW_TIMEOUT=600)
"$PY" tests/crash_f10/hw_check.py keep "$d" || fail=1
echo "crash_f10/hw: $([ $fail = 0 ] && echo PASS || echo FAIL) (EBOOT $(shasum -a 256 "$EB" | cut -c1-8))"
exit $fail
