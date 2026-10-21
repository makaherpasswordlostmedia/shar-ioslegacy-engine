/* Fault-injection adapter for the actual main.c control/save flow.
 * NO PSP emulation, rendering validation, or meaningful performance numbers.
 * The host file driver deliberately rejects the simulated VRAM range. */
#ifndef OB_HOST_PSP_H
#define OB_HOST_PSP_H
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdarg.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
typedef int SceUID;typedef unsigned SceSize;typedef struct stat SceIoStat;
typedef struct {float x,y,z,w;} Vec4;
typedef struct {Vec4 x,y,z,w;} ScePspFMatrix4;
typedef struct {int x,y,z,w;} IVec4;
typedef struct {IVec4 x,y,z,w;} ScePspIMatrix4;
typedef struct {float x,y,z;} ScePspFVector3;
typedef struct {unsigned year,month,day,hour,minute,second;} ScePspDateTime;
typedef struct {unsigned Buttons;} SceCtrlData;
struct mallinfo {unsigned arena,uordblks,fordblks;};
static struct mallinfo mallinfo(void){return (struct mallinfo){0};}
#define PSP_MODULE_INFO(...)
#define PSP_MAIN_THREAD_ATTR(...)
#define PSP_MAIN_THREAD_STACK_SIZE_KB(...)
#define PSP_HEAP_SIZE_KB(...)
#define PSP_CTRL_CROSS 1
#define PSP_CTRL_MODE_DIGITAL 0
#define PSP_O_RDONLY O_RDONLY
#define PSP_O_WRONLY O_WRONLY
#define PSP_O_CREAT O_CREAT
#define PSP_O_EXCL O_EXCL
#define PSP_SEEK_END SEEK_END
#define PSP_SEEK_SET SEEK_SET
enum {GU_FALSE=0,GU_TRUE=1,GU_DIRECT=2,GU_CALL,GU_ALPHA_TEST,GU_BLEND,
 GU_CLIP_PLANES,GU_COLOR_5650,GU_COLOR_8888,GU_COLOR_BUFFER_BIT,GU_CULL_FACE,
 GU_DEPTH_BUFFER_BIT,GU_DEPTH_TEST,GU_DITHER,GU_FOG,GU_GEQUAL,GU_INDEX_16BIT,
 GU_LINEAR,GU_LINEAR_MIPMAP_LINEAR,GU_MODEL,GU_PROJECTION,GU_PSM_5650,
 GU_PSM_8888,GU_PSM_T8,GU_REPEAT,GU_SCISSOR_TEST,GU_SMOOTH,GU_SYNC_FINISH,
 GU_SYNC_NOWAIT,GU_TCC_RGBA,GU_TEXTURE_16BIT,GU_TEXTURE_2D,GU_TEXTURE_AUTO,
 GU_TFX_MODULATE,GU_TRANSFORM_3D,GU_TRIANGLES,GU_TRIANGLE_STRIP,GU_VERTEX_16BIT,GU_VIEW};
