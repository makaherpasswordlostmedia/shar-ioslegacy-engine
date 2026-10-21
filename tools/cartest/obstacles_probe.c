/* Measurement only: reuse Codex-6's city+SPR ray detector and actual car/COL.
   Target grid, every authored foliage volume, and ANM1 at five clip phases. */
#define WALLS_LIBRARY
#include "walls.c"
#include "../../viewer/animobj.h"
static int trials, noGround, seq;
extern int sandboxWheelContacts(const Car*,const ColWorld*,ColSphereContact*,int);
static float phaseNow, foliageExit=-1;
static int actor=-1, injectOldPose;
static AnimObjs animated;
static void observation(const char *family,Car *c,float x,float z,int type,unsigned idx,float v,float still,float rise,float h,int spid){
 printf("{\"family\":\"%s\",\"x\":%.4f,\"y\":%.4f,\"z\":%.4f,\"ptype\":%d,\"pidx\":%u,\"speed\":%.3f,\"still\":%.3f,\"rise\":%.3f,\"step\":%.3f,\"heading\":%.8f,\"phase\":%.3f,\"actor\":%d,\"sp\":%d,\"trial\":%d,\"end\":[%.3f,%.3f],\"foliage\":%.3f}\n",family,x,c->y,z,type,idx,v,still,rise,c->p.step,h,phaseNow,actor,spid,seq,c->x,c->z,c->foliCover);
}
static int visible(Car *c){
 for(int s=-1;s<=1;s++)for(int k=0;k<4;k++){
  float nx=c->wallN[0],nz=c->wallN[1],o[3]={c->wallP[0]+nx*.3f+nz*.5f*s,c->wallP[1]+.4f+k*.33f,c->wallP[2]+nz*.3f-nx*.5f*s},d[3]={-nx,0,-nz};
  if(rayCast(o,d,1.3f)>=0)return 1;
 }return 0;
}
static void drive(float x,float z,float y,float h,float kmh,int foliage){
 float g;seq++;if(!colGround(&W,x,z,y+3,-1000,&g,0)||(y<99&&fabsf(g-y)>8)){noGround++;return;}
 Car c;carInit(&c,0,&W,x,g,z,h);CarInput in={0};for(int n=0;n<15;n++)carUpdate(&c,&W,&in,1.f/60);
 carSetSpeed(&c,kmh/3.6f);in.throttle=1;float ax=c.x,az=c.z,still=0;int lastType=-1,lastId=-1,sent=0,lastVis=0;float lastTop=999;
 trials++;
 int wheelSent=0;
 for(int f=0;f<600;f++){
  carUpdate(&c,&W,&in,1.f/60);
  if(hypotf(c.x-ax,c.z-az)>.5f){ax=c.x;az=c.z;still=0;}else still+=1.f/60;
  if(c.wallV>.2f){
   int changed=lastType!=c.wallType||lastId!=(int)c.wallIdx;lastType=c.wallType;lastId=c.wallIdx;if(changed||f%60==0)lastVis=visible(&c);lastTop=primTop(lastType,lastId)-c.wallP[1];
   if(!sent && c.wallV>2){
   float nx=c.wallN[0],nz=c.wallN[1];float gy=renderGround(c.wallP[0]-nx*.6f,c.wallP[2]-nz*.6f,c.wallP[1]+1.5f);float rise=gy>-1e8f?gy-c.wallP[1]:-9;
   int own=actor<0;
   if(actor>=0){const AoObj *o=&animated.obj[actor];if(!o->nVol){const SpInst*i=&renderedSP.inst[o->firstInst];own=hypotf(c.wallP[0]-i->x,c.wallP[2]-i->z)<15.f;}for(unsigned v=o->firstVol;v<o->firstVol+o->nVol;v++)if((animated.vol[v].kind?COL_CYL:COL_BOX)==lastType&&animated.vol[v].col==(unsigned)lastId)own=1;}
   const char *fam=lastType==COL_SEG?"allowed":lastVis?"visible":actor>=0&&own?"animation":"invisible";
   if(lastType!=COL_SEG&&rise>.01f&&rise<c.p.step&&lastTop<c.p.step+.06f)fam="curb";
   if(!sent && own && c.wallV>2){observation(fam,&c,c.wallP[0],c.wallP[2],lastType,lastId,kmh,still,rise,h,-1);sent=1;}
   }
  }
  if(still>.8f&&!wheelSent){
   ColSphereContact hits[16];int n=sandboxWheelContacts(&c,&W,hits,16);
   for(int j=0;j<n;j++){int t=hits[j].ref>>29;unsigned id=hits[j].ref&0x1fffffff;float floor;
    if(t==COL_SEG||!colGround(&W,c.x,c.z,c.y+.1f,c.y-2,&floor,0))continue;
    float top=primTop(t,id)-floor;
    float gy=renderGround(hits[j].p[0]-hits[j].n[0]*.35f,hits[j].p[2]-hits[j].n[2]*.35f,floor+c.p.step+.1f),rise=gy>-1e8f?gy-floor:-9;
    if(top>.01f&&top<c.p.step&&rise>=-.03f&&rise<c.p.step){observation("curb",&c,hits[j].p[0],hits[j].p[2],t,id,kmh,still,rise,h,-1);wheelSent=1;break;}
   }
  }
  if(still>3.f){
   float fol=c.foliCover;int near=colFoliageNear(&W,c.x,c.y+.5f,c.z,.25f);
   if(foliage&&(fol>0||near)){
    const char *fam=lastType==COL_SEG?"allowed":(lastType==COL_BOX&&lastVis&&lastTop>c.p.step&&!colFoliageNear(&W,c.wallP[0],c.y+.5f,c.wallP[2],.1f))?"visible":"foliage";
    observation(fam,&c,c.x,c.z,lastType,lastId<0?0:lastId,kmh,still,0,h,-1);
   }
   break;
  }
  if(!foliage&&(sent||f>=120))break;
  if(foliageExit>0&&(c.x-x)*sinf(h)+(c.z-z)*cosf(h)>foliageExit)break;
 }
}
static float extent(int t,unsigned i,float dx,float dz){
 if(t==COL_CYL){const ColCyl*c=&W.cyl[i];return c->r+c->halfLen*fabsf(c->axis[0]*dx+c->axis[2]*dz);}
 const ColBox*b=&W.box[i];return b->h[0]*fabsf(b->ax[0]*dx+b->ax[2]*dz)+b->h[1]*fabsf(b->ay[0]*dx+b->ay[2]*dz)+b->h[2]*fabsf(b->az[0]*dx+b->az[2]*dz);
}
static void rebuild(void){free(T);free(gStart);free(gList);T=0;gStart=gList=0;NT=0;loadRender();}
int main(int argc,char**argv){
 if(argc<3)return 2;loadLevel(argv[1]);loadProps();loadRender();
 if(argc>3&&!strcmp(argv[3],"--old-pose"))injectOldPose=1;
 if(!strcmp(argv[2],"foliage")){
  for(int typ=COL_BOX;typ<=COL_CYL;typ++)for(unsigned i=0;i<(typ==COL_BOX?W.nbox:W.ncyl);i++){
   const float*p=typ==COL_BOX?W.box[i].c:W.cyl[i].c;if((typ==COL_BOX?W.box[i].pad:W.cyl[i].pad[0])!=1.f)continue;
   for(int d=0;d<4;d++)for(int v=0;v<4;v++){float h=d*1.5707963f,dx=sinf(h),dz=cosf(h),off=v?extent(typ,i,dx,dz)+5:0;foliageExit=off+extent(typ,i,dx,dz)+3;drive(p[0]-dx*off,p[2]-dz*off,p[1],h,v*20,1);}
  }
 }else if(!strcmp(argv[2],"targets")){
  float x,z,y,h,v;while(scanf("%f %f %f %f %f",&x,&z,&y,&h,&v)==5)drive(x,z,y,h,v,1);
 }else if(!strcmp(argv[2],"animation")){
  unsigned po=*(unsigned*)(file+96);int rc=aoInit(&animated,file+po,*(unsigned*)(file+po+40),&renderedSP,&W);if(rc<0)return 3;
  /* Five complete scene snapshots, not five city rebuilds per object.
     Every collider and drawable uses the same authored phase in each snapshot. */
  for(int f=0;f<5;f++){
   for(unsigned a=0;a<animated.nobj;a++){
    const AoObj*o=&animated.obj[a];if(!o->nInst)continue;float frame=(o->nfr?o->nfr-1:0)*f/4.f;
    for(unsigned i=o->firstInst;i<o->firstInst+o->nInst;i++){renderedSP.run[i].poseF=injectOldPose?0:frame;renderedSP.run[i].poseValid=0;}
    aoPlace(&animated,&renderedSP,&W,a);
    if(injectOldPose)for(unsigned i=o->firstInst;i<o->firstInst+o->nInst;i++){renderedSP.run[i].poseF=frame;renderedSP.run[i].poseValid=0;}
   }
   rebuild();
   for(unsigned a=0;a<animated.nobj;a++){
    const AoObj*o=&animated.obj[a];if(!o->nInst)continue;actor=a;phaseNow=(o->nfr?o->nfr-1:0)*f/4.f;
    if(!o->nVol){const SpInst*i=&renderedSP.inst[o->firstInst];const SpType*t=&renderedSP.type[i->type];for(int d=0;d<4;d++){float h=d*1.5707963f,e=fminf(20.f,hypotf(t->h[0],t->h[2]))+5;drive(i->x-sinf(h)*e,i->z-cosf(h)*e,i->y,h,40,0);}}
    for(unsigned vi=o->firstVol;vi<o->firstVol+o->nVol;vi++){
     const AoVol*v=&animated.vol[vi];int t=v->kind?COL_CYL:COL_BOX;const float*p=t==COL_BOX?W.box[v->col].c:W.cyl[v->col].c;float px=p[0],py=p[1],pz=p[2];
     for(int d=0;d<4;d++){float h=d*1.5707963f,dx=sinf(h),dz=cosf(h),e=extent(t,v->col,dx,dz)+5;drive(px-dx*e,pz-dz*e,py,h,40,0);}
    }
   }
  }
 }else return 2;
 fprintf(stderr,"{\"mode\":\"%s\",\"trials\":%d,\"no_ground\":%d,\"objects\":%u}\n",argv[2],trials,noGround,animated.nobj);return 0;
}
