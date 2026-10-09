"""Local English transcription, highlight selection, and captioned MP4 rendering."""
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from fractions import Fraction

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('HF_HOME', str(ROOT / 'models'))
from hardware import configure_paths
configure_paths()

def run(args, cwd=None):
    result = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError(result.stderr[-2500:] or result.stdout[-2500:])
    return result.stdout

def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path]))

def choose_clips(segments, length=45, count=3, topic='', learn=True):
    from preferences import weights, adjustment
    learned = weights() if learn else {}
    candidates = []
    hooks = re.compile(r'\b(why|how|secret|mistake|never|imagine|truth|realized|surprising|learned|problem|changed|actually|because)\b', re.I)
    for i, first in enumerate(segments):
        if i and i%3 and not re.search(r'[.!?][\s\"\u201d]*$', segments[i-1]['text']) and first['start']-segments[i-1]['end']<.4:
            continue
        group = []
        for segment in segments[i:]:
            if segment['end'] - first['start'] > length * 1.3:
                break
            group.append(segment)
            duration = segment['end'] - first['start']
            if duration >= length * .72 and re.search(r'[.!?][\s\"\u201d]*$', segment['text']):
                if duration >= length * .9:
                    break
        if not group:
            continue
        duration = group[-1]['end'] - first['start']
        if duration < min(12, length * .5):
            continue
        text = ' '.join(s['text'].strip() for s in group)
        opening = ' '.join(text.split()[:25])
        score = len(hooks.findall(opening)) * 2 + min(4, len(hooks.findall(text)))
        score += 2 if '?' in opening else 0
        score += 2 if re.search(r'\b(I|we|my)\b', text) else 0
        score -= 5 if re.search(r'\b(subscribe|sponsor|promo code|like and share)\b', text, re.I) else 0
        score -= abs(duration-length) / length * 3
        score -= 2 if re.match(r'\s*(and|but|so|he|she|they|it)\b', opening, re.I) else 0
        terms=re.findall(r'\w+',topic.lower())
        matches=sum(1 for term in terms if re.search(r'\b'+re.escape(term)+r'\b',text,re.I))
        if terms and not matches:continue
        score += matches*4
        bonus=adjustment(text,duration,learned)
        score += bonus
        reasons=[]
        if abs(bonus)>.05:reasons.append('Adjusted using your clip ratings')
        if hooks.search(opening):reasons.append('Hook language in opening')
        if '?' in text:reasons.append('Question-led passage')
        if matches:reasons.append('Matches requested topic')
        if not reasons:reasons.append('Complete spoken passage')
        candidates.append(dict(start=first['start'], end=group[-1]['end'], text=text, score=round(score, 2),reasons=reasons))
    selected = []
    for candidate in sorted(candidates, key=lambda c: c['score'], reverse=True):
        if all(candidate['end'] <= c['start'] or candidate['start'] >= c['end'] for c in selected):
            selected.append(candidate)
        if len(selected) >= count:
            break
    return selected

def stamp(seconds):
    ms = max(0, round(seconds * 1000))
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'

def captions(segments, start, end):
    from styles import join_words, timed_words
    cues = []
    words=timed_words(segments,start,end)
    groups=[];group=[]
    for word in words:
        if group and (len(group)>=6 or word['start']-group[-1]['end']>.5):
            groups.append(group);group=[]
        group.append(word)
        if re.search(r'[.!?]$',word['text']):groups.append(group);group=[]
    if group:groups.append(group)
    for group in groups:
        a,b=group[0]['start'],group[-1]['end']
        text=join_words(w['text'] for w in group).replace('-->','→')
        if b>a and text:cues.append(f'{len(cues)+1}\n{stamp(a)} --> {stamp(b)}\n{text}\n')
    return '\n'.join(cues)

