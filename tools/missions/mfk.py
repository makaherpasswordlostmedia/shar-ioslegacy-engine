"""Tokenizer/parser for Radical's MFK mission scripts (SHAR).

Grammar actually used on the disc (checked on all 360+ .mfk files):
  script    := { call [';'] }
  call      := Ident '(' [ arg { ',' arg } ] ')'
  arg       := '"' chars '"'        (no escapes: backslashes are path separators)
             | number               (int or float, optional sign, '.5' allowed)
             | bare word            (SpringfieldElementary, count, final, false ...)
  comments  := '//' to end of line  |  '/*' ... '*/'
Anything outside a call that is not a comment/whitespace/';' is reported as a warning
(the original scripts contain a few stray tokens, e.g. a lone ')' ).

Each call -> Call(op, args, line, file). Arg values: int | float | Str (str subclass
with .bare flag telling whether the author wrote it without quotes).
"""
from dataclasses import dataclass, field
import re

class Str(str):
    """String argument; .bare=True if it was written without quotes."""
    bare = False

def _bare(s):
    v = Str(s); v.bare = True; return v

_NUM = re.compile(r'[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?[fF]?$')

@dataclass
class Call:
    op: str
    args: list
    line: int
    file: str = ''
    col: int = 0

    def __repr__(self):
        return f'{self.op}({", ".join(repr(a) for a in self.args)})@{self.file}:{self.line}'

def _number(tok):
    t = tok.rstrip('fF')
    if re.fullmatch(r'[+-]?\d+', t):
        return int(t)
    return float(t)

def parse(text, filename=''):
    """Return (calls, warnings)."""
    calls, warns = [], []
    i, n, line = 0, len(text), 1
    def warn(msg, ln):
        warns.append(f'{filename}:{ln}: {msg}')
    while i < n:
        ch = text[i]
        if ch == '\n':
            line += 1; i += 1; continue
        if ch in ' \t\r;\f\v﻿':
            i += 1; continue
        if text.startswith('//', i):
            j = text.find('\n', i); i = n if j < 0 else j; continue
        if text.startswith('/*', i):
            j = text.find('*/', i + 2)
            if j < 0:
                warn('unterminated block comment', line); break
            line += text.count('\n', i, j); i = j + 2; continue
        m = re.compile(r'[A-Za-z_]\w*').match(text, i)
        if not m:
            warn(f'stray character {ch!r}', line); i += 1; continue
        name = m.group(0); j = m.end()
        # skip whitespace (and comments) between name and '('
        while j < n and text[j] in ' \t\r\n':
            j += 1
        if j >= n or text[j] != '(':
            warn(f'stray word {name!r} (not a call)', line); i = m.end(); continue
        start_line = line + text.count('\n', i, j)
        line = start_line
        j += 1
        args = []
        cur = ''; quoted = False; had_quote = False
        closed = False
        while j < n:
            c = text[j]
            if quoted:
                if c == '"':
                    quoted = False
                else:
                    if c == '\n':
                        line += 1
                    cur += c
                j += 1; continue
            if c == '"':
                if cur.strip():
                    warn(f'{name}: text before quote {cur!r}', line)
                quoted = True; had_quote = True; cur = ''; j += 1; continue
            if text.startswith('//', j):
                k = text.find('\n', j); j = n if k < 0 else k; continue
            if text.startswith('/*', j):
                k = text.find('*/', j + 2)
                if k < 0:
                    break
                line += text.count('\n', j, k); j = k + 2; continue
            if c in ',)':
                tok = cur.strip()
                if had_quote:
                    args.append(Str(cur))
                elif tok:
                    if _NUM.match(tok):
                        args.append(_number(tok))
                    else:
                        args.append(_bare(tok))
                elif c == ',':
                    warn(f'{name}: empty argument', line)
                    args.append(_bare(''))
                cur = ''; had_quote = False; j += 1
                if c == ')':
                    closed = True; break
                continue
            if c == '\n':
                line += 1
            if had_quote and c not in ' \t\r\n':
                warn(f'{name}: text after quote {c!r}', line)
            if not had_quote:
                cur += c
            j += 1
        if not closed:
            warn(f'unterminated call {name}', start_line); break
        calls.append(Call(name, args, start_line, filename))
        i = j
    return calls, warns

def parse_file(path, rel=None):
    data = path.read_bytes().decode('latin-1')
    return parse(data, rel or path.name)
