/* psp_compat.h - PSP SDK API surface for the iOS armv7 (32-bit, iOS 7+) port.
 * One header; every <pspXXX.h> in this directory just includes it.
 * GU calls write real GE command words into a list (ge_list.c); ge_gles2.c
 * interprets that list on OpenGL ES 2.0. Pointers are 32 bit on armv7, so the
 * 24+4 bit GE address packing is replaced by two custom opcodes (GE_PTRLO/HI). */
#ifndef PSP_COMPAT_H
#define PSP_COMPAT_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
#include "malloc.h"
#include <stdarg.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef uint64_t u64;
typedef int8_t s8; typedef int16_t s16; typedef int32_t s32; typedef int64_t s64;
typedef int SceUID; typedef unsigned int SceSize; typedef int SceSSize;
typedef unsigned int SceUInt; typedef int64_t SceInt64; typedef uint64_t SceUInt64;
typedef unsigned int SceMode; typedef int64_t SceOff; typedef int SceMode_t;
typedef unsigned int SceUInt32;
#define GU_PI 3.141593f
#define PSP_ALIGN(x) __attribute__((aligned(x)))
#define __attribute_packed __attribute__((packed))

/* ---------------- math types ---------------- */
typedef struct { float x, y, z; } ScePspFVector3;
typedef struct { float x, y, z, w; } ScePspFVector4;
typedef struct { float x, y; } ScePspFVector2;
typedef struct { int x, y, z, w; } ScePspIVector4;
typedef struct { float x, y, z, w; } ScePspFQuaternion;
typedef struct { float x, y, z, w; } ScePspFVector4_;
typedef struct ScePspFMatrix4 { ScePspFVector4 x, y, z, w; } ScePspFMatrix4;
typedef struct ScePspIMatrix4 { ScePspIVector4 x, y, z, w; } ScePspIMatrix4;
typedef struct { unsigned short year, month, day, hour, minute, second; unsigned int microsecond; } ScePspDateTime;

/* ---------------- kernel / io ---------------- */
#define PSP_O_RDONLY 0x0001
#define PSP_O_WRONLY 0x0002
#define PSP_O_RDWR   0x0003
#define PSP_O_NBLOCK 0x0004
#define PSP_O_APPEND 0x0100
#define PSP_O_CREAT  0x0200
#define PSP_O_TRUNC  0x0400
#define PSP_O_EXCL   0x0800
#define PSP_SEEK_SET 0
#define PSP_SEEK_CUR 1
#define PSP_SEEK_END 2
#define FIO_S_IFDIR 0x1000
#define FIO_S_IFREG 0x2000
#define FIO_S_ISDIR(m) (((m) & 0xf000) == FIO_S_IFDIR)
#define FIO_S_ISREG(m) (((m) & 0xf000) == FIO_S_IFREG)
typedef struct { union { unsigned int mode; unsigned int st_mode; }; unsigned int attr; union { SceOff size; SceOff st_size; }; ScePspDateTime ctime, atime, mtime; unsigned int st_private[6]; } SceIoStat;
typedef struct { SceIoStat d_stat; char d_name[256]; void *d_private; int dummy; } SceIoDirent;
SceUID sceIoOpen(const char *file, int flags, SceMode mode);
int sceIoClose(SceUID fd);
int sceIoRead(SceUID fd, void *data, SceSize size);
int sceIoWrite(SceUID fd, const void *data, SceSize size);
int sceIoLseek32(SceUID fd, int offset, int whence);
SceOff sceIoLseek(SceUID fd, SceOff offset, int whence);
int sceIoGetstat(const char *file, SceIoStat *stat);
int sceIoRemove(const char *file);
int sceIoRename(const char *old, const char *new_);
int sceIoMkdir(const char *dir, SceMode mode);
SceUID sceIoDopen(const char *dirname);
int sceIoDread(SceUID dir, SceIoDirent *dirent);
int sceIoDclose(SceUID dir);
int sceIoReadAsync(SceUID fd, void *data, SceSize size);
int sceIoWaitAsync(SceUID fd, SceInt64 *res);
int sceIoPollAsync(SceUID fd, SceInt64 *res);
int sceIoCancel(SceUID fd);
int sceIoIoctl(SceUID fd, unsigned int cmd, void *indata, int inlen, void *outdata, int outlen);
int sceIoDevctl(const char *dev, int cmd, void *indata, int inlen, void *outdata, int outlen);

