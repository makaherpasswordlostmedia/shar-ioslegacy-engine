#!/bin/bash
# Физические боты по всем семи уровням: круг за кругом до заданного времени. Только процессор Мака:
# без эмулятора, звука, окон, AI и сети; PSP не трогает. Находки — TSV autoexplore (уровень x y z тип вес seed кадр описание).
#
#   tools/cartest/bots_loop.sh --minutes 10            # пробный
#   tools/cartest/bots_loop.sh --until 07:00           # до ближайших 07:00 (caffeinate снаружи: caffeinate -ims tools/cartest/bots_loop.sh ...)
#   --levels 1,3,5     только эти уровни (по умолчанию 1..7)
#   --cars 128         машин в рое (2..1024)           --seconds 120   игровых секунд на один уровень за круг
#   --jobs 3           сколько уровней считать одновременно (под nice 10; Мак бывает занят другими окнами)
#   --seed N           начало нумерации seed (по умолчанию из даты; круг R, уровень L берёт N + R*100 + L)
#   --cap 6            не больше стольких строк на место (8 м) и тип; счётчик «всего» в журнале считает все
#   --out DIR          куда писать (по умолчанию build/autoexplore/<ГГГГММДД-ЧЧММ>-bots)
# Данные: BOT_SET (по умолчанию ~/Downloads/shar-psp/build/botset: level.shr и lN/level.shr — набор, который лежит на PSP),
#         BOT_ROADS (~/Downloads/shar-psp/build/sandbox: roads-lN.bin). Игровые данные никуда не копируются и не публикуются.
# Результат: <out>/findings/bots_L<ур>_s<seed>.tsv, <out>/ЖУРНАЛ.md (строка на уровень за круг), <out>/ОТЧЁТ_БОТЫ.md (после каждого круга).
# Время — только из date. Стоп: до срока, при свободном месте меньше 10 ГиБ, по файлу <out>/STOP или сигналу (отчёт всё равно пишется).
set -u
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
MINUTES=; UNTIL=; LEVELS="1 2 3 4 5 6 7"; CARS=128; SECS=120; JOBS=3; SEED0=; CAP=6; OUT=
BOT_SET=${BOT_SET:-$HOME/Downloads/shar-psp/build/botset}; BOT_ROADS=${BOT_ROADS:-$HOME/Downloads/shar-psp/build/sandbox}
usage() { sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-2}"; }
while [ $# -gt 0 ]; do
  case "$1" in
    --minutes) MINUTES=$2; shift 2;; --until) UNTIL=$2; shift 2;; --levels) LEVELS=$(echo "$2" | tr ',' ' '); shift 2;;
    --cars) CARS=$2; shift 2;; --seconds) SECS=$2; shift 2;; --jobs) JOBS=$2; shift 2;; --seed) SEED0=$2; shift 2;;
    --cap) CAP=$2; shift 2;; --out) OUT=$2; shift 2;; -h|--help) usage 0;; *) echo "неизвестный аргумент: $1" >&2; usage;;
  esac
done
[ -n "$MINUTES$UNTIL" ] || { echo "нужен срок: --minutes N или --until ЧЧ:ММ" >&2; usage; }
NOW=$(date +%s)
if [ -n "$MINUTES" ]; then DEADLINE=$((NOW + MINUTES * 60))
else DEADLINE=$(python3 -I - "$UNTIL" <<'E'
import sys, datetime as dt
h, m = map(int, sys.argv[1].split(':')); n = dt.datetime.now(); t = n.replace(hour=h, minute=m, second=0, microsecond=0)
print(int((t if t > n else t + dt.timedelta(days=1)).timestamp()))
E
); fi
STAMP=$(date +%Y%m%d-%H%M)
[ -n "$SEED0" ] || SEED0=$(( $(date +%j | sed 's/^0*//') * 10000 + $(date +%H%M | sed 's/^0*//') ))
OUT=${OUT:-$ROOT/build/autoexplore/$STAMP-bots}; FIND=$OUT/findings; BIN=$OUT/bin/bots_swarm; mkdir -p "$FIND" "$OUT/bin" "$OUT/runs"
JR=$OUT/ЖУРНАЛ.md; LOCK=$ROOT/build/autoexplore/bots.lock; mkdir -p "$ROOT/build/autoexplore"
say() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/loop.log"; }
if ! mkdir "$LOCK" 2>/dev/null; then
  if kill -0 "$(cat "$LOCK/pid" 2>/dev/null)" 2>/dev/null; then echo "уже идёт другой прогон (pid $(cat "$LOCK/pid")): $LOCK" >&2; exit 3; fi
  rm -rf "$LOCK"; mkdir "$LOCK"
fi
echo $$ > "$LOCK/pid"
CHILD=; finish() { [ -n "$CHILD" ] && kill $CHILD 2>/dev/null; wait 2>/dev/null; python3 -I "$HERE/bots_report.py" "$OUT" >/dev/null 2>&1; rm -rf "$LOCK"; }
trap 'say "сигнал: останавливаюсь, отчёт допишется"; STOPPED=1' INT TERM; trap finish EXIT; STOPPED=0

# сборка: те же правила физики, что в игре (viewer/car.c, col.c, props.c, stateprops.c, coins.c текущего дерева)
say "сборка роя из $ROOT"
cc -std=c99 -O2 -w "$HERE/bots_swarm.c" "$ROOT/viewer/car.c" "$ROOT/viewer/col.c" "$ROOT/viewer/props.c" "$ROOT/viewer/stateprops.c" "$ROOT/viewer/coins.c" -lm -o "$BIN" \
  || { say "СБОРКА НЕ УДАЛАСЬ"; exit 1; }
