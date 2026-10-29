#!/usr/bin/env python3
"""Disc oracle versus independently decoded delivery packets, not exporter output."""
import argparse, json, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from missions.mfk import parse
from missions.commands import OPCODE_ORDER
OPS=['']+OPCODE_ORDER
RULES=set(OPCODE_ORDER)-{'CloseMission'}
OBJS=['none','goto','getin','talkto','dialogue','interior','gooutside','race','follow','losetail','delivery','dump','destroy','pickupitem','destroyboss','timer','fmv','buycar','buyskin','coins','dummy']
def calls(path):
    return parse(path.read_bytes().decode('latin1'),str(path))[0]
def norm(x):
    return round(x,5) if isinstance(x,(float,int)) else str(x)
def sig(op,args): return [op,[norm(x) for x in args]]
class Pack:
    def __init__(self,path):
        self.b=bytearray(path.read_bytes());self.sec=[struct.unpack_from('<II',self.b,16+i*8) for i in range(16)];self.cache={}
        off,n=self.sec[0]; self.strings=[self.string_at(struct.unpack_from('<I',self.b,off+i*4)[0]) for i in range(n)]
    def string_at(self,n):
        p=self.sec[1][0]+n;return bytes(self.b[p:self.b.index(0,p)]).decode('utf8')
    def records(self,sec,fmt):
        key=(sec,fmt)
        if key not in self.cache:
            off,n=self.sec[sec];s=struct.calcsize(fmt);self.cache[key]=[struct.unpack_from(fmt,self.b,off+i*s) for i in range(n)]
        return self.cache[key]
    def command(self,k):
        c=self.records(5,'<HBBIHH')[k];args=[]
        for t,pad,loc,v in self.records(4,'<BBHI')[c[3]:c[3]+c[1]]:
            args.append(self.strings[v] if t in (2,3) else struct.unpack('<f' if t==1 else '<i',struct.pack('<I',v))[0])
        return OPS[c[0]],args
    def phase_cmds(self,m):
        ph=self.records(7,'<IIIHHIHHHHI')[m[6]]
        ids=list(range(ph[2],ph[2]+ph[3]))
        for s in self.records(8,'<IHHhHIIIBBBBHHI4x')[ph[6]:ph[6]+ph[7]]:ids+=range(s[0],s[0]+s[1])
        return [self.command(k) for k in ids]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',type=Path);ap.add_argument('out',type=Path);ap.add_argument('--plant',type=int);a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True);expect=[];manifest=[];fail=0
    for lv in range(2,8):
        if a.plant and lv!=a.plant:continue
        d=ROOT/f'hit-and-run-web/source/game/scripts/missions/level0{lv}'
        scheduled=[str(c.args[0]) for c in calls(d/'level.mfk') if c.op=='AddBonusMission']
        givers={str(c.args[3]):c for c in calls(d/'leveli.mfk') if c.op=='AddNPCCharacterBonusMission'}
        p=Pack(a.stage/f'l{lv}/level0{lv}.msn');missions=p.records(6,'<IIIHHHHIII')
        if a.plant:
            # Corrupt a real loaded numeric race rule, not expected values or pass/fail logic.
            plant_m=next(m for m in missions if p.strings[m[0]]=='sr1')
            plant_ph=p.records(7,'<IIIHHIHHHHI')[plant_m[6]]
            plant_st=p.records(8,'<IHHhHIIIBBBBHHI4x')[plant_ph[6]]
            for k in range(plant_st[0],plant_st[0]+plant_st[1]):
                c=p.records(5,'<HBBIHH')[k]
                if OPS[c[0]]=='SetRaceLaps':
                    off=p.sec[4][0]+c[3]*8;struct.pack_into('<I',p.b,off+4,9);p.cache.pop((4,'<BBHI'),None);print(f'PLANT L{lv} SetRaceLaps packet argument=9');break
        for mid in ('sr1','sr2','sr3','bm1','gr1'):
            matches=[(path,calls(path)) for path in sorted(d.glob('*.mfk')) if any(c.op=='SelectMission' and str(c.args[0]).lower()==mid for c in calls(path))]
            matches.sort(key=lambda item:item[0].name!=f'{mid}i.mfk')
            if not matches:raise ValueError(f'No disc SelectMission({mid}) L{lv}')
            source,cs=matches[0];m=next((m for m in missions if p.strings[m[0]]==mid),None)
            want=[sig(c.op,c.args) for c in cs if c.op in RULES]
            got=[sig(op,args) for op,args in p.phase_cmds(m) if op in RULES] if m else []
            ok=mid in scheduled and mid in givers and m is not None and want==got
            print(f'DATA L{lv} {mid} {"PASS" if ok else "FAIL"} rules={len(want)}')
            fail+=not ok
            if not ok:print('MISMATCH',json.dumps({'disc':want,'packet':got},ensure_ascii=False))
            stages=[];stage=None
            for c in cs:
                if c.op=='AddStage':stage=[];stages.append(stage)
                elif stage is not None and c.op!='CloseStage':stage.append(c)
            # Entry-fee stage is legitimately consumed before wager race starts.
            start=next((i for i,s in enumerate(stages) if any(c.op=='AddObjective' and str(c.args[0])!='coins' for c in s)),0)
            s=stages[start];obj=next(str(c.args[0]).lower() for c in s if c.op=='AddObjective')
            val=lambda op,default:next((float(c.args[0]) for c in s if c.op==op),default)
            laps=int(val('SetRaceLaps',1));items=sum(c.op=='AddCollectible' for c in s)
            cd=[(str(c.args[0]),int(c.args[1])) for c in s if c.op=='AddToCountdownSequence']
            up=int(any(c.op=='UseElapsedTime' for c in s));vehicles=sum(c.op=='AddStageVehicle' for c in s);waypoints=sum(c.op=='AddStageWaypoint' for c in s)
            expect.append(f'{lv}\t{mid}\t{start}\t{OBJS.index(obj)}\t{laps}\t{items}\t{val("SetStageTime",0):g}\t{val("SetParTime",0):g}\t{sum(ms for _,ms in cd)}\t{len(cd)}\t{up}\t{vehicles}\t{waypoints}')
            manifest.append({'level':lv,'mission':mid,'npc':list(givers[mid].args),'first_stage':start,'objective':obj,'laps':laps,'items':items,'countdown_ms':cd,'all_main_rules':want,'source':str(source)})
    (a.out/'expect.tsv').write_text('\n'.join(expect)+'\n')
    (a.out/'disc-rules.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(f'RESULT data {"FAIL" if fail else "PASS"} failures={fail}');return bool(fail)
if __name__=='__main__':sys.exit(main())
