#!/bin/bash
# Гейт пакета «заставка GONE Makers + иконка в меню PSP» (правки Роба 28.09 вечер). Каждая проверка сначала КРАСНАЯ на
# заведомо плохом входе, потом зелёная; итог — строки «КРАСНЫЙ как надо / ЗЕЛЁНЫЙ» и код выхода 0 только если всё так.
#   tools/boot_gate.sh [--emu] [EBOOT]     EBOOT по умолчанию viewer/build/EBOOT.PBP
#   1) знак на Маке (tests/bootlogo): стадии / | \ ■ рисунок, тонкие символы, не касаются знака, 1:1, сетка, пропуск = итог
#      красное: толстый ■ во всё поле 3×3; зазор клетки не с той стороны (символы касаются знака)
#   2) звук включения на Маке (tests/bootsnd, правка 128): щелчок кнопки, раскрутка кулера, мягкий бип POST, поток кусками
#      без швов, быстрее реального времени; красное: без щелчка, кулер сразу на полную, прежний резкий фильтр, кусок 1000
#   3) меню PSP (XMB) и EBOOT (tools/pbp_gate.py): ICON0 144×80 непрозрачна во всю плитку, только логотип без «v.0.1» и
#      «PSP» (правка 146), подпись «The Simpsons Hit & Run»; PIC1 480×272 по обложке Роба мельче (2,45), Мардж правее
#      значков (правка 132); ICON1 12–20 с нарезки демо-геймплея (правка 131); SND0 ATRAC3 (правка 130); всё в EBOOT побайтно;
#      красное: иконка 143×80, прежняя иконка с прозрачными углами, EBOOT с прежней иконкой внутри, плитка с надписями
#      (icon0.py --text keep), прежняя подпись в PARAM.SFO, прежний фон (2,03) и Мардж под значками (--marge-x 120);
#      правка 110/131 (если есть build/assets/icon1.pmf): EBOOT без ICON1, с испорченным ICON1, испорченный PMF, прежний
#      5-секундный значок, монтаж с «DEMO» / через склейку / спокойный кусок; правка 130: PCM вместо ATRAC3, EBOOT без SND0
#   4) --emu: эмулятор (через очередь tools/ppsspp_run.sh): снимки кадров появления + строки BOOTSND и BOOTT в smoke.txt
#      (tools/boot_check.py); красное: прогон со служебным nobeep и без bootframes -> писка нет, кадров нет; прогон с
#      bootslow -> первый кадр заставки позже 50 мс от входа в main (правка Роба 28)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
EMU=0; [ "${1:-}" = --emu ] && { EMU=1; shift; }
EBOOT="${1:-$ROOT/viewer/build/EBOOT.PBP}"
PY="$ROOT/.venv/bin/python"
TMP="$ROOT/build/boot_gate/$(date +%Y%m%d-%H%M%S)-$$"; mkdir -p "$TMP"
BAD=0
red()   { if "$@" > "$TMP/last.txt" 2>&1; then echo "  НЕ КРАСНЫЙ (проверка ничего не ловит): $*"; tail -3 "$TMP/last.txt"; BAD=1
          else echo "  КРАСНЫЙ как надо: $(grep -m1 -E 'RESULT|FAIL' "$TMP/last.txt")  <- ${*//$ROOT\//}"; fi; }
green() { if "$@" > "$TMP/last.txt" 2>&1; then echo "  ЗЕЛЁНЫЙ: $(grep -m1 -E 'RESULT|^OK' "$TMP/last.txt")  <- ${*//$ROOT\//}"
          else echo "  НЕ ЗЕЛЁНЫЙ: $*"; cat "$TMP/last.txt"; BAD=1; fi; }

