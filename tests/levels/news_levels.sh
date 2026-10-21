#!/bin/bash
# Гейт №663 «газета своего уровня»: для N=1..7 кадр газеты (flag newsshot, news_2s) на двух входах — (а) RESUME GAME с сохранением на уровне N, (б) NEW GAME/смена на уровень N (flag lvset N) —
# против loadingN.png с диска (dynaload/images/loading/loadingN.p3d). Сохранения — в СВОЁМ HOME эмулятора (SMOKE_HOME), личные карты не трогаются.
#   tests/levels/news_levels.sh EBOOT НАБОР [ВЫХОД]      LEVELS="2 3" — только эти уровни (по умолчанию 1..7); RED=1 — красный контроль: flag newslvred 1 (газета всегда уровня 1), гейт обязан упасть
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EB=${1:?EBOOT.PBP}; PK=${2:?НАБОР}; T=${3:-$ROOT/build/gates/news_levels/$(date +%H%M%S)}; LV=${LEVELS:-1 2 3 4 5 6 7}
mkdir -p "$T/disk" "$T/res" "$T/scn"; P="$T/pk"; cp -cR "$PK" "$P" 2>/dev/null || cp -R "$PK" "$P"; cp "$EB" "$P/EBOOT.PBP"; trap 'rm -rf "$P"' EXIT
"$ROOT/.venv/bin/python" -I - "$T/disk" <<'PY'
import sys; sys.path[:0] = ['tools', 'hit-and-run-web/tools']
import load_export as L
for n in range(1, 8):
    L.sprite_images(L.GAME / ('dynaload/images/loading/loading%d.p3d' % n))['loading%d.png' % n].convert('RGB').save('%s/loading%d.png' % (sys.argv[1], n))
PY
run() {   # имя сценарий HOME -> папка отчёта
  ( SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_HOME="$3" SMOKE_FILEDATA="meaudio=3" SMOKE_SCN="$2" SMOKE_MAXT=${MAXT:-240} tools/smoke.sh "$P" ) > "$T/$1.out" 2>&1
  echo "$ROOT/$(sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' "$T/$1.out" | tail -1)"
}
# HOME эмулятора — вне build/ (внутри репозитория запись сохранения падает: SAVEDATA_RW_MEMSTICK_FULL), свой на каждый прогон
HB="$HOME/Downloads/.news_levels_home.$$"; mkdir -p "$HB"; trap 'rm -rf "$P" "$HB"' EXIT
RF=""; [ "${RED:-}" = 1 ] && RF="flag newslvred 1"
for n in $LV; do
  H="$HB/home$n"; rm -rf "$H"
  sed "s/^flag lvset 2$/flag lvset $n/" tests/levels/save_level_save.txt > "$T/scn/save_$n.txt"; run save_$n "$T/scn/save_$n.txt" "$H" > /dev/null
  printf 'flag menu\nflag saves\n%s\nwait 1.5\nflag newsshot 1\npress right\nwait 0.4\npress cross\nwait 8\nend\n' "$RF" > "$T/scn/resume_$n.txt"
  d=$(run resume_$n "$T/scn/resume_$n.txt" "$H"); mkdir -p "$T/res/resume_$n"; cp "$d"/news_2s.png "$d"/smoke.txt "$T/res/resume_$n/" 2>/dev/null
  printf 'flag menu\nflag saves\n%s\nflag lvset %s\nwait 1.5\nflag newsshot 1\npress cross\nwait 8\nend\n' "$RF" "$n" > "$T/scn/new_$n.txt"
  d=$(run new_$n "$T/scn/new_$n.txt" "$H.new"); mkdir -p "$T/res/new_$n"; cp "$d"/news_2s.png "$d"/smoke.txt "$T/res/new_$n/" 2>/dev/null
  echo "L$n готов"
done
"$ROOT/.venv/bin/python" tests/levels/news_levels.py "$T"
