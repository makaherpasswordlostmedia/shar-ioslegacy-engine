#!/usr/bin/env python3
"""Source contract + actual conditional gameplay/voice/save route and genuine OLD controls."""
import argparse,json,os,shlex,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];os.chdir(ROOT);sys.path.insert(0,str(ROOT/'tools'))
from ticket_source import facts
from ticket_export import routes
from ticket_audio import voices
sys.path.insert(0,str(ROOT/'tests/levels'))
from ambience_check import sap_tracks
from audio_export import read_rsd
from sound_export import voice_track_name
OUT=ROOT/'build/content-ticket-c3';OUT.mkdir(parents=True,exist_ok=True)
ap=argparse.ArgumentParser();ap.add_argument('--old-flow',action='store_true');ap.add_argument('--old-persist',action='store_true');ap.add_argument('--old-room',action='store_true');ap.add_argument('--collect-source',type=Path,help='actual CLT package; may be composed with dependency0c0ca4e');ap.add_argument('--ticket-source',type=Path,help='actual TKT1 package; defaults to staged L3');a=ap.parse_args()
variant='old-flow' if a.old_flow else 'old-persist' if a.old_persist else 'old-room' if a.old_room else 'new';pack=ROOT/'build/ship_stage/l3';audio=pack/'audio'
facts();ts=sap_tracks(audio/'music.sap')
for v in voices():
 t=ts.get(voice_track_name(v['file']));s=read_rsd(ROOT/'hit-and-run-web/source/game'/v['file']);d=s['data']
 if s['ch']==1:d=b''.join(d[k:k+16]*2 for k in range(0,len(d),16))
 assert t and t['bus']==2 and not t['loop'] and t['data']==d,('original voice identity',v)
source=subprocess.check_output(['bash','-c','V=viewer; source tools/bots/lib.sh; printf "%s" "$BOTS_LIB"'],text=True)
cmd=['cc','-std=c11','-O2','-w','-DSKIN_HOST','-DAUDIO_HOST','-Iviewer','-Itools/bots']
if a.old_flow:cmd+=['-DTICKET_CONTENT_C3_OLD=1']
if a.old_persist:cmd+=['-DTICKET_PERSIST_C3_OLD=1']
exe=OUT/f'host-{variant}'
with (OUT/f'compile-{variant}.log').open('w') as log:
 rc=subprocess.run(cmd+['tests/content/ticket/host.c','viewer/ticket.c','viewer/ticket_view.c','viewer/savegame.c','viewer/sound.c','viewer/audio.c']+shlex.split(source)+['-lm','-o',str(exe)],stdout=log,stderr=subprocess.STDOUT).returncode
if rc:sys.exit('FAIL compilation')
with (OUT/f'runtime-{variant}.log').open('w') as log:rc=subprocess.run([str(exe),str(a.collect_source or (OUT/'reference/without-alias.shr' if a.old_room else pack/'collect-l3.shr')),str(a.ticket_source or pack/'ticket.shr'),str(audio)+"/"],stdout=log,stderr=subprocess.STDOUT).returncode
print('native',variant,'PASS' if not rc else 'FAIL');lines=(OUT/f'runtime-{variant}.log').read_text().splitlines();print(lines[-1] if lines else f'empty runtime output rc={rc}');sys.exit(bool(rc))
