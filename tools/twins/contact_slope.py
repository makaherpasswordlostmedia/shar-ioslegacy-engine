#!/usr/bin/env python3
"""Finite original contact probe; uses existing window/audio watchdog and writable body addresses.

No schedulers. Pose is obtained by driving, never by writing a guessed angle.
The target/start specification comes from a failed COL1 contact gate.
"""
import argparse,json,math,os,sys,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import placement as P
import drive as D
import common as C

PHYSICS_READS=[(f'pm{i}',0x1298ab8+4*i,'f32') for i in range(16)]+[(f'local{i}',0x1298894+4*i,'f32') for i in range(40)]+[(f'state{i}',0x12987b0+4*i,'f32') for i in range(56)]

def contact_regions(state,q):
    """Use the existing original drive/gate atlas, never a distant teleport.

    Numeric free-air inertia observations do not need a city region; contact
    comparisons do. A missing region cannot be repaired by longer settling.
    """
    if int(q.get('level',1))!=1:raise ValueError('contact addresses/region atlas are for L1 only')
    xyz=q.get('port_start',q.get('throw_cm'))
    if xyz is None:raise ValueError('contact point required')
    point=dict(x=xyz[0],z=xyz[2] if 'port_start' in q else -xyz[2])
    point['regions']=sorted(P.RegionIndex(1).near(point['x'],point['z']))
    need=set(P.required_regions(1,[point])[0]['need'])
    snapshots,_=P.base_sets(1,P.base_info(1))
    snapshot=next((s for s in snapshots if Path(s['file']).resolve()==state.resolve()),None)
    if snapshot is None:raise ValueError('snapshot has no recorded original region coverage')
    missing=need-set(snapshot['safe'])
    if missing:raise ValueError('snapshot lacks required contact regions: '+','.join(sorted(missing)))
    return dict(required=sorted(need),initial_safe=snapshot['safe'],initial_full=snapshot['full'],snapshot_frame=snapshot['frame'])

def transport_regions(guard,rows):
    """Check that aiming did not unload the required regions before placement."""
    G=P.Gates();first=rows[0]
    route=[(r['rel'],r['x'],r['y'],-r['z']) for r in rows]
    events,_,_=G.walk(route,set(guard['initial_full']),G.inside(first['x'],first['y'],-first['z']))
    current=set(guard['initial_full']);old=set(guard['initial_safe']);cutoff=rows[-1]['rel']-75
    for frame,regions,_ in events:
        current=set(regions)
        if frame<=cutoff:old=set(regions)
    safe=current&old
    if not set(guard['required'])<=safe:raise ValueError('aiming unloaded required contact regions')
    guard['transport_safe']=sorted(safe)

def throw_preparation(q,s):
    """Do not mistake a recovered/ignored memory write for the requested throw."""
    cm=[s[k] for k in ('cx','cy','cz')];velocity=[s[k] for k in ('vx','vy','vz')]
    position_error=math.dist(cm,q['throw_cm'])
    velocity_error=math.dist(velocity,q.get('throw_velocity',[0,0,0]))
    # Two PAL frames can move a fast body, and gravity changes its velocity;
    # these bounds distinguish that integration from a reset/ignored throw.
    position_limit=.1+.04*math.dist(q.get('throw_velocity',[0,0,0]),[0,0,0])
    return dict(ok=position_error<=position_limit and velocity_error<=2.,position_error=position_error,position_limit=position_limit,velocity_error=velocity_error,observed_cm=cm,observed_velocity=velocity)