#define THREAD_ATTR_USER 0x80000000
#define THREAD_ATTR_VFPU 0x4000
#define PSP_THREAD_ATTR_USER 0x80000000
#define PSP_THREAD_ATTR_VFPU 0x4000
#define PSP_THREAD_ATTR_CLEAR_STACK 0x200000
#define PSP_MODULE_USER 0
#define PSP_MODULE_INFO(a, b, c, d)
#define PSP_MAIN_THREAD_ATTR(a)
#define PSP_MAIN_THREAD_NAME(a)
#define PSP_MAIN_THREAD_STACK_SIZE_KB(a)
#define PSP_HEAP_SIZE_KB(a)
#define PSP_HEAP_SIZE_MAX()
#define PSP_NO_CREATE_MAIN_THREAD()
typedef int (*SceKernelThreadEntry)(SceSize args, void *argp);
typedef struct { unsigned low, hi; } SceKernelSysClock;
typedef struct { SceSize size; char name[32]; unsigned attr; int status; SceKernelThreadEntry entry; void *stack; int stackSize; void *gpReg; int initPriority; int currentPriority; int waitType; SceUID waitId; int wakeupCount; int exitStatus; SceKernelSysClock runClocks; unsigned intrPreemptCount, threadPreemptCount, releaseCount; } SceKernelThreadInfo;
typedef struct { SceSize size; unsigned status, currentPriority, waitType, waitId, wakeupCount; SceKernelSysClock runClocks; unsigned intrPreemptCount, threadPreemptCount, releaseCount; } SceKernelThreadRunStatus;
typedef struct { SceSize size; char name[32]; unsigned attr; int initCount, currentCount, maxCount, numWaitThreads; } SceKernelSemaInfo;
typedef struct { SceSize size; char name[32]; unsigned attr, initPattern, currentPattern; int numWaitThreads; } SceKernelEventFlagInfo;
typedef int (*SceKernelCallbackFunction)(int arg1, int arg2, void *arg);
SceUID sceKernelCreateThread(const char *name, SceKernelThreadEntry entry, int prio, int stack, unsigned attr, void *opt);
int sceKernelStartThread(SceUID th, SceSize arglen, void *argp);
int sceKernelDeleteThread(SceUID th);
int sceKernelTerminateDeleteThread(SceUID th);
int sceKernelExitDeleteThread(int status);
int sceKernelWaitThreadEnd(SceUID th, SceUInt *timeout);
int sceKernelGetThreadId(void);
int sceKernelGetThreadCurrentPriority(void);
int sceKernelReferThreadStatus(SceUID th, SceKernelThreadInfo *info);
int sceKernelReferThreadRunStatus(SceUID th, SceKernelThreadRunStatus *st);
int sceKernelGetThreadmanIdList(int type, SceUID *readbuf, int readbufsize, int *idcount);
int sceKernelRotateThreadReadyQueue(int prio);
int sceKernelDelayThread(SceUInt usec);
int sceKernelSleepThread(void);
int sceKernelSleepThreadCB(void);
SceUID sceKernelCreateSema(const char *name, unsigned attr, int init, int max, void *opt);
int sceKernelDeleteSema(SceUID s);
int sceKernelSignalSema(SceUID s, int n);
int sceKernelWaitSema(SceUID s, int n, SceUInt *timeout);
int sceKernelPollSema(SceUID s, int n);
int sceKernelReferSemaStatus(SceUID s, SceKernelSemaInfo *info);
int sceKernelReferEventFlagStatus(SceUID e, SceKernelEventFlagInfo *info);
SceUID sceKernelCreateCallback(const char *name, SceKernelCallbackFunction f, void *arg);
int sceKernelRegisterExitCallback(SceUID cb);
void sceKernelExitGame(void);
unsigned int sceKernelGetSystemTimeLow(void);
SceInt64 sceKernelGetSystemTimeWide(void);
void sceKernelDcacheWritebackAll(void);
void sceKernelDcacheWritebackRange(const void *p, unsigned size);
void sceKernelDcacheWritebackInvalidateRange(const void *p, unsigned size);
void sceKernelDcacheInvalidateRange(const void *p, unsigned size);
void sceKernelDcacheWritebackInvalidateAll(void);
unsigned sceKernelMaxFreeMemSize(void);
unsigned sceKernelTotalFreeMemSize(void);
int sceKernelVolatileMemTryLock(int unk, void **ptr, int *size);
int sceKernelVolatileMemUnlock(int unk);
int sceKernelStartModule(SceUID m, SceSize al, void *ap, int *st, void *opt);
#define sceKernelDcacheWritebackRange(p, n) sceKernelDcacheWritebackRange((p), (unsigned)(n))
int sceKernelUtilsMt19937Init(void *ctx, unsigned seed);

