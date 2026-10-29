#!/usr/bin/env python3
"""Content cache for declared ship_rules inputs, raw command and export options.

The disc tree is immutable/read-only. Mutable inputs must be in ship_rules deps.
No timestamp participates; the output SHA prevents stale/foreign metadata reuse.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def signature(deps, cmd):
    files = {}
    keys = set()
    for name in shlex.split(deps):
        p = Path(name)
        if p.is_dir():
            files[name] = {str(q.relative_to(p)): sha(q) for q in sorted(p.rglob('*')) if q.is_file()}
        elif p.exists():
            files[name] = sha(p)
        else:
            # ui_typo.json and optional boot marks may be absent; presence is an input too.
            files[name] = None
        s = p.read_text(errors='replace') if p.is_file() and p.suffix in ('.py', '.sh') else ''
        keys.update(re.findall(r'(?:getenv|environ\.get)\(\s*[\'"]([A-Z][A-Z0-9_]+)', s))
        keys.update(re.findall(r'environ\[\s*[\'"]([A-Z][A-Z0-9_]+)', s))
        keys.update(re.findall(r'\$\{([A-Z][A-Z0-9_]+)', s))
    # Temporary conversion/output locations never affect exported bytes.
    keys -= {'SHR_TMP', 'ROOT', 'OUT', 'OUTDIR', 'PSPDEV', 'PATH', 'HOME'}
    env = {k: os.environ.get(k) for k in sorted(keys)}
    payload = dict(version=1, cache=sha(__file__), inputs=files, command=cmd, environment=env)
    payload['sha256'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['check', 'record'])
    ap.add_argument('output', type=Path)
    ap.add_argument('--deps', required=True)
    ap.add_argument('--cmd', required=True)
    a = ap.parse_args()
    try:
        sig = signature(a.deps, a.cmd)
        marker = Path(str(a.output) + '.inputs.sha256')
        if a.action == 'check':
            if not a.output.is_file():
                print('нет файла'); return 1
            try:
                old = json.loads(marker.read_text())
            except (OSError, ValueError):
                print('нет проверенного хеша входов'); return 1
            if old.get('sha256') != sig['sha256']:
                print('изменились входы, команда или параметры'); return 1
            if old.get('output') != sha(a.output):
                print('изменился выход'); return 1
            return 0
        if not a.output.is_file() or not a.output.stat().st_size:
            raise OSError(f'нет готового выхода {a.output}')
        sig['output'] = sha(a.output)
        tmp = marker.with_name(marker.name + f'.{os.getpid()}.tmp')
        tmp.write_text(json.dumps(sig, ensure_ascii=False, indent=1) + '\n')
        tmp.replace(marker)
        return 0
    except OSError as e:
        print(f'хеш входов: {e}'); return 2


if __name__ == '__main__':
    raise SystemExit(main())
