#!/bin/bash
# Стенд PSPLink (этап С.1 аудита ведущего 30.09): игра идёт на НАСТОЯЩЕЙ PSP по кабелю, журнал, счётчики и снимки — на Мак.
#   tools/psplink_run.sh [ключи] [СЦЕНАРИЙ]
#     СЦЕНАРИЙ     команды viewer/smoke.h (scene/goto/foot/flag/press/wait/shot/end); без него — 30 с на старте
#     --dir DIR    откуда EBOOT и данные (по умолчанию build/, набор — tools/ship_files.sh, как у tools/smoke.sh)
#     --exact      взять папку DIR целиком (build/psp-card-… — точная копия того, что лежало на карте)
#     --time S     предел прогона, с (по умолчанию сумма wait сценария + 240)
#     --flag NAME  пустой служебный файл рядом с EBOOT (nolayer, view60 …), можно несколько раз
#     --ballast MB занять MB кучи на старте (файл ballast, гейт 12б)
#     --label NAME приписка к имени папки журнала
#     --check      только проверить связь (PSPLink, батарея, память) и выйти
# PSP: выйти из режима USB, в меню «Игра» запустить PSPLink, оставить на кабеле. На PSP ничего не нажимать
# Мак раздаёт PSP чистую папку прогона как host0: (usbhostfs_pc из pspdev/bin), запускает там ./EBOOT.PBP (pspsh);
# игра пишет журнал smoke.txt прямо на Мак. Раз в секунду стенд смотрит журнал: «SHOT имя» — снимок экрана PSP (scrshot);
# журнал молчит — спрашивает PSPLink: исключение процессора -> ВЫЛЕТ (регистры и строка кода), PSPLink отвечает без
# исключения -> ЗАВИСАНИЕ ИГРЫ (потоки, снимок экрана), не отвечает -> PSP НЕ ОТВЕЧАЕТ (зависла вся приставка)
# Итог: build/psp-logs/<дата-время>[-label]/ — summary.txt (ПЕРВАЯ строка — вердикт), smoke.txt, bench.txt, blackbox*.txt,
#   stand.log (что делал стенд, по времени), usbhostfs.log, stdout.txt/stderr.txt (вывод игры), exception.txt, threads.txt,
#   снимки <имя>.png и contact.png. Папка прогона host/ (клоны файлов) после прогона удаляется
# Код выхода: 0 OK (сценарий дошёл до END) · 1 сценарий дошёл, но проверки сцен провалены (tools/smoke_report.py)
#   · 10 ВЫЛЕТ · 11 ЗАВИСАНИЕ ИГРЫ · 12 PSP НЕ ОТВЕЧАЕТ · 13 ПРЕДЕЛ ВРЕМЕНИ · 2 нет связи с PSP / ошибка стенда
# Гейт стенда (сначала красный): tests/psplink/gate.sh — сценарии crash и hang обязаны дать 10 и 11, idle — 0
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$ROOT/pspdev/bin:$PATH"
SRC="$ROOT/build"; EXACT=0; TLIM=""; LABEL=""; FLAGS=""; BALLAST=""; SCN=""; CHECK=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) SRC="$2"; shift 2 ;;
    --exact) EXACT=1; shift ;;
    --time) TLIM="$2"; shift 2 ;;
    --label) LABEL="$2"; shift 2 ;;
    --flag) FLAGS="$FLAGS $2"; shift 2 ;;
    --ballast) BALLAST="$2"; shift 2 ;;
    --check) CHECK=1; shift ;;
    -h|--help) sed -n '2,23p' "$0"; exit 0 ;;
    -*) echo "psplink_run: неизвестный ключ $1"; exit 2 ;;
    *) SCN="$1"; shift ;;
  esac
