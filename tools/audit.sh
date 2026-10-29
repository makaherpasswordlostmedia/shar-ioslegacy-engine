#!/bin/bash
# Общая проверка проекта одной командой (аудит 28.09): все гейты и тесты на процессоре Мака, итог — таблица PASS/FAIL.
#   tools/audit.sh            всё, кроме эмулятора
#   tools/audit.sh --emu      + эмулятор: честный счётчик кучи (tests/heap) и смоук выпуска (tools/ship.sh --no-install)
# Каждый гейт сам показывает красный контроль (подложенная ошибка обязана поймать) и зелёный. Ничего не ставит на PSP,
# build/ не трогает (выпуск — только --no-install). Итог: build/audit/<время>/summary.txt, логи каждого пункта рядом.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
OUT="build/audit/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$OUT"; SUM="$OUT/summary.txt"; : > "$SUM"
EMU=0; [ "${1:-}" = --emu ] && EMU=1
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
run() {   # run ИМЯ ОЖИДАНИЕ КОМАНДА...: ОЖИДАНИЕ — строка, которая обязана быть в выводе (иначе FAIL), или «код0»
  local name="$1" want="$2"; shift 2; local t0=$(date +%s)
  "$@" > "$OUT/$name.log" 2>&1; local rc=$?
  local ok=0
  if [ "$want" = код0 ]; then [ $rc = 0 ] && ok=1; else grep -q -- "$want" "$OUT/$name.log" && ok=1; fi
  printf '%-22s %-4s %4ss  %s\n' "$name" "$([ $ok = 1 ] && echo PASS || echo FAIL)" "$(( $(date +%s) - t0 ))" "$(grep -v '^\s*$' "$OUT/$name.log" | tail -1 | cut -c1-110)" | tee -a "$SUM"
}
echo "# аудит $(date '+%Y-%m-%d %H:%M'), git $(git rev-parse --short HEAD)" | tee -a "$SUM"
BINS="game_headless nav missioner explorer chase longworld" tools/bots/build.sh > "$OUT/build-bots.log" 2>&1 || echo "сборка ботов FAIL" | tee -a "$SUM"
# движок на Маке: host-тесты
for t in tests/*/host.sh; do n=$(basename "$(dirname "$t")")
  if [ "$n" = movie ] && ! ls build/movies/*.smv >/dev/null 2>&1 && ls build/ship_stage/movies/*.smv >/dev/null 2>&1; then
    run "host-$n" код0 bash "$t" build/ship_stage/movies/*.smv   # ролики ещё не установлены в build/ — из набора поставки
  else run "host-$n" код0 bash "$t"; fi
done
# боты: Б0 детерминизм и save/load, Б1 навигатор, Б2 миссионер, Б3 каскадёр, Б4 догонялки, 10б длинный мир, 11.2 комнаты
run b0-selftest "RESULT: OK" build/bots/game_headless build/level.shr build/homer.shr --selftest --secs 30
run b1-nav "PASS" build/bots/nav build/level.shr build/homer.shr build/sandbox/roads-l1.bin --gate --gens 40 --pop 24 --out "$OUT/nav"
run b2-missions "PASS" python3 tools/bots/missions.py --gate
run b3-explorer "RESULT: OK" python3 tools/bots/explorer.py --gate
run b4-chase "RESULT: OK" python3 tools/bots/chase.py --gate
run 10b-longworld "PASS" tests/longworld/run.sh
run 11.2-rooms "PASS" tests/rooms/run.sh
# полигон: предметы (оракул, аномалия удара с подложенным разгоном), маршруты трамплинов (контроли)
run 10a-props-gate "PASS" $PY tools/cartest/props_sweep.py --gate --out "$OUT/props-sweep.json"
run 10a-props-plant "аномалий" $PY -c "import json,subprocess,sys; subprocess.run([sys.executable,'tools/cartest/props_sweep.py','--plant-kick','4','--out','$OUT/props-plant.json'],capture_output=True); r=json.load(open('$OUT/props-plant.json')); n=sum(v['flew'] for v in r['prp1'].values()); print('подложенный разгон x4: аномалий', n); sys.exit(0 if n>0 else 1)"
# табло и бюджет входа
run tablo-check "проверка: OK" python3 tools/tablo.py --check
if [ $EMU = 1 ]; then
  run 12b-heap-emu "PASS" tests/heap/run.sh
  run ship-smoke "смоук OK" tools/ship.sh --no-install
fi
echo "итог: PASS $(grep -c ' PASS ' "$SUM"), FAIL $(grep -c ' FAIL ' "$SUM") -> $SUM" | tee -a "$SUM"
