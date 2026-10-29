#!/bin/bash
# Постоянная кампания ботов на АКТУАЛЬНОЙ версии (Роб 01.10 13:20: «боты должны идти на актуальной версии, не только ночью,
# с конкретной задачей; миссии надо проходить»). Идёт на процессоре Мака днём и ночью, без AI и сети.
#   tools/bots/campaign.sh            цикл: версия → миссии → отчёт Робу → ждать новую версию
#   touch build/bots/campaign.stop    остановить после текущего шага
# Шаги цикла:
#   1) версия: HEAD main и build/ship_manifest.txt; изменились — пересобрать ботов (tools/bots/build.sh) от текущего main
#   2) МИССИИ первыми: все миссии уровня 1, по 1500 с на миссию (tools/bots/missions.py) — таблица с названиями
#   3) отчёт Робу ~/Downloads/SHAR_боты_отчёт.md: названия миссий словами, итог, почему, где (код места), версия
#   4) нет новой версии — повтор миссий раз в 2 часа (другие водители и случайность), иначе сразу заново с шага 1
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/bots/campaign; mkdir -p "$OUT"; LOG="$OUT/campaign.log"; REP="$HOME/Downloads/SHAR_боты_отчёт.md"
PROCS="${CAMPAIGN_PROCS:-6}"
log() { echo "$(date '+%F %H:%M') $*" | tee -a "$LOG"; }
ver() { echo "$(grep -m1 '^git' build/ship_manifest.txt | cut -d' ' -f2) $(grep -m1 'EBOOT' build/ship_manifest.txt | cut -c1-8)"; }   # версия = собранная и выложенная сборка (коммиты документов не перезапускают миссии)
last=""; lastRun=0
while [ ! -f build/bots/campaign.stop ]; do
  v=$(ver); now=$(date +%s)
  if [ "$v" != "$last" ]; then
    log "версия $v — пересборка ботов от main"
    if ! bash tools/bots/build.sh > "$OUT/build.txt" 2>&1; then log "сборка ботов упала: $(grep -m1 -i error "$OUT/build.txt")"; sleep 300; continue; fi
    last="$v"; lastRun=0
  fi
  if [ $((now - lastRun)) -ge 7200 ]; then
    log "миссии уровня 1: все, по 1500 с, $PROCS процессов"
    r=$(nice -n 10 python3 tools/bots/missions.py --secs 1500 --procs "$PROCS" 2>&1 | grep -o 'build/bots/runs/mission/[0-9-]*' | tail -1)
    lastRun=$(date +%s)
    if [ -n "$r" ] && [ -f "$r/missions.json" ]; then
      python3 - "$r/missions.json" "$REP" "$v" <<'PY'
import json, sys, subprocess, datetime
from pathlib import Path
src, rep, ver = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
d = json.load(open(src)); rows = d if isinstance(d, list) else d.get('missions', d.get('rows', []))
def place(p):
    try:
        out = subprocess.run(['python3', 'tools/place.py', '--at', f'{p[0]:.1f}', f'{p[1]:.1f}'], capture_output=True, text=True, timeout=20).stdout.strip()
        return out.splitlines()[0] if out else f'({p[0]:.0f}, {p[1]:.0f})'
    except Exception: return f'({p[0]:.0f}, {p[1]:.0f})'
ok = sum(1 for r in rows if r.get('result') == 'пройдена')
L = [f'# Боты · миссии уровня 1 · {datetime.datetime.now():%d.%m %H:%M}', '',
     f'Версия игры: `{ver.split()[0]}` (та, что собрана и выложена). Пройдено **{ok} из {len(rows)}**.', '',
     '| миссия | итог | почему | где | время, с |', '|---|---|---|---|---|']
for r in rows:
    why = r.get('why') or ''
    if r.get('cls') == 'намеренно': why = (why + ' — по правилу миссии').strip(' —')
    L.append(f"| {r.get('title','').strip()} | {r.get('result','')} | {why} | {place(r.get('place',[0,0])) if r.get('result') != 'пройдена' else ''} | {r.get('time',0):.0f} |")
L += ['', 'Источник: `' + src + '`. Кампания: `tools/bots/campaign.sh` (идёт на твоём процессоре, только на актуальной версии).']
rep.write_text('\n'.join(L) + '\n')
PY
      log "отчёт: $REP ($(grep -o 'Пройдено [^.]*' "$REP" | head -1))"
    else log "миссии: нет итога ($r)"; fi
  fi
  sleep 60
done
log "остановлено (campaign.stop)"; rm -f build/bots/campaign.stop
