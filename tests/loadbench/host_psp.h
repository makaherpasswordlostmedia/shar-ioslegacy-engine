/* Test-only POSIX adapter. Actual LZ4, files and program flow, no PSP hardware. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <time.h>
#define PSP_MODULE_INFO(...)
#define PSP_MAIN_THREAD_ATTR(...)
#define PSP_MAIN_THREAD_STACK_SIZE_KB(...)
#define PSP_HEAP_SIZE_KB(...)
#define PSP_CTRL_MODE_DIGITAL 0
#define PSP_CTRL_CROSS 1
#define PSP_O_RDONLY O_RDONLY
#define PSP_SEEK_END SEEK_END
#define PSP_SEEK_SET SEEK_SET
typedef int SceUID;
typedef unsigned SceSize;
typedef struct stat SceIoStat;
typedef struct { unsigned Buttons; } SceCtrlData;
static const char *fault(void){const char *s=getenv("LB_FAULT");return s?s:"normal";}
static int dataDescriptors[3]={-1,-1,-1};
static int sceIoOpen(const char *p,int mode,int perm){
    int fd=open(p,mode,perm);
    if(strstr(p,"lb_raw.bin"))dataDescriptors[0]=fd;
    if(strstr(p,"lb_fast.bin"))dataDescriptors[1]=fd;
    if(strstr(p,"lb_hc.bin"))dataDescriptors[2]=fd;
    return fd;
}
static int sceIoRead(int fd,void *b,unsigned n){
    static int triggered;
    if(!triggered&&(fd==dataDescriptors[0]||fd==dataDescriptors[1]||fd==dataDescriptors[2])){
        if(!strcmp(fault(),"short_read")){triggered=1;return (int)read(fd,b,n-1);}
        if(!strcmp(fault(),"payload_corrupt")){triggered=1;int r=(int)read(fd,b,n);if(r>0)((unsigned char*)b)[r/2]^=1;return r;}
    }
    return (int)read(fd,b,n);
}
static int sceIoLseek32(int fd,int off,int mode){return (int)lseek(fd,off,mode);}
static int sceIoClose(int fd){return close(fd);}
static int sceIoGetstat(const char *p,SceIoStat *s){return stat(p,s);}
static int sceIoMkdir(const char *p,int mode){return mkdir(p,mode);}
static int sceIoSync(const char *p,int n){(void)p;(void)n;return 0;}
static int sceIoRename(const char *a,const char *b){return rename(a,b);}
static unsigned sceKernelGetSystemTimeLow(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (unsigned)((uint64_t)t.tv_sec*1000000u+t.tv_nsec/1000);}
static FILE *testFopen(const char *p,const char *m){
    if(!strcmp(fault(),"report_corrupt")&&strstr(p,"case001.csv")&&!strcmp(m,"r")){
        FILE *f=fopen(p,"r+");if(f){fputc('X',f);fclose(f);}
    }
    return fopen(p,m);
}
static size_t testFwrite(const void *b,size_t size,size_t n,FILE *f){
    static int triggered;
    if(!triggered&&!strcmp(fault(),"short_write")){triggered=1;return fwrite(b,size,n-1,f);}
    return fwrite(b,size,n,f);
}
#define fopen testFopen
#define fwrite testFwrite
#define pspDebugScreenInit() ((void)0)
#define pspDebugScreenClear() ((void)0)
#define pspDebugScreenPrintf printf
#define sceCtrlSetSamplingCycle(...) ((void)0)
#define sceCtrlSetSamplingMode(...) ((void)0)
#define sceCtrlReadBufferPositive(p,n) ((p)->Buttons=PSP_CTRL_CROSS)
#define sceKernelExitGame() exit(0)
#define sceKernelDelayThreadCB(...) ((void)0)
#define sceKernelCreateCallback(...) 1
#define sceKernelRegisterExitCallback(...) ((void)0)
#define sceKernelSleepThreadCB(...) ((void)0)
#define sceKernelCreateThread(...) 1
#define sceKernelStartThread(...) 0
#define scePowerSetClockFrequency(...) 0
#define scePowerGetCpuClockFrequencyInt() 333
#define scePowerGetBusClockFrequencyInt() 166
#define scePowerGetBatteryLifePercent() 100
#define scePowerTick(...) ((void)0)
#define sceKernelDcacheWritebackRange(...) ((void)0)
