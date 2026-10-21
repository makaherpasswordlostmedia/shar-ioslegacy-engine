#include <stdio.h>
#include <math.h>
#include <string.h>
#include "col.h"
static struct {ColHdr h;ColTri tri[2];ColBox box;ColCyl cyl;unsigned start[2],ref[4];} data;
static int bad,cases;
static void check(const char *label,int ok){cases++;if(!ok){printf("FAIL %s\n",label);bad++;}}
int main(void){
 memset(&data,0,sizeof data);memcpy(data.h.magic,"COL1",4);data.h.ox=data.h.oz=-20;data.h.cell=40;data.h.W=data.h.H=1;data.h.ntri=2;data.h.nbox=data.h.ncyl=1;data.h.nref=4;
 data.tri[0]=(ColTri){{0,-10,-10},{0,10,-10},{0,0,10},{1,0,0}};
 data.tri[1]=(ColTri){{-20,-5,-20},{20,-5,20},{20,-5,-20},{0,1,0}};
 data.box=(ColBox){{10,0,0},{1,0,0},{0,1,0},{0,0,1},{.25f,1,10},0};
 data.cyl=(ColCyl){{-10,0,0},{0,1,0},1,1,1,{0,0,0}};
 data.start[1]=4;data.ref[0]=0;data.ref[1]=1;data.ref[2]=1u<<29;data.ref[3]=2u<<29;
 ColWorld w;if(colInit(&w,&data,sizeof data))return 2;colHumpKeep(0,0);ColSphereContact c[4];int n;float p[3];
 p[0]=.2f;p[1]=p[2]=0;n=colWheelWallContacts(&w,p,.4f,c,4);check("triangle face",n==1&&fabsf(c[0].depth-.2f)<1e-6&&c[0].ref==0&&fabsf(c[0].n[0]-1)<1e-6);
 p[0]=10.5f;n=colWheelWallContacts(&w,p,.4f,c,4);check("box face",n==1&&fabsf(c[0].depth-.15f)<1e-6&&c[0].ref==(1u<<29));
 p[1]=1.1f;n=colWheelWallContacts(&w,p,.4f,c,4);float d=hypotf(.25f,.1f);check("box corner",n==1&&fabsf(c[0].depth-(.4f-d))<1e-6&&fabsf(c[0].n[1]-.1f/d)<1e-6);
 p[0]=-8.7f;p[1]=1.3f;n=colWheelWallContacts(&w,p,.4f,c,4);check("flat cylinder corner does not acquire a hemisphere",n==0);
 p[0]=-8.8f;p[1]=.5f;n=colWheelWallContacts(&w,p,.4f,c,4);check("flat cylinder side",n==1&&fabsf(c[0].depth-.2f)<1e-6&&fabsf(c[0].n[0]-1)<1e-6);
 p[0]=-10;p[1]=1.2f;n=colWheelWallContacts(&w,p,.4f,c,4);check("walkable crown is handled by suspension",n==0);
 data.cyl.halfLen=10;p[1]=0;n=colWheelWallContacts(&w,p,.4f,c,4);check("cylinder axis exits through the nearest side",n==1&&fabsf(c[0].depth-1.4f)<1e-6&&fabsf(c[0].n[1])<1e-6);data.cyl.halfLen=1;
 ColTri saved=data.tri[0];data.tri[0]=(ColTri){{0,-10,0},{0,0,0},{0,10,0},{1,0,0}};p[0]=.2f;p[1]=p[2]=0;n=colWheelWallContacts(&w,p,.4f,c,4);check("degenerate triangle uses its finite edges",n==1&&fabsf(c[0].depth-.2f)<1e-6&&isfinite(c[0].n[0]));data.tri[0]=saved;
 p[0]=0;p[1]=-5.1f;p[2]=15;n=colWheelWallContacts(&w,p,.4f,c,4);check("ground backface cannot push a tyre downward",n==0);
 // Open seam beside flat ground, tyre centre 0.15 m above it: the edge normal is walkable-side up
 // (ny .447, the J11-9 class: PS2 stop point needs these). COL_WHEEL_GROUND_FACE_OLD (e9558e0) drops it.
 p[0]=7.787868f;p[1]=-4.85f;p[2]=8.212132f;n=colWheelWallContacts(&w,p,.4f,c,4);
 check("open ground seam under a tyre is still support (J11-9)",n==1&&fabsf(c[0].n[1]-.447214f)<1e-4f&&c[0].ref==1);
 saved=data.tri[1];data.tri[1]=(ColTri){{-20,-9,-20},{20,-1,20},{20,-1,-20},{-.196116135f,.980580676f,0}};
 // Tyre centre just below the edge of inclined ground but in front of its face: the closest-point
 // normal points down (G, cyl570 ny -.206). Ground never pushes a tyre down; COL_WHEEL_GROUND_EDGE_OLD does.
 p[0]=7.787868f;p[1]=-3.43f;p[2]=8.212132f;n=colWheelWallContacts(&w,p,.4f,c,4);check("inclined ground edge cannot push a tyre down",n==0);data.tri[1]=saved;
 p[0]=10.5f;p[1]=p[2]=0;data.box.pad=1;colSetFoliagePass(1);n=colWheelWallContacts(&w,p,.4f,c,4);check("passable vegetation remains passable",n==0);
 colSetFoliagePass(0);data.cyl.r=0;p[0]=-10;n=colWheelWallContacts(&w,p,.4f,c,4);check("disabled radius is not a point obstacle",n==0);
 colFree(&w);printf("%s %d sphere/triangle/box/cylinder contact checks\n",bad?"FAIL":"PASS",cases);return !!bad;
}
