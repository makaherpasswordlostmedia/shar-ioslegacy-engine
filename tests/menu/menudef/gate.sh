#!/bin/bash
# Гейт «меню открывается на RESUME GAME при сохранении» (Sonnet-Типографика, 16.10; факт PS2: knowledge/facts/ps2-resume-save-flow.yaml).
# Безголовый эмулятор (scen.py, свой HOME на сборку), две сборки: новая и -DMENU_RESUME_DEFAULT_OLD=1.
#  а) новая, карта с сохранением (scn_save, затем новый процесс scn_menu): верхняя надпись меню «RESUME GAME»
#  б) новая, пустая карта: «NEW GAME» (кадр как у старой с сохранением: надпись курсора та же)
#  красный контроль: старая сборка с сохранением — надпись «NEW GAME», то есть отличается от (а)
# Надпись курсора сравнивается по верхней полосе кадра (y < 17% высоты): новая+сохранение должна отличаться от остальных, а б == красный по надписи.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; cd "$ROOT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
OUT="${MD_OUT:-$ROOT/build/menudef}"; mkdir -p "$OUT"; SCEN=~/.claude/skills/shar-level-polish/scripts/scen.py
for v in new MENU_RESUME_DEFAULT_OLD; do
  [ "${MD_REUSE:-0}" = 1 ] && [ -f "$OUT/gb/$v/EBOOT.PBP" ] && continue
  ( mkdir -p "$OUT/gb/$v" && cd "$OUT/gb/$v" && OPT=""; [ "$v" != new ] && OPT="-DSHAR_OPT=-D$v=1"
    psp-cmake -S "$ROOT/viewer" -B . $OPT >/dev/null 2>&1 && cmake --build . -j4 >/dev/null 2>&1 ) &
done; wait
run() {  # имя HOME-а, EBOOT, сценарий -> папка прогона
  while [ "$(pgrep -x PPSSPPHeadless | wc -l)" -ge 5 ]; do sleep 20; done
  SCEN_HOME="$1" SCEN_EBOOT="$2" timeout 1500 python3 "$SCEN" "md${$}_$3" "$ROOT/tests/menu/menudef/$4" 2>&1 | sed -n 's/^dir \([^ ]*\) .*/\1/p'; }
for v in new MENU_RESUME_DEFAULT_OLD; do [ -f "$OUT/gb/$v/EBOOT.PBP" ] || { echo "FAIL: нет сборки $v"; exit 2; }; done
rm -rf "$OUT/gb/home_enew" "$OUT/gb/home_eold" "$OUT/gb/home_empty" "$OUT/gb/home_save" "$OUT/gb/home_oldsave"
D_EMPTY=$(run "$OUT/gb/home_empty" "$OUT/gb/new/EBOOT.PBP" empty scn_menu.txt)
run "$OUT/gb/home_save" "$OUT/gb/new/EBOOT.PBP" save scn_save.txt >/dev/null
D_NEW=$(run "$OUT/gb/home_save" "$OUT/gb/new/EBOOT.PBP" newsave scn_menu.txt)
cp -R "$OUT/gb/home_save" "$OUT/gb/home_oldsave" 2>/dev/null
D_OLD=$(run "$OUT/gb/home_oldsave" "$OUT/gb/MENU_RESUME_DEFAULT_OLD/EBOOT.PBP" oldsave scn_menu.txt)
D_ENEW=$(run "$OUT/gb/home_enew" "$OUT/gb/new/EBOOT.PBP" enew scn_empty.txt)
D_EOLD=$(run "$OUT/gb/home_eold" "$OUT/gb/MENU_RESUME_DEFAULT_OLD/EBOOT.PBP" eold scn_empty.txt)
echo "пустая: $D_EMPTY | новая+сохр: $D_NEW | старая+сохр: $D_OLD"
python3 - "$D_EMPTY/menu_default.png" "$D_NEW/menu_default.png" "$D_OLD/menu_default.png" "$D_ENEW" "$D_EOLD" <<'PY'
import sys, numpy as np
from PIL import Image
def band(p):
    a = np.asarray(Image.open(p).convert('RGB')).astype(int); h = a.shape[0]; return a[:int(h*.17)]
e, n, o = (band(p) for p in sys.argv[1:4])
d_no = float(np.abs(n - o).mean()); d_eo = float(np.abs(e - o).mean()); d_en = float(np.abs(e - n).mean())
print(f'верхняя полоса: новая+сохр против старой+сохр {d_no:.2f} (>2 — надпись курсора разная); пустая против старой+сохр {d_eo:.2f} (<2 — обе NEW GAME); пустая против новой+сохр {d_en:.2f}')
ok = d_no > 2 and d_eo < 2 and d_en > 2
en, eo = sys.argv[4], sys.argv[5]
b = lambda d, n: band(f'{d}/{n}.png')
s_new = float(np.abs(b(en, 'e1_right') - b(eo, 'e1_right')).mean())   # чистая карта, ► от NEW GAME: у новой LOAD GAME, у старой серый RESUME GAME
s_start = float(np.abs(b(en, 'e0_start') - b(eo, 'e0_start')).mean())  # стартовый кадр (NEW GAME) одинаков
s_back = float(np.abs(b(en, 'e3_back') - b(en, 'e0_start')).mean())     # ◄◄ после ►► возвращает на NEW GAME (круг без скрытого)
print(f'чистая карта: ► от NEW GAME новая против старой {s_new:.2f} (>2 — другой пункт), старт новая против старой {s_start:.2f} (<2), новая после ►►◄◄ против старта {s_back:.2f} (<2)')
ok = ok and s_new > 2 and s_start < 2 and s_back < 2
print('ИТОГ: PASS (новая+сохранение — другая надпись, пустая карта как раньше, старая красная)' if ok else 'ИТОГ: FAIL'); sys.exit(0 if ok else 1)
PY
