#!/bin/bash
# Финал TEST34 без интернета (Роб 18.10: «уйду с телефоном — интернета не будет; поставь себе скрипт, чтобы без интернета всё упаковал»).
# Работает сам, только на Маке: ждёт коммит помощника мультика (ветка toon-779, до 25 мин), сводит ветки, собирает движки игры и тура,
# собирает наборы TEST34 (tools/test34_set.sh + frame_gate в эмуляторе), гонит финальный тур целиком в эмуляторе и кладёт итог на рабочий стол:
#   ~/Desktop/SHAR_ФИНАЛ_18.10/  ОТЧЁТ.txt · сборка.log · тур_кадры.png · «Положить SHAR на PSP.command» (выкладка по SHA, ничего не удаляет)
# Мультик помощника не собрался или не прошёл проверки — откат к сборке без него (ничего не теряется: ветка toon-779 остаётся). На PSP скрипт НЕ кладёт.
I=$HOME/Downloads/shar-psp-integ; R=$HOME/Downloads/shar-psp-render-w; OUT=$HOME/Desktop/SHAR_ФИНАЛ_18.10
BASE=9a5b5d64; JF="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1"
mkdir -p "$OUT"; LOG="$OUT/сборка.log"; exec >> "$LOG" 2>&1
caffeinate -dimsu -w $$ &
export PSPDEV=$I/pspdev PATH=$I/pspdev/bin:$PATH
say_() { echo "$(date '+%H:%M:%S') · $*"; }
REPORT="$OUT/ОТЧЁТ.txt"; : > "$REPORT"; rep() { echo "$*" >> "$REPORT"; say_ "$*"; }
say_ "старт финала TEST34"

# 1) коммит помощника мультика: ждать до 25 мин; после первого коммита — пока ветка не затихнет на 4 мин
T0=$(date +%s); last=""; quiet=0
while :; do
  cur=$(git -C $I rev-parse toon-779 2>/dev/null)
  if [ -n "$cur" ] && [ "$cur" != "$(git -C $I rev-parse $BASE)" ]; then
    if [ "$cur" = "$last" ]; then quiet=$((quiet + 30)); else quiet=0; last=$cur; fi
    [ $quiet -ge 240 ] && break
  fi
  [ $(( $(date +%s) - T0 )) -ge 1500 ] && break
  sleep 30
done
TOON=""; [ -n "$last" ] && TOON=$(git -C $I rev-parse --short toon-779)
say_ "мультик помощника: ${TOON:-нет коммита}"

H_R0=$(git -C $R rev-parse HEAD); H_I0=$(git -C $I rev-parse HEAD)
merge_all() {   # $1 = 1 — с мультиком
  git -C $R reset -q --hard $H_R0; git -C $I reset -q --hard $H_I0
  if [ "$1" = 1 ] && [ -n "$TOON" ]; then
    git -C $R merge --no-edit -q toon-779 || { git -C $R merge --abort; say_ "мультик: конфликт слияния — без него"; return 1; }
  fi
  git -C $I merge --no-edit -q render-perf || { git -C $I merge --abort; say_ "integ: конфликт слияния render-perf"; return 2; }
  return 0
}
build_all() {
  ( cd $I/viewer && rm -rf build_t34game build_g34tour &&
    psp-cmake -S . -B build_t34game -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DCMAKE_C_FLAGS="$JF" >/dev/null &&
    cmake --build build_t34game -j8 2>&1 | grep -E " error|error:|Built target" &&
    psp-cmake -S . -B build_g34tour -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$JF -DBB_SYNC_OLD=1" >/dev/null &&
    cmake --build build_g34tour -j8 2>&1 | grep -E " error|error:|Built target" ) &&
  [ -f $I/viewer/build_t34game/EBOOT.PBP ] && [ -f $I/viewer/build_g34tour/EBOOT.PBP ]
}
WITH=0
if [ -n "$TOON" ]; then
  if merge_all 1 && build_all && (cd $I && tools/test34_set.sh); then WITH=1; else say_ "с мультиком помощника не вышло — собираю без него"; fi
