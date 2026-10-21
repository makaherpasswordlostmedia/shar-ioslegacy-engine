#!/bin/bash
# Набор «загрузка как в TEST26»: копия набора теста + файлы-выключатели нового в пути загрузки (газета на RESUME и музыка уровня остаются).
#   tools/test26load_set.sh НАБОР ВЫХОД   — файлы: bbsyncold (ящик синхронный), resumeringold (круг клеток как раньше), regprehystold (REGPRE без гистерезиса),
#   pfetchold, prereadold (фоновые чтения выключены). loadwaitold НЕ кладётся: страховка SignalSema нужна всегда.
set -eu
SRC=${1:?набор}; OUT=${2:?выход}; [ -e "$OUT" ] && { echo "уже есть: $OUT"; exit 1; }
cp -cR "$SRC" "$OUT" 2>/dev/null || cp -R "$SRC" "$OUT"
for f in bbsyncold resumeringold regprehystold pfetchold prereadold; do : > "$OUT/$f"; done
echo "OK: $OUT (+ bbsyncold resumeringold regprehystold pfetchold prereadold)"