done
case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
[ -n "$SCN" ] && case "$SCN" in /*) ;; *) SCN="$PWD/$SCN" ;; esac

# ---- libusb (usbhostfs_pc собран с Homebrew libusb)
if [ ! -f /opt/homebrew/opt/libusb/lib/libusb-1.0.0.dylib ]; then
  echo "psplink_run: ставлю libusb (brew install libusb)"; brew install libusb >/dev/null || { echo "psplink_run: нет libusb"; exit 2; }
fi

# ---- один стенд за раз (PSP одна)
LOCK=/tmp/psplink.lock
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -f "$LOCK/pid" ] && ! kill -0 "$(cat "$LOCK/pid" 2>/dev/null)" 2>/dev/null; then rm -rf "$LOCK"; mkdir "$LOCK" || exit 2
  else echo "psplink_run: стенд уже занят (PID $(cat "$LOCK/pid" 2>/dev/null))"; exit 2; fi
fi
echo $$ > "$LOCK/pid"

STAMP=$(date +%Y%m%d-%H%M%S)
OUT="$ROOT/build/psp-logs/$STAMP${LABEL:+-$LABEL}"; [ -e "$OUT" ] && OUT="$OUT-$$"
HOST="$OUT/host"
mkdir -p "$HOST" || exit 2
LOG="$OUT/stand.log"; USBLOG="$OUT/usbhostfs.log"
log() { local m="$(date +%H:%M:%S) $*"; echo "$m" >> "$LOG"; echo "$m"; }
UPID=""; NC1=""; NC2=""
cleanup() {
  [ -n "$NC1" ] && kill "$NC1" 2>/dev/null; [ -n "$NC2" ] && kill "$NC2" 2>/dev/null
  exec 7>&- 2>/dev/null
  if [ -n "$UPID" ] && kill -0 "$UPID" 2>/dev/null; then kill "$UPID" 2>/dev/null
    for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$UPID" 2>/dev/null || break; sleep 0.2; done
    kill -9 "$UPID" 2>/dev/null; fi
  rm -f "$OUT/.usbin"; rm -rf "$LOCK"
}
trap cleanup EXIT
trap 'log "прервано (сигнал)"; exit 2' INT TERM

# pspsh: одна команда оболочки PSPLink, без tty; пустой вывод и код 124 — PSPLink не ответил за отведённое время
psh() { timeout "${2:-10}" pspsh -n -e "$1" 2>&1; }
# какой режим USB у PSP: 457 (0x1C9) — PSPLink, 722 (0x2D2) — флешка
usbmode() {
  local p; p=$(ioreg -p IOUSB -w0 -l 2>/dev/null | awk '/"idProduct" =/{pr=$NF} /"idVendor" = 1356/{print pr; exit}')
  case "$p" in 457) echo psplink ;; 722) echo usb ;; "") echo none ;; *) echo "other:$p" ;; esac
}
nolink() {   # вердикт «нет связи» с одной просьбой Робу
  local why
  case "$(usbmode)" in
    usb) why="PSP в режиме USB (флешка): выйди из него, запусти PSPLink из меню «Игра», оставь на кабеле" ;;
    none) why="PSP не видна по USB: подключи кабель, включи PSP, запусти PSPLink из меню «Игра»" ;;
    *) why="PSPLink не отвечает: на PSP выйди из PSPLink (HOME) и запусти его снова из меню «Игра»" ;;
  esac
  echo "НЕТ СВЯЗИ: $why" > "$OUT/summary.txt"; log "НЕТ СВЯЗИ: $why"; exit 2
}

# ---- папка прогона (host0:) — чистая, без чужих служебных файлов
T0FILE="$OUT/.t0"
if [ $CHECK = 0 ]; then
  [ -f "$SRC/EBOOT.PBP" ] || { log "нет $SRC/EBOOT.PBP"; exit 2; }
  if [ $EXACT = 1 ]; then
    cp -cR "$SRC/." "$HOST/" 2>/dev/null || cp -R "$SRC/." "$HOST/" || { log "не скопировать $SRC"; exit 2; }
    for f in scenario.txt smokelog smoke.txt bench.txt blackbox.txt blackbox_prev.txt stream.txt service ballast goto.txt autobench; do
      [ -e "$HOST/$f" ] && mv "$HOST/$f" "$OUT/card_$f"; done   # то, что лежало на карте, — рядом с журналом, не в игру
  else
    cp -c "$SRC/EBOOT.PBP" "$HOST/" 2>/dev/null || cp "$SRC/EBOOT.PBP" "$HOST/" || exit 2
    while IFS='|' read -r f p; do
      s="$SRC/$f"
      [ -f "$s" ] || s="$ROOT/$p"
      [ -f "$s" ] || { case "$f" in l[0-9]/*|movies/fmv*) ;; *) log "предупреждение: нет $f (ни в ${SRC#$ROOT/}, ни $p) — игра идёт без него, как на карте без файла" ;; esac; continue; }
      mkdir -p "$HOST/$(dirname "$f")" || exit 2
      cp -c "$s" "$HOST/$f" 2>/dev/null || cp "$s" "$HOST/$f" || exit 2
    done < <("$ROOT/tools/ship_files.sh" --pairs)
    [ -f "$SRC/settings.bin" ] && cp "$SRC/settings.bin" "$HOST/"
  fi
  if [ -n "$SCN" ]; then [ -f "$SCN" ] || { log "нет сценария $SCN"; exit 2; }; cp "$SCN" "$HOST/scenario.txt"
  else printf 'scene idle\nwait 30\nend\n' > "$HOST/scenario.txt"; fi
  cp "$HOST/scenario.txt" "$OUT/scenario.txt"
  touch "$HOST/smokelog"
  for f in $FLAGS; do touch "$HOST/$f"; done
  [ -n "$BALLAST" ] && echo "$BALLAST" > "$HOST/ballast"
  [ -n "$TLIM" ] || TLIM=$(awk '$1=="wait"{s+=$2} $1=="shot"{s+=2} END{print int(s)+240}' "$HOST/scenario.txt")
fi

# ---- usbhostfs_pc: stdin держим открытым через FIFO (на EOF он выходит; режим -n уходит в фон и теряет PID)
mkfifo "$OUT/.usbin" || exit 2
usbhostfs_pc -v -c "$HOST" < "$OUT/.usbin" > "$USBLOG" 2>&1 &
UPID=$!
exec 7> "$OUT/.usbin"
log "стенд: $(basename "$OUT"), usbhostfs_pc $UPID, host0: = ${HOST#$ROOT/}"
for i in $(seq 1 60); do grep -q 'Connected to device' "$USBLOG" 2>/dev/null && break; kill -0 $UPID 2>/dev/null || break; sleep 0.5; done
grep -q 'Connected to device' "$USBLOG" 2>/dev/null || nolink
V=$(psh ver 10); [ -n "$V" ] || nolink
log "связь: $V; $(psh pspver 10 | head -1)"
psh power 10 | sed -E -n 's/^(External Power|Charge|Battery Temp) *: */\1: /p' | tr '\n' ';' | sed 's/;$//' | { read -r p; log "питание: $p"; }
MEM=$(psh 'meminfo 2' 10 | awk -F'|' '$1+0==2{gsub(/ /,""); print $4" Б свободно, max "$5}'); log "память (раздел 2): $MEM"
if [ $CHECK = 1 ]; then echo "OK: PSPLink на связи ($V)" > "$OUT/summary.txt"; log "проверка связи: OK"; rm -rf "$HOST"; exit 0; fi

