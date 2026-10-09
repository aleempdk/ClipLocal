"""Lossless audio preparation and measured loudness normalization."""
import json
import math
import re
import subprocess
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=1)
def gpu_encoder_available():
    try:
        result=subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=s=1280x720:r=30:d=0.1','-c:v','h264_nvenc','-f','null','-'],capture_output=True,timeout=20)
        return result.returncode==0
    except (OSError,subprocess.TimeoutExpired):return False

def encoder_args(mode='balanced'):
    from hardware import detect
    report=detect()
    selected=report['encoder']
    if selected=='h264_nvenc':
        return ['-c:v','h264_nvenc','-preset','p4' if mode=='fast' else 'p5','-tune','hq','-rc','vbr','-cq','18','-b:v','0'],'NVIDIA H.264 CQ 18'
    if selected=='h264_qsv':
        return ['-c:v','h264_qsv','-preset','fast' if mode=='fast' else 'medium','-global_quality','18'],'Intel Quick Sync H.264 quality 18'
    if selected=='h264_amf':
        return ['-c:v','h264_amf','-quality','speed' if mode=='fast' else 'quality','-rc','cqp','-qp_i','18','-qp_p','18'],'AMD AMF H.264 QP 18'
    return ['-c:v','libx264','-threads',str(report['cpu_threads']),'-preset',{'fast':'veryfast','balanced':'fast','quality':'medium'}.get(mode,'fast'),'-crf','18'],'CPU H.264 CRF 18'

def prepare_audio(source, folder, stem, start, duration, ranges, effects=None, denoise=False):
    from engine import run
    folder=Path(folder)
    output=folder/(stem+'.mix.wav')
    inputs=['-ss',start,'-i',str(Path(source).resolve())]
    graph=[]
    if ranges:
        for i,(a,b) in enumerate(ranges):
            graph.append(f'[0:a]atrim=start={a-start}:end={b-start},asetpts=PTS-STARTPTS[a{i}]')
        graph.append(''.join(f'[a{i}]' for i in range(len(ranges)))+f'concat=n={len(ranges)}:v=0:a=1[cut]')
        audio='[cut]'
    else:audio='[0:a]'
    cleanup='highpass=f=70,afftdn=nf=-25,' if denoise else ''
    if effects:
        inputs+=['-i',str(Path(effects).resolve())]
        graph.append(f'{audio}{cleanup}asplit=2[voice][side]')
        graph.append('[1:a][side]sidechaincompress=threshold=0.025:ratio=8:attack=5:release=120[ducked]')
        graph.append('[voice][ducked]amix=inputs=2:duration=first:normalize=0[mix]')
    else:graph.append(f'{audio}{cleanup}anull[mix]')
    graphfile=folder/(stem+'.audio-filter.txt')
    graphfile.write_text(';'.join(graph),encoding='utf-8')
    run(['ffmpeg','-v','error','-y',*inputs,'-t',duration,'-filter_complex_script',graphfile,'-map','[mix]',
         '-c:a','pcm_f32le','-ar','48000',output])
    measured=subprocess.run(['ffmpeg','-hide_banner','-i',str(output),'-af','loudnorm=I=-16:TP=-2:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if measured.returncode:raise RuntimeError(measured.stderr[-2000:])
    matches=re.findall(r'\{\s*"input_i"[\s\S]*?\}',measured.stderr)
    if not matches:raise RuntimeError('Could not measure source audio loudness')
    info=json.loads(matches[-1])
    if all(math.isfinite(float(info[k])) for k in ('input_i','input_tp','input_lra','input_thresh','target_offset')):
        normalize=('loudnorm=I=-16:TP=-2:LRA=11:linear=true:'
                   f"measured_I={info['input_i']}:measured_TP={info['input_tp']}:measured_LRA={info['input_lra']}:"
                   f"measured_thresh={info['input_thresh']}:offset={info['target_offset']}")
    else:
        # Silence needs no gain; avoid non-finite values in loudnorm options.
        normalize='anull'
    return output,normalize,info
