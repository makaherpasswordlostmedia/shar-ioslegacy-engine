#!/usr/bin/env python3
"""Сводка времён загрузки из smoke.txt прогона: times.py RUNDIR [RUNDIR2 ...] — по уровню: LOADREAD ms, MCPROBE ms (baked), LMAP, LEVEL ms"""
import re, sys, pathlib
def rows(run):
    t = (pathlib.Path(run) / 'smoke.txt').read_text(); out = {}; cur = {}
    for ln in t.splitlines():
        m = re.match(r'(MCPROBE|LMAP|LOADREAD|LEVEL ev=load|FIRSTFRAME|MCPVERIFY)\b(.*)', ln)
        if not m: continue
        kv = dict(re.findall(r'(\w+)=(\S+)', ln))
        if m[1] == 'MCPROBE': cur['mcprobe'] = float(kv['ms']); cur['baked'] = kv.get('baked', '-'); cur['blocked'] = kv['blocked']
        elif m[1] == 'LMAP': cur['lmap'] = kv['used']; cur['lmapms'] = kv['ms']
        elif m[1] == 'MCPVERIFY': cur['verify'] = kv['same']
        elif m[1].startswith('LEVEL'): cur['level'] = float(kv['ms']); cur['n'] = kv['n']
        elif m[1] == 'LOADREAD': cur['loadread'] = float(kv['ms'])
        elif m[1] == 'FIRSTFRAME': cur['first'] = kv['level']; out[kv['level']] = cur; cur = {}
    return out
for run in sys.argv[1:]:
    r = rows(run); print(run)
    for k in sorted(r): d = r[k]; print('  L%s LEVEL %5.0f  LOADREAD %5.0f  MCPROBE %5.0f (baked %s blocked %s)  LMAP %s %sms %s' % (k, d.get('level', 0), d.get('loadread', 0), d.get('mcprobe', 0), d.get('baked', '-'), d.get('blocked', '-'), d.get('lmap', '-'), d.get('lmapms', '-'), ('verify=' + d['verify']) if 'verify' in d else ''))
