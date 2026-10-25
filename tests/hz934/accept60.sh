#!/bin/bash
# ПРИЁМКА №928б + №934в (окно «Даль», ветка t60/dal). Одна команда:  tests/hz934/accept60.sh      последняя строка: PASS или FAIL
# Что проверяется (у каждого гейта есть красный контроль, он обязан падать):
#   1 данные    horizon.shr на 7 уровнях (папка data_dal): есть, свежее экспортёра; нет — собирает tools/horizon_export.py (≈8 мин при 4 параллельных)
#   2 формат    tests/hz934/fmt.py: подвал DSTF, размер и хвост кратны 4 (PSP падает на невыровненном u32), счётчики; красные: урезан на байт, подвал затёрт, счётчик −1
#   3 №928б     tests/horizon/lmq928.py: карточки ориентиров не шире настоящего здания >1,5× на 7 уровнях; красное — прежний профиль из набора TEST59
#   4 №934в     tools/hz934_jump.py на 7 уровнях: p90 скачка ленты за шаг 3 м ≤ 5°; красное — прежняя лента (--old) обязана упасть
#   5 сборка    EBOOT тура (со смоуком) и красный EBOOT (все три флага *_OLD=1), база (aa092b71) для кучи, EBOOT «все столбцы» для красного цены
#   6 движок    скачок в эмуляторе (строки HZE): L1, L3, L5 глаз идёт шагом 3 м через границу клеток на худших перепадах, мировая ≤ 5°, прежняя > 5° (красное в том же прогоне); красный EBOOT HZ_WORLD934_OLD=1 даёт прежнюю ленту
#   7 №928б     L6 пирс C7-6: ориентиры видны (> 200 пикселей разницы hzlm 1/0), красное — файл без ориентиров (0)
#   8 цена      в езде L1, L3, L5: мировая − прежняя (медиана окон) × 5,8 ≤ 200 мкс PSP и вершин ленты ≤ 1,6× прежних; красное — EBOOT «все 181 столбец» на L1 (724 вершины против 148) обязан не пройти
#   9 куча      7 уровней: куча сразу после загрузки ленты (строка HZLOAD, байты) не хуже базы aa092b71 на 10 КБ, минимум в городе на 0,02 МБ; красное — тот же EBOOT с ballast 1 МБ
#   HZ_QUICK=1  пропустить 8 и 9 (цена и куча, ≈ 20 мин эмулятора)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH; export PSPDEV=$ROOT/pspdev PATH=$ROOT/pspdev/bin:$PATH
PY=$ROOT/.venv/bin/python; SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test59tour/PSP/GAME/SHARTEST15}
D=${HZDATA:-$HOME/Downloads/shar-psp/build/t60/data_dal}; BASE_REV=${BASE_REV:-aa092b71}
A=${ACC_OUT:-${TMPDIR:-/tmp}/hz934_accept}; rm -rf "$A"; mkdir -p "$A"; export EMU_OWNER=dal OUT=$A; export EMU_MINE=${EMU_MINE:-2}
want() { [ -z "${HZ_ONLY:-}" ] || [[ " $HZ_ONLY " == *" $1 "* ]]; }   # HZ_ONLY="9" — только шаг 9 (после правки одного гейта; итог всё равно PASS/FAIL по выполненным)
FAIL=0; say() { echo "[$(date +%H:%M:%S)] $*"; }
res() { if [ "$1" = 0 ]; then say "  ok   $2"; else say "  ПАДАЕТ $2"; FAIL=1; fi; }
f1() { [ "$1" = 1 ] && echo "$D/horizon.shr" || echo "$D/l$1/horizon.shr"; }
emu() { # emu ИМЯ СЦЕНАРИЙ EBOOT [OVL] [FLAGS]  — в фоне; общий предел эмуляторов держит emu_run
  ( OVL="${4:-}" FLAGS="${5:-}" "$ROOT/tools/emu_run.sh" "$2" "$1" "$3" ${EMU_T:-420} > "$A/emu_$1.log" 2>&1 ) & }
# --- 1 данные
say "1 данные horizon.shr ($D)"; mkdir -p "$D/l2" "$D/l3" "$D/l4" "$D/l5" "$D/l6" "$D/l7"; need=""
for L in 1 2 3 4 5 6 7; do f=$(f1 $L); { [ -s "$f" ] && [ "$f" -nt tools/horizon_export.py ]; } || need="$need $L"; done
if [ -n "$need" ]; then say "  собираю уровни:$need"; mkdir -p "$D/logs"
  for L in $need; do if [ $L = 1 ]; then LV=$SET/level.shr; else LV=$SET/l$L/level.shr; fi; echo "$LV $(f1 $L) $L"; done | xargs -P 4 -L 1 bash -c 'cd '"$ROOT"' && '"$PY"' tools/horizon_export.py "$0" --out "$1" --cell 60 --lvl "$2" --near 130 --near2 150 --radius 134 > '"$D"'/logs/exp_l$2.log 2>&1'