#define SCE_KERNEL_TMID_Thread 1
struct _reent; extern struct _reent *const _REENT_PTR_;
#define _REENT ((struct _reent *)0)
void __malloc_lock(struct _reent *r); void __malloc_unlock(struct _reent *r);
extern int xsubOn, xsubSkin, xsubCar; extern unsigned xsubU[64], xsubC[64], xsubW[64];
#define PSP_DISPLAY_SETBUF_IMMEDIATE 0
#define PSP_DISPLAY_SETBUF_NEXTFRAME 1
#define PSP_DISPLAY_PIXEL_FORMAT_565 0
#define PSP_DISPLAY_PIXEL_FORMAT_5551 1
#define PSP_DISPLAY_PIXEL_FORMAT_4444 2
#define PSP_DISPLAY_PIXEL_FORMAT_8888 3
/* uncached-alias helper: PSP ORs 0x40000000; no such thing on iOS */
#define PSP_UC(p) (p)
/* ---------------- display / ge ---------------- */
int sceDisplayWaitVblankStart(void);
int sceDisplayWaitVblank(void);
int sceDisplayIsVblank(void);
unsigned sceDisplayGetVcount(void);
unsigned sceDisplayGetCurrentHcount(void);
int sceDisplayGetFrameBuf(void **topaddr, int *bufferwidth, int *pixelformat, int sync);
int sceDisplaySetMode(int mode, int w, int h);
int sceDisplaySetFrameBuf(void *top, int bw, int pf, int sync);
void *sceGeEdramGetAddr(void);
unsigned sceGeEdramGetSize(void);
int sceGeListUpdateStallAddr(int qid, void *stall);

/* ---------------- ctrl ---------------- */
#define PSP_CTRL_SELECT 0x000001
#define PSP_CTRL_START 0x000008
#define PSP_CTRL_UP 0x000010
#define PSP_CTRL_RIGHT 0x000020
#define PSP_CTRL_DOWN 0x000040
#define PSP_CTRL_LEFT 0x000080
#define PSP_CTRL_LTRIGGER 0x000100
#define PSP_CTRL_RTRIGGER 0x000200
#define PSP_CTRL_TRIANGLE 0x001000
#define PSP_CTRL_CIRCLE 0x002000
#define PSP_CTRL_CROSS 0x004000
#define PSP_CTRL_SQUARE 0x008000
#define PSP_CTRL_HOME 0x010000
#define PSP_CTRL_HOLD 0x020000
#define PSP_CTRL_NOTE 0x800000
#define PSP_CTRL_MODE_DIGITAL 0
#define PSP_CTRL_MODE_ANALOG 1
typedef struct { unsigned int TimeStamp; unsigned int Buttons; unsigned char Lx, Ly; unsigned char Rsrv[6]; } SceCtrlData;
int sceCtrlSetSamplingCycle(int cycle);
int sceCtrlSetSamplingMode(int mode);
int sceCtrlPeekBufferPositive(SceCtrlData *pad, int count);
int sceCtrlReadBufferPositive(SceCtrlData *pad, int count);

