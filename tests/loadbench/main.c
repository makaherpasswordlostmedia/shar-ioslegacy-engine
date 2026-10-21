/* Independent bounded loading experiment. No GE commands, no framebuffer IO.
 * Timings are isolated seek+read, decode and output cache writeback; full output
 * integrity checks and report writes are outside the measured ready interval.
 * Host adapter tests flow/integrity only, never PSP speed or device stability. */
#ifdef LB_HOST_TEST
#include "host_psp.h"
#define PLATFORM "host-test"
#else
#include <pspkernel.h>
#include <pspdebug.h>
#include <pspctrl.h>
#include <psppower.h>
#include <pspiofilemgr.h>
#define PLATFORM "PSP"
#endif
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <lz4.h>
#include "dataset_ids.h"

PSP_MODULE_INFO("SHARLOADBENCH", 0, 3, 0);
PSP_MAIN_THREAD_ATTR(THREAD_ATTR_USER);
PSP_MAIN_THREAD_STACK_SIZE_KB(128);
PSP_HEAP_SIZE_KB(4*1024);

#define CAP 65536u
#define GUARD 64u
#define GROUPS 4u
#define MAX_GROUP 64u
#define CASES 72u
#define ROUNDS 3u
typedef struct { char magic[4]; uint32_t version, count, groups, sizes[3], stride; } Header;
typedef struct { uint32_t group, raw, source, hash, offset[6], mask, reserved; } Entry;
typedef char HeaderSize[(sizeof(Header)==32)?1:-1];
typedef char EntrySize[(sizeof(Entry)==48)?1:-1];
typedef struct { unsigned block, stored, read, decode, flush, ready, verify; } Sample;
static unsigned char input[CAP+2*GUARD] __attribute__((aligned(64)));
static unsigned char output[CAP+2*GUARD] __attribute__((aligned(64)));
static unsigned char indexData[DATA_INDEX_SIZE] __attribute__((aligned(64)));
static Header header;
static Entry entries[DATA_COUNT];
static char base[256], run[320];
static const char *files[3]={"lb_raw.bin","lb_fast.bin","lb_hc.bin"};
static const char *codecs[3]={"raw","lz4","lz4hc12"};
static const char *groups[4]={"textures16","cells16","textures64","cells64"};
static SceUID fd[3]={-1,-1,-1};
static volatile int exitRequested;
static unsigned completed, totalSamples;
static unsigned reportHashes[CASES], reportBytes[CASES];