# игра уже идёт (прошлый прогон)? — сброс PSPLink
if psh modlist 15 | grep -q 'Name: SHARVIEW'; then
  log "на PSP ещё идёт SHARVIEW — reset"; psh reset 10 >/dev/null
  for i in $(seq 1 60); do [ "$(grep -c 'Connected to device' "$USBLOG")" -ge 2 ] && break; sleep 0.5; done
fi

# ---- вывод игры (stdout/stderr — каналы usbhostfs 10002/10003)
nc 127.0.0.1 10002 > "$OUT/stdout.txt" 2>/dev/null & NC1=$!
nc 127.0.0.1 10003 > "$OUT/stderr.txt" 2>/dev/null & NC2=$!

touch "$T0FILE"; CONN0=$(grep -c 'Connected to device' "$USBLOG")
R=$(psh './EBOOT.PBP' 30); log "запуск: $(echo "$R" | tr '\n' ' ' | cut -c1-160)"
case "$R" in *[Ff]ailed*|*[Ee]rror*|*"No such"*) echo "СТЕНД: игра не запустилась — $R" > "$OUT/summary.txt"; log "не запустилась"; exit 2 ;; esac

SM="$HOST/smoke.txt"; START=$(date +%s); LASTGROW=$START; LASTSZ=0; SHOTS=0; VERDICT=""; RC=0; GAMEON=0
BOOT_STALL=180; STALL=25
while :; do
  sleep 1; NOW=$(date +%s)
  SZ=$( [ -f "$SM" ] && stat -f %z "$SM" || echo 0 )
  if [ "$SZ" != "$LASTSZ" ]; then LASTSZ=$SZ; LASTGROW=$NOW; fi
  if [ $GAMEON = 0 ] && [ -f "$SM" ] && grep -qE '^[0-9]+\.[0-9]+ ' "$SM"; then GAMEON=1; log "игра идёт (первая строка журнала через $((NOW - START)) с)"; fi
  # снимки: строка «SHOT имя» -> scrshot, потом shot_имя.ok (движок ждёт его до 5 с)
  if [ -f "$SM" ]; then
    n=0
    while read -r tag name _; do
      [ "$tag" = SHOT ] || continue
      n=$((n + 1)); [ $n -le $SHOTS ] && continue
      psh "scrshot host0:/shot_$name.bmp" 20 >/dev/null; touch "$HOST/shot_$name.ok"; SHOTS=$n
      log "снимок $name"
    done < "$SM"
    if grep -q '^END' "$SM"; then VERDICT="OK: сценарий дошёл до END за $((NOW - START)) с"; RC=0; break; fi
    if grep -q '^FAULT' "$SM" && [ "$(grep '^FAULT' "$SM" | tail -1)" != "${LASTFAULT:-}" ]; then LASTFAULT=$(grep '^FAULT' "$SM" | tail -1); log "игра: $LASTFAULT"; fi
  fi
  # PSP перезагрузилась (игра вышла сама без END или PSPLink сбросился)
  if [ "$(grep -c 'Connected to device' "$USBLOG")" -gt "$CONN0" ]; then
    VERDICT="ВЫХОД ИГРЫ БЕЗ END: PSPLink перезапустился через $((NOW - START)) с (выход игры или сброс)"; RC=10; break; fi
  LIM=$STALL; [ $GAMEON = 0 ] && LIM=$BOOT_STALL
  if [ $((NOW - LASTGROW)) -ge $LIM ]; then
    log "журнал молчит $((NOW - LASTGROW)) с — спрашиваю PSPLink"
    EX=$(psh exprint 12); ERC=$?
    if [ $ERC = 124 ] || [ -z "$EX" ]; then
      VERDICT="PSP НЕ ОТВЕЧАЕТ: журнал встал через $((LASTGROW - START)) с от старта, PSPLink молчит (зависла вся приставка)"; RC=12; break; fi
    if ! echo "$EX" | grep -q 'No exception occurred'; then
      echo "$EX" > "$OUT/exception.txt"
      psh 'modinfo @SHARVIEW' 12 >> "$OUT/exception.txt"
      VERDICT="ВЫЛЕТ: $(echo "$EX" | grep -m1 -i '^Exception' | sed 's/^Exception *- *//')"; RC=10; break; fi
    psh 'thlist v' 20 > "$OUT/threads.txt"
    VERDICT="ЗАВИСАНИЕ ИГРЫ: журнал встал через $((LASTGROW - START)) с от старта, PSPLink отвечает, исключения нет"; RC=11; break
  fi
  if [ $((NOW - START)) -ge "$TLIM" ]; then VERDICT="ПРЕДЕЛ ВРЕМЕНИ: $TLIM с, сценарий не дошёл до END"; RC=13; break; fi