echo "1) знак заставки (tests/bootlogo)"
red   bash tests/bootlogo/host.sh '-DBOOTANIM_GLYPHS={0x054,0x092,0x111,0x1FF}'
red   bash tests/bootlogo/host.sh -DBOOTANIM_GOFS=0
red   bash tests/bootlogo/host.sh -DBUI_CW=6          # правка 125: прежний шаг клетки — шрифт не msx 8×8, сетка не 60×34
red   "$PY" tools/bootfont.py --check --out /dev/null  # правка 125: копии шрифта нет
green "$PY" tools/bootfont.py --check                  # viewer/bootmsx.h = msx в libpspdebug.a побайтно
red   bash tests/bootlogo/host.sh -DBSQ_MARK_PLANT      # правка 127: слот знака на знаке GONE
red   bash tests/bootlogo/host.sh -DBOOTMARK_ALWAYS_REDRAW   # правка 127: все знаки каждый кадр — сверх бюджета
[ -f build/bootmarks.bin ] || "$PY" tools/bootmarks.py > /dev/null
green "$PY" tools/bootmarks.py --verify                # build/bootmarks.bin: ≤ 144×40, 2 бита, 4 серых, crc (полный красный — tests/bootlogo/run.sh)
green bash tests/bootlogo/host.sh

echo "2) звук включения (tests/bootsnd)"
red   bash tests/bootsnd/host.sh -DBOOT_SND_CLICK=0
red   bash tests/bootsnd/host.sh -DBOOT_SND_FAN_TAU=0
red   bash tests/bootsnd/host.sh -DBOOT_BEEP_LP=0.55f
red   bash tests/bootsnd/host.sh -DBOOT_SND_CHUNK=1000
green bash tests/bootsnd/host.sh

echo "3) меню PSP (XMB) и EBOOT (tests/xmb/run.sh: tools/pbp_gate.py, icon0/pic1/icon1/snd0)"
XMB_TMP="$TMP/xmb" bash tests/xmb/run.sh "$EBOOT"; [ $? = 0 ] || BAD=1

if [ $EMU = 1 ]; then
  echo "4) эмулятор: кадры появления и писк (tools/boot_check.py)"
  emu_run() {   # $1 = папка итога, $2 = служебные файлы через пробел
    local out="$1" run="$ROOT/build/emu/boot/$(basename "$1")-$$"; mkdir -p "$out" "$run"
    cp -c "$EBOOT" "$run/EBOOT.PBP" 2>/dev/null || cp "$EBOOT" "$run/EBOOT.PBP"
    for f in $(tools/ship_files.sh); do [ -f "build/$f" ] || continue; mkdir -p "$run/$(dirname "$f")"
      cp -c "build/$f" "$run/$f" 2>/dev/null || cp "build/$f" "$run/$f"; done
    printf 'flag menu\nend\n' > "$run/scenario.txt"; touch "$run/smokelog"; for s in $2; do touch "$run/$s"; done
    PPSSPP_SHOTS="$run/smoke.txt" PPSSPP_SHOTDIR="$out" tools/ppsspp_run.sh "$run/EBOOT.PBP" 120
    cp "$run/smoke.txt" "$out/" 2>/dev/null; rm -rf "$run"
  }
  emu_run "$TMP/emu_neg" "nobeep"
  red   "$PY" tools/boot_check.py "$TMP/emu_neg"
  emu_run "$TMP/emu_slow" "bootframes bootslow"   # правка Роба 28: первый кадр позже 50 мс — обязан упасть
  red   "$PY" tools/boot_check.py "$TMP/emu_slow"
  emu_run "$TMP/emu" "bootframes"
  green "$PY" tools/boot_check.py "$TMP/emu"
  cat "$TMP/last.txt" | sed 's/^/    /'
  echo "  снимки кадров появления: ${TMP#$ROOT/}/emu/"
fi
[ $BAD = 0 ] && echo "boot_gate: OK (итоги в ${TMP#$ROOT/})" || echo "boot_gate: FAIL (итоги в ${TMP#$ROOT/})"
exit $BAD