def observe_drop(a):
    extra=P.EXTRA+PHYSICS_READS
    o=P.orig_process(a.out.resolve(),a.state.resolve(),extra,lockstep=2,swthreads=1,null=True);rows=[];timed_out=[]
    def stop_late():
        if o.p.poll() is None:timed_out.append('120 second finite probe timeout');o.p.kill()
    timer=threading.Timer(120,stop_late);timer.daemon=True;timer.start();first=None
    try:
        while True:
            s=o.step()
            if s is None:break
            rows.append(dict(s,rel=o.frame))
            if first is None:first=dict(s)
            if o.frame>=300 or o.bad:break
            cmds=['pad cross 0','pad circle 0',*D.axis('l','x',0)]
            if o.frame in (50,52):cmds+=P.body(first['cx'],first['cy']+15,first['cz'])
            o.send(*cmds)
    finally:
        o.close();timer.cancel()
        (a.out/'trace.json').write_text(json.dumps(rows,indent=1)+'\n')
        report=dict(ok=bool(rows) and o.frame>=300 and not o.bad and not timed_out,frames=o.frame,watchdog=o.bad,timeout=timed_out,state_sha256=C.sha256(a.state))
        (a.out/'report.json').write_text(json.dumps(report,indent=1)+'\n');print(json.dumps(report),flush=True)
    return 0 if report['ok'] else 1

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--state',type=Path,required=True);ap.add_argument('--spec',type=Path);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--observe-drop',action='store_true');a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    if a.observe_drop:return observe_drop(a)
    if a.spec is None:ap.error('--spec required for a contact probe')
    q=json.loads(a.spec.read_text());point=q.get('port_start',q.get('throw_cm'));target=P.ang(math.pi-q['port_heading']);vt=q['speed'];a.out.mkdir(parents=True,exist_ok=True)
    try:region_guard=contact_regions(a.state,q)
    except ValueError as e:
        report=dict(ok=False,error=str(e),frames=0,watchdog=[],state_sha256=C.sha256(a.state),spec=q)
        (a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=1)+'\n');print(json.dumps(report,ensure_ascii=False),flush=True);return 1
    o=P.orig_process(a.out.resolve(),a.state.resolve(),P.EXTRA+PHYSICS_READS,lockstep=2,swthreads=1,null=True)
    start=time.monotonic();timed_out=[]
    def stop_late():
        if o.p.poll() is None:timed_out.append('120 second finite probe timeout');o.p.kill()
    timer=threading.Timer(120,stop_late);timer.daemon=True;timer.start()
    neutral=['pad cross 0','pad circle 0',*D.axis('l','x',0.)];phase='aim';at=0;pose=None;hops=[];failure=None;rows=[]
    # Optional input-only recovery when the original car cannot turn at its
    # starting obstacle. Keep the same frame/time budgets and angle reads;
    # never write a guessed orientation or treat recovery as a driving sample.
    stalled=0;reverse_until=0;reverse_steer=0.;reversals=0;regions_checked=False;preparation=None
    def placement_hops(s):
        if 'throw_cm' in q:return [q['throw_cm'],q['throw_cm']]
        height=max(s['cy']+40,40.);x,y,z=point
        return [(s['cx'],height,s['cz']),(x,height,-z),(x,y+P.CM_LIFT+P.DROP,-z),(x,y+P.CM_LIFT+P.DROP,-z)]
    try:
        while True:
            s=o.step()
            if s is None:break
            f=o.frame;h=math.atan2(s['nx'],s['nz']);v=math.hypot(s['vx'],s['vz']);err=P.ang(target-h)
            rows.append(dict(s,rel=f,phase=phase,aim_reversing=phase=='aim' and f<reverse_until))
            if o.bad or f>2500:failure=str(o.bad or 'frame budget');break
            if phase=='aim':
                if abs(err)<math.radians(3):
                    # Placement already clears linear velocity. A bounded
                    # diagnostic may transport the observed heading directly
                    # instead of drifting past it while braking at a wall.
                    # The settled pose is still measured, not overwritten.
                    phase='place' if q.get('place_on_aim_heading') else 'brake';at=f;cmds=neutral
                    if phase=='place':hops=placement_hops(s)
                else:
                    if q.get('aim_reverse_recovery') and f>=reverse_until:
                        stalled=stalled+2 if v<.2 else 0
                        if stalled>=75 and reversals<4:
                            reverse_until=f+75;reverse_steer=-1 if err>0 else 1;reversals+=1;stalled=0
                    if f<reverse_until:cmds=[*D.axis('l','x',reverse_steer),'pad cross 0','pad circle 1']
                    else:cmds=[*D.axis('l','x',1 if err>0 else -1),f'pad cross {int(v<6)}','pad circle 0']
            elif phase=='brake':
                cmds=['pad cross 0',f'pad circle {int(v>.3)}',*D.axis('l','x',0)]
                if v<.3 or f-at>100:
                    if abs(err)>math.radians(5):phase='aim';o.send(*neutral);continue
                    hops=placement_hops(s);phase='place'
            elif phase=='place':
                if not regions_checked:
                    try:transport_regions(region_guard,rows)
                    except ValueError as e:failure=str(e);break
                    regions_checked=True
                cmds=P.body(*hops.pop(0),*(q.get('throw_velocity',[])))+neutral
                if not hops:
                    phase='drive' if 'throw_cm' in q else 'settle';at=f
            elif phase=='settle':
                cmds=neutral
                if f-at>=125:
                    if s['upy']<.75:failure='placement tilted before contact';break
                    pose=dict(s,heading=h);phase='drive';at=f
                    cmds=P.body(s['cx'],s['cy'],s['cz'],math.sin(h)*vt,0,math.cos(h)*vt)+neutral
            else:
                if pose is None and 'throw_cm' in q:
                    preparation=throw_preparation(q,s)
                    if not preparation['ok']:failure='requested throw was not established in native physics';break
                if pose is None:pose=dict(s,heading=h)
                gas=(f-at<=q.get('gas_frames',20)) if 'throw_cm' in q else v<vt
                rows[-1]['drive_throttle']=int(gas) # held until the next observed lockstep interval
                cmds=neutral+[f'pad cross {int(gas)}']
                if f-at>=300:break
            o.send(*cmds)
    finally:
        o.close();timer.cancel()
        (a.out/'trace.json').write_text(json.dumps(rows,ensure_ascii=False,indent=1)+'\n')
        report=dict(ok=bool(pose) and not failure and not o.bad and not timed_out and bool(rows) and rows[-1]['phase']=='drive' and rows[-1]['rel']-at>=300,
                    error=failure or timed_out or o.bad,pose=pose,frames=o.frame,seconds=time.monotonic()-start,state_sha256=C.sha256(a.state),spec=q,watchdog=o.bad,aim_reversals=reversals,region_guard=region_guard,preparation=preparation)
        (a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=1)+'\n');print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if report['ok'] else 1

if __name__=='__main__':sys.exit(main())
