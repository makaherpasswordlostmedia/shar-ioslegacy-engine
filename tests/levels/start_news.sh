#!/bin/bash
# Гейт №663 «газета на старте из меню» (Роб, видео TEST26: «почему нет заставки газеты»; 5,6 с чёрного после RESUME). Путь игрока: титул → Start → меню → RESUME GAME / NEW GAME.
#   tests/levels/start_news.sh EBOOT НАБОР   (EBOOT — тур-сборка с KEEP_SMOKE; НАБОР — папка данных с level.shr, как build/t26; RESUME нужно сохранение в ~/.ppsspp/PSP/SAVEDATA)
#   красный: «flag startnewsold 1» (поведение магистрали cce625d4: ирис без экрана загрузки) — служебный снимок news_2s (flag newsshot) ЧЁРНЫЙ -> обязан упасть
#   зелёный: по умолчанию — снимок news_2s изнутри экрана загрузки на часах газеты ≥2 с не чёрный (яркость ≥30) на обоих входах; смена уровня — tests/levels/switch.sh (газета там всегда)
# Первая строка вывода — итог, код 0 = OK
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EB=${1:?EBOOT.PBP}; PK=${2:?НАБОР}; T="$ROOT/build/gates/start_news/$(date +%H%M%S)"; mkdir -p "$T"
cp -cR "$PK" "$T/pk" 2>/dev/null || cp -R "$PK" "$T/pk"; cp "$EB" "$T/pk/EBOOT.PBP"; trap 'rm -rf "$T/pk"' EXIT
run() {   # имя сценарий  -> папка отчёта
  ( SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_FILEDATA="meaudio=3" SMOKE_SCN="$2" SMOKE_MAXT=120 tools/smoke.sh "$T/pk" ) > "$T/$1.out" 2>&1
  echo "$ROOT/$(sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' "$T/$1.out" | tail -1)"   # свой каталог отчёта (рядом идут прогоны других окон)
}
check() {   # папка -> «news» (кадр news_2s не чёрный и путь news) | «black» (кадр чёрный) | «none»; закон 7: по кадру, не по журналу
  local d="$1" p m; p=$(sed -n 's/^STARTNEWS path=\([a-z]*\).*/\1/p' "$d/smoke.txt" | head -1)
  m=$("$ROOT/.venv/bin/python" -c "from PIL import Image,ImageStat;import sys;print(int(sum(ImageStat.Stat(Image.open(sys.argv[1]).convert('L')).mean)))" "$d/news_2s.png" 2>/dev/null) || m=-1
  if [ "$m" = -1 ]; then echo none; elif [ "$m" -ge 30 ] && [ "$p" = news ]; then echo news; elif [ "$m" -le 5 ]; then echo black; else echo "dim$m"; fi
}
ok=1; out=""
for e in resume new; do
  scn="tests/levels/start_news_$e.txt"; { echo "flag startnewsold 1"; cat "$scn"; } > "$T/red_$e.txt"
  r=$(check "$(run red_$e "$T/red_$e.txt")"); g=$(check "$(run green_$e "$ROOT/$scn")")
  [ "$r" = black ] && [ "$g" = news ] || ok=0
  out="$out $e: красный=$r зелёный=$g;"
done
[ $ok = 1 ] && { echo "СТАРТ ГАЗЕТА: PASS ($out )"; exit 0; } || { echo "СТАРТ ГАЗЕТА: FAIL ($out )"; exit 1; }