/* ---------------- power / rtc / utility / debug ---------------- */
#define PSP_POWER_CB_POWER_SWITCH 0x80000000
#define PSP_POWER_CB_SUSPENDING 0x00040000
#define PSP_POWER_CB_RESUME_COMPLETE 0x00000080
int scePowerSetClockFrequency(int pll, int cpu, int bus);
int scePowerTick(int type);
int scePowerRegisterCallback(int slot, SceUID cb);
int scePowerIsBatteryExist(void);
int scePowerGetBatteryLifePercent(void);
int scePowerGetCpuClockFrequency(void);
int scePowerGetBusClockFrequency(void);
#define PSP_POWER_TICK_ALL 0
int sceRtcGetCurrentClockLocalTime(ScePspDateTime *t);
uint64_t sceRtcGetCurrentTick(uint64_t *tick);
#define PSP_UTILITY_SYSTEMPARAM_ID_INT_LANGUAGE 8
int sceUtilityGetSystemParamInt(int id, int *value);
#define PSP_AV_MODULE_AVCODEC 0
int sceUtilityLoadAvModule(int m); int sceUtilityUnloadAvModule(int m);
void pspDebugScreenInit(void); void pspDebugScreenInitEx(void *vram, int pf, int sync);
void pspDebugScreenPrintf(const char *fmt, ...); void pspDebugScreenPuts(const char *s);
void pspDebugScreenSetXY(int x, int y); void pspDebugScreenSetOffset(int off);
void pspDebugScreenClear(void); void pspDebugScreenSetTextColor(u32 c); void pspDebugScreenSetBackColor(u32 c);
#define pspDebugScreen printf
#define pspSdkInstallNoDeviceCheckPatch() 0
#define pspSdkInstallNoPlainModuleCheckPatch() 0


/* ---------------- savedata utility (direct file backend on iOS) ---------------- */
typedef enum { PSP_UTILITY_SAVEDATA_AUTOLOAD = 0, PSP_UTILITY_SAVEDATA_AUTOSAVE, PSP_UTILITY_SAVEDATA_LOAD, PSP_UTILITY_SAVEDATA_SAVE, PSP_UTILITY_SAVEDATA_LISTLOAD, PSP_UTILITY_SAVEDATA_LISTSAVE,
  PSP_UTILITY_SAVEDATA_LISTDELETE, PSP_UTILITY_SAVEDATA_DELETE, PSP_UTILITY_SAVEDATA_SIZES, SCE_UTILITY_SAVEDATA_AUTODELETE, SCE_UTILITY_SAVEDATA_SINGLEDELETE, PSP_UTILITY_SAVEDATA_LIST } PspUtilitySavedataMode;
#define PSP_UTILITY_SAVEDATA_AUTODELETE SCE_UTILITY_SAVEDATA_AUTODELETE
enum { PSP_UTILITY_SAVEDATA_FOCUS_UNKNOWN = 0, PSP_UTILITY_SAVEDATA_FOCUS_FIRSTLIST, PSP_UTILITY_SAVEDATA_FOCUS_LASTLIST, PSP_UTILITY_SAVEDATA_FOCUS_LATEST, PSP_UTILITY_SAVEDATA_FOCUS_OLDEST };
#define PSP_SYSTEMPARAM_ID_INT_LANGUAGE 8
#define PSP_SYSTEMPARAM_ID_INT_UNKNOWN 9
typedef struct { unsigned size; int language, buttonSwap, graphicsThread, accessThread, fontThread, soundThread; int result; int reserved[4]; } pspUtilityDialogCommon;
typedef struct { void *buf; unsigned bufSize, size; int unknown; } PspUtilitySavedataFileData;
typedef struct { char title[0x80]; char savedataTitle[0x80]; char detail[0x400]; unsigned char parentalLevel; unsigned char unknown[3]; } PspUtilitySavedataSFOParam;
typedef struct { union { struct {
  pspUtilityDialogCommon base; PspUtilitySavedataMode mode; int bind; int overwrite; char gameName[13]; char reserved[3]; char saveName[20]; char (*saveNameList)[20];
  char fileName[13]; char reserved2[3]; void *dataBuf; unsigned dataBufSize, dataSize; PspUtilitySavedataSFOParam sfoParam;
  PspUtilitySavedataFileData icon0FileData, icon1FileData, pic1FileData, snd0FileData; void *newData; int focus; int abortStatus; unsigned char key[16]; int secureVersion; };
  char raw_[1536]; }; } SceUtilitySavedataParam;
int sceUtilitySavedataInitStart(SceUtilitySavedataParam *p); int sceUtilitySavedataGetStatus(void); int sceUtilitySavedataUpdate(int n); int sceUtilitySavedataShutdownStart(void);
struct mallinfo { int arena, ordblks, smblks, hblks, hblkhd, usmblks, fsmblks, uordblks, fordblks, keepcost; };
struct mallinfo mallinfo(void);
/* ---------------- audio ---------------- */
#define PSP_AUDIO_NEXT_CHANNEL (-1)
#define PSP_AUDIO_FORMAT_STEREO 0
#define PSP_AUDIO_FORMAT_MONO 0x10
#define PSP_AUDIO_VOLUME_MAX 0x8000
int sceAudioChReserve(int channel, int samplecount, int format);
int sceAudioChRelease(int channel);
int sceAudioOutputBlocking(int channel, int vol, void *buf);
int sceAudioOutputPannedBlocking(int channel, int leftvol, int rightvol, void *buf);
int sceAudioGetChannelRestLen(int channel);

