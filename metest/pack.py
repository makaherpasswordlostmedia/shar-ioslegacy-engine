#!/usr/bin/env python3
"""Build-reviewed standalone payload; deploy only SHARME, verify all hashes, preserve existing apps/logs."""
import argparse,datetime,hashlib,json,os,shutil,struct,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_json(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def protect_games(mount):
    paths=[mount/'PSP/GAME'/a/f for a in ['SHARVIEW','SHARTOUR'] for f in ['EBOOT.PBP','sharme.prx','meaudio','mefx']]
    return {str(p):digest(p) for p in paths if p.exists()}
def native_clip(dst):
    src=ROOT/'build/audio/sfx.sab';b=src.read_bytes()
    magic,ver,nr,nf,nc,ro,vo,fo,co,do,ds=struct.unpack_from('<4s10I',b)
    assert magic==b'SAB1' and ver==1
    # Owned native family sedan engine, resolve car -> resource -> variant -> file
    cars=[i for i in range(nc) if b[co+i*152:co+i*152+16].split(b'\0')[0]==b'famil_v'];assert cars
    rid=struct.unpack_from('<h',b,co+cars[0]*152+18)[0];assert 0<=rid<nr
    name,first,num,*_=struct.unpack_from('<24sHHfffII',b,ro+rid*48);assert num
    fid=struct.unpack_from('<H',b,vo+first*2)[0];assert fid<nf
    off,blocks,samples,start,end,rate,ch,pad,*hist=struct.unpack_from('<5IHBB4h',b,fo+fid*32)
    raw=b[do+off:do+off+blocks*16*ch];assert len(raw)==blocks*16*ch and start<end<=samples
    header=struct.pack('<4s6I4h',b'MET1',len(raw),samples,start,end,rate,ch,*hist).ljust(64,b'\0')
    (dst/'engine.vag').write_bytes(header+raw)
    return dict(source='build/audio/sfx.sab',source_sha256=digest(src),resource=name.split(b'\0')[0].decode(),file=fid,rate=rate,channels=ch,raw_sha256=hashlib.sha256(raw).hexdigest())
def native_music(dst):
    src=ROOT/'build/audio/music.sap';b=src.read_bytes()
    magic,ver,count,table=struct.unpack_from('<4sIII',b);assert magic==b'SAP1' and ver==1
    rows=[b[table+i*64:table+(i+1)*64] for i in range(count)]
    rows=[row for row in rows if row[:28].split(b'\0')[0]==b'simpsons_theme'];assert len(rows)==1
    off,blocks,samples,start,end,rate,ch,loop,nxt,bus,*hist=struct.unpack_from('<5IHBBhh4h',rows[0],28)
    raw=b[off:off+blocks*16*ch]
    original=ROOT/'hit-and-run-web/source/game/sound/music/simpsons_theme.rsd'
    assert raw==original.read_bytes()[2048:],'music differs from original disc ADPCM'
    assert len(raw)<=3*1024*1024 and loop and start<end<=samples and ch==2
    header=struct.pack('<4s6I4h',b'MET1',len(raw),samples,start,end,rate,ch,*hist).ljust(64,b'\0')
    (dst/'melody.vag').write_bytes(header+raw)
    return dict(source='build/audio/music.sap',source_sha256=digest(src),track='simpsons_theme',original_sha256=digest(original),seconds=samples/rate,channels=ch,rate=rate,loop=[start,end],raw_sha256=hashlib.sha256(raw).hexdigest())
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--deploy',action='store_true');ap.add_argument('--mount',type=Path,default=Path('/Volumes/PSP'));a=ap.parse_args()
    proof=json.loads((ROOT/'build/metest/check/result.json').read_text());assert proof['host'].startswith('PASS') and proof['negative'].startswith('FAIL') and proof['closures'].startswith('PASS') and proof['boot_publication'].startswith('PASS')
    assert digest(ROOT/'build/metest/native/EBOOT.PBP')==proof['eboot_sha256'] and digest(ROOT/'viewer/me/sharme.prx')==proof['prx_sha256'],'artifacts changed since checks'
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');payload=ROOT/'_deliverables'/('SHARME-'+stamp)/'SHARME';payload.mkdir(parents=True)
    for src,name in [(ROOT/'build/metest/native/EBOOT.PBP','EBOOT.PBP'),(ROOT/'viewer/me/sharme.prx','sharme.prx'),(ROOT/'metest/README.txt','README.txt')]:shutil.copy2(src,payload/name)
    clip=native_clip(payload);music=native_music(payload)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    (payload/'BUILD.txt').write_text('SHAR ME Test v1.6 spatial Simpsons theme\n'+stamp+'\ncommit '+commit+'\nv1.5 hardware PCM empty0/4447; v1.6 main-menu theme through same ME/CPU path; music listening pending PSP\n')
    files={p.name:dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(payload.iterdir())}
    manifest=dict(app='SHARME',commit=commit,created=stamp,files=files,clip=clip,music=music,host_check=proof)
    write_json(payload/'MANIFEST.json',manifest)
    print('PACK '+str(payload));print(json.dumps(files,indent=2))
    if not a.deploy:return
    assert a.mount.is_mount() and (a.mount/'PSP/GAME').is_dir(),'mounted PSP missing'
    before=protect_games(a.mount);dest=a.mount/'PSP/GAME/SHARME';backup=None
    if dest.exists():
        original={str(p.relative_to(dest)):digest(p) for p in dest.rglob('*') if p.is_file()}
        backup=ROOT/'_backups'/('SHARME-before-'+stamp);shutil.copytree(dest,backup)
        assert all(digest(backup/name)==sha for name,sha in original.items()),'old tester/log backup mismatch'
        write_json(backup/'BACKUP_MANIFEST.json',original)
        # Existing tester is moved on card after a verified local backup, never discarded
        card_backup=a.mount/'PSP/BACKUPS'/('SHARME-'+stamp);card_backup.parent.mkdir(exist_ok=True)
        dest.rename(card_backup)
    staging=a.mount/'PSP/GAME'/('SHARME-install-'+stamp);staging.mkdir()
    for p in sorted(payload.iterdir()):
        q=staging/p.name
        with p.open('rb') as src,q.open('wb') as out:shutil.copyfileobj(src,out);out.flush();os.fsync(out.fileno())
        assert digest(q)==digest(p),f'copy mismatch {q}'
    staging.rename(dest)
    after=protect_games(a.mount);assert before==after,'existing game changed'
    receipt=dict(destination=str(dest),payload=str(payload),commit=commit,backup=str(backup) if backup else None,files={p.name:digest(p) for p in dest.iterdir() if p.is_file()},protected_games=after)
    write_json(ROOT/'build/metest/deploy.json',receipt);print('DEPLOY VERIFIED '+str(dest))
if __name__=='__main__':main()
