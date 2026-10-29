#!/bin/bash
# Гейт полигона v2 без игры: тест регистратора на синтетике (зелёный) + красный контроль (POLY_REG_BREAK=merge — склейка мест
# выключена, тест обязан упасть) + сборка инспектора тем же build.sh, что ботов (данные уровня не нужны).
#   bash tests/polygon/run.sh   -> PASS/FAIL, build/polygon_gate/*.txt
set -u; cd "$(dirname "$0")/../.."; O=build/polygon_gate; mkdir -p "$O"
python3 tests/polygon/test_registry.py > "$O/green.txt" 2>&1; g=$?
POLY_REG_BREAK=merge python3 tests/polygon/test_registry.py > "$O/red.txt" 2>&1; r=$?
python3 tests/polygon/test_runner.py > "$O/runner.txt" 2>&1; runner=$?
python3 tests/polygon/test_control.py > "$O/control-green.txt" 2>&1; cg=$?
python3 - <<'PY'
from pathlib import Path
s = Path('tools/polygon/control.py').read_text()
assert 'os.killpg(worker.pid, signal.SIGKILL)' in s
Path('build/polygon_gate/control-broken.py').write_text(s.replace('os.killpg(worker.pid, signal.SIGKILL)', 'os.killpg(worker.pid, signal.SIGTERM)'))
PY
python3 tests/polygon/test_control.py "$O/control-broken.py" > "$O/control-red.txt" 2>&1; cr=$?
OUT_DIR="$O/bin" BINS=inspector bash tools/bots/build.sh > "$O/build.txt" 2>&1; b=$?
echo "зелёный: $([ $g = 0 ] && echo PASS || echo FAIL) · красный (склейка выключена): $([ $r != 0 ] && echo упал — верно || echo НЕ УПАЛ) · сборка инспектора: $([ $b = 0 ] && echo ok || echo ошибка)"
echo "запуск и ошибки: $([ $runner = 0 ] && echo PASS || echo FAIL) · фон: $([ $cg = 0 ] && echo PASS || echo FAIL) · сломанная остановка: $([ $cr != 0 ] && echo упала || echo НЕ_УПАЛА)"
[ $g = 0 ] && [ $r != 0 ] && [ $b = 0 ] && [ $runner = 0 ] && [ $cg = 0 ] && [ $cr != 0 ] && { echo PASS; exit 0; }
grep -h "FAIL" "$O/green.txt" | head -5; echo FAIL; exit 1
