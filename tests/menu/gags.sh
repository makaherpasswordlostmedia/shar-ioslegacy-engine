#!/bin/bash
# Гейт №404 (Роб 08.10: «пасхалки меню — прохожие заглядывают в окно, Мэгги ползает»), Мак, безголовый эмулятор (~3 мин).
#   tests/menu/gags.sh [EBOOT]     (по умолчанию viewer/build/EBOOT.PBP; FE=путь к fe.shr, по умолчанию build/fe.shr)
# 1) экспортёр: tools/frontend3d_export.py --check FE не трогаем здесь (свой гейт); тут — таблица GAG1 и превью из данных;
# 2) ЗЕЛЁНЫЙ: сценарий tests/menu/gags_scenario.txt (SMOKE_HEADLESS=1): база меню, первая сценка сама на 15 с (расписание
#    SLES_518.97), каждая из 8 принудительно в позе — tests/menu/gags_check.py: сценка видна там, куда её ставит сцена диска;
# 3) КРАСНЫЙ: EBOOT с -DFE_GAGS_OLD=1 (прежнее: сценок нет) на тех же данных обязан упасть.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; OUT=build/gates/404; mkdir -p "$OUT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
EB="${1:-viewer/build/EBOOT.PBP}"; FE="${FE:-build/fe.shr}"
[ -f "$EB" ] && [ -f "$FE" ] || { echo "FAIL: нет $EB или $FE"; exit 2; }
echo "EBOOT $(shasum -a 256 "$EB" | cut -c1-8); fe.shr $(shasum -a 256 "$FE" | cut -c1-8)"
psp-cmake -S viewer -B "$OUT/red_build" -DCMAKE_C_FLAGS="-DFE_GAGS_OLD=1" > "$OUT/red_cmake.txt" 2>&1 &&
  cmake --build "$OUT/red_build" > "$OUT/red_build.txt" 2>&1 || { echo "FAIL: красная сборка не собралась ($OUT/red_build.txt)"; exit 2; }
run() {   # имя EBOOT -> папка прогона smoke (build/smoke/<время>)
  local d="$OUT/$1"; rm -rf "$d"; mkdir -p "$d"; cp "$2" "$d/EBOOT.PBP"; cp "$FE" "$d/fe.shr"
  local log; log=$(SMOKE_HEADLESS=1 SMOKE_SCN="$ROOT/tests/menu/gags_scenario.txt" tools/smoke.sh "$d" 2>&1)
  echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
}
G=$(run green "$EB"); R=$(run red "$OUT/red_build/EBOOT.PBP")
[ -f "$G/smoke.txt" ] && [ -f "$R/smoke.txt" ] || { echo "FAIL: прогон не отработал ($G, $R)"; exit 2; }
"$PY" tests/menu/gags_check.py "$G" --fe "$FE" > "$OUT/green.txt" 2>&1; rg=$?
"$PY" tests/menu/gags_check.py "$R" --fe "$FE" --expect-fail > "$OUT/red.txt" 2>&1; rr=$?
echo "зелёный: $(head -1 "$OUT/green.txt" | cut -c1-200)"; tail -n +2 "$OUT/green.txt"
echo "красный (-DFE_GAGS_OLD=1): $(head -1 "$OUT/red.txt" | cut -c1-200)"
echo "снимки: ${G#$ROOT/} (зелёный), ${R#$ROOT/} (красный)"
if [ $rg -eq 0 ] && [ $rr -eq 0 ]; then echo "ИТОГ: PASS (8 сценок видны там, где их ставит сцена диска; первая — на 15 с; красный пойман)"; exit 0; fi
echo "ИТОГ: FAIL (зелёный rc=$rg, красный пойман=$([ $rr -eq 0 ] && echo да || echo НЕТ))"; exit 1