# уровни и дороги
LV=; for n in $LEVELS; do
  if [ "$n" = 1 ]; then f=$BOT_SET/level.shr; else f=$BOT_SET/l$n/level.shr; fi
  r=$BOT_ROADS/roads-l$n.bin
  if [ -f "$f" ] && [ -f "$r" ]; then LV="$LV $n"; else say "L$n пропущен: нет $( [ -f "$f" ] || echo "$f" ) $( [ -f "$r" ] || echo "$r" )"; fi
done
[ -n "$LV" ] || { say "нет ни одного уровня"; exit 1; }
python3 -I - "$OUT" "$ROOT" "$BOT_SET" "$BOT_ROADS" "$CARS" "$SECS" "$JOBS" "$SEED0" "$DEADLINE" $LV <<'E'
import sys, json, hashlib, subprocess, os, time
out, root, bset, rd, cars, secs, jobs, seed0, dl = sys.argv[1:10]; lv = sys.argv[10:]
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:12]
def git(*a):
    try: return subprocess.check_output(['git', '-C', root, *a], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception: return ''
files = {}
for n in lv:
    f = f'{bset}/level.shr' if n == '1' else f'{bset}/l{n}/level.shr'
    files[n] = dict(level=f, mtime=time.strftime('%d.%m %H:%M', time.localtime(os.path.getmtime(f))), sha=sha(f), roads=f'{rd}/roads-l{n}.bin', roadsSha=sha(f'{rd}/roads-l{n}.bin'))
json.dump(dict(started=time.strftime('%d.%m.%Y %H:%M:%S'), deadline=time.strftime('%d.%m.%Y %H:%M:%S', time.localtime(int(dl))), cars=int(cars), seconds=int(secs), jobs=int(jobs), seed0=int(seed0),
               head=git('rev-parse', '--short', 'HEAD') or (open(f'{root}/.src_head').read().strip() if os.path.exists(f'{root}/.src_head') else ''), branch=git('branch', '--show-current') or 'render-perf (выгрузка)', dirty=bool(git('status', '--porcelain', '--', 'viewer', 'tools/cartest')), levels=files),
          open(f'{out}/manifest.json', 'w'), ensure_ascii=False, indent=1)
E
{ echo "# Журнал ботов $STAMP"; echo; echo "срок до $(date -r "$DEADLINE" '+%d.%m %H:%M:%S'), уровни:$LV, машин $CARS, $SECS игровых с на уровень за круг, одновременно $JOBS, seed от $SEED0"; echo; \
  echo "| время | круг | уровень | кадров | сек | находок записано/всего (тип) |"; echo "|---|---|---|---|---|---|"; } > "$JR"
say "до $(date -r "$DEADLINE" '+%H:%M:%S'), уровни:$LV, машин $CARS, $SECS с, одновременно $JOBS, seed от $SEED0 → $OUT"

run_one() {   # круг, уровень
  local R=$1 n=$2 seed f r
  seed=$((SEED0 + R * 100 + n))
  if [ "$n" = 1 ]; then f=$BOT_SET/level.shr; else f=$BOT_SET/l$n/level.shr; fi; r=$BOT_ROADS/roads-l$n.bin
  nice -n 10 "$BIN" --level "$f" --lvl "$n" --roads "$r" --out "$FIND/bots_L${n}_s${seed}.tsv" --cars "$CARS" --seed "$seed" --seconds "$SECS" --until "$DEADLINE" --cap "$CAP" \
    > /dev/null 2> "$OUT/runs/L${n}_s${seed}.log"
  local code=$? line; line=$(tail -n 1 "$OUT/runs/L${n}_s${seed}.log")
  local ticks sec kinds
  ticks=$(echo "$line" | sed -n 's/.*ticks=\([0-9]*\).*/\1/p'); sec=$(echo "$line" | sed -n 's/.*wall=\([0-9.]*\)s.*/\1/p'); kinds=$(echo "$line" | sed 's/^[^|]*| *//')
  [ "$code" = 0 ] || kinds="КОД $code: $line"
  printf '| %s | %s | L%s | %s | %s | %s |\n' "$(date +%H:%M:%S)" "$R" "$n" "${ticks:-—}" "${sec:-—}" "$kinds" >> "$JR"
}

R=0
while :; do
  R=$((R + 1)); [ "$(date +%s)" -lt "$DEADLINE" ] || break
  free=$(df -k "$OUT" | awk 'NR==2{print $4}'); if [ "${free:-0}" -lt $((10 * 1024 * 1024)) ]; then say "свободного места меньше 10 ГиБ — стоп"; break; fi
  [ -e "$OUT/STOP" ] && { say "найден STOP — стоп"; break; }
  [ "$STOPPED" = 1 ] && break
  say "круг $R"
  set -- $LV; while [ $# -gt 0 ]; do
    CHILD=; k=0
    while [ $k -lt "$JOBS" ] && [ $# -gt 0 ]; do
      [ "$(date +%s)" -lt "$DEADLINE" ] && { run_one "$R" "$1" & CHILD="$CHILD $!"; }
      shift; k=$((k + 1))
    done
    wait; CHILD=
  done
  python3 -I "$HERE/bots_report.py" "$OUT" >/dev/null 2>&1 || say "отчёт не собрался"
  say "круг $R готов; находок строк: $(cat "$FIND"/*.tsv 2>/dev/null | grep -vc '^#')"
done
say "стоп: кругов $((R - 1)) (последний мог быть неполным)"
