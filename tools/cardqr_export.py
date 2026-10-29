#!/usr/bin/env python3
"""QR-коды карточек VIEW CARDS (идея Роба 85, 29.09): к каждой карточке уровня — компактный QR на страницу её эпизода в
большой вики сообщества Симпсонов (simpsons.fandom.com, многоязычная: у страницы есть переводы). Эпизод — из текстовой
библии диска (CARD_EPISODE_NN: «Episode 4F22: The City of New York vs. Homer Simpson»), своего текста нет.
Сканировать iPhone с экрана PSP: модуль 2 px, тихая зона 2 модуля (рисует viewer/main.c vcQrDraw).

  python tools/cardqr_export.py [--level 1] [--out build/cardqr-l1.bin]

Формат CQR1: 'CQR1', u8 карточек (7); на карточку: u8 n (сторона в модулях, 0 — нет QR: бонусная карточка без эпизода),
затем ceil(n*n/8) байт — модули построчно, старший бит первым (1 — тёмный). Библиотека segno (BSD-3, чистый Python)."""
import argparse, sys
from urllib.parse import quote_plus
from pathlib import Path
import segno
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_export as U

WIKI = 'https://simpsons.fandom.com/wiki/'


def episode_url(ep):
    """«Episode 4F22: The City of New York vs. Homer Simpson» -> адрес страницы вики; нет эпизода -> None"""
    if not ep or ':' not in ep: return None
    title = ep.split(':', 1)[1].strip()
    # поиск вики с переходом (MediaWiki go): точное название — сразу страница эпизода; у библии диска знаки препинания
    # в названиях опущены («Brother Can You Spare Two Dimes»), тогда первая строка поиска — эта серия
    return WIKI + 'Special:Search?go=Go&search=' + quote_plus(title) if title else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--level', type=int, default=1); ap.add_argument('--out')
    a = ap.parse_args()
    out = Path(a.out) if a.out else Path(__file__).resolve().parents[1] / f'build/cardqr-l{a.level}.bin'
    B = U.load_bible(U.LANG); blob = bytearray(b'CQR1') + bytes([7])
    for k in range(7):
        nn = (a.level - 1) * 8 + k; url = episode_url(B('CARD_EPISODE_%02d' % nn))   # правка 364: 8 на уровень, с нуля (как CARD_TITLE/EPISODE экрана; было ×7 + 1 — QR соседней карточки)
        if not url: blob += bytes([0]); print(f'карточка {k + 1}: без эпизода — QR нет'); continue
        q = segno.make(url, error='l', micro=False); rows = [list(r) for r in q.matrix]; n = len(rows)
        bits = [v & 1 for r in rows for v in r]
        blob += bytes([n]) + bytes(sum(bits[i + j] << (7 - j) for j in range(8) if i + j < len(bits)) for i in range(0, len(bits), 8))
        print(f'карточка {k + 1}: {n}×{n} модулей -> {url}')
    out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(bytes(blob)); print(f'{out.name}: {len(blob)} Б')


if __name__ == '__main__':
    main()
