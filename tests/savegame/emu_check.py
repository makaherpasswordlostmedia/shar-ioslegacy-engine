#!/usr/bin/env python3
"""Сверка прогонов гейта сохранений в эмуляторе (tests/savegame/emu.sh) по строкам smoke.txt (viewer/savemenu.c, main.c saveLog):
  save    — запись прошла и подтверждена чтением (SVIO op=save res=00000000 verify=O), «Save Successful», вопрос перед выходом
            (MSG_CONFIRM_SAVE_BEFORE_QUIT) и выход в меню (вторая строка MENU), игра не упала (END)
  load    — при запуске слот 1 целый (SVSCAN O), загрузка слота 1, SVPROG src=load = прогресс перед записью (SVPROG src=mark
            прогона 1) по полям msn/cards/wasps/gags/coins/wcoins/vol/radar
  resume  — RESUME GAME: SVLATEST при старте меню, SVPROG src=load тот же прогресс
  corrupt — слот 1 испорчен (SVSCAN D), сообщение ERROR_DATA_CORRUPT_LOADING, запись удалена (SVIO op=delete), игра дошла до
            NEW GAME без записи (SVPROG src=new: прогресс пустой) и END — не упала
    emu_check.py SAVE_DIR LOAD_DIR [RESUME_DIR CORRUPT_DIR]   -> первая строка итог, код 0 = OK
"""
import sys
from pathlib import Path

KEYS = ('msn', 'cards', 'wasps', 'gags', 'coins', 'wcoins', 'vol', 'radar')


def lines(d):
    p = Path(d) / 'smoke.txt'
    return p.read_text(errors='replace').splitlines() if p.exists() else []


def kv(line):
    return dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)


def prog(line):
    d = kv(line)
    return {k: d.get(k) for k in KEYS}


def first(log, head, **want):
    for l in log:
        if l.startswith(head + ' ') and all(kv(l).get(k) == v for k, v in want.items()):
            return l
    return None


def main():
    dirs = sys.argv[1:]
    fails, notes = [], []
    save = lines(dirs[0])
    if not any(l.startswith('END') for l in save): fails.append('прогон 1: нет END (упал / завис)')
    mark = first(save, 'SVPROG', src='mark')
    if not mark: fails.append('прогон 1: нет отметки прогресса (SVPROG src=mark)')
    io = first(save, 'SVIO', op='save')
    if not io or kv(io).get('res') != '00000000' or kv(io).get('verify') != 'O':
        fails.append('прогон 1: запись не подтверждена (%s)' % (io or 'нет SVIO op=save'))
    if not first(save, 'SVMSG', key='MSG_SAVE_SUCCESSFUL'): fails.append('прогон 1: нет «Save Successful»')
    if not first(save, 'SVMSG', key='MSG_CONFIRM_SAVE_BEFORE_QUIT'): fails.append('прогон 1: QUIT GAME без вопроса о записи')
    if sum(l.startswith('MENU ') for l in save) < 2: fails.append('прогон 1: после QUIT GAME нет выхода в главное меню')
    want = prog(mark) if mark else None
    load = lines(dirs[1])
    if not any(l.startswith('END') for l in load): fails.append('прогон 2: нет END (упал / завис)')
    sc = first(load, 'SVSCAN')
    if not sc or not kv(sc).get('slots', '').startswith('O'): fails.append('прогон 2: при запуске слот 1 не целый (%s)' % sc)
    got = first(load, 'SVPROG', src='load')
    if not got: fails.append('прогон 2: загрузки не было (нет SVPROG src=load) — прогресс слетел')
    elif want and prog(got) != want:
        diff = ', '.join('%s %s->%s' % (k, want[k], prog(got)[k]) for k in KEYS if want[k] != prog(got)[k])
        fails.append('прогон 2: прогресс после загрузки другой: ' + diff)
    else: notes.append('прогресс после перезапуска тот же: ' + ' '.join('%s=%s' % (k, want[k]) for k in KEYS))
    if len(dirs) > 2:
        res = lines(dirs[2])
        if not first(res, 'SVLATEST'): fails.append('прогон 3: нет самого свежего сохранения для RESUME GAME')
        g = first(res, 'SVPROG', src='load')
        if not g or (want and prog(g) != want): fails.append('прогон 3: RESUME GAME не вернул прогресс (%s)' % g)
        else: notes.append('RESUME GAME: тот же прогресс')
    if len(dirs) > 3:
        cor = lines(dirs[3])
        if not any(l.startswith('END') for l in cor): fails.append('прогон 4: с испорченной записью нет END (упал / завис)')
        sc = first(cor, 'SVSCAN')
        if not sc or not kv(sc).get('slots', '').startswith('D'): fails.append('прогон 4: испорченный слот не опознан (%s)' % sc)
        if not first(cor, 'SVMSG', key='ERROR_DATA_CORRUPT_LOADING_(PS2)'): fails.append('прогон 4: нет сообщения о порче записи')
        de = first(cor, 'SVIO', op='delete')
        if not de: fails.append('прогон 4: испорченная запись не удалена')
        g = first(cor, 'SVPROG', src='new')
        if not g or kv(g).get('msn') != '00000000' or kv(g).get('coins') != '0':
            fails.append('прогон 4: новая игра не с нуля (%s)' % g)
        elif not first(cor, 'GAME'): fails.append('прогон 4: игра не началась')
        else: notes.append('испорченная запись: опознана, сообщение, удалена, новая игра с нуля')
    # 28.09 (проверяющий): подписи слотов попадали на кнопки вопроса/сообщения. Что нарисовано на кнопках — строки SVROWS
    rows = [kv(l) for d in dirs for l in lines(d) if l.startswith('SVROWS')]
    up = lambda x: (x or '').upper()
    badr = [r for r in rows if (r.get('scr') == 'notice' and up(r.get('r0')) != 'CONTINUE') or
            (r.get('scr') == 'prompt' and (up(r.get('r0')), up(r.get('r1'))) != ('YES', 'NO'))]
    if not any(r.get('scr') == 'notice' for r in rows): fails.append('нет ни одного экрана сообщения (SVROWS scr=notice) — кнопки не проверены')
    elif badr: fails.append('на кнопках не их подписи: ' + '; '.join('%s r0=%s r1=%s' % (r.get('scr'), r.get('r0'), r.get('r1')) for r in badr[:3]))
    else: notes.append('кнопки вопросов и сообщений — YES/NO и CONTINUE (%d экранов)' % len(rows))
    # прогресс через 5 с игры после загрузки (src=now) — подгрузка клеток не вернула собранное
    now = first(load, 'SVPROG', src='now')
    if want and (not now or prog(now) != want): fails.append('прогон 2: через 5 с игры прогресс другой (%s)' % now)
    if fails:
        print('FAIL: ' + '; '.join(fails)); return 1
    print('OK: ' + '; '.join(notes)); return 0


if __name__ == '__main__':
    sys.exit(main())