/* ---------------- GU ---------------- */
#define GU_FALSE 0
#define GU_TRUE 1
enum { GU_POINTS = 0, GU_LINES = 1, GU_LINE_STRIP = 2, GU_TRIANGLES = 3, GU_TRIANGLE_STRIP = 4, GU_TRIANGLE_FAN = 5, GU_SPRITES = 6 };
enum { GU_DIRECT = 0, GU_CALL = 1, GU_SEND = 2 };
enum { GU_ALPHA_TEST = 0, GU_DEPTH_TEST = 1, GU_SCISSOR_TEST = 2, GU_STENCIL_TEST = 3, GU_BLEND = 4, GU_CULL_FACE = 5, GU_DITHER = 6, GU_FOG = 7, GU_CLIP_PLANES = 8, GU_TEXTURE_2D = 9, GU_LIGHTING = 10, GU_LIGHT0 = 11, GU_LIGHT1 = 12, GU_LIGHT2 = 13, GU_LIGHT3 = 14, GU_LINE_SMOOTH = 15, GU_PATCH_CULL_FACE = 16, GU_COLOR_TEST = 17, GU_COLOR_LOGIC_OP = 18, GU_FACE_NORMAL_REVERSE = 19, GU_PATCH_FACE = 20, GU_FRAGMENT_2X = 21 };
enum { GU_PSM_5650 = 0, GU_PSM_5551 = 1, GU_PSM_4444 = 2, GU_PSM_8888 = 3, GU_PSM_T4 = 4, GU_PSM_T8 = 5, GU_PSM_T16 = 6, GU_PSM_T32 = 7, GU_PSM_DXT1 = 8, GU_PSM_DXT3 = 9, GU_PSM_DXT5 = 10 };
#define GU_TEXTURE_8BIT (1)
#define GU_TEXTURE_16BIT (2)
#define GU_TEXTURE_32BITF (3)
#define GU_COLOR_5650 (4<<2)
#define GU_COLOR_5551 (5<<2)
#define GU_COLOR_4444 (6<<2)
#define GU_COLOR_8888 (7<<2)
#define GU_NORMAL_8BIT (1<<5)
#define GU_NORMAL_16BIT (2<<5)
#define GU_NORMAL_32BITF (3<<5)
#define GU_VERTEX_8BIT (1<<7)
#define GU_VERTEX_16BIT (2<<7)
#define GU_VERTEX_32BITF (3<<7)
#define GU_WEIGHT_8BIT (1<<9)
#define GU_WEIGHT_16BIT (2<<9)
#define GU_WEIGHT_32BITF (3<<9)
#define GU_INDEX_8BIT (1<<11)
#define GU_INDEX_16BIT (2<<11)
#define GU_TRANSFORM_3D (0)
#define GU_TRANSFORM_2D (1<<23)
enum { GU_NEVER = 0, GU_ALWAYS, GU_EQUAL, GU_NOTEQUAL, GU_LESS, GU_LEQUAL, GU_GREATER, GU_GEQUAL };
enum { GU_CW = 0, GU_CCW = 1 };
enum { GU_FLAT = 0, GU_SMOOTH = 1 };
enum { GU_ADD = 0, GU_SUBTRACT, GU_REVERSE_SUBTRACT, GU_MIN, GU_MAX, GU_ABS };
enum { GU_SRC_COLOR = 0, GU_ONE_MINUS_SRC_COLOR, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, GU_DST_ALPHA, GU_ONE_MINUS_DST_ALPHA, GU_FIX = 10 };
#define GU_DST_COLOR GU_SRC_COLOR
#define GU_ONE_MINUS_DST_COLOR GU_ONE_MINUS_SRC_COLOR
enum { GU_NEAREST = 0, GU_LINEAR = 1, GU_NEAREST_MIPMAP_NEAREST = 4, GU_LINEAR_MIPMAP_NEAREST = 5, GU_NEAREST_MIPMAP_LINEAR = 6, GU_LINEAR_MIPMAP_LINEAR = 7 };
enum { GU_TFX_MODULATE = 0, GU_TFX_DECAL, GU_TFX_BLEND, GU_TFX_REPLACE, GU_TFX_ADD };
enum { GU_TCC_RGB = 0, GU_TCC_RGBA = 1 };
enum { GU_REPEAT = 0, GU_CLAMP = 1 };
enum { GU_TEXTURE_COORDS = 0, GU_TEXTURE_MATRIX, GU_ENVIRONMENT_MAP };
enum { GU_POSITION = 0, GU_TEXTURE_AUTO = 0 };   /* (kept: mapping modes below) */
#undef GU_TEXTURE_AUTO
enum { GU_AUTO = 0, GU_CONST = 1, GU_SLOPE = 2 };
#define GU_TEXTURE_AUTO 0
#define GU_TEXTURE_CONST 1
#define GU_TEXTURE_SLOPE 2
enum { GU_PROJECTION = 0, GU_VIEW = 1, GU_MODEL = 2, GU_TEXTURE = 3 };
enum { GU_AMBIENT = 1, GU_DIFFUSE = 2, GU_SPECULAR = 4 };
enum { GU_DIRECTIONAL = 0, GU_POINTLIGHT = 1, GU_SPOTLIGHT = 2 };
#define GU_COLOR_BUFFER_BIT 0x01
#define GU_STENCIL_BUFFER_BIT 0x02
#define GU_DEPTH_BUFFER_BIT 0x04
#define GU_FAST_CLEAR_BIT 0x10
#define GU_LEVEL_AUTO 0
#define GU_LEVEL_CONST 1
#define GU_LEVEL_SLOPE 2

