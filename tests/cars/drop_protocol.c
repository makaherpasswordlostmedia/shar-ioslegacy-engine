// Controlled replay of recorded COM/velocity write windows, actual carUpdate
// Full seed pose comes from the same native snapshot, NOT an invented impact pose
#include <stdio.h>
#include <stdlib.h>
#include "../../viewer/car.c"
typedef struct { int begin,end,field,axis;float value; } Write;
int main(int argc,char **argv){
 if(argc!=3)return 2;FILE*f=fopen(argv[1],"rb");if(!f)return 2;
 fseek(f,0,SEEK_END);long sz=ftell(f);rewind(f);unsigned char*d=malloc(sz);
 if(!d||fread(d,1,sz,f)!=(size_t)sz)return 2;fclose(f);
 unsigned co,po,pv;memcpy(&co,d+92,4);memcpy(&po,d+96,4);memcpy(&pv,d+88,4);unsigned end=sz;
 if(po>co&&po<end)end=po;if(pv>co&&pv<end)end=pv;ColWorld W;if(colInit(&W,d+co,end-co))return 2;
 f=fopen(argv[2],"r");if(!f)return 2;int frames;float m[16],velocity[3],angular[3],localCM[3],inertia[6];
 if(fscanf(f,"%d",&frames)!=1||frames<1||frames>1200)return 2;
 float*groups[]={m,velocity,angular,localCM,inertia};int lengths[]={16,3,3,3,6};
 for(int i=0;i<5;i++)for(int j=0;j<lengths[i];j++)if(fscanf(f,"%f",&groups[i][j])!=1)return 2;
 int n;if(fscanf(f,"%d",&n)!=1||n<0||n>128)return 2;Write writes[128];
 for(int i=0;i<n;i++){Write*w=&writes[i];if(fscanf(f,"%d%d%d%d%f",&w->begin,&w->end,&w->field,&w->axis,&w->value)!=5)return 2;}
 fclose(f);CarParams p;carParamsFor("famil_v",&p);Car c;carInit(&c,&p,&W,m[12],m[13],-m[14],0);
 M3 R={v3(-m[0],-m[1],m[2]),v3(m[4],m[5],-m[6]),v3(m[8],m[9],-m[10])};mQuat(&R,c.q);quatNorm(c.q);
 V3 base=sub(v3(m[12],m[13],-m[14]),scl(R.U,carModelLift(&c,p.modelLift)));c.x=base.x;c.y=base.y;c.z=base.z;
 c.com[0]=-localCM[0];c.com[1]=localCM[1]+carModelLift(&c,p.modelLift);c.com[2]=localCM[2];
 c.w[0]=-angular[0];c.w[1]=-angular[1];c.w[2]=angular[2];
 V3 cv=add(v3(velocity[0],velocity[1],-velocity[2]),cross(v3(c.w[0],c.w[1],c.w[2]),mulM(&R,v3(-localCM[0],localCM[1],localCM[2]))));
 c.vel[0]=cv.x;c.vel[1]=cv.y;c.vel[2]=cv.z;inertia[1]*=-1;inertia[2]*=-1;tensorSet(&c,inertia);syncOut(&c);
 for(int fr=0;fr<=frames;fr++){
  if(fr){CarInput in={0};carUpdate(&c,&W,&in,.02f);}
  if(fr%2)continue;
  M3 Q=quatM(c.q);V3 model=add(v3(c.x,c.y,c.z),scl(Q.U,carModelLift(&c,p.modelLift)));
  V3 cm=add(v3(c.x,c.y,c.z),mulM(&Q,v3(c.com[0],c.com[1],c.com[2])));
  V3 mv=sub(v3(c.vel[0],c.vel[1],c.vel[2]),cross(v3(c.w[0],c.w[1],c.w[2]),sub(cm,model)));
  printf("%d %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %d %d\n",fr,model.x,model.y,model.z,cm.x,cm.y,cm.z,mv.x,mv.y,mv.z,c.bodyHit,c.wheels);
  // Native PINE writes happen after the sampled frame, on an even PAL counter
  float *coords[]={&c.x,&c.y,&c.z};
  for(int i=0;i<n;i++){Write*w=&writes[i];if(fr<w->begin||fr>w->end)continue;float value=w->axis==2?-w->value:w->value;
   if(w->field==0){float current=w->axis==0?cm.x:w->axis==1?cm.y:cm.z;*coords[w->axis]+=value-current;cm=v3(cm.x,cm.y,cm.z);if(w->axis==0)cm.x=value;else if(w->axis==1)cm.y=value;else cm.z=value;}
   else {
    // Native car_vel is the model-origin point velocity, not integrator COM velocity
    V3 lever=mulM(&Q,v3(c.com[0],c.com[1]-carModelLift(&c,p.modelLift),c.com[2]));
    V3 correction=cross(v3(c.w[0],c.w[1],c.w[2]),lever);
    c.vel[w->axis]=value+(w->axis==0?correction.x:w->axis==1?correction.y:correction.z);
   }
  }
  syncOut(&c);
 }
 colFree(&W);free(d);return 0;
}
