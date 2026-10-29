#!/usr/bin/env python3
import importlib.util
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('allrisk',ROOT/'tools/bots/allrisk.py')
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
def row(fam,verdict='risk',idx='one'):
 return dict(fam=fam,verdict=verdict,id=idx,level='L7',place='K11-1',x='100',y='4',z='20',obj='0:b432',frame='90',metrics='RESET возвращает в ту же ловушку',repro='frozen/bin/allrisk --seed 1 --only one',job='seed1')
rows=[row('pocket_trap'),row('pocket_trap',idx='two'),row('fall_through'),row('stuck','fail')]
d=A.dossiers(rows)
assert len(d)==3
trap=next(x for x in d if x['family']=='pocket_trap')
assert trap['count']==2 and trap['position']==[100,4,20] and trap['place']=='K11-1'
assert trap['object']=='0:b432' and trap['frame']=='90' and trap['hypothesis'] and trap['verify']
failed=next(x for x in d if x['verdict']=='fail')
assert 'причина в игре ещё не подтверждена' in failed['hypothesis']
assert not A.dossiers([row('pocket_trap','ok')])
board=row('invisible_wall');board.update(level='L3',place='H7-7',obj='0:b409')
roof=row('air_wall');roof.update(level='L7',place='F12-9',obj='0:b745')
known=A.dossiers([board,roof]);assert all(x['known'] for x in known)
assert all(x['verdict']=='risk' for x in known),'known cause must not hide measured risk'
board['verdict']='fail';assert A.dossiers([board])[0]['known'] is None
roof['obj']='0:b744';assert A.dossiers([roof])[0]['known'] is None
os.environ['BOT_DOSSIER_OLD']='1'
try:
 assert A.dossiers(rows) and all(x['hypothesis'] for x in A.dossiers(rows))
except AssertionError:
 print('PASS: grouped repeat/location/object/frame/repro, hypotheses marked, failed checker separated; OLD missing dossiers caught')
else:raise AssertionError('OLD escaped')