fi
if [ $WITH = 0 ]; then
  merge_all 0 || { rep "СБОРКА НЕ УДАЛАСЬ: слияние веток (лог: $LOG)"; afplay /System/Library/Sounds/Basso.aiff; exit 1; }
  build_all || { rep "СБОРКА НЕ УДАЛАСЬ: движок не собрался (лог: $LOG)"; afplay /System/Library/Sounds/Basso.aiff; exit 1; }
  (cd $I && tools/test34_set.sh) || { rep "СБОРКА НЕ УДАЛАСЬ: наборы или проверка кадра в эмуляторе (лог: $LOG)"; afplay /System/Library/Sounds/Basso.aiff; exit 1; }
fi
rep "SHAR TEST34 · финал · $(date '+%Y-%m-%d %H:%M')"
rep "коммит integ/test34 $(git -C $I rev-parse --short HEAD), render-perf $(git -C $R rev-parse --short HEAD); мультик помощника: $([ $WITH = 1 ] && echo "включён ($TOON)" || echo 'не вошёл (контур и цвета как в TEST33; ползунки CARTOON пока без действия)')"
rep "игра: $I/build/test34 + EBOOT_SHARVIEW.PBP $(shasum -a 256 $I/build/test34/EBOOT_SHARVIEW.PBP | cut -c1-8); тур: $I/build/test34tour; проверка кадра в эмуляторе: PASS"

# 2) финальный тур целиком в эмуляторе (переходы всех уровней, Settings, мультик, автопилот по дорогам)
T=$I/build/test34tour/PSP/GAME/SHARTEST15
EMU_SET=$T bash $I/tools/emu_run_bb.sh $T/EBOOT.PBP $T/scenario.txt t34final 1500
E=$R/build/emu_runs/t34final
ends=$(grep -a -c '^END' $E/smoke.txt 2>/dev/null); stalls=$(grep -a -c 'BBSTALL' $E/smoke.txt 2>/dev/null); pf=$(grep -a -c 'PLAYERFAIL' $E/smoke.txt 2>/dev/null)
loads=$(grep -a '^LEVEL ev=load' $E/smoke.txt 2>/dev/null | grep -o 'n=[0-9]' | tr '\n' ' '); shots=$(ls $E/*.png 2>/dev/null | wc -l | tr -d ' ')
rep "тур в эмуляторе: дошёл до конца=$([ "${ends:-0}" -ge 1 ] && echo да || echo НЕТ), зависаний=${stalls:-?}, отказов модели игрока=${pf:-?}, загружены уровни: $loads, кадров $shots"
[ -f $E/stall.txt ] && rep "ЗАПИСЬ СТОРОЖА: $(head -2 $E/stall.txt | tr '\n' ' ')"
python3 - "$E" "$OUT/тур_кадры.png" <<'PY'
import sys, glob, os
try:
    from PIL import Image, ImageDraw
except Exception: sys.exit(0)
fs = sorted(glob.glob(os.path.join(sys.argv[1], '*.png')))
if not fs: sys.exit(0)
W, H, C = 320, 182, 6; rows = (len(fs) + C - 1) // C
s = Image.new('RGB', (W * C, H * rows)); d = ImageDraw.Draw(s)
for i, f in enumerate(fs):
    s.paste(Image.open(f).convert('RGB').resize((W, H)), ((i % C) * W, (i // C) * H)); d.text(((i % C) * W + 4, (i // C) * H + 40), os.path.basename(f)[:-4], fill=(255, 255, 0))
s.save(sys.argv[2])
PY
cat > "$OUT/Положить SHAR на PSP.command" <<'CMD'
#!/bin/bash
# Подключи PSP по USB (на PSP: Настройки → USB-соединение) и дважды щёлкни этот файл: игра ляжет в SHARVIEW, тур — в SHARTEST15
python3 "$HOME/Downloads/shar-psp-integ/tools/sv_deploy34.py"
echo; read -n 1 -s -r -p "Нажми любую клавишу, чтобы закрыть окно"
CMD
chmod +x "$OUT/Положить SHAR на PSP.command"
rep "ГОТОВО. Положить на PSP: подключи PSP по USB и дважды щёлкни «Положить SHAR на PSP.command» в этой папке"
afplay /System/Library/Sounds/Glass.aiff
