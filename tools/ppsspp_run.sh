#!/bin/bash
# Очередь на эмулятор PPSSPP для всех сессий и агентов на этом Маке: одно окно за раз.
#   tools/ppsspp_run.sh EBOOT WAIT [OUT.png] [доп. аргументы PPSSPP]
#     WAIT: число секунд, или путь к файлу, появления которого ждать (например bench.txt; максимум 15 мин)
#     OUT.png: снимок ТОЛЬКО окна этого эмулятора (не всего экрана)
#   PPSSPP_SHOTS=smoke.txt PPSSPP_SHOTDIR=dir — режим сценария (см. tools/smoke.sh): WAIT = максимум секунд,
#     снимки по строкам "SHOT имя" (после снимка — файл shot_имя.ok рядом, движок его ждёт), выход по строке "END"
# Ждёт, пока освободится общий замок /tmp/ppsspp.lock И пока не закроются все чужие окна PPSSPP
# (в том числе запущенные вручную или без этого скрипта), потом запускает, снимает, закрывает только своё по PID.
LOCK=/tmp/ppsspp.lock
EBOOT="$1"; WAIT="$2"; OUT="$3"; shift 3 2>/dev/null || shift $#
HERE="$(cd "$(dirname "$0")" && pwd)"
T0=$(date +%s)
while :; do
  if mkdir "$LOCK" 2>/dev/null; then
    echo $$ > "$LOCK/pid"
    if ! pgrep -x PPSSPPSDL >/dev/null; then break; fi
    rm -rf "$LOCK"
  elif [ -f "$LOCK/pid" ] && ! kill -0 "$(cat "$LOCK/pid" 2>/dev/null)" 2>/dev/null; then
    rm -rf "$LOCK"; continue                                   # замок от умершего процесса
  fi
  if [ $(( $(date +%s) - T0 )) -gt 1200 ]; then echo "ppsspp_run: эмулятор занят больше 20 минут, пропускаю" >&2; exit 2; fi
  sleep 2
done
trap 'rm -rf "$LOCK"' EXIT
# без звука (Роб 03.10: «тесты на фоне без звука»): SDL — пустой аудиодрайвер; PPSSPP_SOUND=1 — со звуком (послушать вручную)
AUD=dummy; [ -n "${PPSSPP_SOUND:-}" ] && AUD=coreaudio
SDL_AUDIODRIVER=$AUD /Applications/PPSSPPSDL.app/Contents/MacOS/PPSSPPSDL --windowed "$@" "$EBOOT" >/dev/null 2>&1 &
PID=$!
if [ -n "${PPSSPP_SHOTS:-}" ]; then
  # режим сценария (tools/smoke.sh): WAIT = максимум секунд; следим за файлом PPSSPP_SHOTS (smoke.txt движка):
  # строка "SHOT имя" -> снимок окна в PPSSPP_SHOTDIR/имя.png, строка "END" -> конец
  W=""; done_shots=0
  for i in $(seq 1 $(( ${WAIT:-120} * 4 ))); do
    kill -0 $PID 2>/dev/null || break
    if [ -f "$PPSSPP_SHOTS" ]; then
      n=0
      while read -r tag name _; do
        [ "$tag" = SHOT ] || continue
        n=$((n + 1)); [ $n -le $done_shots ] && continue
        [ -n "$W" ] || W=$("$HERE/winid_pid" $PID | head -1)
        [ -n "$W" ] && screencapture -x -o -l "$W" "${PPSSPP_SHOTDIR:-.}/$name.png"
        touch "$(dirname "$PPSSPP_SHOTS")/shot_$name.ok"   # движок ждёт этот файл и только потом идёт дальше (viewer/smoke.h)
        done_shots=$n
      done < "$PPSSPP_SHOTS"
      grep -q '^END' "$PPSSPP_SHOTS" && break
    fi
    sleep 0.25
  done
elif [[ "$WAIT" =~ ^[0-9]+$ ]]; then sleep "$WAIT"
else for i in $(seq 1 450); do [ -f "$WAIT" ] && break; kill -0 $PID 2>/dev/null || break; sleep 2; done; sleep 1; fi
if [ -n "$OUT" ]; then W=$("$HERE/winid_pid" $PID | head -1); [ -n "$W" ] && screencapture -x -o -l "$W" "$OUT"; fi
kill $PID 2>/dev/null; wait $PID 2>/dev/null
exit 0
