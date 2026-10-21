#!/usr/bin/env python3
"""Read saved clock404 native smoke logs; never launch an emulator or gameplay.

Apply the same expectations to NEW and actual FE_GAG_CLOCK_OLD logs. --plant
corrupts parsed observations in memory to prove the relevant checks are live.
Use --load for the separate Load Game round trip with an already pending gag.
The default trace covers Options and title; neither substitutes for --load.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def parse(text):
    events = []
    for n, line in enumerate(text.splitlines(), 1):
        kind = next((k for k in ('FEGCLOCK', 'FEMENU', 'FEGAG prepare',
                                'FEGAG start', 'FEAUDIO', 'FEFLY')
                     if line.startswith(k + ' ')), None)
        if kind:
            values = dict(re.findall(r'(\w+)=([^\s]+)', line))
            for key in ('ms', 'next', 'pending', 'active', 'flying', 'elapsed_ms',
                        'next_ms', 'i', 'seg', 'forced', 'item', 'mode', 'event',
                        'index', 'segment', 'ready_before', 'track', 'req', 'before_req'):
                if key in values:
                    values[key] = int(values[key])
            values['t'] = float(values['t'])
            events.append(dict(kind=kind, line=n, **values))
    return events


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('log', type=Path)
    ap.add_argument('--load', action='store_true', help='Load Game pending-pause fixture')
    ap.add_argument('--plant', choices=('options-tick', 'title-jump', 'prep-late',
                                       'pending-lost', 'audio-changed'))
    ap.add_argument('--json', type=Path)
    args = ap.parse_args()
    raw = args.log.read_bytes()
    text = raw.decode('utf-8')
    events = parse(text)
    checks = []

    def check(name, condition):
        checks.append(dict(name=name, pass_=bool(condition)))

    clocks = [e for e in events if e['kind'] == 'FEGCLOCK']
    boundaries = [e for e in events if e['kind'] == 'FEMENU']
    prep = [e for e in events if e['kind'] == 'FEGAG prepare']
    starts = [e for e in events if e['kind'] == 'FEGAG start' and e['forced'] == 0]
    check('complete_native_END', text.rstrip().endswith('\nEND'))
    expected = [0, 1] if args.load else [0, 1, 0, 1]
    check('pause_return_boundaries', [e['active'] for e in boundaries] == expected)
    check('native_clock_samples', len(clocks) > 100)
    if len(boundaries) != len(expected) or not clocks:
        return finish(args, raw, checks, {})
    opt_out, opt_back = boundaries[:2]
    label = 'LoadGame' if args.load else 'Options'

    def between(begin, end, kind='FEGCLOCK'):
        return [e for e in events if e['kind'] == kind and
                begin['line'] < e['line'] < end['line']]

    def after(boundary):
        return [e for e in clocks if e['line'] > boundary['line']][:3]

    option_clocks = between(opt_out, opt_back)
    title_resume = after(boundaries[3]) if not args.load else []
    if args.plant == 'options-tick' and option_clocks:
        option_clocks[len(option_clocks) // 2]['ms'] += 17
    elif args.plant == 'title-jump' and title_resume:
        title_resume[0]['ms'] += 3100
    elif args.plant == 'prep-late' and prep:
        prep[0]['elapsed_ms'] = prep[0]['next_ms'] - 1000
    elif args.plant == 'pending-lost' and option_clocks:
        option_clocks[len(option_clocks) // 2]['pending'] = -1
    elif args.plant == 'audio-changed':
        audio = [e for e in events if e['kind'] == 'FEAUDIO' and e.get('event') == 181]
        if audio:
            audio[0]['track'] += 1

    names = ('SHOT load_pause ', 'SHOT load_still ', 'PRESS triangle ') if args.load else (
             'SHOT options_pause ', 'SHOT options_still ', 'PRESS triangle ')
    check(label + '_screens_and_Back_recorded', all(s in text for s in names) and
          opt_back['t'] - opt_out['t'] >= 5)
    if args.load:
        check('real_LoadGame_screen_opened', any('SVOPEN mode=load ' in ln for ln in
              text.splitlines()[opt_out['line']:opt_back['line'] - 1]))
        check('pending_selected_before_LoadGame_and_retained_at_Back',
              opt_out['pending'] >= 0 and opt_back['pending'] == opt_out['pending'])
    flights = between(opt_out, opt_back, 'FEFLY')
    # FE fly table: Load Game is the VCR (item 0), Options the sofa (item 2).
    # SVOPEN independently identifies Load Game; a flight alone is insufficient.
    item = 0 if args.load else 2
    check(label + '_outbound_and_return_flights',
          {e['mode'] for e in flights if e['item'] == item} == {0, 1})
    pairs = [(label, opt_out, opt_back)]
    if not args.load:
        pairs.append(('Title', boundaries[2], boundaries[3]))
    for name, first, last in pairs:
        check(name + '_retains_elapsed_and_pending', first['elapsed_ms'] > 0 and
              first['elapsed_ms'] == last['elapsed_ms'] and
              first['pending'] == last['pending'])
        resumed = after(last)
        check(name + '_first_return_excludes_absent_wall_time', bool(resumed) and
              resumed[0]['ms'] == last['elapsed_ms'] and resumed[0]['active'] == 1)
        check(name + '_Back_resumes_without_reset', len(resumed) == 3 and
              0 < resumed[2]['ms'] - resumed[0]['ms'] <= 100)
        check(name + '_no_automatic_prepare_or_play_while_absent',
              not between(first, last, 'FEGAG prepare') and
              not [e for e in between(first, last, 'FEGAG start') if not e['forced']])
    check(label + '_all_inactive_clock_samples_retained', bool(option_clocks) and
          all(e['active'] == 0 and e['ms'] == opt_out['elapsed_ms'] and
              e['pending'] == opt_out['pending'] for e in option_clocks))
    check('both_flights_freeze_clock', sum(e['flying'] for e in option_clocks) > 20 and
          all(e['ms'] == opt_out['elapsed_ms'] for e in option_clocks if e['flying']))
    if not args.load:
        title_out, title_back = boundaries[2:]
        check('Title_PressStart_observed_during_pause', title_back['t'] - title_out['t'] >= 1 and
              any('show=PRESS_START' in ln for ln in
                  text.splitlines()[title_out['line']:title_back['line'] - 1]))
    check('one_automatic_preparation_and_start', len(prep) == 1 and len(starts) == 1)
    if len(prep) == len(starts) == 1:
        p, s = prep[0], starts[0]
        prior = [e for e in clocks if e['line'] < p['line']][-1:]
        check('prepare_crosses_next_minus_2000ms', bool(prior) and
              prior[0]['ms'] < p['next_ms'] - 2000 <= p['elapsed_ms'] and
              0 < p['elapsed_ms'] - prior[0]['ms'] <= 100)
        pending = between(p, s)
        check('prepared_index_retained_until_play', bool(pending) and
              p['i'] == s['i'] and p['seg'] == s['seg'] and
              all(e['pending'] == p['i'] and e['next'] == p['next_ms']
                  and e['ms'] < p['next_ms'] for e in pending))
        # Native t is rounded to 0.1s. Use integer clock samples for the threshold;
        # +/-0.1s covers the two rounded event timestamps, not gameplay variance.
        check('play_crosses_next_threshold', bool(pending) and
              0 < p['next_ms'] - pending[-1]['ms'] <= 100)
        paused = sum(b['t'] - a['t'] for _, a, b in pairs
                     if p['line'] < a['line'] < b['line'] < s['line'])
        check('two_seconds_preparation_lead_excludes_paused_wall_time',
              1.9 <= round(s['t'] - p['t'] - paused, 1) <= 2.1)
        check('play_resets_clock_after_threshold', bool(after(s)) and
              after(s)[0]['ms'] == 0 and after(s)[0]['pending'] == -1)
        audio = [e for e in events if e['kind'] == 'FEAUDIO' and
                 e.get('event') == 181 and p['line'] < e['line'] < s['line']]
        check('prepared_audio_ready_at_automatic_play', bool(audio) and
              audio[-1]['index'] == p['i'] and audio[-1]['ready_before'] == 1)
        prepared_audio = [e for e in events if e['kind'] == 'FEAUDIO' and
                          e.get('event') == 180 and e['line'] < p['line']]
        check('same_prepared_audio_request_at_play', bool(audio) and bool(prepared_audio) and
              audio[-1]['track'] == prepared_audio[-1]['track'] >= 0 and
              audio[-1]['req'] == prepared_audio[-1]['req'] == audio[-1]['before_req'] and
              audio[-1]['index'] == prepared_audio[-1]['index'] and
              audio[-1]['segment'] == prepared_audio[-1]['segment'])
    metrics = {'boundaries': boundaries, 'prepare': prep, 'automatic_start': starts,
               'clock_samples': len(clocks), 'options_samples': len(option_clocks)}
    return finish(args, raw, checks, metrics)


def finish(args, raw, checks, metrics):
    failed = sum(not c['pass_'] for c in checks)
    result = dict(log=str(args.log.resolve()), sha256=hashlib.sha256(raw).hexdigest(),
                  plant=args.plant, load_fixture=args.load, checks=checks, metrics=metrics, failures=failed,
                  limits=['Saved native observations only; no new game run',
                          'Default Options/title and --load are distinct native fixtures',
                          'This gate does not establish exact PS2 audio or title rendering'])
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2) + '\n')
    for c in checks:
        print('CHECK', c['name'], 'PASS' if c['pass_'] else 'FAIL')
    print('SOURCE sha256=' + result['sha256'], 'plant=' + str(args.plant))
    print(f'RESULT {"FAIL" if failed else "PASS"} checks={len(checks)} failures={failed}')
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
