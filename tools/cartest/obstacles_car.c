/* Host-only observation of the exact wheel collider used by carUpdate.
   Including car.c keeps wheel pose/radius logic identical; no runtime edits. */
#include "../../viewer/car.c"
int sandboxWheelContacts(const Car*c,const ColWorld*w,ColSphereContact*out,int max){
 M3 m=quatM(c->q);V3 pos=v3(c->x,c->y,c->z);int count=0;
 for(int i=0;i<4&&count<max;i++){float r;V3 local=wheelColliderLocal(c,i,&r);V3 p=add(pos,mulM(&m,local));float xyz[3]={p.x,p.y,p.z};count+=colWheelWallContacts(w,xyz,r+.015f,out+count,max-count);}
 return count;
}
