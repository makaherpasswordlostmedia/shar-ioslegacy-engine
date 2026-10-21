/* Standalone hardware experiment; does not read or write SHARVIEW.
 * Timing: CPU start through GE completion, no vsync; GPU wait is not total GPU time.
 * All file IO and framebuffer comparisons are outside measured render intervals. */
#ifdef OB_HOST_TEST
#include "host_psp.h"
#else
#include <pspkernel.h>
#include <pspdisplay.h>
#include <pspdebug.h>
#include <pspgu.h>
#include <pspgum.h>
#include <pspge.h>
#include <psppower.h>
#include <psprtc.h>
#include <pspsysmem.h>
#include <pspctrl.h>
#include <malloc.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdarg.h>
#include <math.h>
#include "data_ids.h"
#include "frame_io.h"

PSP_MODULE_INFO("SHAROPTBENCH", 0, 1, 0);
PSP_MAIN_THREAD_ATTR(THREAD_ATTR_USER | THREAD_ATTR_VFPU);
PSP_MAIN_THREAD_STACK_SIZE_KB(128);
PSP_HEAP_SIZE_KB(12*1024);
#define BW 512
#define SW 480
#define SH 272
#define FRAME_BYTES (BW * SH * 2)
#define NFR 120
#define WARM 12
#define ROUNDS 3
#define NV 4
#define IOSAMPLES 64
#define IO_BYTES (8 * 1024 * 1024)
#define IO_SEED 0x93a51c7du
typedef struct { char magic[4]; unsigned version, nt, np, ns; float eye[3], at[3]; unsigned fog; float dist; unsigned bytes, pad[18]; } Header;
typedef struct { unsigned short w,h,levels,pad; unsigned pal,lv[8],pad2; } Texture;
typedef struct { unsigned count, stride, prim, voff, ioff, nv; } Set;
typedef struct { int tex; unsigned flags; float scale,origin[3]; unsigned source,far; Set set[NV]; } Piece;
typedef char CheckHeader[(sizeof(Header)==128)?1:-1];
typedef char CheckTexture[(sizeof(Texture)==48)?1:-1];
typedef char CheckPiece[(sizeof(Piece)==128)?1:-1];
static const char *variant[NV] = {"list_current", "meshopt_hybrid", "indexed_control", "greedy_hybrid"};
static unsigned __attribute__((aligned(64))) commandList[65536];
static unsigned *calls[NV];
static unsigned char *data;
static Header *H; static Texture *T; static Piece *P;
static unsigned short *referenceFrame, *captureFrame;
static char base[256], run[320];
static unsigned errors, visualDiffs;
static volatile int exitRequested;
static int geActive;
static void *drawBuf=(void *)0, *displayBuf=(void *)FRAME_BYTES;
static const ScePspIMatrix4 dither={{-4,0,-3,1},{2,-2,3,-1},{-3,1,-4,0},{3,-1,2,-2}};
static int exitCallback(int a,int b,void *c) { exitRequested=1; return 0; }
static int callbackThread(SceSize a,void *b) { int cb=sceKernelCreateCallback("exit",exitCallback,0); sceKernelRegisterExitCallback(cb); sceKernelSleepThreadCB(); return 0; }
static void idleExit(void) __attribute__((noreturn));
static void idleExit(void) {
    for(;;){SceCtrlData pad;sceCtrlReadBufferPositive(&pad,1);if(exitRequested||(pad.Buttons&PSP_CTRL_CROSS))sceKernelExitGame();sceKernelDelayThreadCB(20000);}
}
static void fail(const char *why) __attribute__((noreturn));
static void fail(const char *why) {
    if(geActive)sceGuBreak(1);
    if(run[0]){char path[384];snprintf(path,sizeof path,"%s/STOPPED.txt",run);FILE *f=fopen(path,"w");if(f){fprintf(f,"%s\n%s\nPartial results preserved; no COMPLETE marker\n",OPTBENCH_VERSION,why);fclose(f);}sceIoSync("ms0:",0);}
    pspDebugScreenInit();pspDebugScreenPrintf("SHAR OPT BENCH R2\n\nSTOPPED\n%s\n\nResults saved so far remain on the card\nPress X or HOME to exit",why);idleExit();
}
static void checkCancel(void) {if(exitRequested)fail("Cancelled by HOME");}
static void syncGE(void) {
    unsigned start=sceKernelGetSystemTimeLow();
    for(;;){int status=sceGuSync(GU_SYNC_FINISH,GU_SYNC_NOWAIT);if(status==0){geActive=0;return;}if(status<0||status==GU_SYNC_WHAT_CANCEL)fail("Graphics command error");if(sceKernelGetSystemTimeLow()-start>2000000u)fail("Graphics timeout; benchmark stopped");}
}
static FILE *resultFile(const char *name,const char *mode) {
    char p[512]; if(snprintf(p,sizeof p,"%s/%s",run,name)>=(int)sizeof p)fail("Report path too long"); FILE *f=fopen(p,mode); if(!f) fail("Cannot save report"); return f;
}
static void logLine(const char *fmt,...) {
    FILE *f=resultFile("results.jsonl","a");va_list a;va_start(a,fmt);int bad=vfprintf(f,fmt,a)<0;va_end(a);bad|=fputc('\n',f)==EOF;bad|=fclose(f)!=0;
    if(bad)fail("Cannot finish report write");
}
static void checkpoint(const char *phase,int scene,int vi) {
    logLine("{\"type\":\"checkpoint\",\"phase\":\"%s\",\"scene\":%d,\"variant\":%d}",phase,scene,vi);
    if(sceIoSync("ms0:",0)<0)fail("Card sync failed");checkCancel();
}
static void createRun(const char *arg) {
    snprintf(base,sizeof base,"%s",arg);char *s=strrchr(base,'/');if(!s)fail("Invalid launch path");*s=0;
    for(int i=1;i<=9999;i++) {
        snprintf(run,sizeof run,"%s/run%04d",base,i);SceIoStat st;
        if(sceIoGetstat(run,&st)>=0)continue;
        if(sceIoMkdir(run,0777)<0)fail("Cannot create a result folder");return;
    }
    fail("Result folders full");
}
static unsigned fnv(const unsigned char *p,unsigned n) { unsigned h=2166136261u;for(unsigned i=0;i<n;i++)h=(h^p[i])*16777619u;return h; }
static void memoryReport(const char *stage) {
    struct mallinfo m=mallinfo();
    logLine("{\"type\":\"memory\",\"stage\":\"%s\",\"heap_arena\":%u,\"heap_used\":%u,\"heap_free\":%u,\"kernel_total_free\":%u,\"kernel_max_free\":%u}",stage,(unsigned)m.arena,(unsigned)m.uordblks,(unsigned)m.fordblks,sceKernelTotalFreeMemSize(),sceKernelMaxFreeMemSize());
}
static int cmpUnsigned(const void *a,const void *b) {unsigned x=*(const unsigned*)a,y=*(const unsigned*)b;return x<y?-1:x>y;}
typedef struct {unsigned med,p95,p99,max;double avg;} Stats;
static Stats statistics(const unsigned *v,int n) {
    unsigned a[NFR];if(n>NFR)fail("Stats capacity");memcpy(a,v,n*sizeof(unsigned));qsort(a,n,sizeof(unsigned),cmpUnsigned);
    Stats s={a[n/2],a[(n*95-1)/100],a[(n*99-1)/100],a[n-1],0};for(int i=0;i<n;i++)s.avg+=v[i];s.avg/=n;return s;
}
static int validIo(const unsigned char *b,unsigned offset,unsigned size) {
    unsigned first,last;memcpy(&first,b,4);memcpy(&last,b+size-4,4);return first==((offset/4)^IO_SEED)&&last==(((offset+size-4)/4)^IO_SEED);
}
static void ioBench(void) {
    pspDebugScreenPrintf("1/3 Card read tests\nFirst/repeat passes; no cold-cache claim\n");
    unsigned char *b=memalign(64,262144);if(!b)fail("IO buffer allocation failed");
    unsigned check[2]={IO_SEED,IO_SEED^1u};int good=validIo((unsigned char*)check,0,8);check[1]^=1;int bad=validIo((unsigned char*)check,0,8);
    if(!good||bad)fail("IO negative control failed");
    logLine("{\"type\":\"oracle\",\"name\":\"io_data_negative_control\",\"pass\":true}");
    char p[384];snprintf(p,sizeof p,"%s/io.bin",base);SceUID fd=sceIoOpen(p,PSP_O_RDONLY,0);if(fd<0)fail("io.bin missing");
    if(sceIoLseek32(fd,0,PSP_SEEK_END)!=IO_BYTES)fail("io.bin size mismatch");
    const unsigned sizes[]={4096,16384,65536,262144};
    FILE *csv=resultFile("io.csv","w");fprintf(csv,"mode,pass,block_bytes,sample,offset,read_us,ok\n");
    for(int pass=0;pass<2;pass++)for(int mode=0;mode<2;mode++)for(int si=0;si<4;si++) {
        unsigned us[IOSAMPLES],offsets[IOSAMPLES],ok[IOSAMPLES],seed=0x12345u,sz=sizes[si],total=0,caseErrors=0;
        for(int j=0;j<IOSAMPLES;j++) {
            seed=seed*1664525u+1013904223u;unsigned off=(mode?(seed>>8)%(IO_BYTES/sz):(unsigned)j%(IO_BYTES/sz))*sz;
            unsigned t=sceKernelGetSystemTimeLow();int seek=sceIoLseek32(fd,off,PSP_SEEK_SET);int n=seek==(int)off?sceIoRead(fd,b,sz):-1;us[j]=sceKernelGetSystemTimeLow()-t;
            ok[j]=n==(int)sz&&validIo(b,off,sz);caseErrors+=!ok[j];offsets[j]=off;total+=us[j];
        }
        errors+=caseErrors;Stats s=statistics(us,IOSAMPLES);const char *m=mode?"random":"sequential";
        for(int j=0;j<IOSAMPLES;j++)fprintf(csv,"%s,%d,%u,%d,%u,%u,%u\n",m,pass+1,sz,j,offsets[j],us[j],ok[j]);fflush(csv);
        logLine("{\"type\":\"io\",\"mode\":\"%s\",\"pass\":%d,\"block\":%u,\"samples\":64,\"median_us\":%u,\"p95_us\":%u,\"max_us\":%u,\"bytes_per_second\":%.0f,\"errors\":%u}",m,pass+1,sz,s.med,s.p95,s.max,total?(double)sz*IOSAMPLES*1000000./total:0,caseErrors);
        pspDebugScreenPrintf(" %s %3uK pass %d: %.2f ms\n",mode?"rnd":"seq",sz/1024,pass+1,s.med/1000.f);scePowerTick(0);checkCancel();
    }
    sceIoClose(fd);
    for(int pass=0;pass<2;pass++) {
        unsigned us[IOSAMPLES],badCount=0,total=0;
        for(int j=0;j<IOSAMPLES;j++) {
            unsigned i=(unsigned)j%32;snprintf(p,sizeof p,"%s/small/%02u.bin",base,i);
            unsigned t=sceKernelGetSystemTimeLow();SceUID f=sceIoOpen(p,PSP_O_RDONLY,0);int n=f>=0?sceIoRead(f,b,16384):-1;int c=f>=0?sceIoClose(f):-1;us[j]=sceKernelGetSystemTimeLow()-t;
            int ok=n==16384&&c>=0&&validIo(b,i*16384,16384);badCount+=!ok;total+=us[j];fprintf(csv,"open_files,%d,16384,%d,%u,%u,%d\n",pass+1,j,i*16384,us[j],ok);
        }
        Stats s=statistics(us,IOSAMPLES);errors+=badCount;logLine("{\"type\":\"io\",\"mode\":\"open_files\",\"pass\":%d,\"block\":16384,\"samples\":64,\"median_us\":%u,\"p95_us\":%u,\"max_us\":%u,\"bytes_per_second\":%.0f,\"errors\":%u}",pass+1,s.med,s.p95,s.max,total?16384.*IOSAMPLES*1000000./total:0,badCount);
    }
    int writeBad=ferror(csv);writeBad|=fclose(csv)!=0;if(writeBad)fail("IO report write failed");free(b);checkpoint("io_saved",-1,-1);
}
static int span(unsigned off,unsigned count,unsigned stride,unsigned size) {return off>=128&&off<=size&&count<=(size-off)/stride;}
static int power2(unsigned n) {return n&&!(n&(n-1));}
static void loadScene(int scene) {
    char p[384];snprintf(p,sizeof p,"%s/%s",base,sceneInfo[scene].name);SceUID f=sceIoOpen(p,PSP_O_RDONLY,0);if(f<0)fail("Scene missing");
    int size=sceIoLseek32(f,0,PSP_SEEK_END);if(size!=(int)sceneInfo[scene].size)fail("Scene size mismatch");sceIoLseek32(f,0,PSP_SEEK_SET);
    data=memalign(64,size);if(!data)fail("Scene allocation failed");if(sceIoRead(f,data,size)!=size)fail("Scene read failed");sceIoClose(f);
    if(fnv(data,size)!=sceneInfo[scene].fnv)fail("Scene checksum failed");
    H=(Header*)data;if(memcmp(H->magic,"OPB1",4)||H->version!=1||H->ns!=NV||H->bytes!=(unsigned)size||H->nt>512||H->np>2048)fail("Invalid scene header");
    if(H->np*512u+4096u>256u*1024u)fail("Scene exceeds conservative command budget");
    if(!span(128,H->nt,48,size)||!span(128+48*H->nt,H->np,128,size))fail("Invalid scene tables");
    T=(Texture*)(data+128);P=(Piece*)(data+128+48*H->nt);
    for(unsigned i=0;i<H->nt;i++) {
        Texture *t=T+i;if(!power2(t->w)||!power2(t->h)||t->w<16||t->w>512||t->h>512||!t->levels||t->levels>8||!span(t->pal,1024,1,size))fail("Invalid texture");
        for(unsigned l=0;l<t->levels;l++){unsigned w=t->w>>l,h=t->h>>l;if(!h)h=1;if(w<16||!span(t->lv[l],w*((h+7)&~7),1,size)||(t->lv[l]&15))fail("Invalid mip");}
    }
    for(unsigned i=0;i<H->np;i++)for(int v=0;v<NV;v++) {
        Piece *p=P+i;Set *s=p->set+v;if(p->tex< -1||p->tex>=(int)H->nt||(s->stride!=12&&s->stride!=16)||s->prim>1||s->count<3||!span(s->voff,s->nv,s->stride,size)||(s->voff&15))fail("Invalid geometry");
        if(s->ioff){if(!span(s->ioff,s->count,2,size)||(s->ioff&15))fail("Invalid indices");unsigned short *ix=(unsigned short*)(data+s->ioff);for(unsigned k=0;k<s->count;k++)if(ix[k]>=s->nv)fail("Index out of bounds");}
        else if(s->count!=s->nv)fail("Vertex count mismatch");
        if(!s->prim&&s->count%3)fail("Triangle count mismatch");
    }
    sceKernelDcacheWritebackRange(data,size);
    logLine("{\"type\":\"scene\",\"name\":\"%s\",\"sha256\":\"%s\",\"bytes\":%d,\"pieces\":%u,\"textures\":%u,\"draw_distance\":%.0f,\"checksum_ok\":true}",sceneInfo[scene].name,sceneInfo[scene].sha,size,H->np,H->nt,H->dist);
}
static int log2i(unsigned x) {return 31-__builtin_clz(x);}
static void texture(int ti) {
    if(ti<0){sceGuDisable(GU_TEXTURE_2D);return;}sceGuEnable(GU_TEXTURE_2D);Texture *t=T+ti;unsigned pal=(unsigned)(data+t->pal);
    sceGuSendCommandi(0xb0,pal&0xffffff);sceGuSendCommandi(0xb1,(pal>>8)&0xf0000);sceGuSendCommandi(0xc4,32);
    sceGuSendCommandi(0xc2,((t->levels-1)<<16)|1);sceGuSendCommandi(0xc3,GU_PSM_T8);
    for(unsigned l=0;l<t->levels;l++){unsigned w=t->w>>l,h=t->h>>l;if(!h)h=1;unsigned a=(unsigned)(data+t->lv[l]);sceGuSendCommandi(0xa0+l,a&0xffffff);sceGuSendCommandi(0xa8+l,((a>>8)&0xf0000)|w);sceGuSendCommandi(0xb8+l,(log2i(h)<<8)|log2i(w));}
    sceGuSendCommandi(0xcb,0);sceGuTexFilter(t->levels>1?GU_LINEAR_MIPMAP_LINEAR:GU_LINEAR,GU_LINEAR);
}
static void emit(int vi) {
    int bound=-2;
    for(unsigned i=0;i<H->np;i++) {
        Piece *p=P+i;Set *s=p->set+vi;if(p->tex!=bound){texture(p->tex);bound=p->tex;}
        float k=p->scale;ScePspFMatrix4 m={{k,0,0,0},{0,k,0,0},{0,0,k,0},{p->origin[0],p->origin[1],p->origin[2],1}};sceGuSetMatrix(GU_MODEL,&m);
        int vt=GU_TEXTURE_16BIT|GU_VERTEX_16BIT|GU_TRANSFORM_3D|(s->stride==12?GU_COLOR_5650:GU_COLOR_8888)|(s->ioff?GU_INDEX_16BIT:0);
        for(unsigned start=0;start<s->count;) {
            unsigned n=s->count-start;if(n>65532)n=65532;
            const void *idx=s->ioff?data+s->ioff+start*2:NULL;
            const void *verts=data+s->voff+(s->ioff?0:start*s->stride);
            sceGuDrawArray(s->prim?GU_TRIANGLE_STRIP:GU_TRIANGLES,vt,n,idx,verts);
            if(start+n>=s->count)break;start+=s->prim?n-2:n; /* even step preserves strip winding */
        }
    }
}
static void frameBegin(void) {
    sceGuStart(GU_DIRECT,commandList);
    sceGuOffset(2048-SW/2,2048-SH/2);sceGuViewport(2048,2048,SW,SH);
    sceGuDepthRange(65535,0);sceGuScissor(0,0,SW,SH);sceGuEnable(GU_SCISSOR_TEST);sceGuDepthFunc(GU_GEQUAL);sceGuEnable(GU_DEPTH_TEST);sceGuDepthMask(GU_FALSE);
    sceGuDisable(GU_CULL_FACE);sceGuDisable(GU_BLEND);sceGuDisable(GU_ALPHA_TEST);sceGuShadeModel(GU_SMOOTH);sceGuEnable(GU_CLIP_PLANES);
    sceGuSetDither(&dither);sceGuEnable(GU_DITHER);sceGuTexWrap(GU_REPEAT,GU_REPEAT);sceGuTexFunc(GU_TFX_MODULATE,GU_TCC_RGBA);sceGuTexScale(128,128);sceGuTexOffset(0,0);sceGuTexLevelMode(GU_TEXTURE_AUTO,0);sceGuClutMode(GU_PSM_8888,0,0xff,0);
    sceGuEnable(GU_FOG);sceGuFog(H->dist*.5f,H->dist,H->fog);sceGuClearColor(0xff000000|H->fog);sceGuClearDepth(0);sceGuClear(GU_COLOR_BUFFER_BIT|GU_DEPTH_BUFFER_BIT);
    sceGumMatrixMode(GU_PROJECTION);sceGumLoadIdentity();sceGumPerspective(62,16.f/9.f,.7f,H->dist+10);
    sceGumMatrixMode(GU_VIEW);sceGumLoadIdentity();ScePspFVector3 e={H->eye[0],H->eye[1],H->eye[2]},a={H->at[0],H->at[1],H->at[2]},u={0,1,0};sceGumLookAt(&e,&a,&u);
    sceGumMatrixMode(GU_MODEL);sceGumLoadIdentity();sceGumUpdateMatrix();
}
static void render(int vi,int inlined,unsigned *work,unsigned *cpu,unsigned *wait) {
    checkCancel();unsigned t0=sceKernelGetSystemTimeLow();geActive=1;frameBegin();if(inlined)emit(vi);else sceGuCallList(calls[vi]);sceGuFinish();unsigned t1=sceKernelGetSystemTimeLow();syncGE();unsigned t2=sceKernelGetSystemTimeLow();
    *work=t2-t0;*cpu=t1-t0;*wait=t2-t1;
}
static void swap(void) {void *p=sceGuSwapBuffers();displayBuf=drawBuf;drawBuf=p;}
static const unsigned short *framePtr(void) {
#ifdef OB_HOST_TEST
    return hostFrame(drawBuf);
#else
    unsigned off=(unsigned)drawBuf;if(off!=0&&off!=FRAME_BYTES)fail("Invalid framebuffer offset");
    if(off+FRAME_BYTES>sceGeEdramGetSize())fail("Framebuffer outside VRAM");
    return (const unsigned short*)(0x40000000u|(unsigned)sceGeEdramGetAddr()|off);
#endif
}
static unsigned frameDifference(const unsigned short *a,const unsigned short *b) {unsigned n=0;for(int y=0;y<SH;y++)for(int x=0;x<SW;x++)n+=a[y*BW+x]!=b[y*BW+x];return n;}
static int frameWriter(void *ctx,const void *p,unsigned n) {
#ifndef OB_HOST_TEST
    uintptr_t a=(uintptr_t)p;
    if(a<0x08800000u||a>=0x0c000000u||n>0x0c000000u-a)return -1;
#endif
    return sceIoWrite(*(SceUID*)ctx,p,n);
}
static void saveFrame(const char *name,const unsigned short *ram) {
    char path[384];snprintf(path,sizeof path,"%s/%s",run,name);
    sceKernelDcacheWritebackRange(ram,FRAME_BYTES);
    SceUID fd=sceIoOpen(path,PSP_O_WRONLY|PSP_O_CREAT|PSP_O_EXCL,0777);if(fd<0)fail("Cannot create frame file");
    int bad=write_frame_chunks(ram,FRAME_BYTES,frameWriter,&fd);bad|=sceIoClose(fd)<0;if(bad)fail("Frame write failed; partial file retained");
    if(sceIoSync("ms0:",0)<0)fail("Frame sync failed");
    fd=sceIoOpen(path,PSP_O_RDONLY,0);if(fd<0)fail("Cannot verify frame file");
    unsigned char verify[16384] __attribute__((aligned(64)));
    bad=0;for(unsigned off=0;off<FRAME_BYTES;){unsigned n=FRAME_BYTES-off;if(n>sizeof verify)n=sizeof verify;int got=sceIoRead(fd,verify,n);if(got!=(int)n||memcmp(verify,(const unsigned char*)ram+off,n)){bad=1;break;}off+=n;}
    bad|=sceIoClose(fd)<0;if(bad)fail("Frame read-back mismatch");
}
static void capture(int si,int vi) {
    checkpoint("capture_copy_begin",si,vi);
    const unsigned short *vram=framePtr();
    snapshot_words((uint32_t*)captureFrame,(const volatile uint32_t*)vram,FRAME_BYTES);
    const unsigned short *p=captureFrame;
    checkpoint("capture_ram_ready",si,vi);
    char name[80];snprintf(name,sizeof name,"s%d-v%d.rgb565",si,vi);saveFrame(name,p);
    if(!vi) {
        memcpy(referenceFrame,p,FRAME_BYTES);referenceFrame[0]^=1;unsigned d=frameDifference(referenceFrame,p);referenceFrame[0]^=1;
        if(d!=1)fail("Frame negative control failed");logLine("{\"type\":\"oracle\",\"name\":\"frame_negative_control\",\"scene\":%d,\"changed_pixels\":%u,\"pass\":true}",si,d);
    }
    unsigned difference=frameDifference(referenceFrame,p);visualDiffs+=difference!=0;
    logLine("{\"type\":\"frame\",\"scene\":%d,\"variant\":\"%s\",\"file\":\"%s\",\"width\":480,\"height\":272,\"stride_pixels\":512,\"format\":\"little_endian_R5G6B5_R_in_low_bits\",\"different_pixels_vs_list\":%u}",si,variant[vi],name,difference);
    checkpoint("capture_saved_verified",si,vi);
}
static void frameCase(FILE *csv,int si,int vi,int round,int inlineMode) {
    unsigned work[NFR],cpu[NFR],wait[NFR],a,b,c;
    for(int j=0;j<WARM+NFR;j++){render(vi,inlineMode,&a,&b,&c);if(j>=WARM){work[j-WARM]=a;cpu[j-WARM]=b;wait[j-WARM]=c;}swap();}
    Stats s=statistics(work,NFR),cs=statistics(cpu,NFR),gs=statistics(wait,NFR);
    unsigned over60=0,over30=0;for(int j=0;j<NFR;j++){over60+=work[j]>16667;over30+=work[j]>33333;}
    for(int j=0;j<NFR;j++)fprintf(csv,"%d,%s,%d,%d,%d,%u,%u,%u\n",si,variant[vi],round+1,inlineMode,j,work[j],cpu[j],wait[j]);fflush(csv);
    logLine("{\"type\":\"ge\",\"scene\":%d,\"variant\":\"%s\",\"round\":%d,\"inline_commands\":%s,\"frames\":120,\"warmup\":12,\"median_us\":%u,\"p95_us\":%u,\"p99_us\":%u,\"max_us\":%u,\"avg_us\":%.2f,\"cpu_submit_median_us\":%u,\"gpu_wait_median_us\":%u}",si,variant[vi],round+1,inlineMode?"true":"false",s.med,s.p95,s.p99,s.max,s.avg,cs.med,gs.med);
    logLine("{\"type\":\"work_budget\",\"scene\":%d,\"variant\":\"%s\",\"round\":%d,\"over_16667us\":%u,\"over_33333us\":%u,\"scope\":\"work-time thresholds, NOT missed-vblank counters\"}",si,variant[vi],round+1,over60,over30);
    if(ferror(csv)||fflush(csv))fail("Timing save failed");checkpoint("timing_saved",si,vi);scePowerTick(0);
}
static void geBench(void) {
    pspDebugScreenPrintf("\n3/3 Geometry: three city views, four variants\nPlease wait while city images change\n");sceKernelDelayThread(700000);
    checkpoint("geometry_begin",-1,-1);
    referenceFrame=memalign(64,FRAME_BYTES);captureFrame=memalign(64,FRAME_BYTES);if(!referenceFrame||!captureFrame)fail("Frame buffer allocation failed");
    for(int v=0;v<NV;v++){calls[v]=memalign(64,256*1024);if(!calls[v])fail("Command list allocation failed");}
    sceGuInit();geActive=1;sceGuStart(GU_DIRECT,commandList);sceGuDrawBuffer(GU_PSM_5650,drawBuf,BW);sceGuDispBuffer(SW,SH,displayBuf,BW);sceGuDepthBuffer((void*)(FRAME_BYTES*2),BW);sceGuFinish();syncGE();sceDisplayWaitVblankStart();sceGuDisplay(GU_TRUE);
    FILE *csv=resultFile("frames.csv","w");fprintf(csv,"scene,variant,round,inline_commands,frame,work_us,cpu_submit_us,gpu_wait_us\n");if(fflush(csv))fail("Timing header save failed");
    for(int si=0;si<SCENE_COUNT;si++) {
        checkpoint("scene_load_begin",si,-1);loadScene(si);memoryReport(sceneInfo[si].name);
        for(int v=0;v<NV;v++){sceGuStart(GU_CALL,calls[v]);emit(v);int bytes=sceGuFinish();if(bytes<=0||bytes>256*1024)fail("Command list capacity");logLine("{\"type\":\"commands\",\"scene\":%d,\"variant\":\"%s\",\"bytes\":%d}",si,variant[v],bytes);}
        sceKernelDcacheWritebackAll();
        for(int v=0;v<NV;v++){unsigned a,b,c;render(v,0,&a,&b,&c);capture(si,v);swap();}
        for(int round=0;round<ROUNDS;round++)for(int k=0;k<NV;k++)frameCase(csv,si,(k+round)%NV,round,0);
        frameCase(csv,si,0,ROUNDS,1);frameCase(csv,si,1,ROUNDS,1);
        syncGE();free(data);data=NULL;checkpoint("scene_complete",si,-1);
    }
    int bad=ferror(csv);bad|=fclose(csv)!=0;if(bad)fail("Frame report write failed");sceGuDisplay(GU_FALSE);sceGuTerm();for(int v=0;v<NV;v++)free(calls[v]);free(referenceFrame);free(captureFrame);memoryReport("after_scenes");checkpoint("geometry_saved",-1,-1);
}
int main(int argc,char **argv) {
    SceUID cb=sceKernelCreateThread("callback",callbackThread,0x11,0x1000,0,0);if(cb>=0)sceKernelStartThread(cb,0,0);
    sceCtrlSetSamplingCycle(0);sceCtrlSetSamplingMode(PSP_CTRL_MODE_DIGITAL);
    pspDebugScreenInit();pspDebugScreenPrintf("SHAR Optimization Bench R2\n%s\n\nAutomatic run, about 2-4 minutes\nHOME cancels; completed stages are saved\n\n",OPTBENCH_VERSION);
    createRun(argc>0&&argv[0]?argv[0]:"ms0:/PSP/GAME/SHAROPT/EBOOT.PBP");scePowerSetClockFrequency(333,333,166);
    ScePspDateTime dt;memset(&dt,0,sizeof dt);sceRtcGetCurrentClockLocalTime(&dt);unsigned start=sceKernelGetSystemTimeLow();
    logLine("{\"type\":\"start\",\"version\":\"%s\",\"build\":\"%s %s\",\"time\":\"%04u-%02u-%02uT%02u:%02u:%02u\",\"firmware_hex\":\"%08x\",\"cpu_mhz\":%d,\"bus_mhz\":%d,\"memory_requested\":\"MEMSIZE=1\",\"model\":\"user_target_PSP2000_not_queried_via_kernel\",\"vsync_during_timing\":false,\"scope\":\"microbench, opaque city only, no game simulation\"}",OPTBENCH_VERSION,__DATE__,__TIME__,dt.year,dt.month,dt.day,dt.hour,dt.minute,dt.second,sceKernelDevkitVersion(),scePowerGetCpuClockFrequencyInt(),scePowerGetBusClockFrequencyInt());
    logLine("{\"type\":\"runtime_policy\",\"heap_limit_bytes\":12582912,\"allocation_stress\":false,\"frame_write\":\"RAM_16KiB_chunks_with_readback\",\"ge_wait\":\"nonblocking_poll_2s_timeout\"}");
    memoryReport("startup");checkpoint("startup_saved",-1,-1);ioBench();pspDebugScreenPrintf("\n2/3 Memory report saved\n");memoryReport("after_io");if(errors)fail("Read errors; benchmark stopped");geBench();
    unsigned elapsed=sceKernelGetSystemTimeLow()-start;logLine("{\"type\":\"complete\",\"seconds\":%.2f,\"io_errors\":%u,\"frames_with_visual_differences\":%u,\"visual_review_required\":%s}",elapsed/1000000.,errors,visualDiffs,visualDiffs?"true":"false");
    FILE *f=resultFile("COMPLETE.txt","w");int bad=fprintf(f,"%s\nCompleted in %.1f seconds\nIO errors: %u\nFrames with visual differences: %u\nDifferences require review, not automatic acceptance\n",OPTBENCH_VERSION,elapsed/1000000.,errors,visualDiffs)<0;bad|=fclose(f)!=0;if(bad)fail("Completion save failed");if(sceIoSync("ms0:",0)<0)fail("Completion sync failed");
    pspDebugScreenInit();pspDebugScreenPrintf("SHAR Optimization Bench R2\n\nDONE - results saved\n\nTime: %.1f seconds\nRead errors: %u\nImages needing review: %u\n\n%s\n\nPress X or HOME, then connect USB\nCodex will read the report and images",elapsed/1000000.,errors,visualDiffs,run);idleExit();
}
