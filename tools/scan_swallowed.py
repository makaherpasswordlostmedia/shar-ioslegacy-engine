#!/usr/bin/env python3
"""Поиск кода, проглоченного комментарием `//` в конце строки (16.10: `if (...) {...}   // текст else drawGeo(...);` — else исчез, кузова не рисовались).
Признак: после `//` в тексте есть ASCII-вызов с `;` на конце или `else`/`if (`/`for (` рядом со скобками, а код слева — закрытый блок `}` / `)` без `;`.
python3 tools/scan_swallowed.py [папка]  -> строки файл:номер: текст; код выхода = число находок"""
import re, sys, pathlib
root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'viewer')
pat_code = re.compile(r'(\belse\b\s*(\{|[A-Za-z_]\w*\s*\()|\b[A-Za-z_]\w*\s*\([^()]*(\([^()]*\)[^()]*)*\)\s*;\s*$|\bif\s*\(|\bfor\s*\(|\breturn\b[^;]*;\s*$)')
n = 0
for f in sorted(list(root.glob('*.h')) + list(root.glob('*.c'))):
    for i, l in enumerate(f.read_text(errors='replace').splitlines(), 1):
        # убрать строки в кавычках
        t = re.sub(r'"(\\.|[^"\\])*"', '""', l)
        k = t.find('//')
        if k < 0: continue
        code, com = t[:k], t[k + 2:]
        if not code.strip(): continue   # строка целиком комментарий
        if re.search(r'[А-Яа-яЁё]', com) is None and not pat_code.search(com): continue
        # интересует «код» внутри комментария: слово else или вызов функции с ; в конце после русского текста
        m = re.search(r'\belse\b\s*(\{|[A-Za-z_]\w*\s*\()', com) or re.search(r'[A-Za-z_]\w*\s*\([^()]*\)\s*;\s*$', com)
        if not m: continue
        if re.search(r'[А-Яа-яЁё]', com) is None and not code.strip().endswith(('}', ')')): continue
        n += 1; print(f'{f}:{i}: {l.strip()[:200]}')
print(f'находок: {n}')
sys.exit(1 if n else 0)
