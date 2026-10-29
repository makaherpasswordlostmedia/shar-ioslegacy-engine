#!/usr/bin/env python3
"""№526: у текста будки (SPEED, ACCELERATION, TOUGHNESS, HANDLING) есть группа выбора шрифта phone_stats_text (kind pix8, строки рисует pix8); сдвиг блока остаётся у phone_stats.
Зелёный: группа есть, стоит раньше phone_stats, подхватывает 4 строки PhoneBooth.pag и не берёт звёзды; UI_TYPO_PHONE_TEXT_OLD=1 её убирает (красный контроль).
    python3 tests/ui/typo_phone_text.py"""
import os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import ui_typo as UT
ids = [g['id'] for g in UT.GROUPS]
ok = 'phone_stats_text' in ids and ids.index('phone_stats_text') < ids.index('phone_stats')
g = UT.GROUP['phone_stats_text']
names = ('Speed', 'Acceleration', 'Toughness', 'Stability')
mk = lambda n, ty: dict(type=ty, page='PhoneBooth.pag', name=n)
ok &= all(UT.matches(g, 'phone', mk(n, UT.T_TEXT)) for n in names)
ok &= not any(UT.matches(g, 'phone', mk(n, UT.T_IMG)) for n in ('Spe_Stars0', 'Acc_Stars1'))
old = subprocess.run([sys.executable, '-c', "import sys; sys.path.insert(0, %r); import ui_typo as U; print('phone_stats_text' in U.GROUP)" % str(ROOT / 'tools')],
                     capture_output=True, text=True, env=dict(os.environ, UI_TYPO_PHONE_TEXT_OLD='1')).stdout.strip()
ok &= old == 'False'
print('группа есть, 4 строки, без звёзд, откат UI_TYPO_PHONE_TEXT_OLD=1 убирает' if ok else 'КРАСНЫЙ')
sys.exit(0 if ok else 1)
