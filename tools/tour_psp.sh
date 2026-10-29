#!/bin/bash
# Замер-тур уровня 1 на PSP (просьба Роба 03.10 вечер): отдельная папка PSP/GAME/SHARTOUR, игру SHARVIEW не трогает.
# В папке — тот же набор игры (tools/ship_files.sh), EBOOT с подписью «SHAR замер-тур» в XMB и сценарий тура
# (tools/tour_make.py): игра сама объезжает и обходит уровень, заходит в комнаты, по каждой сцене пишет замеры в smoke.txt,
# раз в секунду строку ящика (BB), снимки — в shots/*.bmp. Роб только запускает «SHAR замер-тур» и ждёт END (около 15 мин),
# потом подключает PSP.
#   tools/tour_psp.sh --deploy [--freeze-route|--room-check|--test8]   собрать сценарий и положить тур на PSP (сверка cmp); прежние отчёты стираются
#   tools/tour_psp.sh --fetch                     забрать отчёты в build/psp-tour/<время>/ и собрать ОТЧЁТ.md (tools/tour_report.py)
# Переменные (03.10 21:5x, Роб: «назови по-другому — два одинаковых клона, не понять, где что»; в XMB нет кириллицы):
#   TOUR_TITLE  подпись в XMB латиницей (по умолчанию «SHAR TEST»), TOUR_ICON — PNG 144×80 своей иконки (иначе иконка игры);
#               у проверки нет картинки фона и музыки игры — в XMB её не спутать с игрой
#   TOUR_LEVEL  другой level.shr для тура (например эталон до правки швов build/seams/ref/level_pre_seams.shr — сравнение на железе)
# EBOOT берётся из viewer/build/EBOOT.PBP (движок main), данные — из build/ (последний tools/ship.sh). --freeze-route —
# последней частью путь к месту зависания 252 (может повесить PSP: отчёт до этого места уже на карте).
set -u
cd "$(dirname "$0")/.."
PSPR="${TOUR_PSP_ROOT:-/Volumes/PSP}"   # TOUR_PSP_ROOT=папка — собрать пакет тура туда (структура PSP/GAME/<апка>), не трогая карту PSP
ROOT="$PWD"; D=$PSPR/PSP/GAME/${TOUR_DIR:-SHARTOUR}; PY=.venv/bin/python   # TOUR_DIR — своя папка апки (08.10: три апки тура всех уровней)
[ -d "$PSPR/PSP" ] || { echo "подключи PSP по USB"; exit 1; }
case "${1:-}" in
  --deploy)
    export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
    FR=""; for x in "${@:2}"; do case "$x" in --freeze-route) FR="$FR --freeze-route";; --fresh-msn) FR="$FR --fresh-msn";; --room-check) FR="$FR --room-check";; --test8) FR="$FR --test8";; --test9) FR="$FR --test9";; --test10) FR="$FR --test10";; --test11) FR="$FR --test11";; --test12) FR="$FR --test12";; --test13) FR="$FR --test13";; --test14) FR="$FR --test14";; --test15) FR="$FR --test15";; --test16) FR="$FR --test16";; --test17) FR="$FR --test17";; --all-levels) FR="$FR --all-levels";; esac; done
    "$PY" tools/tour_make.py $FR || exit 1
    [ -f viewer/build/EBOOT.PBP ] || { echo "нет viewer/build/EBOOT.PBP — собери движок"; exit 1; }
    [ -z "${TOUR_SRC:-}" ] || cmp -s "$TOUR_SRC/EBOOT.PBP" viewer/build/EBOOT.PBP || { echo "viewer/build/EBOOT.PBP не тот, что в $TOUR_SRC — собери набор заново (ship.sh)"; exit 1; }
    T=build/tour/pbp; rm -rf "$T"; mkdir -p "$T"
    ( cd "$T" && unpack-pbp "$ROOT/viewer/build/EBOOT.PBP" > /dev/null ) || { echo "unpack-pbp не смог"; exit 1; }
    mksfoex -d MEMSIZE=1 -s APP_VER= "${TOUR_TITLE:-SHAR TEST}" "$T/PARAM.SFO" || exit 1
    a() { [ -f "$T/$1" ] && echo "$T/$1" || echo NULL; }
    ICON="$(a ICON0.PNG)"; [ -n "${TOUR_ICON:-}" ] && ICON="$TOUR_ICON"
    # правка 296 (музыка XMB): TOUR_ICON1=1 — видео значка игры; TOUR_SND0=<файл> — своя музыка значка (сравнение наведением с SHARVIEW)
    I1=NULL; [ -n "${TOUR_ICON1:-}" ] && I1="$(a ICON1.PMF)"; S0=NULL; [ -n "${TOUR_SND0:-}" ] && S0="$TOUR_SND0"
    pack-pbp build/tour/EBOOT.PBP "$T/PARAM.SFO" "$ICON" "$I1" NULL NULL "$S0" "$T/DATA.PSP" "$(a DATA.PSAR)" > /dev/null || exit 1
    need=$(( $(bash tools/ship_files.sh --pairs | awk -F'|' '{print $2}' | xargs stat -f %z 2>/dev/null | awk '{s+=$1} END{print s+0}') / 1048576 + 200 ))
    free=$(df -m "$PSPR" | awk 'NR==2{print $4}')
    [ "$free" -gt "$need" ] || { echo "на карте свободно ${free} МБ, нужно ~${need}"; exit 1; }
    mkdir -p "$D"; rm -rf "$D/shots" "$D/smoke.txt" "$D/blackbox.txt" "$D/blackbox_prev.txt" "$D/crash.txt" "$D/trace.txt" "$D/me.txt" "$D/meaudio" "$D/mefx" "$D/mescheme" "$D/mewbold" "$D/audio/audlate" "$D"/shot_*.ok
    bad=""; n=0
    while IFS='|' read -r name src; do
      [ -n "${TOUR_SRC:-}" ] && src="$TOUR_SRC/$name"   # TOUR_SRC=build/ship_stage — тот же набор, что выпуск (без установки в build/)
      [ -f "$src" ] || continue; mkdir -p "$D/$(dirname "$name")"
      cmp -s "$src" "$D/$name" 2>/dev/null || { cp "$src" "$D/$name" && n=$((n + 1)); }
      cmp -s "$src" "$D/$name" || bad="$bad $name"
    done < <(bash tools/ship_files.sh --pairs | if [ -n "${TOUR_LEVEL:-}" ]; then sed "s#^level.shr|.*#level.shr|$TOUR_LEVEL#"; else cat; fi)
    cp build/tour/EBOOT.PBP "$D/EBOOT.PBP"; cmp -s build/tour/EBOOT.PBP "$D/EBOOT.PBP" || bad="$bad EBOOT.PBP"
    cp build/tour/scenario.txt "$D/scenario.txt"; cmp -s build/tour/scenario.txt "$D/scenario.txt" || bad="$bad scenario.txt"
    : > "$D/smokelog"   # строка раз в секунду в smoke.txt
    [ -n "${TOUR_MEAUDIO:-}" ] && printf "%s" "$TOUR_MEAUDIO" > "$D/meaudio"   # 04.10: звук на ME (буква схемы памяти, u — память игры)
    [ -n "${TOUR_MEFX:-}" ] && printf "%s" "$TOUR_MEFX" > "$D/mefx"
    [ -n "${TOUR_MEWBOLD:-}" ] && : > "$D/mewbold"   # правка 410: звук на ME с прежним сбросом задания целиком (сравнение К1 в одной сборке)
    find "$D" -name '._*' -delete 2>/dev/null; sync
    [ -z "$bad" ] || { echo "на PSP не совпало:$bad"; exit 1; }
    [ -n "${TOUR_LEVEL:-}" ] && echo "level.shr тура: $TOUR_LEVEL ($(shasum -a 256 "$D/level.shr" | cut -c1-8))"
    echo "тур на PSP: $D («${TOUR_TITLE:-SHAR TEST}») (скопировано $n файлов данных, EBOOT $(shasum -a 256 "$D/EBOOT.PBP" | cut -c1-8), сценарий $(grep -c '^scene' build/tour/scenario.txt) сцен, $(grep -c '^shot' build/tour/scenario.txt) снимков)"
    echo "Робу: в XMB «${TOUR_TITLE:-SHAR TEST}» — запустить и не трогать до конца (около 15 мин), потом подключить PSP по USB" ;;
  --fetch)
    [ -f "$D/smoke.txt" ] || { echo "на PSP нет отчёта тура (smoke.txt): тур ещё не запускали"; exit 1; }
    O="build/psp-tour/$(date +%Y%m%d-%H%M)-${TOUR_DIR:-SHARTEST}"; mkdir -p "$O"   # папка с именем теста: два --fetch в одну минуту не затирают друг друга
    for f in smoke.txt blackbox.txt blackbox_prev.txt crash.txt trace.txt bench.txt sfxlog.txt intro.txt me.txt; do [ -f "$D/$f" ] && cp -p "$D/$f" "$O/"; done
    [ -d "$D/shots" ] && cp -R -p "$D/shots" "$O/"
    echo "забрано в $O: $(ls "$O" | tr '\n' ' ')"
    "$PY" tools/tour_report.py "$O" ;;
  *) echo "tools/tour_psp.sh --deploy [--freeze-route] | --fetch"; exit 2 ;;
esac
