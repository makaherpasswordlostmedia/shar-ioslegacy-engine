#!/bin/bash
# Гейт «круг клеток RESUME» (аудит времени загрузки 16.10): на RESUME игрок стартует у своей миссии (L1: в 562 м от spawnP), фоновый круг у spawnP читался зря (240 клеток, 7 МБ, 238 выброшено).
#   tests/levels/resume_ring.sh EBOOT НАБОР   красный: файл resumeringold (прежнее) — строка «CELLRING released=… far=…» и bgkb > 0 обязаны быть; зелёный: released нет, bgkb = 0.
#   Сценарий — tests/levels/start_news_resume.txt (режим игрока, RESUME на записи в ~/.ppsspp, flag nosave: только чтение). Цифры мс — ориентир эмулятора, итог на железе
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EB=${1:?EBOOT.PBP}; PK=${2:?НАБОР}; T="$ROOT/build/gates/resume_ring/$(date +%H%M%S)"; mkdir -p "$T"
P="$T/pk"; cp -cR "$PK" "$P" 2>/dev/null || cp -R "$PK" "$P"; cp "$EB" "$P/EBOOT.PBP"; trap 'rm -rf "$P"' EXIT
one() { ( SMOKE_FLAGS="$2" SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_FILEDATA="meaudio=3" SMOKE_SCN="$ROOT/tests/levels/start_news_resume.txt" SMOKE_MAXT=${MAXT:-200} tools/smoke.sh "$P" ) > "$T/$1.out" 2>&1
  D="$ROOT/$(sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' "$T/$1.out" | tail -1)"
  rel=$(grep -c '^CELLRING released=' "$D/smoke.txt"); bg=$(sed -n 's/^CELLRING cells=.* bgkb=\([0-9]*\).*/\1/p' "$D/smoke.txt" | head -1)
  rd=$(sed -n 's/^LOADREAD ms=\([0-9]*\).*/\1/p' "$D/smoke.txt" | head -1); gm=$(sed -n 's/^GAME n=.* ms=\([0-9]*\) .*/\1/p' "$D/smoke.txt" | head -1)
  echo "$1: released_строк=$rel bgkb=${bg:--} LOADREAD=${rd:--} мс GAME=${gm:--} мс"; eval "$1_rel=$rel; $1_bg=${bg:-0}"; }
one red resumeringold; one green ""
[ "$red_rel" -ge 1 ] && [ "$red_bg" -gt 0 ] && [ "$green_rel" = 0 ] && [ "$green_bg" = 0 ] && { echo "КРУГ RESUME: PASS"; exit 0; }
echo "КРУГ RESUME: FAIL"; exit 1