void sceGuInit(void); void sceGuTerm(void);
void sceGuStart(int cid, void *list); int sceGuFinish(void); int sceGuFinishId(unsigned id);
int sceGuSync(int mode, int what); void *sceGuSwapBuffers(void); void sceGuDisplay(int state);
int sceGuCheckList(void); void *sceGuGetMemory(int size);
void sceGuCallList(const void *list); void sceGuSendCommandi(int cmd, int argument); void sceGuSendCommandf(int cmd, float argument);
void sceGuDrawBuffer(int psm, void *fbp, int fbw); void sceGuDispBuffer(int w, int h, void *dp, int dw); void sceGuDepthBuffer(void *zbp, int zbw);
void sceGuOffset(unsigned x, unsigned y); void sceGuViewport(int cx, int cy, int w, int h); void sceGuDepthRange(int n, int f);
void sceGuScissor(int x, int y, int w, int h);
void sceGuEnable(int s); void sceGuDisable(int s); int sceGuGetStatus(int s); int sceGuSetStatus(int s, int st);
void sceGuDepthFunc(int f); void sceGuDepthMask(int m); void sceGuDepthOffset(unsigned o);
void sceGuAlphaFunc(int f, int v, int m); void sceGuBlendFunc(int op, int src, int dst, unsigned sf, unsigned df);
void sceGuFrontFace(int o); void sceGuShadeModel(int m); void sceGuFog(float n, float f, unsigned c);
void sceGuClearColor(unsigned c); void sceGuClearDepth(unsigned d); void sceGuClear(int f);
void sceGuColor(unsigned c); void sceGuAmbient(unsigned c); void sceGuAmbientColor(unsigned c);
void sceGuColorMaterial(int c); void sceGuMaterial(int mode, int c); void sceGuModelColor(unsigned e, unsigned a, unsigned d, unsigned s);
void sceGuLight(int l, int t, int c, const ScePspFVector3 *pos); void sceGuLightColor(int l, int c, unsigned col);
void sceGuLightAtt(int l, float a0, float a1, float a2); void sceGuLightSpot(int l, const ScePspFVector3 *d, float e, float c);
void sceGuSpecular(float p); void sceGuSetDither(const ScePspIMatrix4 *m);
void sceGuSetMatrix(int type, const ScePspFMatrix4 *m); void sceGuBoneMatrix(unsigned index, const ScePspFMatrix4 *m);
#define GU_WEIGHTS(n) ((((n)-1)&7)<<14)
#define GU_VERTICES(n) ((((n)-1)&7)<<18)
void sceGuTexMode(int tpsm, int maxmips, int a2, int swizzle);
void sceGuTexImage(int mipmap, int w, int h, int tbw, const void *tbp);
void sceGuTexFunc(int tfx, int tcc); void sceGuTexEnvColor(unsigned c);
void sceGuTexFilter(int mn, int mg); void sceGuTexWrap(int u, int v);
void sceGuTexScale(float u, float v); void sceGuTexOffset(float u, float v);
void sceGuTexLevelMode(unsigned mode, float bias); void sceGuTexSlope(float s);
void sceGuTexMapMode(int mode, unsigned a1, unsigned a2); void sceGuTexProjMapMode(int mode); void sceGuTexFlush(void); void sceGuTexSync(void);
void sceGuClutMode(unsigned cpsm, unsigned shift, unsigned mask, unsigned a3); void sceGuClutLoad(unsigned num_blocks, const void *cbp);
void sceGuDrawArray(int prim, int vtype, int count, const void *indices, const void *vertices);
void sceGuDrawBezier(int, int, int, int, const void *, const void *);
void sceGuCopyImage(int psm, int sx, int sy, int w, int h, int srcw, void *src, int dx, int dy, int destw, void *dest);
void sceGuStencilFunc(int f, int r, int m); void sceGuStencilOp(int a, int b, int c);
void sceGuPixelMask(unsigned mask); void sceGuLogicalOp(int op); void sceGuMorphWeight(int i, float w);
void sceGuSetCallback(int sig, void (*cb)(int)); void sceGuBreak(int mode); void sceGuContinue(void);
void sceGuSignal(int b, int s); void sceGuSetAllStatus(int s); int sceGuGetAllStatus(void);

