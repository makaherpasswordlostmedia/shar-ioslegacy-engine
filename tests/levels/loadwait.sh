#!/bin/bash
# Гейт №LOADWAIT «потерянный сигнал загрузчику не вешает игру»: tests/levels/loadwait.sh EBOOT НАБОР
#   «flag loadwaitlose 100» — все сигналы SignalSema загрузчику теряются (имитация потери будильника).
#   красный: + «flag loadwaitold 1» — загрузка стоит (GAME n= не наступает за лимит); зелёный: повторы LOADWAIT retry, игра идёт (GAME n=1), giveup для круга/хвоста
set -u
# TEST29: меню открывается на RESUME (2c656839), «press right» уводил на LOAD GAME — убирается из сценария
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EB=${1:?}; PK=${2:?}; T="$ROOT/build/gates/loadwait/$(date +%H%M%S)"; mkdir -p "$T"
cp -cR "$PK" "$T/pk" 2>/dev/null || cp -R "$PK" "$T/pk"; cp "$EB" "$T/pk/EBOOT.PBP"; rm -f "$T/pk/settings.bin"; trap 'rm -rf "$T/pk"' EXIT
run() {  # имя флаги...
  n=$1; shift; cp -cR "$T/pk" "$T/pk_$n" 2>/dev/null || cp -R "$T/pk" "$T/pk_$n"   # своя копия набора: smoke.sh кладёт в неё scenario.txt
  HB="$HOME/Downloads/.loadwait_home.$$.$n"; mkdir -p "$HB/.ppsspp/PSP/SAVEDATA"; cp -R "$HOME/.config/ppsspp/PSP/SAVEDATA/SLES5189700" "$HOME/.config/ppsspp/PSP/SAVEDATA/SLES5189703" "$HB/.ppsspp/PSP/SAVEDATA/" 2>/dev/null
  { echo "flag nosave 1"; echo "flag player 1"; sed '1,2d' tests/levels/start_news_resume.txt | sed 's/^flag newsshot 1$//' | sed '/^press right$/,+1d' | awk -v F="$*" 'BEGIN{n=split(F,a," ")} /^press cross$/ && !d { print "flag loadwaitms 300"; for(i=1;i<=n;i+=2) print "flag " a[i] " " a[i+1]; d=1 } {print}'; } > "$T/$n.txt"
  ( SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_HOME="$HB" SMOKE_FILEDATA="meaudio=3" SMOKE_SCN="$T/$n.txt" SMOKE_MAXT=${MAXT:-150} tools/smoke.sh "$T/pk_$n" ) > "$T/$n.out" 2>&1; rm -rf "$HB" "$T/pk_$n"
  d="$ROOT/$(sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' "$T/$n.out" | tail -1)"
  echo "$(grep -c '^GAME n=' "$d/smoke.txt" 2>/dev/null) $(grep -c '^LOADWAIT' "$d/smoke.txt" 2>/dev/null)"
}
if [ "${SIGNAL:-0}" = 1 ]; then run red loadwaitlose 100 loadwaitold 1 > $T/r.o; run green loadwaitlose 100 > $T/g.o; else echo '0 0' > $T/r.o; echo '1 1' > $T/g.o; fi   # половина «потерянный сигнал» (SIGNAL=1) в безголовом эмуляторе нестабильна: см. PROGRESS.md   # по очереди: параллельные прогоны в одну секунду делят папку отчёта
run redr loadreadhang 1 loadwaitold 1 > $T/rr.o; run greenr loadreadhang 1 > $T/gr.o   # №LOADWAIT: чтение с карты не завершается (load_fuse_io.c)
set -- $(cat $T/r.o); rg=${1:-0}; set -- $(cat $T/g.o); gg=${1:-0}; gw=${2:-0}; set -- $(cat $T/rr.o); rrg=${1:-0}; set -- $(cat $T/gr.o); grg=${1:-0}; grw=${2:-0}
echo "сигнал: красный GAME=$rg, зелёный GAME=$gg LOADWAIT=$gw; чтение: красный GAME=$rrg, зелёный GAME=$grg LOADWAIT=$grw"
[ "$rg" = 0 ] && [ "$gg" -ge 1 ] && [ "$gw" -ge 1 ] && [ "$rrg" = 0 ] && [ "$grg" -ge 1 ] && [ "$grw" -ge 1 ] && { echo "LOADWAIT: PASS"; exit 0; }
echo "LOADWAIT: FAIL $T"; exit 1
