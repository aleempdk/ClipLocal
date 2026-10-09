"""Local face-guided reframing; no claim of audio/visual active-speaker recognition."""
import json
import math
from pathlib import Path
import subprocess
import cv2
import numpy as np

MODEL=Path(__file__).parent/'models/face_detection_yunet_2023mar.onnx'

def stable_plan(points, width, height, scaled_w, scaled_h, duration, fps):
    """Hold per shot, ignore jitter, ease only sustained movement. No cross-cut pan."""
    starts=[0]+[i for i,p in enumerate(points) if i and p[4]]+[len(points)]
    commands=[];shots=[];trajectory=[]
    for a,b in zip(starts,starts[1:]):
        shot=points[a:b];begin=shot[0][0];end=points[b][0] if b<len(points) else duration
        faces=[p for p in shot if p[3]]
        # Make one crop/wide decision per shot; intermittent misses cannot flash views.
        cropped=len(faces)>=max(2,math.ceil(len(shot)*.3))
        shots.append(dict(start=begin,end=end,cropped=cropped))
        initial=faces[:6] if faces else shot[:1]
        cx=float(np.median([p[1] for p in initial]));cy=float(np.median([p[2] for p in initial]))
        def position(x,y):
            return (max(0,min(scaled_w-width,x*scaled_w-width/2)),
                    max(0,min(scaled_h-height,y*scaled_h-height*.35)))
        current=np.array(position(cx,cy),dtype=float);target=current.copy()
        outside=0;history=[];last_sample=-1
        for frame in range(math.ceil(begin*fps),math.ceil(end*fps)):
            t=frame/fps;i=min(b-1,max(a,int(t*4)))
            p=points[i]
            if i!=last_sample:
                last_sample=i
                if p[3]:
                    history.append(position(p[1],p[2]));history=history[-5:]
                    desired=np.median(history,axis=0)
                    # The face may move inside this dead zone without moving the camera.
                    deviation=np.abs(desired-current)
                    outside=outside+1 if deviation[0]>width*.16 or deviation[1]>height*.10 else 0
                    if outside>=4:target=desired;outside=0
                else:outside=0  # Hold on short losses instead of chasing a new person.
            delta=target-current
            # Low-pass ease plus speed cap, in output pixels/second.
            step=delta*(1-math.exp(-1/(fps*1.3)))
            step=np.clip(step,[-width*.16/fps,-height*.10/fps],[width*.16/fps,height*.10/fps])
            current+=step
            x,y=(round(float(v)/2)*2 for v in current)
            commands.append(f'{t:.4f} crop@follow x {x}, crop@follow y {y};')
            trajectory.append([round(t,4),x,y])
    return commands,shots,trajectory

def follow(source, ranges, width, height, fps, dest):
    if not MODEL.exists(): raise ValueError('Face tracking model is missing. Choose Fill or Fit framing.')
    cap=cv2.VideoCapture(str(source))
    sw,sh=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    sample_w=640;sample_h=round(sh/sw*sample_w)//2*2
    detector=cv2.FaceDetectorYN.create(str(MODEL),'',(sample_w,sample_h),.75,.3,100)
    cv2.setNumThreads(4)
    first=ranges[0][0];end=ranges[-1][1]
    cuts=';'.join(f'[0:v]trim=start={a-first}:end={b-first},setpts=PTS-STARTPTS[c{i}]' for i,(a,b) in enumerate(ranges))
    cuts+=';'+''.join(f'[c{i}]' for i in range(len(ranges)))+f'concat=n={len(ranges)}:v=1:a=0,fps=4,scale={sample_w}:{sample_h}[v]'
    cmd=['ffmpeg','-v','error','-ss',str(first),'-t',str(end-first),'-i',str(source),'-filter_complex',cuts,'-map','[v]','-f','rawvideo','-pix_fmt','bgr24','pipe:1']
    proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    points=[];previous=None;center=None;missing=0
    try:
        while True:
            raw=proc.stdout.read(sample_w*sample_h*3)
            if not raw:break
            if len(raw)!=sample_w*sample_h*3:raise RuntimeError('Incomplete tracking frame')
            frame=np.frombuffer(raw,np.uint8).reshape(sample_h,sample_w,3)
            small=cv2.resize(frame,(32,18)).astype(float)
            cut=previous is not None and np.mean(np.abs(small-previous))>35
            if cut:center=None
            previous=small
            _,faces=detector.detect(frame)
            if faces is not None and len(faces):
                def score(f):
                    area=f[2]*f[3]
                    if center is None:return area
                    distance=abs((f[0]+f[2]/2)/sample_w-center[0])
                    return area/(1+5*distance)
                # Avoid jumping to a different distant face during an existing shot.
                nearby=[f for f in faces if center is None or abs((f[0]+f[2]/2)/sample_w-center[0])<.25]
                face=max(nearby or faces,key=score)
                target=((face[0]+face[2]/2)/sample_w,(face[1]+face[3]/2)/sample_h)
                if center is not None and not nearby:
                    missing+=1;visible=False
                    points.append((len(points)/4,*map(float,center),visible,bool(cut)))
                    continue
                center=target
                missing=0;visible=True
            else:
                missing+=1;visible=False
            points.append((len(points)/4,*map(float,center or (.5,.5)),bool(visible),bool(cut)))
    finally:
        proc.stdout.close()
        if proc.poll() is None:proc.terminate()
        proc.wait()
    if not points:raise RuntimeError('Could not decode video for face tracking')
    factor=max(width/sw,height/sh);scaled_w=math.ceil(sw*factor/2)*2;scaled_h=math.ceil(sh*factor/2)*2
    duration=sum(b-a for a,b in ranges)
    commands,shots,trajectory=stable_plan(points,width,height,scaled_w,scaled_h,duration,fps)
    command_file=Path(dest).with_suffix('.tracking.txt')
    command_file.write_text('\n'.join(commands),encoding='utf-8')
    enabled='+'.join(f'gte(t,{s["start"]:.3f})*lt(t,{s["end"]:.3f})' for s in shots if s['cropped']) or '0'
    graph=(f'[0:v]split=3[track][bg][fg];'
           f'[track]scale={scaled_w}:{scaled_h}:flags=lanczos,sendcmd=f={command_file.name},crop@follow={width}:{height}:0:0[tracked];'
           f'[bg]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur=20:2[back];'
           f'[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[front];'
           f'[back][front]overlay=(W-w)/2:(H-h)/2[wide];'
           f"[wide][tracked]overlay=0:0:enable='{enabled}',setsar=1[picture]")
    Path(dest).with_suffix('.framing.json').write_text(json.dumps(dict(method='Stable per-scene YuNet face framing',samples=len(points),face_samples=sum(p[3] for p in points),fallback='Wide framing chosen per scene',shots=shots,trajectory=trajectory,points=points),indent=2),encoding='utf-8')
    return graph
