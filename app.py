import json
import os
from pathlib import Path
import secrets
import re
import threading
import time
import uuid
import math
from concurrent.futures import ThreadPoolExecutor
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from engine import ROOT, process, reedit, resume_exports
import preferences
import hardware
from editing import metadata,write_metadata,bundle

TOKEN = secrets.token_urlsafe(32)
JOBS = {}
LOCK = threading.Lock()
RUNS = ROOT/'clips'
RUNS.mkdir(exist_ok=True)
QUEUE=ThreadPoolExecutor(max_workers=1)
PRESETS=ROOT/'presets.json'

def settings(config):
    config=dict(config)
    defaults=dict(count=3,length=45,model='base.en',layout='follow',style='spotlight',sound='subtle',aspect='9:16',resolution=1080,position=.5,color='#ffff00',brand='',hook='',topic='',denoise=False,pauses=False,fillers=False,learn=True,caption_size='large',motion='off',sound_density='regular',decorations='auto')
    for k,v in defaults.items():config.setdefault(k,v)
    for name in ('count','length','resolution'):config[name]=int(config[name])
    if not 1<=config['count']<=10 or config['length'] not in (30,45,60,90):raise ValueError('Invalid count or duration')
    config.setdefault('speed','balanced')
    config.setdefault('transcript_source','auto')
    choices=dict(model=('base.en','small.en'),layout=('fit','crop','follow'),motion=('off','gentle','dynamic'),sound_density=('sparse','regular'),decorations=('off','auto','bubbles','stickers'),style=('classic','punch','karaoke','bold','minimal','boxed','podcast','spotlight','neon','editorial','comic','kinetic','cinema'),sound=('off','subtle','cinematic','digital','punchy'),caption_size=('medium','large','xl'),aspect=('9:16','1:1','16:9'),resolution=(720,1080),speed=('fast','balanced','quality'),transcript_source=('auto','local'))
    for key,values in choices.items():
        if config[key] not in values:raise ValueError('Invalid '+key)
    config['position']=float(config['position'])
    if not math.isfinite(config['position']) or not 0<=config['position']<=1:raise ValueError('Invalid crop position')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',config['color']):raise ValueError('Invalid caption color')
    for key,limit in [('hook',100),('brand',50),('topic',200)]:
        if not isinstance(config[key],str) or len(config[key])>limit:raise ValueError('Invalid '+key)
    for key in ('denoise','pauses','fillers','learn'):
        if not isinstance(config[key],bool):raise ValueError('Invalid '+key)
    for key in ('manual_start','manual_end'):
        if config.get(key) in ('',None):config.pop(key,None)
        else:
            config[key]=float(config[key])
            if not math.isfinite(config[key]) or config[key]<0:raise ValueError('Invalid manual range')
    return config

def job_folder(name):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',name):raise ValueError('Invalid project')
    folder=RUNS/name
    if not folder.is_dir():raise ValueError('Project not found')
    return folder

def metadata_clip(job,file):
    folder=job_folder(job)
    clips=json.loads((folder/'clips.json').read_text(encoding='utf-8'))
    clip=next((c for c in clips if c['file']==file),None)
    if clip is None:raise ValueError('Clip not found')
    saved=folder/(Path(file).stem+'.youtube.json')
    info=json.loads(saved.read_text(encoding='utf-8')) if saved.exists() else metadata(clip.get('text',''))
    return folder,clips,clip,info

def enqueue(config,parent=None,edits=None):
    job=time.strftime('%Y%m%d-%H%M%S-')+uuid.uuid4().hex[:6]
    (RUNS/job).mkdir()
    with LOCK:JOBS[job]=dict(state='queued',message='Queued',progress=0,clips=[])
    QUEUE.submit(work,job,config,parent,edits)
    return job

