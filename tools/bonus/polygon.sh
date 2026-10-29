#!/bin/bash
# Полигон бонус-игры (правка Роба 420, пункт 4): гонщики-боты на всех 7 трассах меню, оба хода. Машины — 3 соперника данных
# (ходовые bonus/bgT_K.con) + машина игрока под тем же водителем ИИ. Итог — build/bonus/polygon/<время>/: прогон на трассу
# (txt, json), сводка summary.tsv (круги, лучший круг, общее время, удары о стены и машины, возвраты на путь) и report.md.
#   tools/bonus/polygon.sh [LAPS]
cd "$(dirname "$0")/../.."
B=build/bonus; L=${1:-3}; OUT=$B/polygon/$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
tools/bonus/build_host.sh || exit 1
echo -e "track\tdir\tcar\tcon\tlaps\tfinished\tbest_s\ttotal_s\tplace\twalls\tcars\tresets\tvmax_kmh\tresult" > "$OUT/summary.tsv"
for t in 1 2 3 4 5 6 7; do for r in fwd rev; do
  a=""; [ $r = rev ] && a=--reverse
  $B/bin/race_host $B/b0$t.shr $B/b0$t.bns $B/msncars-b.shr --laps $L $a --json "$OUT/b0${t}_$r.json" > "$OUT/b0${t}_$r.txt"
  res=$(grep -o 'RESULT: [A-Z]*' "$OUT/b0${t}_$r.txt" | cut -d' ' -f2)
  python3 - "$OUT/b0${t}_$r.json" "$t" "$r" "$res" >> "$OUT/summary.tsv" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for c in d['racers']:
    print('\t'.join(map(str, [sys.argv[2], sys.argv[3], c['car'], c['con'] or '-', c['laps'], c['finished'], round(c['best'], 2),
                              round(c['total'], 2), c['place'], c['walls'], c['cars'], c['resets'], c['vmax'], sys.argv[4]])))
PY
  echo "b0$t $r: $res"
done; done
python3 - "$OUT" <<'PY'
import csv, sys, os
rows = list(csv.DictReader(open(os.path.join(sys.argv[1], 'summary.tsv')), delimiter='\t'))
out = ['| трасса | ход | доехали | лучший круг, с (ИИ данных) | возвратов на путь | ударов о стены | итог |', '|---|---|---|---|---|---|---|']
for t in sorted({(r['track'], r['dir']) for r in rows}):
    rs = [r for r in rows if (r['track'], r['dir']) == t]
    fin = sum(int(r['finished']) for r in rs); best = [float(r['best_s']) for r in rs if r['con'] != '-' and float(r['best_s']) > 0]
    out.append(f"| b0{t[0]} | {t[1]} | {fin}/4 | {min(best):.1f}–{max(best):.1f} |" if best else f"| b0{t[0]} | {t[1]} | {fin}/4 | — |")
    out[-1] += f" {sum(int(r['resets']) for r in rs)} | {sum(int(r['walls']) for r in rs)} | {rs[0]['result']} |"
open(os.path.join(sys.argv[1], 'report.md'), 'w').write('\n'.join(out) + '\n'); print('\n'.join(out))
PY
echo "полигон: $OUT"
