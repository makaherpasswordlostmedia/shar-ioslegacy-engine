// Separate PSP hardware evidence, not an emulator benchmark and never CPU fallback
#include <pspkernel.h>
#include <pspdisplay.h>
#include <pspdebug.h>
#include <pspctrl.h>
#include <psppower.h>
#include <pspaudio.h>
#include <stdio.h>
#include <stdarg.h>
#include <stddef.h>
#include "workloads.h"
#include "audition_controls.h"
#include "pcm_output.h"
#include "reference_tone.h"
#include "../viewer/me/mebox.h"
#include "../viewer/fpuguard.h"
PSP_MODULE_INFO("SHARME_TEST",0,1,0);
PSP_MAIN_THREAD_ATTR(THREAD_ATTR_USER | THREAD_ATTR_VFPU);
PSP_HEAP_SIZE_KB(2048);
volatile int fpuKeep;volatile unsigned fpuSeenThr,fpuSeenFlg;
extern int meSvcBootUser(const char*,int,char*,int),meSvcScheme(void),meSvcSlept(void);
extern int meSvcSubmit(int,volatile MeBox*,unsigned,void*,unsigned);
extern int meSvcPoll(int,volatile MeBox*,unsigned,unsigned*);
extern unsigned meSvcQuiesce(void);
// Loader references these game clients; tester sends its own static jobs instead
int audioMeAttach(void){return -1;} unsigned audioMeJobAddr(void){return 0;} unsigned audioMeDataAddr(void){return 0;}
int fxMeAttach(void){return -1;}
static char dir[256],report[24576];static unsigned used;
static volatile int exitWanted;static volatile int available;static int passed,failed,stickyFault;
static volatile int audioActive;static char audioFault[160];
static MeBox box __attribute__((aligned(64)));
static MeBox fxBox __attribute__((aligned(64)));
static unsigned jointCases,jointLate;
static SpatialJob sp,spRef;
static MixJob mix,mixRef;
static FxJob fx,fxRef;
static FxEmit emit __attribute__((aligned(64)));
static FxV vertices[FX_NEL*4] __attribute__((aligned(64))),refVertices[FX_NEL*4] __attribute__((aligned(64)));
static unsigned char bank[3*1024*1024] __attribute__((aligned(64)));
static PcmOutput pcm;
static int soundOnly;
typedef struct {char magic[4];unsigned bytes,samples,start,end,rate,ch;short hist[4];unsigned pad[7];} Clip;
static Clip clip;
static unsigned now(void){return sceKernelGetSystemTimeLow();}
static void save(void){
  char fn[300];snprintf(fn,sizeof fn,"%sme-test.txt",dir);
  SceUID f=sceIoOpen(fn,PSP_O_WRONLY|PSP_O_CREAT|PSP_O_TRUNC,0777);int ok=0;
  if(f>=0){ok=sceIoWrite(f,report,used)==(int)used;sceIoClose(f);}
  if(!ok){pspDebugScreenPrintf("LOG WRITE FAILED; restart after USB check\n");stickyFault=1;available=0;}
}
static void logLine(const char *fmt,...){char s[512];va_list a;va_start(a,fmt);vsnprintf(s,sizeof s,fmt,a);va_end(a);unsigned n=strlen(s);if(used+n<sizeof report){memcpy(report+used,s,n+1);used+=n;}pspDebugScreenPrintf("%s",s);}
static void stage(const char *name,int n){logLine("BEGIN %s n=%d\n",name,n);save();}
static int exitCb(int a,int b,void*c){(void)a;(void)b;(void)c;exitWanted=1;return 0;}
static int callbacks(SceSize a,void*b){(void)a;(void)b;int cb=sceKernelCreateCallback("exit",exitCb,NULL);sceKernelRegisterExitCallback(cb);sceKernelSleepThreadCB();return 0;}
static unsigned long long threadClocks(void){SceKernelThreadInfo i;memset(&i,0,sizeof i);i.size=sizeof i;if(sceKernelReferThreadStatus(sceKernelGetThreadId(),&i)<0)return 0;return ((unsigned long long)i.runClocks.hi<<32)|i.runClocks.low;}
static int fail(const char *why){
  failed++;stickyFault=1;available=0;
  // No screen or Memory Stick I/O on the real-time producer, even on failure
  if(audioActive){snprintf(audioFault,sizeof audioFault,"%s",why);return 0;}
  logLine("FAIL %s\n",why);save();return 0;
}
// Total wall latency includes cache handoff and polling. Thread residency includes polling;
// it is not labelled raw ME execution time or a whole-game FPS measurement
static int dispatch(unsigned kind,void *job,unsigned size,unsigned *latency,unsigned *resident,unsigned expected){
  if(!available||exitWanted)return 0;
  unsigned t=now(),sum=0;unsigned long long c=threadClocks();
  if(size)sceKernelDcacheWritebackInvalidateRange(job,size);
  int seq;
  do{seq=meSvcSubmit(0,&box,kind,job,size);if(seq<0)sceKernelDelayThreadCB(10);}while(seq<0&&now()-t<ME_PROBE_TIMEOUT_US&&!exitWanted);
  if(seq<=0)return fail("submit/timeout");
  while(!meSvcPoll(0,&box,(unsigned)seq,&sum)){
    if(now()-t>ME_PROBE_TIMEOUT_US)return fail("ME response timeout (no CPU fallback)");
    if(meSvcSlept())return fail("suspended; restart test after wake");
    sceKernelDelayThreadCB(50);
  }
  volatile MeBox *u=(volatile MeBox*)ME_UNCACHED(&box);
  while(!(u->chain&ME_CH_FIN)){
    if(now()-t>ME_PROBE_TIMEOUT_US)return fail("ME chain tail timeout");
    sceKernelDelayThreadCB(10);
  }
  if(size)sceKernelDcacheInvalidateRange(job,size);
  *latency=now()-t;*resident=(unsigned)(threadClocks()-c);
  if(sum!=expected)return fail("wrong ME signature/size");
  return 1;
}
typedef struct {unsigned cpu,wall,resident,max,late,n;unsigned long long cpuRun;} Stats;
static int summarize(const char *name,int n,Stats *s){
  if(s->n!=64)return fail("incomplete benchmark");
  passed++;
  unsigned cpu=s->cpu/s->n,res=s->resident/s->n;
  logLine("PASS %s %d x%u cpu=%uus me-wall=%uus\n",name,n,s->n,cpu,s->wall/s->n);
  logLine(" main runClocks: cpu=%llu ME=%u ticks\n",s->cpuRun/s->n,res);
  logLine(" worst=%uus late=%u candidate=%s\n",s->max,s->late,s->cpuRun&&res&&res<s->cpuRun/s->n&&s->late==0?"YES":"NO/NEEDS QUEUE");save();return 1;
}
static void measure(Stats *s,unsigned cpu,unsigned wall,unsigned resident){s->cpu+=cpu;s->wall+=wall;s->resident+=resident;s->n++;if(wall>s->max)s->max=wall;if(wall>11610)s->late++;}
static int spatialCase(int n){
  stage("distance/pan",n);Stats s={0};
  for(unsigned k=0;k<64&&!exitWanted;k++){
    spatialInput(&sp,n,k+17);spRef=sp;unsigned long long c=threadClocks();unsigned t=now();mixSpatialBatchRun(&spRef);unsigned cpu=now()-t,wall,res;s.cpuRun+=threadClocks()-c;
    if(!dispatch(ME_KIND_SPATIAL,&sp,sizeof sp,&wall,&res,0))return 0;
    if(memcmp(&sp,&spRef,sizeof sp))return fail("distance/pan mismatch");measure(&s,cpu,wall,res);
  }
  return summarize("distance/pan",n,&s);
}
static int mixCase(int n){
  stage("ADPCM/resample/mix",n);Stats s={0};
  for(unsigned k=0;k<64&&!exitWanted;k++){
    mixerInput(&mix,bank,clip.samples,clip.start,clip.end,clip.rate,clip.ch,clip.hist,n,k+13);
    mixRef=mix;unsigned long long c=threadClocks();unsigned t=now();mixDspRun(&mixRef);unsigned cpu=now()-t,wall,res;s.cpuRun+=threadClocks()-c;
    mix.data=(const unsigned char*)ME_UNCACHED(bank);
    if(!dispatch(ME_KIND_MIX,&mix,sizeof mix,&wall,&res,0))return 0;
    mix.data=bank;
    if(memcmp(&mix,&mixRef,sizeof mix))return fail("ADPCM/voice-state mismatch");measure(&s,cpu,wall,res);
  }
  return summarize("ADPCM/mix",n,&s);
}
static int fxCase(int n){
  stage("particles/FPU/vertices",n);Stats s={0};
  for(unsigned k=0;k<64&&!exitWanted;k++){
    memset(vertices,0,sizeof vertices);memset(refVertices,0,sizeof refVertices);
    particlesInput(&fx,&emit,vertices,n,k+3,fpuGet()&FPU_KEEP_MASK);fxRef=fx;fxRef.vout=refVertices;
    sceKernelDcacheWritebackInvalidateRange(&emit,sizeof emit);
    sceKernelDcacheWritebackInvalidateRange(vertices,sizeof vertices);
    unsigned long long c=threadClocks();unsigned t=now();fxdRun(&fxRef);unsigned cpu=now()-t,wall,res;s.cpuRun+=threadClocks()-c;
    if(!dispatch(ME_KIND_FX,&fx,sizeof fx,&wall,&res,0))return 0;
    sceKernelDcacheInvalidateRange(vertices,sizeof vertices);
    fxRef.vout=vertices;
    if(memcmp(&fx,&fxRef,sizeof fx)||fx.nq<1||memcmp(vertices,refVertices,fx.nq*4*sizeof(FxV)))return fail("particle/FPU/vertex mismatch");
    measure(&s,cpu,wall,res);
  }
  return summarize("particles",n,&s);
}
static int loadClip(const char *name){
  char fn[300];snprintf(fn,sizeof fn,"%s%s",dir,name);SceUID f=sceIoOpen(fn,PSP_O_RDONLY,0);if(f<0)return 0;
  int ok=sceIoRead(f,&clip,sizeof clip)==sizeof clip&&!memcmp(clip.magic,"MET1",4)&&clip.bytes<=sizeof bank&&clip.bytes>0&&(clip.ch==1||clip.ch==2)&&clip.rate>0&&clip.rate<=48000&&clip.start<clip.end&&clip.end<=clip.samples&&clip.samples<=clip.bytes/(16*clip.ch)*28;
  if(ok)ok=sceIoRead(f,bank,clip.bytes)==(int)clip.bytes;sceIoClose(f);sceKernelDcacheWritebackInvalidateRange(bank,sizeof bank);return ok;
}
// Force an audio arrival while FX is already running. References are computed
// BEFORE the measured interval, so the checker does not manufacture audio lateness
static int jointCase(int nv,int np){
  stage("JOINT audio after FX",np);
  unsigned worst=0,total=0,late=0,tries=0,chains0;
  extern unsigned meSvcChained;chains0=meSvcChained;
  for(unsigned k=0;k<32&&!exitWanted;k++){
    mixerInput(&mix,bank,clip.samples,clip.start,clip.end,clip.rate,clip.ch,clip.hist,nv,k+71);
    mixRef=mix;mixDspRun(&mixRef);mix.data=(const unsigned char*)ME_UNCACHED(bank);
    memset(vertices,0,sizeof vertices);memset(refVertices,0,sizeof refVertices);
    particlesInput(&fx,&emit,vertices,np,k+13,fpuGet()&FPU_KEEP_MASK);fxRef=fx;fxRef.vout=refVertices;fxdRun(&fxRef);
    sceKernelDcacheWritebackInvalidateRange(&emit,sizeof emit);
    sceKernelDcacheWritebackInvalidateRange(vertices,sizeof vertices);
    sceKernelDcacheWritebackInvalidateRange(&fx,sizeof fx);
    unsigned start=now();int fq;
    do{fq=meSvcSubmit(1,&fxBox,ME_KIND_FX,&fx,sizeof fx);if(fq<0)sceKernelDelayThreadCB(10);}while(fq<0&&now()-start<50000&&!exitWanted);
    if(fq<=0)return fail("JOINT FX submit timeout");
    // Alternating immediate and slightly delayed audio arrivals, not just one race
    if(k%3)sceKernelDelayThreadCB((k%3)*250);
    unsigned at=now();sceKernelDcacheWritebackInvalidateRange(&mix,sizeof mix);int aq;
    do{aq=meSvcSubmit(0,&box,ME_KIND_MIX,&mix,sizeof mix);if(aq<0){tries++;sceKernelDelayThreadCB(10);}}while(aq<0&&now()-at<50000&&!exitWanted);
    if(aq<=0)return fail("JOINT audio submit timeout");
    unsigned sumA=0,sumF=0;int ad=0,fd=0;unsigned latency=0;
    volatile MeBox *ua=(volatile MeBox*)ME_UNCACHED(&box),*uf=(volatile MeBox*)ME_UNCACHED(&fxBox);
    while(!ad||!fd||!(ua->chain&ME_CH_FIN)||!(uf->chain&ME_CH_FIN)){
      if(!ad&&meSvcPoll(0,&box,(unsigned)aq,&sumA)){ad=1;latency=now()-at;}
      if(!fd&&meSvcPoll(1,&fxBox,(unsigned)fq,&sumF))fd=1;
      if(now()-at>50000)return fail("JOINT response/tail timeout");
      if(meSvcSlept())return fail("JOINT suspend; restart test");
      sceKernelDelayThreadCB(50);
    }
    if(sumA||sumF)return fail("JOINT layout/signature");
    sceKernelDcacheInvalidateRange(&mix,sizeof mix);sceKernelDcacheInvalidateRange(&fx,sizeof fx);sceKernelDcacheInvalidateRange(vertices,sizeof vertices);
    mix.data=bank;fxRef.vout=vertices;
    if(memcmp(&mix,&mixRef,sizeof mix)||memcmp(&fx,&fxRef,sizeof fx)||fx.nq<1||memcmp(vertices,refVertices,fx.nq*4*sizeof(FxV)))return fail("JOINT audio/FX bit mismatch");
    total+=latency;if(latency>worst)worst=latency;if(latency>11610)late++;
  }
  if(exitWanted)return 0;
  unsigned chains=meSvcChained-chains0;
  if(!chains)return fail("JOINT priority chain never exercised");
  jointCases++;jointLate+=late;
  logLine("JOINT voices=%d FX=%d jobs=32 exact=PASS\n",nv,np);
  logLine(" chains=%u retries=%u audio-avg=%uus worst=%uus late=%u\n",chains,tries,total/32,worst,late);
  logLine(" audio-budget=%s (limit 11610us)\n",late?"OVER; reduce FX":"PASS");save();return 1;
}
static void suite(void){
  pspDebugScreenClear();stage("boot native user-memory ME",0);char boot[512];if(stickyFault)return;
  int emu=0,v=0;emu=sceIoDevctl("emulator:",3,NULL,0,&v,4)==0&&v;
  if(emu){logLine("SKIP PPSSPP has no real ME; no hardware PASS\n");save();return;}
  int rc=meSvcBootUser(dir,emu,boot,sizeof boot);logLine("%s",boot);
  if(rc<0){fail("native service startup; see res fields above");return;}
  if(meSvcScheme()!=ME_MEM_USER){fail("unsupported service scheme");return;}
  available=1;memset(&box,0,sizeof box);sceKernelDcacheWritebackInvalidateRange(&box,sizeof box);
  unsigned wall,res;stage("hardware heartbeat",0);
  if(!dispatch(ME_KIND_TINY,&sp,0,&wall,&res,0x7e57u))return;
  logLine("ME heartbeat=%u status=%08x native scheme=u\n",((volatile MeBox*)ME_UNCACHED(&box))->beat,((volatile MeBox*)ME_UNCACHED(&box))->status);
  // A malformed job must be rejected, not counted as a successful DSP execution
  stage("bad-size guard",0);if(!dispatch(ME_KIND_SPATIAL,&sp,sizeof sp-64,&wall,&res,ME_MIX_BADSIZE))return;
  if(soundOnly){logLine("MODE MUSIC ONLY; DSP matrix not repeated\n");save();return;}
  const int counts[]={1,8,24,128};for(int i=0;i<4&&available&&!exitWanted;i++)if(!spatialCase(counts[i]))return;
  if(!loadClip("engine.vag")){fail("missing/invalid native engine clip");return;}
  const int voices[]={1,8,24};for(int i=0;i<3&&available&&!exitWanted;i++)if(!mixCase(voices[i]))return;
  const int particles[]={32,128,400};for(int i=0;i<3&&available&&!exitWanted;i++)if(!fxCase(particles[i]))return;
  memset(&fxBox,0,sizeof fxBox);sceKernelDcacheWritebackInvalidateRange(&fxBox,sizeof fxBox);
  const int joint[][2]={{8,128},{24,32},{24,128},{24,400}};
  for(int i=0;i<4&&available&&!exitWanted;i++)if(!jointCase(joint[i][0],joint[i][1]))return;
  logLine("END cases=%d/10 fail=%d hardware=%s joint=%u/4 late=%u\n",passed,failed,passed==10&&!failed?"PASS":"INCOMPLETE",jointCases,jointLate);save();
}
typedef struct {
  AudControls controls;unsigned frame,receipts,peak,wall,empty,clips,pcmPeak,events;
  unsigned routeBuffers[4],routeEmpty[4];int gl,gr,tone;
} AudView;
typedef struct {unsigned keys,frame;int dist,side,sweep,me,mute,tone;} AudEvent;
static AudView audioView;static AudEvent audioEvents[128];
static SceUID audioViewLock;static volatile int audioDone;
static short toneTable[REF_TONE_SAMPLES];
// UI copies only a small snapshot under this lock. Screen drawing happens AFTER
// releasing it, so audio never waits for a framebuffer clear or printf
static void publishView(const AudView *v){sceKernelWaitSema(audioViewLock,1,NULL);audioView=*v;sceKernelSignalSema(audioViewLock,1);}
static void readView(AudView *v){sceKernelWaitSema(audioViewLock,1,NULL);*v=audioView;sceKernelSignalSema(audioViewLock,1);}
static int auditionAudio(SceSize args,void *argp){
  (void)args;(void)argp;fpuThreadInit();AudView v={0};
  int channel=sceAudioChReserve(-1,MIX_FRAMES,PSP_AUDIO_FORMAT_STEREO);
  if(channel<0){fail("audition channel reserve");audioDone=1;return 0;}
  mixerInput(&mix,bank,clip.samples,clip.start,clip.end,clip.rate,clip.ch,clip.hist,1,0);
  // Match the game's native looping voice reset, including interpolation history
  mix.v[0].end=clip.end;mix.v[0].bufLen=1;mix.v[0].pos=1u<<16;
  SceCtrlData initial;sceCtrlPeekBufferPositive(&initial,1);
  unsigned held=(initial.Buttons&PSP_CTRL_CROSS?AU_SWEEP:0)|(initial.Buttons&PSP_CTRL_TRIANGLE?AU_ROUTE:0);
  v.controls=(AudControls){10,0,1,0,0,held,0,0};
  unsigned startHeld=initial.Buttons&PSP_CTRL_START,tonePhase=0,toneBlend=0;
  memset(&pcm,0,sizeof pcm);
  while(!exitWanted&&available){
    fpuThreadPoll(FPU_T_MIX);
    SceCtrlData p;sceCtrlPeekBufferPositive(&p,1);unsigned keys=0;
    if(p.Buttons&PSP_CTRL_UP)keys|=AU_NEAR;if(p.Buttons&PSP_CTRL_DOWN)keys|=AU_FAR;
    if(p.Buttons&PSP_CTRL_LEFT)keys|=AU_LEFT;if(p.Buttons&PSP_CTRL_RIGHT)keys|=AU_RIGHT;
    if(p.Buttons&PSP_CTRL_TRIANGLE)keys|=AU_ROUTE;if(p.Buttons&PSP_CTRL_CROSS)keys|=AU_SWEEP;
    if(p.Buttons&PSP_CTRL_SQUARE)keys|=AU_MUTE;if(p.Buttons&PSP_CTRL_SELECT)keys|=AU_CENTER;
    if(p.Buttons&PSP_CTRL_LTRIGGER)keys|=AU_SNAP_LEFT;if(p.Buttons&PSP_CTRL_RTRIGGER)keys|=AU_SNAP_RIGHT;
    if(p.Buttons&PSP_CTRL_CIRCLE)keys|=AU_EXIT;
    unsigned hit=audControlsStep(&v.controls,keys,now(),v.frame);
    if((p.Buttons&PSP_CTRL_START)&&!startHeld){v.tone=!v.tone;hit|=2048;}
    startHeld=p.Buttons&PSP_CTRL_START;
    if(hit){
      if(v.events<128)audioEvents[v.events]=(AudEvent){hit,v.frame,v.controls.dist,v.controls.side,v.controls.autoSweep,v.controls.useME,v.controls.muted,v.tone};
      v.events++;
    }
    if(hit&AU_EXIT)break;
    MixVoice *voice=&mix.v[0];voice->point.p[0]=v.controls.side*16;voice->point.p[2]=v.controls.dist*16;
    voice->tgl=voice->tgr=v.controls.muted?0:8192;
    unsigned t=now(),res=0;v.wall=0;
    if(v.controls.useME){mix.data=(const unsigned char*)ME_UNCACHED(bank);if(!dispatch(ME_KIND_MIX,&mix,sizeof mix,&v.wall,&res,0))break;mix.data=bank;v.receipts++;}
    else{mixDspRun(&mix);v.wall=now()-t;}
    if(v.wall>v.peak)v.peak=v.wall;v.gl=voice->gl;v.gr=voice->gr;
    short *out=pcmOutputBuffer(&pcm);
    // The clean carrier is CPU-generated; gains still come from the selected DSP.
    // Keep native decode running to preserve identical producer load during A/B.
    refToneMix(out,mix.acc,toneTable,&tonePhase,&toneBlend,v.tone,v.gl,v.gr,&v.clips,&v.pcmPeak);
    sceKernelDcacheWritebackRange(out,MIX_FRAMES*2*sizeof(short));
    unsigned route=(v.controls.useME?0:1)+(v.tone?2:0);
    if(v.frame&&sceAudioGetChannelRestLen(channel)==0){v.empty++;v.routeEmpty[route]++;}
    int ar=sceAudioOutputBlocking(channel,PSP_AUDIO_VOLUME_MAX,out);
    if(ar<0){fail("audition audio output");break;}
    pcmOutputQueued(&pcm);v.frame++;v.routeBuffers[route]++;publishView(&v);
  }
  unsigned drain=now();while(sceAudioGetChannelRestLen(channel)>0&&now()-drain<100000)sceKernelDelayThread(500);
  sceAudioChRelease(channel);publishView(&v);audioDone=1;return 0;
}
static void audition(void){
  if(!available||(!soundOnly&&passed!=10)||stickyFault)return;
  stage("audition music",1);if(!loadClip("melody.vag")){fail("missing/invalid Simpsons theme");return;}
  memset(&audioView,0,sizeof audioView);audioDone=0;audioFault[0]=0;
  for(unsigned i=0;i<REF_TONE_SAMPLES;i++)toneTable[i]=(short)(8192.f*sinf(25.13274122872f*i/REF_TONE_SAMPLES));
  logLine("AUDITION started; source=simpsons_theme channels=2 gain=0.25 PCM=2 audio-priority=0x12 UI=10Hz\n");save();
  audioViewLock=sceKernelCreateSema("aud-view",0,1,1,NULL);
  if(audioViewLock<0){fail("audition snapshot semaphore");return;}
  SceUID th=sceKernelCreateThread("aud-pcm",auditionAudio,0x12,0x10000,PSP_THREAD_ATTR_USER,NULL);
  if(th<0){sceKernelDeleteSema(audioViewLock);fail("audition producer create");return;}
  audioActive=1;
  if(sceKernelStartThread(th,0,NULL)<0){audioActive=0;sceKernelDeleteThread(th);sceKernelDeleteSema(audioViewLock);fail("audition producer start");return;}
  while(!audioDone){
    AudView v;readView(&v);
    pspDebugScreenClear();pspDebugScreenPrintf("SHAR ME Test 1.6   %s\n\n",soundOnly?"MUSIC ONLY":"DSP 10/10 PASS");
    pspDebugScreenPrintf("ROUTE: %s  native replies: %u\n",v.controls.useME?"MEDIA ENGINE":"MAIN CPU",v.receipts);
    pspDebugScreenPrintf("SOURCE: %s\n",v.tone?"CLEAN TONE (CPU carrier + DSP gains)":"SIMPSONS THEME (main menu)");
    pspDebugScreenPrintf("Forward: %dm   side: %+dm\n",v.controls.dist,v.controls.side);
    pspDebugScreenPrintf("Gain L %.3f  R %.3f  range 60m\n",v.gl/32768.f,v.gr/32768.f);
    pspDebugScreenPrintf("DSP %uus  peak %uus  budget 11610\n",v.wall,v.peak);
    pspDebugScreenPrintf("PCM buffers=%u empty=%u clipped=%u\n\n",v.frame,v.empty,v.clips);
    pspDebugScreenPrintf("HOLD D-pad: move / stop sweep\nL / R: source left / right\nSELECT: centre + 10m\nTRIANGLE: ME / CPU\nSTART: melody / clean tone\nCROSS: sweep (%s)  SQUARE: mute (%s)\nCIRCLE: finish + save; HOME: exit\n",v.controls.autoSweep?"ON":"OFF",v.controls.muted?"ON":"OFF");
    sceKernelDelayThreadCB(100000);
  }
  sceKernelWaitThreadEnd(th,NULL);audioActive=0;sceKernelDeleteThread(th);sceKernelDeleteSema(audioViewLock);
  AudView *v=&audioView;
  for(unsigned i=0;i<v->events&&i<128;i++){
    AudEvent *e=&audioEvents[i];logLine("CTRL frame=%u keys=%04x near=%d side=%d sweep=%d ME=%d mute=%d tone=%d\n",e->frame,e->keys,e->dist,e->side,e->sweep,e->me,e->mute,e->tone);
  }
  if(audioFault[0])logLine("FAIL audio producer: %s\n",audioFault);
  logLine("AUDITION END buffers=%u native-replies=%u peak=%uus events=%u held-moves=%u near=%d side=%d\n",v->frame,v->receipts,v->peak,v->events,v->controls.heldMoves,v->controls.dist,v->controls.side);
  logLine("PCM buffers=2 empty-at-submit=%u clipped=%u peak-sample=%u producer=0x12 UI=10Hz\n",v->empty,v->clips,v->pcmPeak);
  const char *names[]={"melody-ME","melody-CPU","tone-ME-gains","tone-CPU-gains"};
  for(unsigned i=0;i<4;i++)logLine("PCM route=%s buffers=%u empty=%u\n",names[i],v->routeBuffers[i],v->routeEmpty[i]);save();
}
int main(int argc,char **argv){
  strcpy(dir,"ms0:/PSP/GAME/SHARME/");if(argc&&argv[0]){snprintf(dir,sizeof dir,"%s",argv[0]);char *s=strrchr(dir,'/');if(s)s[1]=0;}
  pspDebugScreenInit();msioInit();sceCtrlSetSamplingCycle(0);sceCtrlSetSamplingMode(PSP_CTRL_MODE_DIGITAL);
  int th=sceKernelCreateThread("callbacks",callbacks,0x11,0x2000,0,NULL);if(th>=0)sceKernelStartThread(th,0,NULL);
  fpuThreadInit();scePowerSetClockFrequency(333,333,166);
  logLine("SHAR ME Test v1.6 Simpsons theme spatial music\nCPU=%d bus=%d FW=%08x battery=%d%%\n",scePowerGetCpuClockFrequency(),scePowerGetBusClockFrequency(),sceKernelDevkitVersion(),scePowerGetBatteryLifePercent());
  logLine("TRIANGLE: PLAY MUSIC / move source\nCROSS: full DSP + joint loads, then music\nReport: PSP/GAME/SHARME/me-test.txt\nNo CPU fallback counted as ME PASS\nKeep PSP awake during test\n\nHOME exits; game files are separate\n");save();
  while(!exitWanted){SceCtrlData p;sceCtrlPeekBufferPositive(&p,1);if(p.Buttons&PSP_CTRL_TRIANGLE){soundOnly=1;break;}if(p.Buttons&PSP_CTRL_CROSS)break;sceKernelDelayThreadCB(20000);}
  if(!exitWanted){suite();if(!exitWanted&&available&&(soundOnly||passed==10))audition();}
  logLine("FINAL PASS=%d/10 FAIL=%d JOINT=%u/4 LATE=%u\n",passed,failed,jointCases,jointLate);save();
  while(!exitWanted){sceKernelDelayThreadCB(20000);}
  // Static buffers remain alive on timeout; no frees while ME may still own them
  meSvcQuiesce();sceKernelExitGame();return 0;
}
