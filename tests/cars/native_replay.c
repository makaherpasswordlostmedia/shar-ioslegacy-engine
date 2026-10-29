// Replay a measured native pose, including COM velocity and angular momentum.
#include <stdio.h>
#include <stdlib.h>
#include "../../viewer/car.c"
int main(int argc,char**argv){
 if(argc!=3)return 2;FILE*f=fopen(argv[1],"rb");if(!f)return 2;fseek(f,0,SEEK_END);long size=ftell(f);rewind(f);unsigned char*d=malloc(size);if(!d||fread(d,1,size,f)!=(size_t)size)return 2;fclose(f);
 unsigned co,po,pv;memcpy(&co,d+92,4);memcpy(&po,d+96,4);memcpy(&pv,d+88,4);unsigned end=size;if(po>co&&po<end)end=po;if(pv>co&&pv<end)end=pv;ColWorld W;if(colInit(&W,d+co,end-co))return 2;
 f=fopen(argv[2],"r");if(!f)return 2;char name[16];int frames,gas;float m[16],velocity[3],angular[3],localCM[3],inertia[6];
 if(fscanf(f,"%15s%d%d",name,&frames,&gas)!=3||frames<2||frames>1000)return 2;
 float*groups[]={m,velocity,angular,localCM,inertia};int lengths[]={16,3,3,3,6};
 for(int i=0;i<5;i++)for(int j=0;j<lengths[i];j++)if(fscanf(f,"%f",&groups[i][j])!=1)return 2;
 int throttle[1001];for(int i=0;i<=frames;i++)throttle[i]=i<=gas;
 char tag[16];int count;
 if(fscanf(f,"%15s",tag)==1) {
  if(strcmp(tag,"INPUTS")||fscanf(f,"%d",&count)!=1||count!=frames)return 2;
  for(int i=1;i<=frames;i++)if(fscanf(f,"%d",&throttle[i])!=1||(throttle[i]!=0&&throttle[i]!=1))return 2;
 }
 fclose(f);
 Car c;CarParams p;if(!carParamsFor(name,&p))return 2;
#ifdef PS2_RESTITUTION_OLD
 p.groundRestitution=.3f; // previous port coefficient; only the negative replay fixture
#endif
 carInit(&c,&p,&W,m[12],m[13],-m[14],0);
 M3 R={v3(-m[0],-m[1],m[2]),v3(m[4],m[5],-m[6]),v3(m[8],m[9],-m[10])};mQuat(&R,c.q);quatNorm(c.q);
 V3 base=sub(v3(m[12],m[13],-m[14]),scl(R.U,carModelLift(&c,p.modelLift)));
 c.x=base.x;c.y=base.y;c.z=base.z;
 c.com[0]=-localCM[0];c.com[1]=localCM[1]+carModelLift(&c,p.modelLift);c.com[2]=localCM[2];
 c.w[0]=-angular[0];c.w[1]=-angular[1];c.w[2]=angular[2];
 // The Vehicle velocity sample follows the model origin. The integrator
 // needs COM velocity; include the measured rigid-body point velocity.
 V3 omega=v3(c.w[0],c.w[1],c.w[2]);
 V3 lever=mulM(&R,v3(-localCM[0],localCM[1],localCM[2]));
 V3 cv=add(v3(velocity[0],velocity[1],-velocity[2]),cross(omega,lever));
 c.vel[0]=cv.x;c.vel[1]=cv.y;c.vel[2]=cv.z;
 inertia[1]*=-1;inertia[2]*=-1;tensorSet(&c,inertia);syncOut(&c);
 c.grounded=localCM[1]>p.weebleOffset*.5f;if(!c.grounded)c.wheels=0;c.fallTop=c.y;c.fallT0=c.t;
 for(int fr=0;fr<=frames;fr++) {
  if(fr){CarInput in={0};in.throttle=throttle[fr];carUpdate(&c,&W,&in,1/50.f);}
  if(fr%2)continue;M3 Q=quatM(c.q);V3 model=add(v3(c.x,c.y,c.z),scl(Q.U,carModelLift(&c,p.modelLift)));
  V3 cm=add(v3(c.x,c.y,c.z),mulM(&Q,v3(c.com[0],c.com[1],c.com[2])));
  V3 modelVelocity=sub(v3(c.vel[0],c.vel[1],c.vel[2]),cross(v3(c.w[0],c.w[1],c.w[2]),sub(cm,model)));
  printf("%d %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %d %.9g %.9g %.9g\n",fr,model.x,model.y,model.z,cm.x,cm.y,cm.z,c.vel[0],c.vel[1],c.vel[2],Q.U.y,c.pitch,c.roll,c.h,c.recoveries,modelVelocity.x,modelVelocity.y,modelVelocity.z);
 }
 colFree(&W);free(d);return 0;
}