static int exitCallback(int a,int b,void *c) { (void)a;(void)b;(void)c;exitRequested=1;return 0; }
static int callbackThread(SceSize a,void *b) {
    (void)a;(void)b;
    int cb=sceKernelCreateCallback("exit",exitCallback,0);
    if(cb>=0){sceKernelRegisterExitCallback(cb);sceKernelSleepThreadCB();}
    return 0;
}
static void idleExit(void) __attribute__((noreturn));
static void idleExit(void) {
    for(;;){SceCtrlData pad;sceCtrlReadBufferPositive(&pad,1);
        if(exitRequested||(pad.Buttons&PSP_CTRL_CROSS))sceKernelExitGame();
        sceKernelDelayThreadCB(20000);
    }
}
static void fail(const char *why) __attribute__((noreturn));
static void fail(const char *why) {
    for(unsigned i=0;i<3;i++)if(fd[i]>=0){sceIoClose(fd[i]);fd[i]=-1;}
    if(run[0]){char path[384];snprintf(path,sizeof path,"%s/STOPPED.txt",run);
        FILE *f=fopen(path,"w");if(f){fprintf(f,"%s\n%s\nPartial results only\n",LOADBENCH_VERSION,why);fclose(f);}
        sceIoSync("ms0:",0);
    }
    pspDebugScreenClear();pspDebugScreenPrintf("SHAR LOADING BENCH R3\n\nSTOPPED\n%s\n\nPartial results kept\nPress X, reconnect USB",why);
#ifdef LB_HOST_TEST
    exit(20);
#else
    idleExit();
#endif
}
static void cancel(void) {if(exitRequested)fail("Cancelled by HOME");}
static FILE *reportFile(const char *name,const char *mode) {
    char path[384];if(snprintf(path,sizeof path,"%s/%s",run,name)>=(int)sizeof path)fail("Report path length");
    FILE *f=fopen(path,mode);if(!f)fail("Cannot open report");return f;
}
static void closeReport(FILE *f) {
    int bad=ferror(f);bad|=fclose(f)!=0;if(bad)fail("Report write failed");
    if(sceIoSync("ms0:",0)<0)fail("Card sync failed");
}
static void logLine(const char *fmt,...) {
    FILE *f=reportFile("events.jsonl","a");va_list ap;va_start(ap,fmt);
    int bad=vfprintf(f,fmt,ap)<0;va_end(ap);bad|=fputc('\n',f)==EOF;
    if(bad){fclose(f);fail("Event write failed");}closeReport(f);
}
static unsigned fnv(const unsigned char *b,unsigned n) {
    unsigned h=2166136261u;for(unsigned i=0;i<n;i++)h=(h^b[i])*16777619u;return h;
}
static unsigned fnvAppend(unsigned hash,const unsigned char *b,unsigned n) {
    for(unsigned i=0;i<n;i++)hash=(hash^b[i])*16777619u;
    return hash;
}
static void createRun(const char *arg) {
    if(!arg||snprintf(base,sizeof base,"%s",arg)>=(int)sizeof base)fail("Launch path length");
    char *slash=strrchr(base,'/');if(!slash)fail("Invalid launch path");*slash=0;
    for(unsigned i=1;i<10000;i++){
        char candidate[320];snprintf(candidate,sizeof candidate,"%s/load%04u",base,i);
        SceIoStat st;if(sceIoGetstat(candidate,&st)>=0)continue;
        if(sceIoMkdir(candidate,0777)<0)fail("Cannot create result folder");
        strcpy(run,candidate);return;
    }fail("Result folders full");
}
static int guardsOk(const unsigned char *b,unsigned used) {
    for(unsigned i=0;i<GUARD;i++)if(b[i]!=0xa5||b[GUARD+used+i]!=0xa5)return 0;
    return 1;
}
static void guardsSet(unsigned char *b,unsigned used) {
    memset(b,0xa5,GUARD);memset(b+GUARD+used,0xa5,GUARD);
}
static void readIndex(void) {
    char path[384];snprintf(path,sizeof path,"%s/lb_index.bin",base);
    SceUID f=sceIoOpen(path,PSP_O_RDONLY,0);if(f<0)fail("Index missing");
    int n=sceIoLseek32(f,0,PSP_SEEK_END);
    if(n!=(int)DATA_INDEX_SIZE){sceIoClose(f);fail("Index size mismatch");}
    if(sceIoLseek32(f,0,PSP_SEEK_SET)!=0||sceIoRead(f,indexData,n)!=n){sceIoClose(f);fail("Index read failed");}
    if(sceIoClose(f)<0)fail("Index close failed");
    if(fnv(indexData,n)!=DATA_INDEX_FNV)fail("Index checksum mismatch");
    memcpy(&header,indexData,sizeof header);
    if(memcmp(header.magic,"LB03",4)||header.version!=3||header.count!=DATA_COUNT||header.groups!=4||header.stride!=48)fail("Index header invalid");
    for(unsigned c=0;c<3;c++)if(!header.sizes[c]||header.sizes[c]>32u*1024u*1024u)fail("Container size invalid");
    memcpy(entries,indexData+32,sizeof entries);
    unsigned counts[4]={0,0,0,0},ends[3]={0,0,0};
    for(unsigned i=0;i<DATA_COUNT;i++){
        Entry *e=&entries[i];
        if(e->group>=4||!e->raw||e->raw>CAP||((e->group<2)&&e->raw>16384)||e->reserved||(e->mask&~6u))fail("Block metadata invalid");
        if(i&&e->group<entries[i-1].group)fail("Group order invalid");
        if(++counts[e->group]>MAX_GROUP)fail("Too many group blocks");
        for(unsigned c=0;c<3;c++){
            unsigned off=e->offset[2*c],size=e->offset[2*c+1];
            if(!size||size>e->raw||off>header.sizes[c]||size>header.sizes[c]-off||off!=ends[c]||(off&15))fail("Block span invalid");
            if((!(e->mask&(1u<<c))&&size!=e->raw)||((e->mask&(1u<<c))&&size>=e->raw))fail("Block codec invalid");
            ends[c]=(off+size+15u)&~15u;
        }
    }
    for(unsigned g=0;g<4;g++)if(!counts[g])fail("Empty group");
    for(unsigned c=0;c<3;c++){
        if(header.sizes[c]>32u*1024u*1024u||ends[c]!=header.sizes[c])fail("Container size invalid");
        snprintf(path,sizeof path,"%s/%s",base,files[c]);fd[c]=sceIoOpen(path,PSP_O_RDONLY,0);
        if(fd[c]<0||sceIoLseek32(fd[c],0,PSP_SEEK_END)!=(int)header.sizes[c])fail("Container missing or truncated");
    }
}
static void controls(void) {
    /* A literal-only block: eight known bytes; last byte removed is invalid. */
    static const char packed[]={ (char)0x80,1,2,3,4,5,6,7,8 };
    unsigned char *out=output+GUARD;
    guardsSet(output,8);
    if(LZ4_decompress_safe(packed,(char*)out,9,8)!=8||memcmp(out,packed+1,8)||!guardsOk(output,8))fail("Decoder self-check");
    unsigned hash=fnv(out,8);out[3]^=1;if(fnv(out,8)==hash)fail("Checksum self-check");
    if(LZ4_decompress_safe(packed,(char*)out,8,8)>=0||!guardsOk(output,8))fail("Truncation self-check");
    output[GUARD+8]^=1;if(guardsOk(output,8))fail("Guard self-check");
    logLine("{\"type\":\"controls\",\"valid_decode\":true,\"changed_output_rejected\":true,\"truncated_input_rejected\":true,\"overrun_detected\":true}");
}
static void oneCase(unsigned round,unsigned mode,unsigned group,unsigned codec) {
    unsigned ids[MAX_GROUP],count=0;
    Sample samples[MAX_GROUP];
    for(unsigned i=0;i<DATA_COUNT;i++)if(entries[i].group==group)ids[count++]=i;
    if(mode){unsigned seed=0x93a51c7du+round*97u+group;
        for(unsigned n=count;n>1;n--){seed=seed*1664525u+1013904223u;unsigned j=seed%n,t=ids[n-1];ids[n-1]=ids[j];ids[j]=t;}
    }
    pspDebugScreenClear();pspDebugScreenPrintf("SHAR LOADING BENCH R3\n\nCase %u / %u\n%s / %s\n%s / round %u\n\nKeep the card connected\nResults saved after each case\nHOME stops at a safe boundary",completed+1,CASES,groups[group],codecs[codec],mode?"shuffled":"sequential",round+1);
    unsigned start=sceKernelGetSystemTimeLow();
    for(unsigned j=0;j<count;j++){
        cancel();Entry *e=&entries[ids[j]];
        unsigned size=e->offset[2*codec+1],off=e->offset[2*codec];int compressed=(e->mask&(1u<<codec))!=0;
        unsigned char *out=output+GUARD,*in=input+GUARD,*dest=compressed?in:out;
        guardsSet(input,size);guardsSet(output,e->raw);
        unsigned t0=sceKernelGetSystemTimeLow();
        int seek=sceIoLseek32(fd[codec],off,PSP_SEEK_SET);
        int got=seek==(int)off?sceIoRead(fd[codec],dest,size):-1;
        unsigned t1=sceKernelGetSystemTimeLow();
        if(got!=(int)size)fail("Short read or seek failure");
        int decoded=compressed?LZ4_decompress_safe((const char*)in,(char*)out,(int)size,(int)e->raw):(int)e->raw;
        unsigned t2=sceKernelGetSystemTimeLow();
        if(decoded!=(int)e->raw)fail("Decompression failed");
        sceKernelDcacheWritebackRange(out,e->raw);
        unsigned t3=sceKernelGetSystemTimeLow();
        if(!guardsOk(input,size)||!guardsOk(output,e->raw)||fnv(out,e->raw)!=e->hash)fail("Output integrity failed");
        unsigned t4=sceKernelGetSystemTimeLow();
        samples[j]=(Sample){ids[j],size,t1-t0,t2-t1,t3-t2,t3-t0,t4-t3};
        if(t4-start>10000000u)fail("Case exceeded 10 second budget");
    }
    char name[32];snprintf(name,sizeof name,"case%03u.csv",completed+1);
    FILE *f=reportFile(name,"w");
    const char *heading="case,round,mode,group,codec,sample,block,raw_bytes,stored_bytes,compressed,read_us,decode_us,flush_us,ready_us,verify_us,ok\n";
    unsigned bytes=(unsigned)strlen(heading),hash=fnv((const unsigned char*)heading,bytes);
    int bad=fwrite(heading,1,bytes,f)!=bytes;
    for(unsigned j=0;j<count;j++){
        Sample *s=&samples[j];Entry *e=&entries[s->block];
        char line[256];int n=snprintf(line,sizeof line,"%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,1\n",completed+1,round+1,mode,group,codec,j,s->block,(unsigned)e->raw,s->stored,(unsigned)!!(e->mask&(1u<<codec)),s->read,s->decode,s->flush,s->ready,s->verify);
        if(n<0||n>=(int)sizeof line){fclose(f);fail("Report line length");}
        bad|=fwrite(line,1,(unsigned)n,f)!=(unsigned)n;
        hash=fnvAppend(hash,(const unsigned char*)line,(unsigned)n);bytes+=(unsigned)n;
    }
    if(bad){fclose(f);fail("Sample write failed");}closeReport(f);
    reportHashes[completed]=hash;reportBytes[completed]=bytes;
    completed++;totalSamples+=count;
    logLine("{\"type\":\"case_saved\",\"case\":%u,\"round\":%u,\"mode\":%u,\"group\":%u,\"codec\":%u,\"samples\":%u}",completed,round+1,mode,group,codec,count);
    scePowerTick(0);cancel();
}
static void verifyReports(void) {
    /* All report IO is normal RAM. Verify case files after close before COMPLETE. */
    for(unsigned i=1;i<=CASES;i++){
        char name[32];unsigned char block[512];snprintf(name,sizeof name,"case%03u.csv",i);
        FILE *f=reportFile(name,"r");unsigned bytes=0,hash=2166136261u;size_t n;
        while((n=fread(block,1,sizeof block,f))>0){hash=fnvAppend(hash,block,(unsigned)n);bytes+=(unsigned)n;}
        int bad=ferror(f);bad|=fclose(f)!=0;
        if(bad||bytes!=reportBytes[i-1]||hash!=reportHashes[i-1])fail("Report readback failed");
    }
}
int main(int argc,char **argv) {
    pspDebugScreenInit();sceCtrlSetSamplingCycle(0);sceCtrlSetSamplingMode(PSP_CTRL_MODE_DIGITAL);
    if(argc<1)fail("Missing launch path");
    createRun(argv[0]);
    int thread=sceKernelCreateThread("exit_thread",callbackThread,0x11,0x1000,0,0);
    if(thread<0||sceKernelStartThread(thread,0,0)<0)fail("Cannot create exit handler");
    int power=scePowerSetClockFrequency(333,333,166);if(power<0)fail("Cannot set normal 333 MHz clock");
    logLine("{\"type\":\"start\",\"version\":\"%s\",\"platform\":\"%s\",\"lz4\":\"%s\",\"cpu_mhz\":%d,\"bus_mhz\":%d,\"battery_percent\":%d,\"blocks\":%u,\"cases\":72,\"samples\":%u,\"index_fnv\":%u,\"static_buffers_bytes\":%u,\"heap_limit_kib\":4096}",LOADBENCH_VERSION,PLATFORM,LZ4_versionString(),scePowerGetCpuClockFrequencyInt(),scePowerGetBusClockFrequencyInt(),scePowerGetBatteryLifePercent(),DATA_COUNT,DATA_COUNT*18u,DATA_INDEX_FNV,(unsigned)(sizeof input+sizeof output+sizeof indexData+sizeof entries));
    readIndex();controls();
    unsigned start=sceKernelGetSystemTimeLow();
    for(unsigned round=0;round<ROUNDS;round++)for(unsigned mode=0;mode<2;mode++)for(unsigned group=0;group<GROUPS;group++)for(unsigned c=0;c<3;c++)oneCase(round,mode,group,(c+round+mode+group)%3);
    for(unsigned c=0;c<3;c++){if(sceIoClose(fd[c])<0)fail("Container close failed");fd[c]=-1;}
    verifyReports();cancel();
    if(completed!=CASES||totalSamples!=DATA_COUNT*18u)fail("Incomplete run");
    logLine("{\"type\":\"finished\",\"cases\":%u,\"samples\":%u,\"elapsed_us\":%u,\"readback_verified\":true}",completed,totalSamples,sceKernelGetSystemTimeLow()-start);
    FILE *f=reportFile("COMPLETE.tmp","w");
    if(fprintf(f,"%s\n72 cases verified\n%u samples\n",LOADBENCH_VERSION,totalSamples)<0){fclose(f);fail("Completion write failed");}closeReport(f);
    char temp[384],done[384];snprintf(temp,sizeof temp,"%s/COMPLETE.tmp",run);snprintf(done,sizeof done,"%s/COMPLETE.txt",run);
    if(sceIoRename(temp,done)<0||sceIoSync("ms0:",0)<0)fail("Completion rename or sync failed");
    pspDebugScreenClear();pspDebugScreenPrintf("SHAR LOADING BENCH R3\n\nDONE\nResults saved\n%u cases / %u samples\n\nPress X to exit\nThen reconnect USB",completed,totalSamples);
    idleExit();
}
