// Frozen observer poses/pad sequence, actual carUpdate/col; no PS2 process
#include <stdio.h>
#include <stdlib.h>
#include "../../viewer/car.c"
int main(int argc,char **argv){
 if(argc!=3)return 2;FILE*f=fopen(argv[1],"rb");if(!f)return 2;
 fseek(f,0,SEEK_END);long sz=ftell(f);rewind(f);unsigned char*d=malloc(sz);
 if(!d||fread(d,1,sz,f)!=(size_t)sz)return 2;fclose(f);
 unsigned co,po,pv;memcpy(&co,d+92,4);memcpy(&po,d+96,4);memcpy(&pv,d+88,4);unsigned end=sz;
 if(po>co&&po<end)end=po;if(pv>co&&pv<end)end=pv;
 ColWorld W;if(colInit(&W,d+co,end-co))return 2;
 f=fopen(argv[2],"r");if(!f)return 2;char id[96];int frames,seg;
 while(fscanf(f,"%95s%d%d",id,&frames,&seg)==3){
  if(frames<1||frames>400||seg<0||seg>=(int)W.nseg)return 2;
  float m[16],v[3],cm[3];float*gr[]={m,v,cm};int lens[]={16,3,3};
  for(int i=0;i<3;i++)for(int k=0;k<lens[i];k++)if(fscanf(f,"%f",&gr[i][k])!=1)return 2;
  int input[401];for(int i=1;i<=frames;i++)if(fscanf(f,"%d",&input[i])!=1)return 2;
  CarParams p;carParamsFor("famil_v",&p);Car c;carInit(&c,&p,&W,m[12],m[13],-m[14],0);
  M3 R={v3(-m[0],-m[1],m[2]),v3(m[4],m[5],-m[6]),v3(m[8],m[9],-m[10])};mQuat(&R,c.q);quatNorm(c.q);
  V3 base=sub(v3(m[12],m[13],-m[14]),scl(R.U,carModelLift(&c,p.modelLift)));
  c.x=base.x;c.y=base.y;c.z=base.z;c.com[0]=-cm[0];c.com[1]=cm[1]+carModelLift(&c,p.modelLift);c.com[2]=cm[2];
  c.vel[0]=v[0];c.vel[1]=v[1];c.vel[2]=-v[2];syncOut(&c);
  const ColSeg*s=&W.seg[seg];float minside=1e9f,maxv=0;
  for(int i=1;i<=frames;i++){
   CarInput in={0};in.throttle=input[i];carUpdate(&c,&W,&in,.02f);
   float side=(c.x-s->a[0])*s->n[0]+(c.z-s->a[1])*s->n[1];if(side<minside)minside=side;
   if(i<=4)maxv=fmaxf(maxv,hypotf(c.vel[0],c.vel[2])*3.6f);
  }
  printf("%s %.9g %.9g %.9g %.9g %.9g %.9g\n",id,c.x,c.y,c.z,hypotf(c.vel[0],c.vel[2])*3.6f,minside,maxv);
 }
 fclose(f);colFree(&W);free(d);return 0;
}
