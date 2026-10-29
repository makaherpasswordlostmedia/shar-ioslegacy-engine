#!/usr/bin/env python3
"""Real disc clips with known pitch/gain/onset changes; no-pitch negative."""
import importlib.util
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('identify',ROOT/'tools/audio_identify.py')
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
disc=ROOT/'hit-and-run-web/source/game/sound/soundfx/collisions'
names=['small_vehicle_crash_01','small_vehicle_crash_02','small_vehicle_crash_03','medium_vehicle_crash_01','large_vehicle_crash_01','mailbox_crash_03','gen_metal_01']
refs={n:A.read(disc/(n+'.rsd')) for n in names if (disc/(n+'.rsd')).exists()}
target='small_vehicle_crash_01';x=refs[target];n=int(.12*A.RATE)
rng=np.random.default_rng(16)
for pitch in (.92,1.08):
 q=np.zeros(int(.5*A.RATE));start=int(.037*A.RATE)
 q[start:start+n]=.23*np.interp(np.arange(n)*pitch,np.arange(len(x)),x)
 q+=rng.normal(0,1e-5,len(q))
 good=A.cross_spectrum(q,refs);bad=A.cross_spectrum(q,refs,False)
 assert good[0]['clip']==target and good[0]['score']>.99,good[:2]
 assert bad[0]['score']<.6, 'no-pitch old matcher escaped'
 print(f'PASS pitch{pitch}: {good[0]["clip"]} {good[0]["score"]:.4f}; OLD max{bad[0]["score"]:.4f}')
unknown=A.cross_spectrum(rng.normal(0,.2,int(.5*A.RATE)),refs)
assert unknown[0]['score']<.4,unknown[:2]
silent=A.cross_spectrum(np.zeros(int(.5*A.RATE)),refs)
assert silent[0]['score']==0
print('PASS: unknown noise/silence are low/zero coherence; no false certified identity')
