#include "gevb.h"
#ifndef GEVB_POLICE_OLD
#define GEVB_POLICE_OLD 0   // -DGEVB_POLICE_OLD=1 — лучи мигалок в список GE, как раньше
#endif
#include "police_fx.h"
#include <math.h>
#include <string.h>
#include <strings.h>
typedef struct { char name[32];float pos[3],w,h,dist,uv[8];int nkey;unsigned char key[32];unsigned color[32]; } PfDef;
#include "police_fx_data.h"
#include "police_beam_data.h"
// Слово Роба 15.10 («фонари не должны мигать»): вспышки и лучи мигалки полиции по умолчанию НЕ рисуются (сирена звучит как раньше). POLICE_FLASH_ON=1 при сборке
// (или «flag policeflash 1» в сценарии) возвращает вспышки; прежние POLICE_FX_OLD/policeFxOld — «вспышек нет» — теперь значение по умолчанию
#ifndef POLICE_FLASH_ON
#define POLICE_FLASH_ON 0
#endif
#ifndef POLICE_FX_OLD
#define POLICE_FX_OLD (!POLICE_FLASH_ON)
#endif
int policeFxOld=POLICE_FX_OLD;
#ifndef POLICE_BEAM_OLD
#define POLICE_BEAM_OLD 0
#endif
int policeBeamOld=POLICE_BEAM_OLD;
// №538: луч — плоский квад, дважды за оборот он стоит ребром к камере: тонкая щель в доли пикселя мерцает («мигающие лучи на перекрёстке»). Альфа квада умножается на плавный
// множитель по углу плоскости к лучу взгляда: ниже PB_FADE_LO (|cos| ≈ ребром) 0, выше PB_FADE_HI 1, между — гладкая ступень. SIREN_FADE_OLD=1 / policeSirenFadeOld=1 — как до правки
#ifndef SIREN_FADE_OLD
#define SIREN_FADE_OLD 0
#endif
int policeSirenFadeOld=SIREN_FADE_OLD;
#define PB_FADE_LO 0.06f
#define PB_FADE_HI 0.6f
float pfBeamFade(const float w[4][3],const float eye[3]){
 float e1[3]={w[1][0]-w[0][0],w[1][1]-w[0][1],w[1][2]-w[0][2]},e2[3]={w[3][0]-w[0][0],w[3][1]-w[0][1],w[3][2]-w[0][2]};
 float n[3]={e1[1]*e2[2]-e1[2]*e2[1],e1[2]*e2[0]-e1[0]*e2[2],e1[0]*e2[1]-e1[1]*e2[0]};float nl=sqrtf(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]);if(nl<1e-6f)return 0.f;
 float cx=(w[0][0]+w[1][0]+w[2][0]+w[3][0])*.25f,cy=(w[0][1]+w[1][1]+w[2][1]+w[3][1])*.25f,cz=(w[0][2]+w[1][2]+w[2][2]+w[3][2])*.25f;
 float v[3]={cx-eye[0],cy-eye[1],cz-eye[2]};float vl=sqrtf(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);if(vl<1e-6f)return 1.f;
 float f=fabsf(n[0]*v[0]+n[1]*v[1]+n[2]*v[2])/(nl*vl);float t=(f-PB_FADE_LO)/(PB_FADE_HI-PB_FADE_LO);t=t<0?0:t>1?1:t;return t*t*(3.f-2.f*t);
}
#define PB_RANGE2 (70.f*70.f)   // лучи дальше 70 м от глаза не рисуем (кадр погони тяжёлый, на таком расстоянии луч — пиксели)
static unsigned colorAt(const PfDef *d,float f){
 int j=0;while(j+1<d->nkey&&d->key[j+1]<=f)j++;
 if(j+1==d->nkey)return d->color[j];
 float u=(f-d->key[j])/(d->key[j+1]-d->key[j]);unsigned col=0;
 for(int k=0;k<4;k++){int a=(d->color[j]>>(8*k))&255,b=(d->color[j+1]>>(8*k))&255;col|=(unsigned)lroundf(a+(b-a)*u)<<(8*k);}
 return col;
}
int policeFxQuads(const McCar *c,float time,const float eye[3],PfQuad out[4]){
 if(policeFxOld||!c||!c->on||!c->police||c->car.destroyed||strcasecmp(c->name,"cPolice")||!isfinite(time))return 0;
 float B[16];carPieceMatrix(&c->car,carModelLift(&c->car,c->car.p.modelLift),0,0,0,1,B);
 float frame=fmodf(time*PF_FPS,PF_FRAME_COUNT);if(frame<0)frame+=PF_FRAME_COUNT;int n=0;
 for(int i=0;i<PF_FLARES;i++){
  const PfDef *d=&pfDefs[i];unsigned col=colorAt(d,frame);if(!(col&0xffffffu))continue;
  float p[3];for(int k=0;k<3;k++)p[k]=B[12+k]+B[k]*d->pos[0]+B[4+k]*d->pos[1]+B[8+k]*d->pos[2];
  float nx=eye[0]-p[0],ny=eye[1]-p[1],nz=eye[2]-p[2],len=sqrtf(nx*nx+ny*ny+nz*nz);if(len<=0)continue;
  nx/=len;ny/=len;nz/=len;float rx=nz,rz=-nx,rl=sqrtf(rx*rx+rz*rz);if(rl<=0)continue;rx/=rl;rz/=rl;
  // AAX: обе оси в плоскости, обращённой к камере; DIST с диска к глазу
  float ux=ny*rz,uy=nz*rx-nx*rz,uz=-ny*rx;
  p[0]+=nx*d->dist;p[1]+=ny*d->dist;p[2]+=nz*d->dist;
  PfVertex v[4];static const int sx[4]={-1,1,1,-1},sy[4]={1,1,-1,-1};
  for(int k=0;k<4;k++){float x=sx[k]*d->w*.5f,y=sy[k]*d->h*.5f;
   v[k]=(PfVertex){d->uv[k*2],d->uv[k*2+1],col,p[0]+rx*x+ux*y,p[1]+uy*y,p[2]+rz*x+uz*y};}
  out[n].v[0]=v[0];out[n].v[1]=v[1];out[n].v[2]=v[2];out[n].v[3]=v[0];out[n].v[4]=v[2];out[n].v[5]=v[3];out[n].flare=i;n++;
 }
 return n;
}
// большие лучи: углы квадов в модели машины по кадрам клипа сустава (tools/police_beam_export.py), между кадрами линейно
int policeFxBeams(const McCar *c,float time,const float eye[3],PfQuad out[PF_BEAMS]){
 if(policeBeamOld||policeFxOld||!c||!c->on||!c->police||c->car.destroyed||strcasecmp(c->name,"cPolice")||!isfinite(time))return 0;
 float dx=eye[0]-c->car.x,dy=eye[1]-c->car.y,dz=eye[2]-c->car.z;if(dx*dx+dy*dy+dz*dz>PB_RANGE2)return 0;
 float B[16];carPieceMatrix(&c->car,carModelLift(&c->car,c->car.p.modelLift),0,0,0,1,B);
 float fr=fmodf(time*PB_FPS,PB_FRAMES);if(fr<0)fr+=PB_FRAMES;int i0=(int)fr;if(i0>=PB_FRAMES)i0=0;int i1=(i0+1)%PB_FRAMES;float u=fr-i0;
 for(int i=0;i<PB_COUNT;i++){
  const PbDef *d=&pbDefs[i];float w[4][3];
  for(int k=0;k<4;k++){float m[3];for(int a=0;a<3;a++)m[a]=d->c[i0][k][a]+(d->c[i1][k][a]-d->c[i0][k][a])*u;
   for(int a=0;a<3;a++)w[k][a]=B[12+a]+B[a]*m[0]+B[4+a]*m[1]+B[8+a]*m[2];}
  unsigned col=d->color;if(!policeSirenFadeOld){float fd=pfBeamFade((const float(*)[3])w,eye);unsigned al=(unsigned)((col>>24)*fd+.5f);col=(col&0x00ffffffu)|(al<<24);}
  PfVertex v[4];for(int k=0;k<4;k++)v[k]=(PfVertex){d->uv[k*2],d->uv[k*2+1],col,w[k][0],w[k][1],w[k][2]};
  out[i].v[0]=v[0];out[i].v[1]=v[1];out[i].v[2]=v[2];out[i].v[3]=v[0];out[i].v[4]=v[2];out[i].v[5]=v[3];out[i].flare=PF_FLARES+i;
 }
 return PB_COUNT;
}
#ifndef SKIN_HOST
#include <pspgu.h>
#include <pspkernel.h>
int policeFxDraw(const McCar *c,float time,const float eye[3]){
 PfQuad q[PF_FLARES+PF_BEAMS];int n=policeFxQuads(c,time,eye,q);
 int nb=policeFxBeams(c,time,eye,q+n);if(!n&&!nb)return 0;
 static int flushed;if(!flushed){sceKernelDcacheWritebackRange((void*)pfTexture,sizeof pfTexture);flushed=1;}
 int fog=sceGuGetStatus(GU_FOG),light=sceGuGetStatus(GU_LIGHTING),alpha=sceGuGetStatus(GU_ALPHA_TEST),cull=sceGuGetStatus(GU_CULL_FACE);
 ScePspFMatrix4 I;memset(&I,0,sizeof I);I.x.x=I.y.y=I.z.z=I.w.w=1.f;sceGuSetMatrix(GU_MODEL,&I);
 sceGuDisable(GU_FOG);sceGuDisable(GU_LIGHTING);sceGuDisable(GU_ALPHA_TEST);sceGuEnable(GU_DEPTH_TEST);
 sceGuEnable(GU_TEXTURE_2D);sceGuEnable(GU_BLEND);sceGuBlendFunc(GU_ADD,GU_SRC_ALPHA,GU_FIX,0,0xffffffff);sceGuDepthMask(GU_TRUE);
 sceGuTexMode(GU_PSM_8888,0,0,0);sceGuTexImage(0,PF_TEX_W,PF_TEX_H,PF_TEX_W,pfTexture);
 sceGuTexFunc(GU_TFX_MODULATE,GU_TCC_RGBA);sceGuTexScale(1.f,1.f);sceGuTexOffset(0,0);sceGuTexFilter(GU_LINEAR,GU_LINEAR);
 if(nb)sceGuDisable(GU_CULL_FACE);   // луч — плоскость без лицевой стороны: виден с обеих
 n+=nb;
 for(int i=0;i<n;i++){PfVertex *v=geVbAlloc(sizeof q[i].v,GEVB_POLICE_OLD);memcpy(v,q[i].v,sizeof q[i].v);
  sceGuDrawArray(GU_TRIANGLES,GU_TEXTURE_32BITF|GU_COLOR_8888|GU_VERTEX_32BITF|GU_TRANSFORM_3D,6,0,v);}
 sceGuTexScale(128.f,128.f);sceGuBlendFunc(GU_ADD,GU_SRC_ALPHA,GU_ONE_MINUS_SRC_ALPHA,0,0);
 sceGuDisable(GU_BLEND);sceGuDepthMask(GU_FALSE);
 sceGuSetStatus(GU_FOG,fog);sceGuSetStatus(GU_LIGHTING,light);sceGuSetStatus(GU_ALPHA_TEST,alpha);sceGuSetStatus(GU_CULL_FACE,cull);
 return n;
}
#else
int policeFxDraw(const McCar *c,float time,const float eye[3]){PfQuad q[PF_FLARES+PF_BEAMS];int n=policeFxQuads(c,time,eye,q);return n+policeFxBeams(c,time,eye,q+n);}
#endif
