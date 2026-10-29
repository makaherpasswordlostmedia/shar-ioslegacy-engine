#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <assert.h>
typedef int SceUID; typedef unsigned SceSize; typedef long long SceInt64;
static unsigned now, due;static int thread=1,locked,asyncN,syncN,flushN,waitN,submitFail,pollFail,readError,shortRead;
static unsigned char input[200000];static unsigned pos;static void *dst;static unsigned req;
int sceKernelGetThreadId(void){return thread;}
int sceKernelGetThreadCurrentPriority(void){return 32;}
int sceKernelRotateThreadReadyQueue(int p){assert(p==32);now+=50;return 0;}
unsigned sceKernelGetSystemTimeLow(void){return now;}
int sceKernelDelayThread(unsigned us){now+=us;return 0;}
int sceKernelCreateSema(const char*n,int a,int b,int c,void*d){return 1;}
int sceKernelPollSema(int s,int n){assert(!locked);locked=1;return 0;}
int sceKernelWaitSema(int s,int n,void*t){assert(0);return -1;}
int sceKernelSignalSema(int s,int n){assert(locked);locked=0;return 0;}
static int copybytes(void *d,unsigned n){if(readError)return -9;if(shortRead&&n>7)n=7;if(n>sizeof input-pos)n=sizeof input-pos;memcpy(d,input+pos,n);pos+=n;return n;}
int sceIoRead(int fd,void*d,unsigned n){syncN++;now+=200000;return copybytes(d,n);}
int sceIoWrite(int fd,const void*d,unsigned n){assert(locked);return n;}
int sceIoIoctl(int f,unsigned c,void*a,int b,void*d,int e){assert(locked);flushN++;return -1;}
int sceIoReadAsync(int fd,void*d,unsigned n){assert(locked);asyncN++;if(submitFail)return -1;dst=d;req=n;due=now+200000;return 0;}
int sceIoPollAsync(int fd,SceInt64*r){if(pollFail){pollFail=0;return -7;}if(now<due)return 1;*r=copybytes(dst,req);return 0;}
int sceIoWaitAsync(int fd,SceInt64*r){waitN++;now=due;*r=copybytes(dst,req);return 0;}
#define MSIO_HOST_STUBS
#include "../../../viewer/msio.c"
#define LOAD_FUSE_HOST_STUBS
#include "../../../viewer/load_fuse_io.c"
static int frames,mask;static unsigned last;
static void pump(void){assert(thread==1 && locked && loadFuseIoPumping());if(now-last>=40000){frames++;mask|=1u<<((now*15ull/1000000)%2);last=now;}}
int main(void){
 unsigned char out[sizeof input];for(unsigned i=0;i<sizeof input;i++)input[i]=(i*19+7)&255;
 msioInit();loadFuseIoBegin(pump);loadFuseIoSlow(350000,4);
 int r=msioRead(1,out,sizeof out);assert(r==sizeof out && !memcmp(out,input,sizeof out));assert(flushN==4 && !locked);
 printf("slow chunks4 data exact; frames=%d phases=%d old=%d\n",frames,mask,LOAD_FUSE_ANIM_OLD);
 int bad=frames<12 || mask!=3;
 int a=asyncN;thread=2;pos=0;msioRead(1,out,4);assert(asyncN==a);thread=1;
 loadFuseIoEnd();pos=0;msioRead(1,out,4);assert(asyncN==a);
 loadFuseIoBegin(pump);loadFuseIoSlow(0,0);pos=0;submitFail=1;assert(msioRead(1,out,4)==4);submitFail=0;
 shortRead=1;pos=0;assert(msioRead(1,out,100)==7);shortRead=0;
 readError=1;assert(msioRead(1,out,100)==-9);readError=0;
 pos=sizeof input;assert(msioRead(1,out,100)==0);
 if(!LOAD_FUSE_ANIM_OLD){pos=0;pollFail=1;assert(msioRead(1,out,4)==4 && waitN==1);}
 loadFuseIoEnd();assert(!locked);puts("PASS owner/disabled/fallback/short/EOF/error/drain and cache-lock invariants");
 puts(bad?"FAIL flame frozen during slow read":"PASS flame changes during slow read");return bad;
}
