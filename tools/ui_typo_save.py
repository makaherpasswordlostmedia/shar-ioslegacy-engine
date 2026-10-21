#!/usr/bin/env python3
"""Offline browser downloads -> the explicitly configured typography file, without a web server."""
import argparse
import hashlib
import json
import math
import os
import time
from pathlib import Path
import ui_typo


def save(source, target, status, expires=None, log=True):
    raw = source.read_bytes()
    if len(raw) > 256 * 1024:
        raise ValueError('typography JSON exceeds 256 KiB')
    cfg = json.loads(raw)
    if cfg.get('target') != 'shar-psp/build/ui_typo.json' or cfg.get('version') != 1:
        raise ValueError('not a SHAR typography panel save')
    groups = cfg.get('groups')
    if not isinstance(groups, dict) or any(k not in ui_typo.GROUP and k not in ui_typo.LEGACY for k in groups):
        raise ValueError('invalid typography groups')
    for group in groups.values():
        if not isinstance(group, dict):
            raise ValueError('invalid typography values')
        for value in group.values():
            if not isinstance(value, (int, float, str)) or isinstance(value, (int, float)) and not math.isfinite(value):
                raise ValueError('invalid typography value')
    els = cfg.get('elements', {})
    if not isinstance(els, dict) or any(not isinstance(k, str) or k.count('|') < 2 or not isinstance(v, dict) or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in v.values()) for k, v in els.items()):
        raise ValueError('invalid element settings')   # №574: настройки отдельных элементов «экран|вид|имя» -> dx, dy
    if os.environ.get('UI_TYPO_SAVE_OLD') == '1':
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    # хозяин типографики (10.10): группы, которых нет в новом сохранении, берём из прежнего файла (страница иногда поднимала старое состояние и теряла группы);
    # список изменённых групп — в журнал. UI_TYPO_SAVE_MERGE_OLD=1 — как раньше, сохранение целиком
    changed, restored = [], []
    if os.environ.get('UI_TYPO_SAVE_MERGE_OLD') != '1' and target.exists():
        try:
            prev = json.loads(target.read_bytes()).get('groups') or {}
        except ValueError:
            prev = {}
        for k, v in prev.items():
            if k not in groups and k in ui_typo.GROUP:
                cfg['groups'][k] = v
                restored.append(k)
        groups = cfg['groups']
        changed = sorted(k for k in groups if k not in prev or prev[k] != groups[k]) + ['−' + k for k in prev if k not in groups]
        if restored:
            cfg['note'] = (cfg.get('note') or '') + ' · слито %s: из прежнего файла возвращены группы %s' % (time.strftime('%d.%m %H:%M'), ', '.join(restored))
            raw = json.dumps(cfg, ensure_ascii=False, indent=1).encode()
    if target.exists() and target.read_bytes() != raw:
        backup = target.parent.parent / '_backups' / 'ui-typo-saves'
        backup.mkdir(parents=True, exist_ok=True)
        old = target.read_bytes()
        (backup / (time.strftime('%Y%m%d-%H%M%S') + '-' + hashlib.sha256(old).hexdigest()[:16] + '.json')).write_bytes(old)
    temporary = target.with_suffix('.json.pending')
    temporary.write_bytes(raw)
    temporary.replace(target)
    (status.parent / 'saved.json').write_bytes(raw)   # правка 10.10: страница при загрузке берёт сохранённый json (saved.json рядом), а не только память браузера
    state = dict(saved=time.strftime('%H:%M:%S'), groups=groups, sha256=hashlib.sha256(raw).hexdigest())
    status.parent.mkdir(parents=True, exist_ok=True)
    if expires is not None: state['expires'] = expires
    pending = status.with_suffix('.js.pending')
    pending.write_text('window.TYPO_SAVE_STATUS = ' + json.dumps(state, ensure_ascii=False) + ';\n')
    pending.replace(status)
    journal = Path(os.environ.get('UI_TYPO_JOURNAL', Path.home() / 'Downloads/shar-psp/docs/handoff/ПАРА_ЖУРНАЛ.md'))
    if log and (changed or restored):
        try:
            with journal.open('a', encoding='utf-8') as f:
                f.write('- %s · Сохранение Роба %s: изменены группы %s%s\n' % (time.strftime('%Y-%m-%d %H:%M'), source.name if source is not None else '',
                        ', '.join(changed) or 'нет', ('; возвращены из прежнего: ' + ', '.join(restored)) if restored else ''))
        except OSError:
            pass
    return True


NOTES_TARGET = 'shar-psp/build/ТИПОГРАФИКА_ПАНЕЛЬ/notes.json'


