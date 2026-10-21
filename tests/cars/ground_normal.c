// Земля порта под точками (x y z движка из stdin): есть ли опора, нормаль, высота. Для tools/twins/attitude_ref.py (крен PS2 относительно земли)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "col.h"
int main(int argc,char**argv){FILE*f=fopen(argv[1],"rb");fseek(f,0,SEEK_END);long size=ftell(f);rewind(f);unsigned char*d=aligned_alloc(16,(size+15)&~15L);fread(d,1,size,f);fclose(f);
 unsigned co,po,pv;memcpy(&co,d+92,4);memcpy(&po,d+96,4);memcpy(&pv,d+88,4);unsigned end=size;if(po>co&&po<end)end=po;if(pv>co&&pv<end)end=pv;ColWorld W;if(colInit(&W,d+co,end-co))return 2;
 float x,y,z;while(scanf("%f %f %f",&x,&y,&z)==3){float gy,n[3]={0,1,0};int ok=colGround(&W,x,z,y+1.f,y-3.f,&gy,n);printf("%d %.4f %.4f %.4f %.3f\n",ok,n[0],n[1],n[2],gy);}
}
