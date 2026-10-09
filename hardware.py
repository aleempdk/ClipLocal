"""Startup capability checks and measured local encoder selection."""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import threading
import time

ROOT=Path(__file__).resolve().parent
REPORT=None
LOCK=threading.Lock()

def configure_paths():
    candidates=[ROOT/'tools'/'bin',Path('C:/ffmpeg/bin')]
    local=os.environ.get('LOCALAPPDATA')
    if local:
        packages=Path(local)/'Microsoft'/'WinGet'/'Packages'
        if packages.exists():
            candidates+=list(packages.glob('Gyan.FFmpeg*/**/bin'))
    for path in candidates:
        if (path/'ffmpeg.exe').is_file() or (path/'ffmpeg').is_file():
            value=str(path)
            if value not in os.environ.get('PATH','').split(os.pathsep):os.environ['PATH']=value+os.pathsep+os.environ.get('PATH','')

def execute(args,timeout=15):
    return subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)

def detect(force=False):
    global REPORT
    with LOCK:
        if REPORT is not None and not force:return REPORT
        configure_paths()
        threads=min(8,max(1,(os.cpu_count() or 4)//2))
        result=dict(os=platform.system(),cpu=platform.processor() or platform.machine(),logical_cpus=os.cpu_count() or 1,
                    cpu_threads=threads,ffmpeg=shutil.which('ffmpeg'),ffprobe=shutil.which('ffprobe'),node=shutil.which('node'),
                    gpu=[],encoders=[],encoder='libx264',speech_device='cpu',speech_compute='int8',batch_size=1,warnings=[])
        try:
            smi=execute(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'])
            for line in smi.stdout.splitlines():
                parts=line.rsplit(',',2)
                if len(parts)==3:result['gpu'].append(dict(name=parts[0].strip(),memory_mb=int(parts[1]),free_mb=int(parts[2])))
        except (OSError,ValueError,subprocess.TimeoutExpired):pass
        if result['ffmpeg']:
            try:
                available=execute(['ffmpeg','-hide_banner','-encoders']).stdout
                for encoder in ('h264_nvenc','h264_qsv','h264_amf','libx264'):
                    if encoder not in available:continue
                    extra={'h264_nvenc':['-preset','p5','-rc','vbr','-cq','18','-b:v','0'],
                           'h264_qsv':['-preset','medium','-global_quality','18'],
                           'h264_amf':['-quality','quality','-rc','cqp','-qp_i','18','-qp_p','18'],
                           'libx264':['-preset','fast','-crf','18','-threads',str(threads)]}[encoder]
                    started=time.perf_counter()
                    try:
                        test=execute(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=1080x1920:r=30:d=2',
                                      '-pix_fmt','yuv420p','-c:v',encoder,*extra,'-f','null','-'],12)
                        if test.returncode==0:result['encoders'].append(dict(name=encoder,benchmark_seconds=round(time.perf_counter()-started,3)))
                    except (OSError,subprocess.TimeoutExpired):pass
                if result['encoders']:
                    result['encoder']=min(result['encoders'],key=lambda e:e['benchmark_seconds'])['name']
            except (OSError,subprocess.TimeoutExpired) as error:result['warnings'].append('Encoder check unavailable: '+str(error))
        else:result['warnings'].append('FFmpeg is missing. Run Setup ClipLocal.cmd.')
        if not result['ffprobe']:result['warnings'].append('FFprobe is missing. Run Setup ClipLocal.cmd.')
        try:
            from acceleration import enable_cuda_libraries
            enable_cuda_libraries()
            import ctranslate2
            import sysconfig
            pure=Path(sysconfig.get_paths()['purelib'])
            libraries=all(list((pure/'nvidia').glob(pattern)) for pattern in ('cublas/bin/cublas64_12.dll','cudnn/bin/cudnn64_9.dll')) if os.name=='nt' else True
            if libraries and ctranslate2.get_cuda_device_count()>0 and 'float16' in ctranslate2.get_supported_compute_types('cuda'):
                free=result['gpu'][0]['free_mb'] if result['gpu'] else 2000
                result.update(speech_device='cuda',speech_compute='float16',batch_size=8 if free>=6000 else 4 if free>=3500 else 2)
            elif result['gpu']:result['warnings'].append('CUDA speech libraries unavailable; CPU speech will be used. Run Setup ClipLocal.cmd to install them.')
        except (ImportError,RuntimeError,OSError):pass
        result['speech_status']='Capability detected; transcription confirms availability at use time'
        result['selection_note']='Lowest elapsed time in a short 1080p balanced-quality encode check; real editing workloads may differ.'
        REPORT=result
        (ROOT/'hardware-report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        return result

if __name__=='__main__':
    report=detect(force=True)
    print(f"Video: {report['encoder']} | Speech: {report['speech_device']} / {report['speech_compute']} | CPU threads: {report['cpu_threads']}")
    for warning in report['warnings']:print(warning)