def save_notes(source, target, copy=None):
    """замечания Роба из панели (№574, «Все замечания» -> ui_notes.json в Загрузках): build/ТИПОГРАФИКА_ПАНЕЛЬ/notes.json и копия в docs/handoff/ЗАМЕЧАНИЯ_ПАНЕЛЬ.json; прежний файл -> _backups/ui-notes-saves"""
    raw = source.read_bytes()
    if len(raw) > 1024 * 1024:
        raise ValueError('notes JSON exceeds 1 MiB')
    cfg = json.loads(raw)
    if cfg.get('target') != NOTES_TARGET or cfg.get('version') != 1 or not isinstance(cfg.get('notes'), list):
        raise ValueError('not a SHAR panel notes save')
    for n in cfg['notes']:
        if not isinstance(n, dict) or not isinstance(n.get('text'), str) or not isinstance(n.get('scene'), str):
            raise ValueError('invalid note')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != raw:
        backup = target.parent.parent.parent / '_backups' / 'ui-notes-saves'
        backup.mkdir(parents=True, exist_ok=True)
        old = target.read_bytes()
        (backup / (time.strftime('%Y%m%d-%H%M%S') + '-' + hashlib.sha256(old).hexdigest()[:16] + '.json')).write_bytes(old)
    tmp = target.with_suffix('.json.pending'); tmp.write_bytes(raw); tmp.replace(target)
    if copy is not None:
        try:
            copy.parent.mkdir(parents=True, exist_ok=True); copy.write_bytes(raw)
        except OSError:
            pass
    return len(cfg['notes'])


def ui_typo_stamp():
    f = Path(ui_typo.__file__); return (f.stat().st_mtime_ns, f.stat().st_size)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target', type=Path, default=ui_typo.DEFAULT_PATH)
    p.add_argument('--status', type=Path)
    p.add_argument('--downloads', type=Path, default=Path.home() / 'Downloads')
    p.add_argument('--once', type=Path)
    p.add_argument('--once-notes', type=Path, help='разобрать один файл ui_notes.json (проверка)')
    p.add_argument('--seconds', type=int, default=14400)
    a = p.parse_args()
    status = a.status or a.target.parent / 'ТИПОГРАФИКА_ПАНЕЛЬ/save-status.js'
    notes_target = a.target.parent / 'ТИПОГРАФИКА_ПАНЕЛЬ/notes.json'
    notes_copy = Path(os.environ.get('UI_NOTES_COPY', Path.home() / 'Downloads/shar-psp/docs/handoff/ЗАМЕЧАНИЯ_ПАНЕЛЬ.json'))
    if a.once_notes:
        print('notes saved:', save_notes(a.once_notes, notes_target, notes_copy)); return
    if a.once:
        print('saved' if save(a.once, a.target, status) else 'OLD: save ignored')
        return
    start = time.time()
    seen = {}
    status.parent.mkdir(parents=True, exist_ok=True)
    status.write_text('window.TYPO_SAVE_STATUS = ' + json.dumps(dict(ready=True, expires=start+a.seconds)) + ';\n')
    while time.time() - start < a.seconds:
        try:   # 11.10: группы панели добавляются в ui_typo.py уже после запуска забирателя — перечитывать модуль, иначе сохранение с новой группой молча отвергалось (ui_typo (19).json)
            if os.environ.get('UI_TYPO_SAVE_RELOAD_OLD') != '1' and ui_typo_stamp() != getattr(main, '_stamp', None):
                import importlib; importlib.reload(ui_typo); main._stamp = ui_typo_stamp()
        except Exception as e:
            print('reload ui_typo failed:', e, flush=True)
        for source in a.downloads.glob('ui_notes*.json'):   # №574: замечания панели
            st = source.stat()
            if st.st_mtime < start or seen.get(str(source)) == (st.st_mtime_ns, st.st_size):
                continue
            try:
                n = save_notes(source, notes_target, notes_copy); seen[str(source)] = (st.st_mtime_ns, st.st_size)
                print('notes saved', source.name, '->', notes_target, n, flush=True)
            except (OSError, ValueError, TypeError):
                continue
        for source in a.downloads.glob('ui_typo*.json'):
            st = source.stat()
            if st.st_mtime < start or seen.get(str(source)) == (st.st_mtime_ns, st.st_size):
                continue
            try:
                if save(source, a.target, status, start+a.seconds):
                    seen[str(source)] = (st.st_mtime_ns, st.st_size)
                    print('saved', source.name, '->', a.target, flush=True)
            except (OSError, ValueError, TypeError):
                # Ignore foreign or incomplete browser downloads; retry when bytes change.
                continue
        time.sleep(1)


if __name__ == '__main__':
    main()