#define GU_SYNC_WHAT_CANCEL 4
static int hostStopped,hostGuMode;
static uintptr_t hostDraw;
static uint32_t hostVideo[2*512*272/2];
static char hostPaths[256][512];
static int hostFault(const char *s){const char *f=getenv("OB_FAULT");return f&&!strcmp(f,s);}
static void *memalign(size_t align,size_t n){void *p=0;if(n==278528&&hostFault("frame_alloc"))return NULL;if(posix_memalign(&p,align,n))return NULL;return p;}
static const unsigned short *hostFrame(void *offset){
 if((uintptr_t)offset!=0&&(uintptr_t)offset!=278528)abort();
 for(unsigned i=0;i<sizeof hostVideo/4;i++)hostVideo[i]=(i%(278528/4))*2654435761u;
 return (const unsigned short*)((const unsigned char*)hostVideo+(uintptr_t)offset);
}
static void pspDebugScreenPrintf(const char *fmt,...){if(strstr(fmt,"STOPPED"))hostStopped=1;va_list ap;va_start(ap,fmt);vprintf(fmt,ap);va_end(ap);}
static void pspDebugScreenInit(void){}
static void sceKernelExitGame(void) __attribute__((noreturn));
static void sceKernelExitGame(void){exit(hostStopped?20:0);}
static int sceKernelCreateThread(const char*a,int(*b)(SceSize,void*),int c,int d,int e,void*f){return 1;}
static int sceKernelCreateCallback(const char*a,int(*b)(int,int,void*),void*c){return 1;}
static int sceKernelStartThread(int a,int b,void*c){return 0;}
static int sceKernelRegisterExitCallback(int a){return 0;}
static int sceKernelSleepThreadCB(void){return 0;}
static int sceKernelDelayThread(unsigned a){return 0;}
static int sceKernelDelayThreadCB(unsigned a){return 0;}
static unsigned sceKernelGetSystemTimeLow(void){static unsigned n;n+=50;return n;}
static unsigned sceKernelTotalFreeMemSize(void){return 32*1024*1024;}
static unsigned sceKernelMaxFreeMemSize(void){return 30*1024*1024;}
static unsigned sceKernelDevkitVersion(void){return 0x06060110;}
static void sceCtrlReadBufferPositive(SceCtrlData*p,int n){p->Buttons=PSP_CTRL_CROSS;}
#define sceCtrlSetSamplingCycle(...) ((void)0)
#define sceCtrlSetSamplingMode(...) ((void)0)
#define sceKernelDcacheWritebackRange(...) ((void)0)
#define sceKernelDcacheWritebackAll(...) ((void)0)
#define scePowerSetClockFrequency(...) ((void)0)
#define scePowerTick(...) ((void)0)
static int scePowerGetCpuClockFrequencyInt(void){return 333;}
static int scePowerGetBusClockFrequencyInt(void){return 166;}
static void sceRtcGetCurrentClockLocalTime(ScePspDateTime*t){*t=(ScePspDateTime){2026,9,27,0,0,0};}
static int sceIoGetstat(const char*p,SceIoStat*s){return stat(p,s);}
static int sceIoMkdir(const char*p,int mode){return mkdir(p,mode);}
static int sceIoOpen(const char*p,int flags,int mode){int fd=open(p,flags,mode);if(fd>=0){if(fd>=256)abort();snprintf(hostPaths[fd],512,"%s",p);}return fd;}
static int sceIoClose(int fd){return close(fd);}
static int sceIoSync(const char*p,int x){return 0;}
static int sceIoLseek32(int fd,int off,int mode){return (int)lseek(fd,off,mode);}
static int sceIoRead(int fd,void*p,unsigned n){int r=(int)read(fd,p,n);if(r>0&&hostFault("readback")&&strstr(hostPaths[fd],".rgb565"))((unsigned char*)p)[0]^=1;return r;}
static int sceIoWrite(int fd,const void*p,unsigned n){
 uintptr_t a=(uintptr_t)p,b=(uintptr_t)hostVideo;
 if(a>=b&&a<b+sizeof hostVideo){fprintf(stderr,"REJECTED: video memory passed to file driver\n");exit(91);}
 if(n>16384)abort();
 if(hostFault("short_write"))return (int)write(fd,p,n/2);
 return (int)write(fd,p,n);
}
static void sceGuStart(int mode,void*p){hostGuMode=mode;}
static int sceGuFinish(void){return 16000;}
static int sceGuSync(int a,int b){return hostFault("ge_timeout")?2:0;}
static void *sceGuSwapBuffers(void){hostDraw=hostDraw?0:278528;return (void*)hostDraw;}
static int sceGuBreak(int mode){return 0;}
#define sceGuInit(...) ((void)0)
#define sceGuTerm(...) ((void)0)
#define sceGuCallList(...) ((void)0)
#define sceGuClear(...) ((void)0)
#define sceGuClearColor(...) ((void)0)
#define sceGuClearDepth(...) ((void)0)
#define sceGuClutMode(...) ((void)0)
#define sceGuDepthBuffer(...) ((void)0)
#define sceGuDepthFunc(...) ((void)0)
#define sceGuDepthMask(...) ((void)0)
#define sceGuDepthRange(...) ((void)0)
#define sceGuDisable(...) ((void)0)
#define sceGuDispBuffer(...) ((void)0)
#define sceGuDisplay(...) ((void)0)
#define sceGuDrawArray(...) ((void)0)
#define sceGuDrawBuffer(...) ((void)0)
#define sceGuEnable(...) ((void)0)
#define sceGuFog(...) ((void)0)
#define sceGuOffset(...) ((void)0)
#define sceGuScissor(...) ((void)0)
#define sceGuSendCommandi(...) ((void)0)
#define sceGuSetDither(...) ((void)0)
#define sceGuSetMatrix(...) ((void)0)
#define sceGuShadeModel(...) ((void)0)
#define sceGuTexFilter(...) ((void)0)
#define sceGuTexFunc(...) ((void)0)
#define sceGuTexLevelMode(...) ((void)0)
#define sceGuTexOffset(...) ((void)0)
#define sceGuTexScale(...) ((void)0)
#define sceGuTexWrap(...) ((void)0)
#define sceGuViewport(...) ((void)0)
#define sceGumLoadIdentity(...) ((void)0)
#define sceGumLookAt(...) ((void)0)
#define sceGumMatrixMode(...) ((void)0)
#define sceGumPerspective(...) ((void)0)
#define sceGumUpdateMatrix(...) ((void)0)
#define sceDisplayWaitVblankStart(...) ((void)0)
#endif
