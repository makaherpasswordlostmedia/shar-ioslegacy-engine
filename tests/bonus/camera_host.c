#include "bonus.h"
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
int main(int argc,char **argv){
 if(argc!=2)return 2;FILE*f=fopen(argv[1],"rb");if(!f)return 2;fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);void*p=malloc(n);if(!p||fread(p,1,n,f)!=(size_t)n)return 2;fclose(f);
 BnsTrack t;if(bnsParse(&t,p,n))return 2;float fv=2*atanf(tanf(t.h->fov*.5f)*.75f)*180/3.14159265f,zn=1,zf=1000,e[3],a[3],u[3],d;
 brTopLens(&t,&fv,&zn,&zf);brTopCam(&t,fv,480.f/272.f,e,a,u,&d);
 printf("{\"eye\":[%.9g,%.9g,%.9g],\"target\":[%.9g,%.9g,%.9g],\"up\":[%.9g,%.9g,%.9g],\"vertical_fov_deg\":%.9g,\"near_parameter\":%.9g,\"far_parameter\":%.9g,\"distance_eye_target\":%.9g}\n",e[0],e[1],e[2],a[0],a[1],a[2],u[0],u[1],u[2],fv,zn,zf,d);free(p);return 0;
}
