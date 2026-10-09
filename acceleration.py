"""Local GPU setup, bounded model reuse and transcript caching."""
import hashlib
import json
import os
from pathlib import Path
import sysconfig

DLL_HANDLES=[]
DLL_DIRECTORIES=set()
MODEL=None
MODEL_KEY=None

def enable_cuda_libraries():
    base=Path(sysconfig.get_paths()['purelib'])/'nvidia'
    for directory in base.glob('*/bin'):
        if str(directory) in DLL_DIRECTORIES:continue
        DLL_DIRECTORIES.add(str(directory))
        os.environ['PATH']=str(directory)+os.pathsep+os.environ.get('PATH','')
        if hasattr(os,'add_dll_directory'):DLL_HANDLES.append(os.add_dll_directory(str(directory)))

def cache_path(root,source,model,speed):
    p=Path(source).resolve();stat=p.stat()
    key=f'{p}|{stat.st_size}|{stat.st_mtime_ns}|{model}|{speed}|v2'
    folder=Path(root)/'.cache'/'transcripts';folder.mkdir(parents=True,exist_ok=True)
    return folder/(hashlib.sha256(key.encode()).hexdigest()+'.json')

def platform_captions(info,downloader):
    """Prefer English JSON3 captions; failures safely fall back to local speech."""
    try:
        for kind in ('subtitles','automatic_captions'):
            languages=info.get(kind) or {}
            key=next((k for k in ('en','en-orig','en-US','en-GB') if k in languages),None)
            if not key:continue
            track=next((x for x in languages[key] if x.get('ext')=='json3'),None)
            if not track:continue
            with downloader.urlopen(track['url']) as response:data=json.loads(response.read())
            result=[];seen=set()
            for e in data.get('events',[]):
                pieces=[x for x in e.get('segs',[]) if x.get('utf8','').strip()]
                if not pieces:continue
                start=e.get('tStartMs',0)/1000;end=start+e.get('dDurationMs',0)/1000
                if end<=start:continue
                text=' '.join(x['utf8'].strip() for x in pieces)
                if (start,text) in seen:continue
                seen.add((start,text));words=[]
                for i,piece in enumerate(pieces):
                    a=start+piece.get('tOffsetMs',0)/1000
                    b=start+pieces[i+1]['tOffsetMs']/1000 if i+1<len(pieces) and 'tOffsetMs' in pieces[i+1] else end
                    tokens=piece['utf8'].split();step=max(.01,b-a)/max(1,len(tokens))
                    words.extend(dict(start=a+j*step,end=min(end,a+(j+1)*step),word=w) for j,w in enumerate(tokens))
                result.append(dict(start=start,end=end,text=text,words=words))
            if result:return sorted(result,key=lambda s:s['start']),('YouTube English captions' if kind=='subtitles' else 'YouTube automatic English captions')
    except Exception:
        pass
    return None,None

def transcribe(wav,model_name,models_root,duration,mode,update):
    global MODEL,MODEL_KEY
    enable_cuda_libraries()
    import ctranslate2
    from faster_whisper import WhisperModel,BatchedInferencePipeline
    from hardware import detect
    hardware=detect()
    batch=hardware['batch_size']
    beam={'fast':1,'balanced':3,'quality':5}.get(mode,3)
    devices=['cuda','cpu'] if hardware['speech_device']=='cuda' else ['cpu']
    for device in devices:
        try:
            key=(model_name,device)
            if key!=MODEL_KEY:
                MODEL=None
                import gc;gc.collect()
                MODEL=WhisperModel(model_name,device=device,compute_type='float16' if device=='cuda' else 'int8',download_root=str(models_root),cpu_threads=hardware['cpu_threads'])
                MODEL_KEY=key
            update('Transcribing on NVIDIA GPU' if device=='cuda' else 'Transcribing on CPU',20)
            kwargs=dict(language='en',word_timestamps=True,vad_filter=True,beam_size=beam)
            if device=='cuda':stream,_=BatchedInferencePipeline(MODEL).transcribe(str(wav),batch_size=batch,**kwargs)
            else:stream,_=MODEL.transcribe(str(wav),**kwargs)
            segments=[]
            for s in stream:
                segments.append(dict(start=s.start,end=s.end,text=s.text,words=[dict(start=w.start,end=w.end,word=w.word) for w in (s.words or [])]))
                update(f"{'GPU' if device=='cuda' else 'CPU'} transcription · {min(100,int(s.end/duration*100))}%",20+min(45,int(s.end/duration*45)))
            return segments,(f'NVIDIA GPU · float16 · batch {batch}' if device=='cuda' else 'CPU · int8')
        except Exception:
            MODEL=None;MODEL_KEY=None
            if device=='cpu':raise
            update('GPU transcription unavailable; using CPU fallback',20)