def work(job, config, parent=None, edits=None):
    def update(message, progress):
        with LOCK:
            JOBS[job].update(message=message, progress=progress)
    try:
        with LOCK:JOBS[job].update(state='running')
        result = resume_exports(RUNS/job,update) if config.get('_resume') else (reedit(parent,RUNS/job,edits,update) if parent else process(config, RUNS/job, update))
        with LOCK:
            JOBS[job].update(state='done', clips=result)
    except Exception as error:
        with LOCK:
            JOBS[job].update(state='error', message=str(error))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, data, status=200, mime='application/json'):
        content = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(content)

    def send_file(self, file):
        size = file.stat().st_size
        start, end = 0, size-1
        partial = self.headers.get('Range')
        if partial:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', partial)
            if not match or not any(match.groups()):
                return self.send({'error':'Invalid range'},416)
            a, b = match.groups()
            if a:
                start, end = int(a), min(int(b),end) if b else end
            else:
                start = max(0,size-int(b))
            if start > end or start >= size:
                return self.send({'error':'Invalid range'},416)
        self.send_response(206 if partial else 200)
        self.send_header('Content-Type',{'.mp4':'video/mp4','.jpg':'image/jpeg','.json':'application/json','.zip':'application/zip'}.get(file.suffix,'application/octet-stream'))
        self.send_header('Content-Length',str(end-start+1))
        self.send_header('Accept-Ranges','bytes')
        self.send_header('X-Content-Type-Options','nosniff')
        if partial:
            self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        try:
            with file.open('rb') as stream:
                stream.seek(start)
                remaining = end-start+1
                while remaining:
                    chunk = stream.read(min(65536,remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (ConnectionAbortedError,ConnectionResetError,BrokenPipeError):
            pass

    def do_GET(self):
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
            return self.send({'error':'Invalid host'},403)
        path = urlparse(self.path).path
        if path == '/':
            return self.send((ROOT/'index.html').read_text(encoding='utf-8').replace('__TOKEN__', TOKEN).encode(), mime='text/html; charset=utf-8')
        if path == '/api/jobs':
            with LOCK:
                return self.send(JOBS)
        if path == '/api/hardware':return self.send(hardware.detect())
        if path.startswith('/api/metadata/'):
            try:
                parts=path.split('/')
                _,_,_,info=metadata_clip(parts[-2],parts[-1])
                return self.send(info)
            except (ValueError,OSError,IndexError):return self.send({'error':'Metadata unavailable'},404)
        if path == '/api/feedback':
            with preferences.LOCK: data=preferences.read()
            return self.send({key:value['rating'] for key,value in data.items()})
        if path == '/api/presets':
            return self.send(json.loads(PRESETS.read_text(encoding='utf-8')) if PRESETS.exists() else {})
        if path.startswith('/api/project/'):
            try:
                folder=job_folder(path.split('/')[-1])
                project=json.loads((folder/'project.json').read_text(encoding='utf-8'))
                transcript=json.loads((folder/'transcript.json').read_text(encoding='utf-8'))
                return self.send(dict(duration=project['duration'],config=project['config'],segments=transcript))
            except (ValueError,OSError):return self.send({'error':'Project is not ready for editing'},404)
        if path.startswith('/clips/'):
            file = (ROOT/path.lstrip('/')).resolve()
            if not file.is_relative_to(RUNS.resolve()) or file.suffix not in ('.mp4','.srt','.json','.vtt','.ass','.jpg','.zip','.txt') or not file.is_file() or file.name=='project.json':
                return self.send({'error':'Not found'},404)
            return self.send_file(file)
        self.send({'error':'Not found'},404)

    def do_POST(self):
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
            return self.send({'error':'Invalid host'},403)
        if self.headers.get('X-ClipLocal-Token') != TOKEN:
            return self.send({'error':'Reload ClipLocal and try again'},403)
        try:
            size = int(self.headers.get('Content-Length','0'))
            if self.path=='/api/upload':
                if not 0<size<=2*1024**3:raise ValueError('Upload a video up to 2 GB, or use a local file path for larger files')
                suffix=Path(self.headers.get('X-Filename','video.mp4')).suffix.lower()
                if suffix not in ('.mp4','.mov','.mkv','.webm','.avi','.m4v'):raise ValueError('Unsupported video file type')
                uploads=ROOT/'uploads';uploads.mkdir(exist_ok=True)
                file=uploads/(uuid.uuid4().hex+suffix)
                self.connection.settimeout(120)
                try:
                    with file.open('wb') as stream:
                        remaining=size
                        while remaining:
                            chunk=self.rfile.read(min(1024*1024,remaining))
                            if not chunk:raise ValueError('Upload interrupted')
                            stream.write(chunk);remaining-=len(chunk)
                except Exception:
                    file.unlink(missing_ok=True)
                    raise
                return self.send({'source':str(file)},201)
            if size<0 or size > 2000000:
                raise ValueError('Request too large')
            config = json.loads(self.rfile.read(size))
            if self.path=='/api/hardware':return self.send(hardware.detect(force=True))
            if self.path=='/api/metadata':
                folder,clips,clip,_=metadata_clip(config['job'],config['file'])
                info=config['metadata']
                for key,limit in [('title',100),('description',5000),('hashtags',300)]:
                    if not isinstance(info.get(key),str) or len(info[key])>limit:raise ValueError('Invalid '+key)
                if not info['title'].strip():raise ValueError('Enter a title')
                if not isinstance(info.get('tags'),list) or any(not isinstance(t,str) or len(t)>80 for t in info['tags']):raise ValueError('Invalid tags')
                if len(', '.join(info['tags']))>500:raise ValueError('Keep tags under 500 characters')
                info={key:info[key] for key in ('title','description','hashtags','tags')}
                with LOCK:
                    write_metadata(folder,Path(clip['file']).stem,info)
                    clip.update(info)
                    (folder/'clips.json').write_text(json.dumps(clips,indent=2),encoding='utf-8')
                    if folder.name in JOBS:JOBS[folder.name]['clips']=clips
                bundle(folder)
                return self.send({'saved':True})
            if self.path=='/api/feedback':
                folder=job_folder(config['job'])
                clips=json.loads((folder/'clips.json').read_text(encoding='utf-8'))
                clip=next((c for c in clips if c['file']==config.get('file')),None)
                if clip is None:raise ValueError('Clip not found')
                return self.send(preferences.save(folder.name,clip,config.get('rating')))
            if self.path=='/api/presets':
                name=config.get('name','').strip()
                if not 1<=len(name)<=60:raise ValueError('Enter a preset name up to 60 characters')
                saved=settings(config.get('settings',{}))
                for key in ('source','manual_start','manual_end','topic','hook'):saved.pop(key,None)
                data=json.loads(PRESETS.read_text(encoding='utf-8')) if PRESETS.exists() else {}
                data[name]=saved
                PRESETS.write_text(json.dumps(data,indent=2),encoding='utf-8')
                return self.send({'saved':name})
            if self.path.startswith('/api/edit/'):
                parent=job_folder(self.path.split('/')[-1])
                project=json.loads((parent/'project.json').read_text(encoding='utf-8'))
                start,end=float(config['start']),float(config['end'])
                if not math.isfinite(start) or not math.isfinite(end) or not 0<=start<end<=project['duration']:raise ValueError('Invalid time range')
                config['settings']=settings(project['config']|config.get('settings',{}))
                if not isinstance(config.get('corrections',{}),dict):raise ValueError('Invalid corrections')
                for key,value in config.get('corrections',{}).items():
                    int(key)
                    if not isinstance(value,str) or not value.strip() or len(value)>5000:raise ValueError('Invalid caption correction')
                return self.send({'id':enqueue({},parent,config)},202)
            if self.path != '/api/jobs':return self.send({'error':'Not found'},404)
            if not isinstance(config.get('source'),str) or not config['source'].strip():
                raise ValueError('Enter a video URL or local file path')
            self.send({'id':enqueue(settings(config))},202)
        except (ValueError,TypeError,KeyError,OSError) as error:
            self.send({'error':str(error)},400)

if __name__ == '__main__':
    hardware.detect()
    for folder in sorted(RUNS.iterdir(),key=lambda f:f.stat().st_mtime):
        if (folder/'clips.json').exists():
            clips=json.loads((folder/'clips.json').read_text(encoding='utf-8'))
            changed=False
            for clip in clips:
                if 'file' not in clip:continue
                stem=Path(clip['file']).stem
                if not (folder/(stem+'.youtube.json')).exists():
                    info=metadata(clip.get('text',''));write_metadata(folder,stem,info);clip.update(info);changed=True
            if changed:
                (folder/'clips.json').write_text(json.dumps(clips,indent=2),encoding='utf-8')
                bundle(folder)
            JOBS[folder.name] = dict(state='done',message='Saved clips',progress=100,clips=clips)
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--resume')
    args=parser.parse_args()
    if args.resume:
        job_folder(args.resume)
        JOBS[args.resume]=dict(state='queued',message='Resuming saved transcript',progress=65,clips=[])
        QUEUE.submit(work,args.resume,{'_resume':True})
    server = ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    (ROOT/'server.pid').write_text(str(os.getpid()))
    url = f'http://127.0.0.1:{server.server_port}'
    (ROOT/'running-url.txt').write_text(url)
    print(f'ClipLocal is running at {url}\nKeep this process running while editing.', flush=True)
    if '--no-browser' not in __import__('sys').argv:
        webbrowser.open(url)
    server.serve_forever()
