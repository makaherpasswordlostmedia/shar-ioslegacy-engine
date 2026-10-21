// №394: screen-anchored native-pixel halftone; no animated phase or blurred sampling
#include "groundshade.h"
#include <pspgu.h>
#include <pspkernel.h>
#include <string.h>
// №398 (Роб 08.10: «тень полутоном мигает, лагает, слишком контрастная»): полутон 1 px с удвоенной альфой на экране PSP даёт жёсткое
// зерно, которое «кипит» при движении. Тень — гладкая: та же сетка 4×4 с мягким краем по альфе вершин, без текстуры (нечему
// мигать при выборке) и со смещением глубины 4 (тень не борется с землёй — это и было мигание до №394). Средняя темнота прежняя.
// Прежнее (полутон №394): -DGROUND_SHADE_HALFTONE=1
#ifndef GROUND_SHADE_HALFTONE
#define GROUND_SHADE_HALFTONE 0
#endif
int groundShadeOld;
static ScePspFMatrix4 projection;
static unsigned dots[16*16] __attribute__((aligned(16)));
static int ready, viewReady;
void groundShadeView(const float *eye, const float *forward, const float *right, const float *up, float focal) {
  float *m=(float *)&projection; memset(m,0,sizeof projection);
  for(int k=0;k<3;k++) {
    m[k*4]=(focal*right[k]+240.f*forward[k])/16.f;
    m[k*4+1]=(-focal*up[k]+136.f*forward[k])/16.f;
    m[k*4+2]=forward[k];
    for(int a=0;a<3;a++)m[12+a]-=m[k*4+a]*eye[k];
  }
  m[15]=1.f;
  viewReady=1;
}
unsigned groundShadeAlpha(float alpha) {
  if(GROUND_SHADE_HALFTONE && !groundShadeOld && viewReady)alpha*=2.f; // 50% coverage keeps the previous mean opacity
  return (unsigned)(alpha<0.f?0.f:alpha>255.f?255.f:alpha);
}
void groundShadeBegin(void) {
  sceGuDepthOffset(groundShadeOld || !viewReady?0:4);
  sceGuDisable(GU_ALPHA_TEST);
  if(groundShadeOld || !viewReady || !GROUND_SHADE_HALFTONE) { sceGuDisable(GU_TEXTURE_2D);return; }
  if(!ready) {
    for(int y=0;y<16;y++)for(int x=0;x<16;x++)dots[y*16+x]=((x+y)&1)?0x00ffffffu:0xffffffffu;
    sceKernelDcacheWritebackRange(dots,sizeof dots);ready=1;
  }
  sceGuEnable(GU_TEXTURE_2D); sceGuTexMode(GU_PSM_8888,0,0,0); sceGuTexImage(0,16,16,16,dots);
  sceGuTexMapMode(GU_TEXTURE_MATRIX,0,0); sceGuTexProjMapMode(GU_POSITION); sceGuSetMatrix(GU_TEXTURE,&projection);
  sceGuTexScale(1.f,1.f); sceGuTexOffset(0.f,0.f); sceGuTexWrap(GU_REPEAT,GU_REPEAT);
  sceGuTexFilter(GU_NEAREST,GU_NEAREST); sceGuTexFunc(GU_TFX_MODULATE,GU_TCC_RGBA);
  sceGuEnable(GU_ALPHA_TEST); sceGuAlphaFunc(GU_GREATER,0,0xff);
}
void groundShadeEnd(void) {
  sceGuTexMapMode(GU_TEXTURE_COORDS,0,0); sceGuDisable(GU_TEXTURE_2D);
  sceGuDisable(GU_ALPHA_TEST); sceGuAlphaFunc(GU_GREATER,0x40,0xff);
  sceGuDepthOffset(0); sceGuTexScale(128.f,128.f);
}
