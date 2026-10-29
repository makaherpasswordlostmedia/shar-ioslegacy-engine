# пул эмуляторов (EMU_MINE, по умолчанию 2) через общий раннер tools/emu_run.sh: куски сценариев, результат в out_N<имя>, ненужные bmp удаляются; уже готовые куски пропускаются
import subprocess,glob,os,sys,threading,queue,time
ROOT=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..'))
J=os.environ.get('NIGHT913_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','build','night913'); J=os.path.abspath(J); os.chdir(J)   # рабочая папка: night913/sc, hz913, EBOOT; NIGHT913_DIR переопределяет
EMU=os.path.join(ROOT,'tools','emu_run.sh'); EB=os.path.abspath(os.environ.get('EB','z913f.PBP'))   # EBOOT ночного прогона: EB=… или J/z913f.PBP
q=queue.Queue()
for f in sorted(glob.glob('night913/sc/L*.txt')):
    n=os.path.basename(f)[:-4]
    if not os.path.exists(f'out_N{n}/DONE'): q.put((f,n))
def work(home):
    while True:
        try: f,n=q.get_nowait()
        except queue.Empty: return
        t=time.time(); env=dict(os.environ,OUT=J,EMU_OWNER='night913')   # общий раннер: итог в J/out_N<имя>, очередь эмуляторов общая (Мак ≤ EMU_SLOTS, хозяин ≤ EMU_MINE)
        subprocess.run([EMU,os.path.abspath(f),'N'+n,EB,'900'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for b in glob.glob(f'out_N{n}/*.bmp'): os.remove(b)
        ok=os.path.exists(f'out_N{n}/smoke.txt') and any(l.startswith('SCENE b_') for l in open(f'out_N{n}/smoke.txt'))
        if ok: open(f'out_N{n}/DONE','w').write('1')
        open('night913/progress.log','a').write(f"{time.strftime('%H:%M:%S')} {n} {'ok' if ok else 'FAIL'} {int(time.time()-t)}s\n")
ts=[threading.Thread(target=work,args=(h,)) for h in range(int(os.environ.get('EMU_MINE','2')))]
[t.start() for t in ts]; [t.join() for t in ts]; open('night913/ALLDONE','w').write(time.strftime('%H:%M:%S'))
