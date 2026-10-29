#!/bin/bash
# Гейт правки 259 (03.10: замер-тур на PSP вставал 5 раз из 5 в первом кадре камеры миссии m0): старт миссий, пока Гомер в
# комнате. Безголовый эмулятор (~/.claude/skills/shar-level-polish/scripts/scen.py): вход в дом Симпсонов, точка sh_path1,
# служебный «flag msn» (как NEW GAME). Зелёный:
#   (1) в smoke.txt «ROOM ev=msnstart room=SimpsonsHouse» — старт вывел из комнаты;
#   (2) после MSNSTART строки HOMER — room=- и высота не ниже -2 м (Гомер на земле у дома, не падает сквозь пол);
#   (3) в trace.txt первый кадр камеры миссии — «TRC frame inR=0», город нарисован («TRC city nd=N», N > 0).
#   (4) «TRC cam … proj=1 view=1» — матрицы кадра, ушедшие в видеочип, конечные.
# Красный 1: «flag msnoldroom 1» (старт миссий, не выходя из комнаты, — как до правки) обязан упасть по (1)–(3), а камера кадра
#   при этом под защитой: (4) зелёный и есть строка «GEGUARD cam» — защита поймала FOV 0 и взгляд строго вниз.
# Красный 2: «flag msnoldroom 1» + «flag camguardoff 1» (и комната, и камера как до правки) обязан упасть по (4): в видеочип
#   ушли матрицы с NaN/бесконечностью — то, на чём PSP вставала в турах 1–5
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/gates/msn_from_room; mkdir -p "$OUT"; PY=.venv/bin/python; SCEN=~/.claude/skills/shar-level-polish/scripts/scen.py
EB="${EBOOT:-$ROOT/viewer/build/EBOOT.PBP}"
mk() {   # $1, $2 — служебные флаги или пусто
  printf '%s\n' 'scene start' 'wait 3' 'scene house_door' 'foot 228.94 180.5 0 3.83' 'wait 3' 'press up 0.3' 'press circle 0.3' 'wait 1' \
    'press triangle' 'wait 2' 'scene sh_path1' 'foot 500.316 398.080 0 -17.40' 'wait 3' 'scene msn_from_room' 'flag trace 1' ${1:+"$1"} ${2:+"$2"} 'flag player' 'wait 2' \
    'flag msn' 'wait 6' 'end'
}
check() {   # $1 — папка прогона -> 0 зелёный
  local d="$1" bad=0
  grep -q 'ROOM ev=enter room=SimpsonsHouse' "$d/smoke.txt" || { echo "  в дом не вошли — прогон не проверяет правку"; return 2; }
  grep -q 'ROOM ev=msnstart room=SimpsonsHouse' "$d/smoke.txt" || { echo "  старт миссий не вывел из комнаты (нет ROOM ev=msnstart)"; bad=1; }
  local after; after=$(sed -n '/^MSNSTART /,$p' "$d/smoke.txt" | grep '^HOMER ')
  [ -n "$after" ] || { echo "  после MSNSTART нет строк HOMER"; bad=1; }
  local inroom; inroom=$(printf '%s\n' "$after" | grep -c -v 'room=- ')
  [ "$inroom" -eq 0 ] || { echo "  после старта миссий Гомер числится в комнате: $inroom строк ($(printf '%s\n' "$after" | grep -v 'room=- ' | head -1 | cut -c1-90))"; bad=1; }
  local low; low=$(printf '%s\n' "$after" | sed -E 's/.*pos=[-0-9.]+,([-0-9.]+),.*/\1/' | awk '$1 < -2 {n++} END{print n+0}')
  [ "$low" -eq 0 ] || { echo "  Гомер ниже -2 м после старта (падает сквозь пол): $low строк"; bad=1; }
  local fr; fr=$(grep -m1 '^TRC frame' "$d/trace.txt" 2>/dev/null)
  case "$fr" in *"inR=0 "*) ;; *) echo "  первый кадр камеры миссии не в городе: ${fr:-нет строки TRC frame}"; bad=1;; esac
  local nd; nd=$(grep -m1 '^TRC city nd=' "$d/trace.txt" 2>/dev/null | sed -E 's/TRC city nd=([0-9]+).*/\1/')
  [ "${nd:-0}" -gt 0 ] || { echo "  в первом кадре город пуст (nd=${nd:-нет})"; bad=1; }
  echo "  первый кадр: ${fr:0:110}; кусков города ${nd:-0}; строк HOMER после старта $(printf '%s\n' "$after" | grep -c .)"
  return $bad
}
cam() {   # $1 — папка прогона -> 0: матрицы первого кадра камеры миссии конечные
  local c; c=$(grep -m1 '^TRC cam ' "$1/trace.txt" 2>/dev/null)
  echo "  камера первого кадра: ${c:-нет строки TRC cam}"
  case "$c" in *"proj=1 view=1"*) return 0;; *) return 1;; esac
}
run() { mk "$2" "${3:-}" > "$OUT/$1.txt"; SCEN_EBOOT="$EB" SCEN_HOME="$ROOT/$OUT/home_$1" "$PY" "$SCEN" "msnroom_$1" "$OUT/$1.txt" > "$OUT/$1_run.txt" 2>&1; }
run old 'flag msnoldroom 1'; run noguard 'flag msnoldroom 1' 'flag camguardoff 1'; run new ''
F=build/twins/scen/full; red=0
check $F/msnroom_old > "$OUT/red.txt"; rc=$?
if [ $rc -eq 1 ]; then echo "красный 1 (msnoldroom): комната — упал, как должен"; red=$((red + 1)); else echo "КРАСНЫЙ 1 НЕ ПОЙМАН (rc $rc):"; fi; cat "$OUT/red.txt"
if cam $F/msnroom_old && grep -q '^GEGUARD cam ' $F/msnroom_old/smoke.txt; then echo "  защита камеры в красном 1 сработала: $(grep -m1 '^GEGUARD cam ' $F/msnroom_old/smoke.txt | cut -c1-100)"; red=$((red + 1))
else echo "  ЗАЩИТА КАМЕРЫ НЕ СРАБОТАЛА в красном 1"; fi
if cam $F/msnroom_noguard; then echo "КРАСНЫЙ 2 НЕ ПОЙМАН: без защиты камеры матрицы конечные — проверка (4) ничего не доказывает"
else echo "красный 2 (msnoldroom + camguardoff): в видеочип ушли матрицы с NaN — упал, как должен"; red=$((red + 1)); fi
[ $red -eq 3 ] && red=1 || red=0
if check $F/msnroom_new > "$OUT/green.txt" && cam $F/msnroom_new >> "$OUT/green.txt"; then echo "зелёный: старт миссий из комнаты — в городе, Гомер на земле"; cat "$OUT/green.txt"
  [ $red -eq 1 ] && { echo PASS; exit 0; }; echo FAIL; exit 1
else echo "FAIL:"; cat "$OUT/green.txt"; exit 1; fi
