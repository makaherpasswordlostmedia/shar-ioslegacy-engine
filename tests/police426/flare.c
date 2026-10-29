#include <stdio.h>
#include <stdlib.h>
#include "../../viewer/police_fx.c"
int main(int argc,char **argv){
 if(argc!=2)return 2;FILE *f=fopen(argv[1],"wb");if(!f)return 2;fwrite(pfTexture,1,sizeof pfTexture,f);fclose(f);
 McCar c={0};c.on=c.police=1;strcpy(c.name,"cPolice");c.car.q[0]=1;float eye[3]={0,3,10};PfQuad q[4];
 for(int i=0;i<84;i++){
  float t=i/(24.f*2);int n=policeFxQuads(&c,t,eye,q);printf("F %d %d\n",i,n);
  for(int j=0;j<n;j++){
   printf("Q %d %d %08x",i,q[j].flare,q[j].v[0].color);
   for(int k=0;k<6;k++)printf(" %.9g %.9g %.9g %.9g %.9g",q[j].v[k].u,q[j].v[k].v,q[j].v[k].x,q[j].v[k].y,q[j].v[k].z);
   puts("");
  }
 }
 c.police=0;if(policeFxQuads(&c,0,eye,q))return 1;c.police=1;c.car.destroyed=1;if(policeFxQuads(&c,0,eye,q))return 1;
 c.car.destroyed=0;strcpy(c.name,"cHears");if(policeFxQuads(&c,0,eye,q))return 1;return 0;
}