fi
n=0; for L in 1 2 3 4 5 6 7; do [ -s "$(f1 $L)" ] && n=$((n + 1)); done; [ $n = 7 ]; res $? "7 файлов horizon.shr"
# --- 2 формат
say "2 формат DST2"; F=(); for L in 1 2 3 4 5 6 7; do F+=("$(f1 $L)"); done
$PY tests/hz934/fmt.py "${F[@]}" | tail -1; $PY tests/hz934/fmt.py "${F[@]}" > /dev/null; res $? "формат всех семи"
$PY tests/hz934/fmt.py --red "$D/l3/horizon.shr" | tail -1; $PY tests/hz934/fmt.py --red "$D/l3/horizon.shr" > /dev/null; res $? "красный: порча формата поймана"
# --- 3 №928б
say "3 №928б ориентиры (lmq928)"; mkdir -p "$A/lmq/new" "$A/lmq/old"
for L in 1 2 3 4 5 6 7; do ln -s "$(f1 $L)" "$A/lmq/new/l$L.shr"; [ $L = 1 ] && ln -s "$SET/horizon.shr" "$A/lmq/old/l1.shr" || ln -s "$SET/l$L/horizon.shr" "$A/lmq/old/l$L.shr"; done
$PY tests/horizon/lmq928.py "$SET" "$A/lmq/new" "$A/lmq/old" | tee "$A/lmq.txt" | tail -3; [ "$(tail -1 "$A/lmq.txt")" = PASS ]; res $? "lmq928 PASS и красный (прежний профиль) красный"
# --- 4 №934в аналитика
say "4 №934в скачок ленты, аналитика (tools/hz934_jump.py)"; ok=0; rd=0
for L in 1 2 3 4 5 6 7; do f=$(f1 $L); o=$($PY tools/hz934_jump.py "$f" | grep "ИТОГ"); $PY tools/hz934_jump.py "$f" > /dev/null || ok=1; r=$($PY tools/hz934_jump.py "$f" --old | grep "ИТОГ"); $PY tools/hz934_jump.py "$f" --old > /dev/null && rd=1; echo "  L$L  $o"; echo "      $r"; done
res $ok "мировая лента ≤ 5° на всех семи"; res $rd "красное: прежняя лента падает на всех семи"
# --- 5 сборка
say "5 сборка"; B() { # B ПАПКА ФЛАГИ [КОРЕНЬ]
  local R=${3:-$ROOT}; ( cd "$R/viewer" && { [ -d "$1" ] || psp-cmake -S . -B "$1" -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1 $2" > /dev/null 2>&1; } && cmake --build "$1" -j4 > "$A/build_$(basename $1).log" 2>&1 ); }
B build_t60 ""; res $? "EBOOT тура"; EB=$ROOT/viewer/build_t60/EBOOT.PBP
B build_t60_old "-DHZ_WORLD934_OLD=1 -DHZ_VB934_OLD=1 -DHZ_WCOLS934_OLD=1"; res $? "EBOOT с флагами OLD"; EBO=$ROOT/viewer/build_t60_old/EBOOT.PBP
if [ -z "${HZ_QUICK:-}" ]; then
  B build_t60_allcols "-DHZ_WCOLS934_OLD=1"; res $? "EBOOT все столбцы (красный цены)"; EBA=$ROOT/viewer/build_t60_allcols/EBOOT.PBP
  mkdir -p "$A/base" && git archive $BASE_REV viewer tools | tar -x -C "$A/base" && ln -sfn "$ROOT/build" "$A/base/build"
  $PY - "$A/base/viewer/horizon.h" <<'PYEOF'
import sys; p = sys.argv[1]; s = open(p).read(); a = "  hzData = m; hzSize = (unsigned)sz; hzN = n;"; assert s.count(a) == 1; k = s.index("\n", s.index(a))
s = s[:k] + '\n  if (smkOn) { char s_[96]; snprintf(s_, sizeof s_, "HZLOAD level=%d bytes=%u dst=%d free=%u\\n", level, (unsigned)sz, 0, heapFreeBytes()); smkWrite(s_); }' + s[k:]; open(p, 'w').write(s)   # та же строка кучи, что у новой сборки (базе её нет)
PYEOF
  B build_t60 "" "$A/base"; res $? "EBOOT базы $BASE_REV"; EBB=$A/base/viewer/build_t60/EBOOT.PBP
fi
# --- 6 движок: скачок
if want 6; then
say "6 №934в скачок ленты в эмуляторе (HZE)"
for L in 1 3 5; do $PY tests/hz934/scn.py $L "$(f1 $L)" 2 3 > "$A/jump_l$L.txt"; mkdir -p "$A/ovl"; done
mkdir -p "$A/ovl_all"; cp "$D/horizon.shr" "$A/ovl_all/horizon.shr"; for L in 2 3 4 5 6 7; do mkdir -p "$A/ovl_all/l$L"; cp "$D/l$L/horizon.shr" "$A/ovl_all/l$L/"; done
for L in 1 3 5; do emu j$L "$A/jump_l$L.txt" "$EB" "$A/ovl_all"; done; wait
for L in 1 3 5; do $PY tests/hz934/jump.py "$A/out_j$L/smoke.txt" | tee "$A/jump_$L.txt" | tail -3; $PY tests/hz934/jump.py "$A/out_j$L/smoke.txt" > /dev/null; res $? "L$L мировая ≤ 5°"; $PY tests/hz934/jump.py "$A/out_j$L/smoke.txt" --red > /dev/null; res $? "L$L красное: прежняя лента в том же прогоне > 5°"; done
grep -v "flag hzworld" "$A/jump_l1.txt" > "$A/jump_l1_old.txt"; emu jo1 "$A/jump_l1_old.txt" "$EBO" "$A/ovl_all"; wait; $PY tests/hz934/jump.py "$A/out_jo1/smoke.txt" --oldbuild | tail -2; $PY tests/hz934/jump.py "$A/out_jo1/smoke.txt" --oldbuild > /dev/null; res $? "EBOOT с флагами OLD рисует только прежнюю ленту (прежний скачок на месте)"
fi
# --- 7 №928б в движке
if want 7; then
say "7 №928б ориентир виден в кадре (L6)"; mkdir -p "$A/ovl_nolm/l6"; cp "$D/l6/horizon.shr" "$A/ovl_nolm/l6/horizon.shr"
$PY - "$A/ovl_nolm/l6/horizon.shr" <<'PYEOF'
import sys, struct; p = sys.argv[1]; b = bytearray(open(p, 'rb').read()); struct.pack_into('<I', b, 12, 0); open(p, 'wb').write(bytes(b))   # nl = 0: ориентиров нет, остальное прежнее
PYEOF
emu lmn tests/hz934/lm_scn.txt "$EB" "$A/ovl_all"; emu lmo tests/hz934/lm_scn.txt "$EB" "$A/ovl_nolm"; wait
pn=$($PY tests/hz934/lmpx.py "$A/out_lmn" 2>/dev/null || echo 0); po=$($PY tests/hz934/lmpx.py "$A/out_lmo" 2>/dev/null || echo 999); say "  пикселей силуэта: с ориентирами $pn, без $po"
[ "$pn" -gt 200 ]; res $? "ориентиры видны (> 200 пикселей)"; [ "$po" -lt 20 ]; res $? "красное: без ориентиров < 20 пикселей"
fi
if [ -z "${HZ_QUICK:-}" ]; then
# --- 8 цена
  if want 8; then
  say "8 цена ленты в езде (Мак × 5,8)"
  for L in 1 3 5; do tests/hz934/cost_scn.sh $L > "$A/cost_l$L.txt"; done
  emu c1 "$A/cost_l1.txt" "$EB" "$A/ovl_all"; emu c3 "$A/cost_l3.txt" "$EB" "$A/ovl_all"; emu c5 "$A/cost_l5.txt" "$EB" "$A/ovl_all"; emu c1a "$A/cost_l1.txt" "$EBA" "$A/ovl_all"; wait
  for L in 1 3 5; do $PY tests/hz934/cost.py "$A/out_c$L/smoke.txt"; $PY tests/hz934/cost.py "$A/out_c$L/smoke.txt" > /dev/null; res $? "L$L цена ≤ 200 мкс PSP"; done
  say "  красное: все 181 столбец на L1"; $PY tests/hz934/cost.py "$A/out_c1a/smoke.txt" | tail -2; $PY tests/hz934/cost.py "$A/out_c1a/smoke.txt" > /dev/null; [ $? != 0 ]; res $? "красное: EBOOT «все столбцы» не проходит предел цены"
  fi
# --- 9 куча
  if want 9; then
  say "9 куча уровней не хуже базы $BASE_REV"
  for L in 1 2 3 4 5 6 7; do tests/hz934/heap_scn.sh $L > "$A/heap_l$L.txt"; done
  for L in 1 2 3 4 5 6 7; do emu hb$L "$A/heap_l$L.txt" "$EBB" ""; emu hn$L "$A/heap_l$L.txt" "$EB" "$A/ovl_all"; wait; done
  emu hr3 "$A/heap_l3.txt" "$EB" "$A/ovl_all" "ballast=1"; wait
  for L in 1 2 3 4 5 6 7; do echo -n "  "; $PY tests/hz934/heap.py "$A/out_hb$L/smoke.txt" "$A/out_hn$L/smoke.txt" $L; $PY tests/hz934/heap.py "$A/out_hb$L/smoke.txt" "$A/out_hn$L/smoke.txt" $L > /dev/null; res $? "L$L куча не хуже базы"; done
  $PY tests/hz934/heap.py "$A/out_hb3/smoke.txt" "$A/out_hr3/smoke.txt" 3 --expect-fail | tail -1; $PY tests/hz934/heap.py "$A/out_hb3/smoke.txt" "$A/out_hr3/smoke.txt" 3 --expect-fail > /dev/null; res $? "красное: ballast 1 МБ краснит гейт кучи"
  fi
fi
if [ $FAIL = 0 ]; then echo "ПРИЁМКА №928б + №934в: PASS"; echo PASS; else echo "ПРИЁМКА №928б + №934в: FAIL"; echo FAIL; fi
exit $FAIL
