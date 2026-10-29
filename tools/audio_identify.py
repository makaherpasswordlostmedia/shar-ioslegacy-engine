#!/usr/bin/env python3
"""Rank disc impacts by log-frequency spectrum, searching playback pitch.

Offline WAV/RSD only. --at is seconds in the WAV, not the absolute PS2 frame.
The result is a ranked hypothesis; it does not certify a mixed/noisy recording.
Example: audio_identify.py AUDIO.wav --at .72 --refs DISC/sound/soundfx/collisions
"""
import argparse
import json
import hashlib
from pathlib import Path
import sys
import wave
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audio_export as AE

RATE=22050
FREQ=np.geomspace(300,9000,192)


def read(path):
    path=Path(path)
    if path.suffix.lower()=='.rsd':
        x=AE.ffmpeg_decode(str(path),RATE).astype(float).mean(1)/32768
        return x
    with wave.open(str(path),'rb') as w:
        if w.getsampwidth()!=2:raise ValueError('WAV must be PCM16')
        x=np.frombuffer(w.readframes(w.getnframes()),'<i2').astype(float).reshape(-1,w.getnchannels()).mean(1)/32768
        rate=w.getframerate()
    return np.interp(np.arange(int(len(x)*RATE/rate))*rate/RATE,np.arange(len(x)),x)


def power(x):
    x=np.pad(x,(0,max(0,1024-len(x))))
    frames=np.lib.stride_tricks.sliding_window_view(x,1024)[::256]
    p=np.mean(abs(np.fft.rfft(frames*np.hanning(1024),axis=1))**2,axis=0)
    return np.interp(FREQ,np.fft.rfftfreq(1024,1/RATE),p)


def feature(p):
    # Spectral envelope after background subtraction; gain does not change ranking.
    a=np.log(np.maximum(p, max(np.max(p)*1e-5,1e-16)))
    a-=a.mean();length=np.linalg.norm(a)
    return a/length if length>1e-12 else np.zeros_like(a)


def rank(query, refs, background=None, pitch=True):
    p=power(query)
    if background is not None:p=np.maximum(p-power(background),0)
    q=feature(p);result=[]
    for name,x in refs.items():
        p=power(x[:int(.5*RATE)]);best=(-2,0)
        for semitone in np.arange(-6,6.001,.25) if pitch else [0]:
            shifted=np.interp(np.log(FREQ)-semitone*np.log(2)/12,np.log(FREQ),p)
            score=float(q@feature(shifted))
            if score>best[0]:best=(score,float(semitone))
        result.append(dict(clip=name,score=best[0],pitch_semitones=best[1]))
    return sorted(result,key=lambda x:-x['score'])


def cross_spectrum(query, refs, pitch=True):
    """Matched complex spectrum, with playback-rate search and normalized local energy.

    Phase is retained: an average envelope alone confuses metal/glass mixtures.
    This is a spectral matcher, not a claim of phase invariance.
    """
    length=int(.12*RATE)
    if len(query)<length:return []
    n=1<<(len(query)+length-1).bit_length()
    freq=np.fft.rfftfreq(n,1/RATE);keep=(freq>=1000)&(freq<=9000)
    def filtered(x):
        return np.fft.irfft(np.fft.rfft(x,n)*keep,n)[:len(x)]
    y=filtered(query);fy=np.fft.rfft(y,n)
    energy=np.convolve(y*y,np.ones(length),mode='valid')
    result=[]
    for name,x in refs.items():
        best=(-2.,1.,0)
        for factor in np.arange(.8,1.2001,.001) if pitch else [1.]:
            indices=np.arange(length)*factor
            z=np.interp(indices,np.arange(len(x)),x,left=0,right=0)
            z=filtered(z);den=np.sqrt(np.sum(z*z)*energy)+1e-12
            corr=np.fft.irfft(fy*np.conj(np.fft.rfft(z,n)),n)[:len(energy)]/den
            at=int(np.argmax(corr));value=float(corr[at])
            if value>best[0]:best=(value,float(factor),at)
        result.append(dict(clip=name,score=best[0],pitch_semitones=float(12*np.log2(best[1])),offset_s=best[2]/RATE))
    return sorted(result,key=lambda x:-x['score'])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('wav',type=Path);ap.add_argument('--at',type=float,required=True)
    ap.add_argument('--span',type=float,default=.5);ap.add_argument('--refs',type=Path,required=True)
    ap.add_argument('--out',type=Path);ap.add_argument('--old',action='store_true',help='negative: no pitch search')
    a=ap.parse_args();x=read(a.wav);i=int(a.at*RATE);j=i+int(a.span*RATE)
    if i<0 or j>len(x):ap.error('window outside recording; use WAV-relative seconds')
    refs={p.stem:read(p) for p in sorted(a.refs.glob('*.rsd'))}
    if not refs:ap.error('no RSD references')
    bg=x[max(0,i-int(.4*RATE)):max(0,i-int(.05*RATE))]
    result=cross_spectrum(x[i:j],refs,not a.old)
    obj=dict(wav=str(a.wav),wav_sha256=hashlib.sha256(a.wav.read_bytes()).hexdigest(),refs_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(a.refs.glob('*.rsd'))},start=a.at,span=a.span,reference_count=len(refs),kind='ranked hypothesis',top=result[:10])
    if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    for r in result[:5]:print(f'{r["score"]:.4f}  {r["pitch_semitones"]:+.2f} st  {r["clip"]}')
    return 0


if __name__=='__main__':raise SystemExit(main())