/* GUM */
void sceGumMatrixMode(int m); void sceGumLoadIdentity(void); void sceGumLoadMatrix(const ScePspFMatrix4 *m); void sceGumStoreMatrix(ScePspFMatrix4 *m);
void sceGumMultMatrix(const ScePspFMatrix4 *m); void sceGumPushMatrix(void); void sceGumPopMatrix(void); void sceGumUpdateMatrix(void);
void sceGumTranslate(const ScePspFVector3 *v); void sceGumScale(const ScePspFVector3 *v); void sceGumRotateX(float a); void sceGumRotateY(float a); void sceGumRotateZ(float a);
void sceGumPerspective(float fovy, float aspect, float n, float f); void sceGumOrtho(float l, float r, float b, float t, float n, float f);
void sceGumLookAt(const ScePspFVector3 *eye, const ScePspFVector3 *center, const ScePspFVector3 *up);
void sceGumDrawArray(int prim, int vtype, int count, const void *indices, const void *vertices);
void sceGumFullInverse(void); void sceGumFastInverse(void);
void gumLoadIdentity(ScePspFMatrix4 *m);

/* MJPEG (cutscenes): decoded with ImageIO on iOS */
int sceJpegInitMJpeg(void); int sceJpegFinishMJpeg(void); int sceJpegCreateMJpeg(int w, int h); int sceJpegDeleteMJpeg(void);
int sceJpegDecodeMJpeg(unsigned char *jpeg, unsigned size, void *rgba, unsigned dht);

/* ---------------- iOS bridge (implemented in ios/host) ---------------- */
void ios_present(void);                 /* swap the GL renderbuffer */
void ios_gl_make_current(void);
void ios_screen_size(int *w, int *h);   /* backing size in pixels */
const char *ios_docs_dir(void);
void ios_log(const char *fmt, ...);
void ios_exit_requested(void);
extern volatile unsigned ios_pad_buttons; extern volatile signed char ios_pad_lx, ios_pad_ly;

/* ---------------- GE pointer packing ---------------- */
#define GE_PTRLO 0xf0   /* arg = slot<<16 | ptr & 0xffff */
#define GE_PTRHI 0xf1   /* arg = slot<<16 | ptr >> 16     */
enum { GE_SLOT_VADDR = 0, GE_SLOT_IADDR, GE_SLOT_CALL, GE_SLOT_CLUT, GE_SLOT_TEX0 /* ..TEX0+7 */ = 4, GE_SLOT_TBW0 = 12 };
void geTexAddr(int level, const void *p, int tbw);   /* iOS replacement of raw 0xa0/0xa8 writes */
void geClutAddr(const void *p);                      /* iOS replacement of raw 0xb0/0xb1 writes */

#ifdef __cplusplus
}
#endif
#endif
