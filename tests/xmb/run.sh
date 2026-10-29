#!/bin/bash
# Гейт меню PSP (XMB) — правки Роба 130 (музыка SND0), 131 (живой значок ICON1), 132 (фон PIC1), 146 (значок ICON0 и
# подпись), прежние 28–30, 68, 110. Каждая проверка сначала КРАСНАЯ на заведомо плохом входе (прежнее поведение или
# испорченный файл), потом зелёная; код выхода 0 только если всё так. Только Мак, без эмулятора: PPSSPP значок ICON1 и
# музыку XMB не играет — вживую проверяет Роб на PSP. Тот же блок — раздел 3 tools/boot_gate.sh.
#   tests/xmb/run.sh [EBOOT]      EBOOT по умолчанию viewer/build/EBOOT.PBP
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EBOOT="${1:-$ROOT/viewer/build/EBOOT.PBP}"
PY="$ROOT/.venv/bin/python"
TMP="${XMB_TMP:-$ROOT/build/xmb_gate/$(date +%Y%m%d-%H%M%S)-$$}"; mkdir -p "$TMP"
BAD=0
red()   { if "$@" > "$TMP/last.txt" 2>&1; then echo "  НЕ КРАСНЫЙ (проверка ничего не ловит): $*"; tail -3 "$TMP/last.txt"; BAD=1
          else echo "  КРАСНЫЙ как надо: $(grep -m1 -E 'RESULT|FAIL' "$TMP/last.txt")  <- ${*//$ROOT\//}"; fi; }
green() { if "$@" > "$TMP/last.txt" 2>&1; then echo "  ЗЕЛЁНЫЙ: $(grep -m1 -E 'RESULT|^OK' "$TMP/last.txt")  <- ${*//$ROOT\//}"
          else echo "  НЕ ЗЕЛЁНЫЙ: $*"; cat "$TMP/last.txt"; BAD=1; fi; }

"$PY" -c "from PIL import Image; Image.open('$ROOT/build/assets/icon0.png').resize((143, 80)).save('$TMP/icon_143.png')"
# прежняя иконка с прозрачными углами (как до плитки 28.09): текущая, углы по 3x3 прозрачные — не зависит от архива
"$PY" -c "from PIL import Image; im = Image.open('$ROOT/build/assets/icon0.png').convert('RGBA'); px = im.load()
for x0, y0 in ((0, 0), (141, 0), (0, 77), (141, 77)):
    for dx in range(3):
        for dy in range(3): px[x0 + dx, y0 + dy] = (0, 0, 0, 0)
im.save('$TMP/icon_alpha.png')"
OLD="$TMP/icon_alpha.png"
"$PY" tools/pbp_art.py "$EBOOT" "$TMP/EBOOT_oldicon.PBP" --icon0 "$OLD" > /dev/null
red   "$PY" tools/pbp_gate.py --eboot "$EBOOT" --icon "$TMP/icon_143.png"
red   "$PY" tools/pbp_gate.py --eboot "$EBOOT" --icon "$OLD"
red   "$PY" tools/pbp_gate.py --eboot "$TMP/EBOOT_oldicon.PBP"
# правка 146: прежняя плитка с «v.0.1» и «PSP» (icon0.py --text keep, раскладка правки 68) — красная
"$PY" tools/icon0.py --text keep --align right --out "$TMP/icon_text.png" > /dev/null
red   "$PY" tools/pbp_gate.py --eboot "$EBOOT" --icon "$TMP/icon_text.png"
# правка 146: подпись в XMB прежняя («SHAR Springfield Viewer») — EBOOT с прежним PARAM.SFO красный
pspdev/bin/mksfoex -d MEMSIZE=1 -s APP_VER= "SHAR Springfield Viewer" "$TMP/PARAM_old.SFO" > /dev/null
"$PY" tools/pbp_art.py "$EBOOT" "$TMP/EBOOT_oldtitle.PBP" --sfo "$TMP/PARAM_old.SFO" > /dev/null
red   "$PY" tools/pbp_gate.py --eboot "$TMP/EBOOT_oldtitle.PBP"
if [ -f build/assets/pic1-source-rob.png ]; then   # правка 132: прежний фон (2,03, Мардж под значками) и Мардж под значками при 2,45
  "$PY" tools/pic1.py --shift 28 --zoom 2.03 --x0 1 --y0 84 --out "$TMP/pic1_old.png" > /dev/null
  red   "$PY" tools/pbp_gate.py --eboot "$EBOOT" --pic1 "$TMP/pic1_old.png"
  "$PY" tools/pic1.py --marge-x 120 --out "$TMP/pic1_under.png" > /dev/null
  red   "$PY" tools/pbp_gate.py --eboot "$EBOOT" --pic1 "$TMP/pic1_under.png"