done
log "$VERDICT"

# ---- после: снимок экрана (если PSP отвечает), строка кода вылета, остановка игры
if [ $RC -ge 10 ] && [ $RC != 12 ]; then psh 'scrshot host0:/screen.bmp' 20 >/dev/null; fi
if [ -f "$OUT/exception.txt" ]; then
  EPC=$(sed -n 's/^EPC *- *\(0x[0-9A-Fa-f]*\).*/\1/p' "$OUT/exception.txt" | head -1)
  TXT=$(sed -n 's/.*[Tt]ext *[Aa]ddr[^0-9x]*\(0x[0-9A-Fa-f]*\).*/\1/p' "$OUT/exception.txt" | head -1)
  ELF="$ROOT/viewer/build/sharview"
  if [ -n "$EPC" ] && [ -n "$TXT" ] && [ -f "$ELF" ] && cmp -s "$HOST/EBOOT.PBP" "$ROOT/viewer/build/EBOOT.PBP"; then
    OFF=$(printf '0x%x' $((EPC - TXT)))
    W=$(psp-addr2line -f -i -e "$ELF" "$OFF" 2>/dev/null | paste -sd' ' -)
    echo "EPC $EPC - text $TXT = $OFF -> $W" >> "$OUT/exception.txt"; log "место вылета: $OFF $W"
    VERDICT="$VERDICT · $W"
  else log "место вылета: EPC ${EPC:-?}, text ${TXT:-?} (строку кода даёт только EBOOT из viewer/build)"; fi
