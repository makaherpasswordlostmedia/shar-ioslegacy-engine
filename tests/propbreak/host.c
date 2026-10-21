// Actual contact response, including disc state callbacks, not a rewritten model.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "stateprops.h"
#include "props.h"
static int fail,broken,solid,stops;
static void hit(StateProps *s,unsigned i,const SpCol *v,int direction){
 SpRun*r=&s->run[i];float center[3],extent=0;
 for(int k=0;k<3;k++)center[k]=(k==0?r->x:k==1?r->y:r->z)+r->R[k]*v->c[0]+r->R[3+k]*v->c[1]+r->R[6+k]*v->c[2];
 if(v->kind==1)extent=v->h[0];else for(int k=0;k<3;k++){float axis=r->R[0]*v->a[k*3]+r->R[3]*v->a[k*3+1]+r->R[6]*v->a[k*3+2];extent+=fabsf(axis)*v->h[k];}
 Car c={0};carDefaults(&c.p);c.q[0]=1;c.x=center[0]+direction*(extent+c.p.halfW-.1f);c.z=center[2]+c.p.bodyOfs;
 CarBox cb;carBox(&c,&cb);c.y=center[1]-(cb.y+(cb.lo+cb.hi)*.5f);c.vel[0]=-direction*15.f;c.vel[1]=-3;c.v=15;
 float x=c.x,z=c.z;int h=s->hits;spHitCar(s,NULL,&c,NULL);
 if(s->hits==h)return;
 if(!r->alive||!r->colOn){broken++;if(fabsf(c.vel[0]+direction*15.f)>.00001f||c.vel[1]!=-3||c.x!=x||c.z!=z){fail++;stops++;}}
 else {solid++;if(c.vel[0]==-direction*15.f&&c.x==x)fail++;}
 if(s->killSpeed)fail++;
}
static int kick(void*u,unsigned i,float x,float z){(void)u;(void)i;(void)x;(void)z;return 1;}
static void fixtures(void){
 SpType type={0};type.nCol=1;type.nState=2;type.mass=100;type.h[0]=type.h[1]=type.h[2]=1;type.cls=4;
 SpState state[2]={0};state[0].autoTo=state[1].autoTo=255;state[0].nEvent=1;state[1].nCall=2;
 SpEvent event={SP_EV_VEHICLE_HIT,1,0};SpCall calls[2]={{SP_OP_COLOFF,0,0,0},{SP_OP_KILLSPEED,0,0,0}};
 SpCol volume={0};volume.a[0]=volume.a[4]=volume.a[8]=1;volume.h[0]=volume.h[1]=volume.h[2]=1;
 SpInst inst={0};SpRun run={0};run.alive=run.colOn=1;run.R[0]=run.R[4]=run.R[8]=1;
 StateProps s={0};s.type=&type;s.state=state;s.event=&event;s.call=calls;s.col=&volume;s.inst=&inst;s.run=&run;s.ntype=s.ninst=1;
 hit(&s,0,&volume,1);
 // An authored hit without collision-off is still a real obstacle.
 memset(&run,0,sizeof run);run.alive=run.colOn=1;run.R[0]=run.R[4]=run.R[8]=1;state[1].nCall=0;
 hit(&s,0,&volume,1);
 // DynaPhys replacement by its BreakableObject is also pass-through this frame.
 PropType t={1,1,100,0,0};PropDef def={0};PropState p={0};p.q[0]=1;p.hx=p.hy=p.hz=1;p.asleep=1;
 Props props={0};props.types=&t;props.def=&def;props.st=&p;props.ninst=props.ntype=1;props.onKick=kick;
 unsigned char fx[2]={0,1};props.typeFx=fx;props.ntypeFx=1;
 Car c={0};carDefaults(&c.p);c.q[0]=1;c.vel[0]=-15;c.x=c.p.halfW+.9f;c.v=15;
 struct {ColHdr h;ColTri t[2];unsigned starts[2],refs[2];} floor={0};
 memcpy(floor.h.magic,"COL1",4);floor.h.ox=floor.h.oz=-100;floor.h.cell=200;floor.h.W=floor.h.H=1;floor.h.ntri=floor.h.nref=2;floor.starts[1]=2;floor.refs[1]=1;
 floor.t[0]=(ColTri){{-100,0,-100},{100,0,100},{100,0,-100},{0,1,0}};floor.t[1]=(ColTri){{-100,0,-100},{-100,0,100},{100,0,100},{0,1,0}};ColWorld world;if(colInit(&world,&floor,sizeof floor))exit(2);
 propsHitCar(&props,&world,&c,NULL);colFree(&world);if(!p.hidden||c.vel[0]!=-15)fail++;
}
int main(int argc,char**argv){fixtures();
 for(int a=1;a<argc;a++){
  FILE*f=fopen(argv[a],"rb");if(!f)return 2;unsigned po;if(fseek(f,96,SEEK_SET)||fread(&po,4,1,f)!=1)return 2;
  fseek(f,0,SEEK_END);long n=ftell(f)-po;void*b=malloc(n);fseek(f,po,SEEK_SET);if(fread(b,1,n,f)!=(size_t)n)return 2;fclose(f);
  Props p;StateProps s;if(propsInit(&p,b,n)||spInit(&s,p.spr,p.sprSize))return 2;
  int b0=broken;for(unsigned i=0;i<s.ninst;i++)s.run[i].colOn=0;
  for(unsigned i=0;i<s.ninst;i++){const SpType*T=&s.type[s.inst[i].type];if(T->kind||!T->nCol||T->cls==2)continue;
   for(int d=-1;d<=1;d+=2){spEnter(&s,i,0);s.run[i].cool=0;hit(&s,i,&s.col[T->firstCol],d);s.run[i].colOn=0;}
  }
  printf("DISC %s brokenContacts=%d\n",argv[a],broken-b0);spFree(&s);propsFree(&p);free(b);
 }
 printf("%s broken=%d solidControls=%d stoppedAfterBreak=%d failures=%d\n",fail?"FAIL":"PASS",broken,solid,stops,fail);return !!fail;
}
