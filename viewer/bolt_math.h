#ifndef BOLT_MATH_H
#define BOLT_MATH_H
#include <math.h>
// Earliest intersection of a segment with a moving, vertical capsule.
// Relative motion is linear over one simulation step. No sampling/tunnelling.
static float boltCapsule(const float a[3], const float b[3], const float old[3], const float now[3],
                         float radius, float height, float boltRadius) {
  float x=a[0]-old[0], y=a[1]-old[1], z=a[2]-old[2];
  float vx=b[0]-now[0]-x, vy=b[1]-now[1]-y, vz=b[2]-now[2]-z;
  float cuts[4]={0,1,0,0}; int n=2;
  if (fabsf(vy)>1e-8f) for(int k=0;k<2;k++) {
    float t=((k ? height-radius : radius)-y)/vy;
    if(t>0 && t<1) cuts[n++]=t;
  }
  for(int i=0;i<n;i++) for(int j=i+1;j<n;j++) if(cuts[j]<cuts[i]) {float t=cuts[i];cuts[i]=cuts[j];cuts[j]=t;}
  float R=radius+boltRadius;
  for(int i=0;i<n-1;i++) {
    float lo=cuts[i], hi=cuts[i+1], ym=y+vy*(lo+hi)*.5f;
    float dy=ym<radius ? y-radius : ym>height-radius ? y-height+radius : 0;
    float ddy=(ym<radius || ym>height-radius) ? vy : 0;
    float A=vx*vx+vz*vz+ddy*ddy, B=2*(x*vx+z*vz+dy*ddy), C=x*x+z*z+dy*dy-R*R;
    if((A*lo+B)*lo+C<=0) return lo;
    if(A>1e-12f) {
      float D=B*B-4*A*C;
      if(D>=0) {float t=(-B-sqrtf(D))/(2*A);if(t>=lo && t<=hi) return t;}
    }
  }
  return 2.f;
}
#endif