fi
if [ $RC != 12 ] && psh modlist 15 | grep -q 'Name: SHARVIEW'; then
  log "останавливаю игру (reset PSPLink)"; psh reset 10 >/dev/null
  for i in $(seq 1 60); do [ "$(grep -c 'Connected to device' "$USBLOG")" -gt "$CONN0" ] && break; sleep 0.5; done
elif [ $RC = 0 ]; then
  for i in $(seq 1 30); do [ "$(grep -c 'Connected to device' "$USBLOG")" -gt "$CONN0" ] && break; sleep 0.5; done   # выход игры -> PSPLink заново
fi

# ---- журнал на Мак: всё, что игра написала за прогон
for f in "$HOST"/*; do
  [ -f "$f" ] && [ "$f" -nt "$T0FILE" ] || continue
  b=$(basename "$f")
  case "$b" in shot_*.ok) continue ;;
    *.bmp) n=${b#shot_}; n=${n%.bmp}; sips -s format png "$f" --out "$OUT/$n.png" >/dev/null 2>&1 || cp "$f" "$OUT/" ;;
    *) cp "$f" "$OUT/" ;;
  esac
done
rm -rf "$HOST"
CHK=""
if [ -f "$OUT/smoke.txt" ]; then
  . "$ROOT/.venv/bin/activate" 2>/dev/null
  CHK=$(python "$ROOT/tools/smoke_report.py" "$OUT" "$OUT/scenario.txt" 2>&1 | head -1)
  [ $RC = 0 ] && case "$CHK" in OK*) ;; *) RC=1 ;; esac
fi
{ echo "$VERDICT"; [ -n "$CHK" ] && echo "проверки сцен: $CHK"; echo
  [ -f "$OUT/summary.txt" ] && cat "$OUT/summary.txt"
  [ -f "$OUT/exception.txt" ] && { echo; echo "--- exception.txt"; head -40 "$OUT/exception.txt"; }
  echo; echo "--- stand.log"; cat "$LOG"; } > "$OUT/summary.new"
mv "$OUT/summary.new" "$OUT/summary.txt"
echo "итог: ${OUT#$ROOT/}/summary.txt"
exit $RC