else echo "  (нет обложки build/assets/pic1-source-rob.png — фон правки 132 не проверяется)"; fi
if [ -f build/assets/icon1.pmf ]; then   # правка Роба 110: живой значок XMB ICON1.PMF (tools/icon1.py)
  : > "$TMP/empty.pmf"; "$PY" tools/pbp_art.py "$EBOOT" "$TMP/EBOOT_noicon1.PBP" --icon1 "$TMP/empty.pmf" > /dev/null
  "$PY" -c "d = bytearray(open('$ROOT/build/assets/icon1.pmf', 'rb').read()); d[:4] = b'PSMX'; open('$TMP/icon1_bad.pmf', 'wb').write(d)"
  "$PY" tools/pbp_art.py "$EBOOT" "$TMP/EBOOT_badicon1.PBP" --icon1 "$TMP/icon1_bad.pmf" > /dev/null
  red   "$PY" tools/pbp_gate.py --eboot "$TMP/EBOOT_noicon1.PBP"
  red   "$PY" tools/pbp_gate.py --eboot "$TMP/EBOOT_badicon1.PBP" --icon1 "$TMP/icon1_bad.pmf"
  red   "$PY" tools/icon1.py --verify "$TMP/icon1_bad.pmf"
  # правка 131: прежний 5-секундный значок (куски из intro) — красный в EBOOT и в гейте монтажа
  CUTS_OLD="$("$PY" -c 'import sys; sys.path.insert(0, "tools"); import icon1; print(icon1.CUTS_OLD)')"
  "$PY" tools/icon1.py --cuts "$CUTS_OLD" --out "$TMP/icon1_old.pmf" > /dev/null
  "$PY" tools/pbp_art.py "$EBOOT" "$TMP/EBOOT_oldicon1.PBP" --icon1 "$TMP/icon1_old.pmf" > /dev/null
  red   "$PY" tools/pbp_gate.py --eboot "$TMP/EBOOT_oldicon1.PBP" --icon1 "$TMP/icon1_old.pmf"
  red   "$PY" tools/icon1.py --check-cuts "$TMP/icon1_old.pmf"
  # монтаж нынешний, но последний кусок испорчен: с видоискателем «DEMO» / через склейку 14,08 с / спокойный интерьер
  CUTS_NOW="$("$PY" -c 'import sys; sys.path.insert(0, "tools"); import icon1; print(icon1.CUTS)')"
  red   "$PY" tools/icon1.py --check "${CUTS_NOW%,*},demo:37.20:1.40:0.50"
  red   "$PY" tools/icon1.py --check "${CUTS_NOW%,*},demo:13.50:1.40:0.50"
  red   "$PY" tools/icon1.py --check "${CUTS_NOW%,*},demo:44.20:1.40:0.50"
  green "$PY" tools/icon1.py --check "$CUTS_NOW"
  green "$PY" tools/icon1.py --verify build/assets/icon1.pmf
  green "$PY" tools/icon1.py --check-cuts build/assets/icon1.pmf
else echo "  (нет build/assets/icon1.pmf — живой значок не проверяется; собрать: tools/icon1.py)"; fi
# правка 130: музыка XMB SND0.AT3 (tools/snd0.py): PCM-WAV вместо ATRAC3 — красный; без SND0 при --need-snd0 — красный
"$PY" -c "
import struct; pcm = bytes(44100 * 4 * 12)
open('$TMP/snd0_pcm.at3', 'wb').write(b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 2, 44100, 176400, 4, 16) + b'data' + struct.pack('<I', len(pcm)) + pcm)"
red   "$PY" tools/snd0.py --verify "$TMP/snd0_pcm.at3"
if [ -f build/assets/snd0.at3 ]; then
  : > "$TMP/empty.at3"; "$PY" tools/pbp_art.py "$EBOOT" "$TMP/EBOOT_nosnd0.PBP" --snd0 "$TMP/empty.at3" > /dev/null
  red   "$PY" tools/pbp_gate.py --eboot "$TMP/EBOOT_nosnd0.PBP" --need-snd0
  green "$PY" tools/snd0.py --verify build/assets/snd0.at3 --src
  green "$PY" tools/pbp_gate.py --eboot "$EBOOT" --need-snd0
else
  red   "$PY" tools/pbp_gate.py --eboot "$EBOOT" --need-snd0
  echo "  (нет build/assets/snd0.at3 — музыка XMB не собрана: нужен кодировщик atracdenc, tools/snd0.py; правка 130 открыта)"
fi
green "$PY" tools/pbp_gate.py --eboot "$EBOOT"
[ $BAD = 0 ] && echo "xmb: OK (итоги в ${TMP#$ROOT/})" || echo "xmb: FAIL (итоги в ${TMP#$ROOT/})"
exit $BAD