def render(source, dest, clip, segments, layout='fit', style='classic', sound='off', hook='', options=None):
    options=options or {}
    resolution=int(options.get('resolution',1080))
    source_info=probe(source)
    video_info=next(s for s in source_info['streams'] if s['codec_type']=='video')
    try:
        fps=float(Fraction(video_info.get('avg_frame_rate','30/1')))
        if not math.isfinite(fps) or fps<=0:fps=30
    except (ValueError,ZeroDivisionError):fps=30
    fps=min(fps,60)
    ranges=options.get('_ranges')
    seek=ranges[0][0] if ranges else clip['start']
    duration=clip['end']-clip['start']
    aspect=options.get('aspect','9:16')
    width,height={'9:16':(resolution,resolution*16//9),'1:1':(resolution,resolution),'16:9':(resolution*16//9,resolution)}[aspect]
    width-=width%2;height-=height%2
    position=float(options.get('position',.5))
    dest = Path(dest).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    srt = dest.with_suffix('.srt')
    srt.write_text(captions(segments, clip['start'], clip['end']), encoding='utf-8')
    subtitle = f"subtitles={srt.name}:force_style='FontName=Arial,FontSize={dict(medium=22,large=28,xl=33).get(options.get('caption_size','large'),28)},Bold=1,Outline=2,Shadow=1,MarginV=42,Alignment=2'"
    accents = []
    mask=None
    if style != 'classic':
        from styles import write_punch_ass
        ass = dest.with_suffix('.ass')
        accents = write_punch_ass(ass,segments,clip['start'],clip['end'],hook,width,height,options.get('color','#ffff00'),options.get('brand',''),style,options.get('caption_size','large'),options.get('decorations','off'))
        subtitle=f'ass={ass.name}'
    if style == 'punch':
        # 720 x 940 picture card, black headline margin and rounded corners.
        card_height=round(height*(.735 if height>width else .76))//2*2
        top=round(height*.10)
        scaling = (f'scale={width}:{card_height}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{card_height}:(iw-ow)*{position}:(ih-oh)/2' if layout=='crop' else
                   f'scale={width}:{card_height}:force_original_aspect_ratio=decrease:flags=lanczos,pad={width}:{card_height}:(ow-iw)/2:(oh-ih)/2:black')
        from styles import rounded_mask
        mask=dest.with_suffix('.mask.pgm')
        rounded_mask(mask,width,card_height,round(width*.06))
        graph = (f'[0:v]{scaling},setsar=1,format=yuv420p[rawcard];[rawcard][2:v]alphamerge[card];'
                 f'color=c=black:s={width}x{height}:r={fps}[canvas];[canvas][card]overlay=0:{top}:shortest=1,ass={ass.name}[v]')
    elif layout == 'crop':
        graph = f'[0:v]scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{height}:(iw-ow)*{position}:(ih-oh)/2,setsar=1,{subtitle}[v]'
    else:
        graph = (f'[0:v]split=2[bg][fg];[bg]scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{height},boxblur=25:2[back];'
                 f'[fg]scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos[front];[back][front]overlay=(W-w)/2:(H-h)/2,setsar=1,{subtitle}[v]')
    motion=options.get('motion','off')
    motion_filter=''
    if motion!='off':
        amount=.035 if motion=='gentle' else .07
        motion_filter=f"zoompan=z='1+{amount}*pow(sin(on/{fps}/3),2)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps={fps},"
    if layout=='follow':
        from framing import follow
        graph=follow(source,ranges or [(seek,seek+duration)],width,height,fps,dest)+f';[picture]{motion_filter}{subtitle}[v]'
        if mask:mask.unlink(missing_ok=True)
        mask=None
    elif motion_filter:
        graph=graph.replace(subtitle+'[v]',motion_filter+subtitle+'[v]')
    if ranges:
        trims=[f'[0:v]trim=start={a-seek}:end={b-seek},setpts=PTS-STARTPTS[cut{i}]' for i,(a,b) in enumerate(ranges)]
        trims.append(''.join(f'[cut{i}]' for i in range(len(ranges)))+f'concat=n={len(ranges)}:v=1:a=0[edited]')
        graph=';'.join(trims)+';'+graph.replace('[0:v]','[edited]')
    effect=None
    if sound != 'off':
        from styles import synth_effects
        if not accents:
            accents = [dict(time=.06,kind='whoosh')]
        if options.get('sound_density','sparse')=='regular':
            # Supplement keyword accents with spaced cues throughout any type of video.
            for t in range(8,max(8,int(duration)-1),8):
                if all(abs(t-a['time'])>=3 for a in accents):accents.append(dict(time=t,kind='tap'))
        accents=sorted(accents,key=lambda a:a['time'])
        effect = dest.with_suffix('.effects.wav')
        synth_effects(effect,clip['end']-clip['start'],accents,sound)
    from quality import prepare_audio,encoder_args
    mix,normalization,audio_info=prepare_audio(source,dest.parent,dest.stem,seek,duration,ranges,effect,options.get('denoise',False))
    graphfile=dest.with_suffix('.video-filter.txt')
    graphfile.write_text(graph,encoding='utf-8')
    inputs=['-ss',seek,'-i',Path(source).resolve(),'-i',mix]
    if mask:inputs+=['-loop','1','-framerate',fps,'-i',mask]
    encoder,encoder_name=encoder_args(options.get('speed','balanced'))
    command=['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',*inputs,
         '-t',duration,'-filter_complex_script',graphfile,'-map','[v]','-map','1:a:0','-af',normalization,
         *encoder,'-pix_fmt','yuv420p','-r',fps,
         '-c:a','aac','-b:a','256k','-ar','48000','-movflags','+faststart',dest.name]
    try:run(command,cwd=dest.parent)
    except RuntimeError:
        if not any(e in encoder for e in ('h264_nvenc','h264_qsv','h264_amf')):raise
        first=command.index('-c:v');last=command.index('-pix_fmt')
        command[first:last]=['-c:v','libx264','-preset','fast','-crf','18']
        encoder_name='CPU H.264 CRF 18 (GPU fallback)'
        run(command,cwd=dest.parent)
    mix.unlink(missing_ok=True)
    graphfile.unlink(missing_ok=True)
    dest.with_suffix('.tracking.txt').unlink(missing_ok=True)
    dest.with_suffix('.audio-filter.txt').unlink(missing_ok=True)
    if effect:effect.unlink(missing_ok=True)
    if mask:mask.unlink(missing_ok=True)
    dest.with_suffix('.quality.json').write_text(json.dumps(dict(source_width=video_info.get('width'),source_height=video_info.get('height'),width=width,height=height,fps=fps,encoder=encoder_name,audio='AAC 256 kbps / 48 kHz',loudness_target_lufs=-16,true_peak_target_dbtp=-2,measured_input=audio_info),indent=2),encoding='utf-8')
    return dest

def export_clip(source, folder, clip, segments, config, index, excluded=()):
    from editing import keep_ranges,retime,sidecars
    ranges=keep_ranges(segments,clip['start'],clip['end'],config.get('pauses',False),config.get('fillers',False),excluded)
    if not ranges:raise ValueError('All speech was excluded. Keep at least one passage.')
    timeline=retime(segments,ranges)
    duration=sum(b-a for a,b in ranges)
    if duration<.3:raise ValueError('The selected passage is too short.')
    stem=f'clip-{index:02}'
    clip['file']=stem+'.mp4'
    # One final video encode, even when the edit includes multiple cuts.
    render(source,folder/clip['file'],dict(start=0,end=duration),timeline,config.get('layout','fit'),config.get('style','classic'),config.get('sound','off'),config.get('hook',''),config|{'_ranges':ranges})
    clip.update(duration=round(duration,3),removed_seconds=round(clip['end']-clip['start']-duration,3),style=config.get('style','classic'),sound=config.get('sound','off'))
    clip['text']=' '.join(s['text'].strip() for s in timeline)
    clip.update(sidecars(folder,stem,timeline,duration))
    return clip

def process(config, folder, update):
    folder = Path(folder).resolve()
    folder.mkdir(parents=True,exist_ok=True)
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise RuntimeError('FFmpeg and FFprobe are required. Install FFmpeg and restart ClipLocal.')
    source = config['source'].strip().strip('"')
    supplied_segments=None;transcript_method=None
    from acceleration import cache_path,platform_captions,transcribe
    if source.startswith(('http://', 'https://')):
        original_url=source
        # A previously downloaded source is reusable; never download it twice for a style change.
        for previous in sorted((ROOT/'clips').glob('*/project.json'),reverse=True):
            try:
                saved=json.loads(previous.read_text(encoding='utf-8'))
                if saved.get('config',{}).get('source')==source and Path(saved['source']).is_file():
                    source=saved['source'];update('Reusing the downloaded source',5)
                    if (previous.parent/'transcript.json').is_file() and saved.get('config',{}).get('model')==config.get('model','base.en'):
                        supplied_segments=json.loads((previous.parent/'transcript.json').read_text(encoding='utf-8'))
                        transcript_method='Reused project transcript'
                    break
            except (ValueError,OSError):continue
    if source.startswith(('http://', 'https://')):
        update('Downloading video', 5)
        import yt_dlp
        options = dict(outtmpl=str(folder/'source.%(ext)s'), noplaylist=True, quiet=True,
                       format='bv*[height<=2160]+ba/b[height<=2160]/b',format_sort=['hdr:SDR'], merge_output_format='mp4',
                       socket_timeout=30, retries=3, js_runtimes={'node': {}})
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(source, download=True)
            if config.get('transcript_source','auto')=='auto':
                update('Checking available English captions',12)
                supplied_segments,transcript_method=platform_captions(info,downloader)
            source = next((str(p) for p in folder.glob('source.*') if p.suffix in ('.mp4','.mkv','.webm','.mov')), downloader.prepare_filename(info))
            (folder/'source-info.json').write_text(json.dumps({'title': info.get('title'), 'url': config['source']}, indent=2), encoding='utf-8')
    else:
        source = str(Path(source).resolve())
        if not Path(source).is_file():
            raise ValueError('Enter a supported video URL or an existing local video file path.')
    details = probe(source)
    if not any(s['codec_type'] == 'video' for s in details['streams']):
        raise ValueError('The source does not contain video.')
    if not any(s['codec_type'] == 'audio' for s in details['streams']):
        raise ValueError('The source needs spoken audio for automatic highlight selection.')
    duration = float(details['format']['duration'])
    (folder/'project.json').write_text(json.dumps(dict(source=str(Path(source).resolve()),duration=duration,config=config),indent=2),encoding='utf-8')
    cache=cache_path(ROOT,source,config.get('model','base.en'),config.get('speed','balanced'))
    if supplied_segments is not None:segments=supplied_segments
    elif cache.exists():
        segments=json.loads(cache.read_text(encoding='utf-8'));transcript_method='Cached local transcript'
    else:
        update('Preparing English audio',15)
        wav=folder/'speech.wav'
        run(['ffmpeg','-v','error','-y','-i',source,'-vn','-ac','1','-ar','16000',wav])
        segments,transcript_method=transcribe(wav,config.get('model','base.en'),ROOT/'models',duration,config.get('speed','balanced'),update)
        wav.unlink(missing_ok=True)
        cache.write_text(json.dumps(segments),encoding='utf-8')
    update(transcript_method,65)
    project=json.loads((folder/'project.json').read_text(encoding='utf-8'))
    project['transcription_method']=transcript_method
    (folder/'project.json').write_text(json.dumps(project,indent=2),encoding='utf-8')
    (folder/'transcript.json').write_text(json.dumps(segments, indent=2), encoding='utf-8')
    (folder/'transcript.txt').write_text('\n'.join(f"[{stamp(s['start'])}] {s['text'].strip()}" for s in segments),encoding='utf-8')
    update('Selecting complete, non-overlapping highlights', 68)
    if config.get('manual_end') is not None:
        start=float(config.get('manual_start',0));end=min(duration,float(config['manual_end']))
        if not 0<=start<end<=duration:raise ValueError('The manual time range is outside the video.')
        clips=[dict(start=start,end=end,text='',score=None,reasons=['Manually selected range'])]
    else:
        clips = choose_clips(segments, config['length'], config['count'],config.get('topic',''),config.get('learn',True))
    if not clips:
        raise ValueError('No usable spoken highlights found. Try a longer video with clear English speech.')
    for i, clip in enumerate(clips):
        update(f'Editing clip {i+1} of {len(clips)}', 70+int(i/len(clips)*28))
        export_clip(source,folder,clip,segments,config,i+1)
        (folder/'clips.json').write_text(json.dumps(clips[:i+1], indent=2), encoding='utf-8')
    from editing import bundle
    bundle(folder)
    update(f'Saved {len(clips)} clips', 100)
    return clips

def reedit(parent, folder, edits, update):
    from editing import bundle
    parent,folder=Path(parent),Path(folder)
    project=json.loads((parent/'project.json').read_text(encoding='utf-8'))
    segments=json.loads((parent/'transcript.json').read_text(encoding='utf-8'))
    for key,text in edits.get('corrections',{}).items():
        i=int(key)
        if not 0<=i<len(segments):raise ValueError('Unknown transcript segment')
        if segments[i]['text'].strip()!=text.strip():
            segments[i]['text']=text.strip()
            segments[i]['words']=[] # Corrected phrases use evenly spaced timing.
    start,end=float(edits['start']),float(edits['end'])
    if not 0<=start<end<=project['duration']:raise ValueError('Invalid time range')
    config=project['config']|edits.get('settings',{})
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'project.json').write_text(json.dumps(project|dict(config=config),indent=2),encoding='utf-8')
    (folder/'transcript.json').write_text(json.dumps(segments,indent=2),encoding='utf-8')
    (folder/'transcript.txt').write_text('\n'.join(s['text'].strip() for s in segments),encoding='utf-8')
    clip=dict(start=start,end=end,score=None,reasons=['Edited transcript selection'])
    update('Rendering edited selection',35)
    export_clip(project['source'],folder,clip,segments,config,1,set(map(int,edits.get('excluded',[]))))
    (folder/'clips.json').write_text(json.dumps([clip],indent=2),encoding='utf-8')
    bundle(folder)
    update('Saved edited clip',100)
    return [clip]

def resume_exports(folder,update):
    """Resume from an existing transcript without re-downloading or retranscribing."""
    from editing import bundle
    folder=Path(folder)
    project=json.loads((folder/'project.json').read_text(encoding='utf-8'))
    segments=json.loads((folder/'transcript.json').read_text(encoding='utf-8'))
    config=project['config']
    if config.get('manual_end') is not None:
        clips=[dict(start=float(config.get('manual_start',0)),end=min(float(config['manual_end']),project['duration']),score=None,reasons=['Manually selected range'])]
    else:clips=choose_clips(segments,config['length'],config['count'],config.get('topic',''),config.get('learn',True))
    if not clips:raise ValueError('No suitable passages in the saved transcript')
    for i,clip in enumerate(clips):
        update(f'GPU-ready export · clip {i+1} of {len(clips)}',70+int(i/len(clips)*28))
        export_clip(project['source'],folder,clip,segments,config,i+1)
        (folder/'clips.json').write_text(json.dumps(clips[:i+1],indent=2),encoding='utf-8')
    bundle(folder)
    update(f'Saved {len(clips)} clips',100)
    return clips
