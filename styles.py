"""Reference-inspired typography and original, locally synthesized sound accents."""
import math
import re
import wave
from pathlib import Path
import numpy as np

def ass_time(t):
    n = max(0, round(t*100))
    return f'{n//360000}:{n//6000%60:02}:{n//100%60:02}.{n%100:02}'

def clean(text):
    return re.sub(r'[{}\\\r\n]', ' ', text).strip()

def join_words(words):
    return re.sub(r'\s+([,.;!?])',r'\1',' '.join(words)).strip()

def timed_words(segments, start, end):
    words = []
    for segment in segments:
        if segment['end'] <= start or segment['start'] >= end:
            continue
        source = segment.get('words') or []
        if not source:
            tokens = segment['text'].split()
            step = (segment['end']-segment['start'])/max(1,len(tokens))
            source = [dict(word=t,start=segment['start']+i*step,end=segment['start']+(i+1)*step) for i,t in enumerate(tokens)]
        for word in source:
            a,b=max(start,word['start'])-start,min(end,word['end'])-start
            if b>a and clean(word['word']):
                words.append(dict(text=clean(word['word']),start=a,end=b))
    words.sort(key=lambda w:w['start'])
    merged=[]
    for word in words:
        if word['text']=='>>' or re.fullmatch(r'\[(?:applause|music|laughter|snorts|laughs|inaudible)\]',word['text'],re.I):continue
        if merged and word['text']==merged[-1]['text'] and abs(word['start']-merged[-1]['start'])<.12:continue
        # Whisper can split "$75,000" into "$75" and ",000".
        if merged and re.search(r'\d$',merged[-1]['text']) and re.match(r'^[,.]\d',word['text']):
            merged[-1]['text']+=word['text']
            merged[-1]['end']=word['end']
        else:merged.append(word)
    for current,next_word in zip(merged,merged[1:]):
        current['end']=min(current['end'],next_word['start'])
    return [w for w in merged if w['end']>w['start']]

def write_punch_ass(path, segments, start, end, hook='', width=720, height=1280, color='#ffff00', brand='', theme='punch', caption_size='large',decorations='off'):
    words = timed_words(segments,start,end)
    scale=width/720
    fontsize=round({'punch':56,'karaoke':54,'bold':64,'minimal':42,'boxed':52,'podcast':56,'spotlight':64,'neon':60,'editorial':52,'comic':62,'kinetic':62,'cinema':46}.get(theme,36)*scale*{'medium':.82,'large':1,'xl':1.18}.get(caption_size,1))
    margin=round(height*.215) if theme=='punch' and height>width else round(height*.12)
    if theme in ('podcast','spotlight','neon','editorial','comic','kinetic','cinema'):margin=round(height*.24)
    font='Arial Black' if theme in ('spotlight','bold','punch','neon','comic','kinetic') else 'Arial'
    if theme=='neon':color='#68ffcb'
    if theme=='comic':color='#78e4ff'
    if theme=='cinema':margin=round(height*.15)
    border=3 if theme=='boxed' else 1
    outline=0 if theme=='minimal' else round((5 if theme=='comic' else 3)*scale)
    accent=color.lstrip('#')
    accent=accent[4:6]+accent[2:4]+accent[:2]
    lines = ['[Script Info]','ScriptType: v4.00+',f'PlayResX: {width}',f'PlayResY: {height}','WrapStyle: 0',
        'ScaledBorderAndShadow: yes','[V4+ Styles]',
        'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
        f'Style: Caption,{font},{fontsize},&H00FFFFFF,&H0000FFFF,&H00000000,&H60000000,-1,0,0,0,100,100,0,0,{border},{outline},1,2,{round(44*scale)},{round(44*scale)},{margin},1',
        f'Style: Hook,Arial,{round(42*scale)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,1,0,8,35,35,{round(height*.026)},1',
        f'Style: Amount,Arial,{round(47*scale)},&H004CF45A,&H004CF45A,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,1,8,30,30,{round(height*.12)},1',
        f'Style: Brand,Arial,{round(22*scale)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,30,30,{round(height*.035)},1',
        '[Events]','Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    def event(a,b,style,text,layer=1):
        if b>a:
            lines.append(f'Dialogue: {layer},{ass_time(a)},{ass_time(b)},{style},,0,0,0,,{text}')
    if brand.strip():event(0,end-start,'Brand',clean(brand))
    # An opening excerpt is grounded in the transcript; it is not an invented claim.
    title = clean(hook)[:100] if hook.strip() else (' '.join(w['text'] for w in words[:8]) if theme in ('punch','spotlight') else '')
    tokens=title.split()
    if tokens:
        middle=math.ceil(len(tokens)/2)
        title=' '.join(tokens[:middle])+r'\N'+r'{\c&H4CF45A&}'+' '.join(tokens[middle:])
        event(0,end-start,'Hook',title)
    groups=[]
    group=[]
    for word in words:
        if group and (len(group)>=(3 if theme in ('bold','podcast','spotlight','neon','editorial','comic','kinetic','cinema') else 4) or sum(len(w['text'])+1 for w in group)+len(word['text'])>20 or word['start']-group[-1]['end']>.45):
            groups.append(group);group=[]
        group.append(word)
        if re.search(r'[.!?,]$',word['text']):
            groups.append(group);group=[]
    if group:groups.append(group)
    accents=[]
    last_accent=-4
    for group_index,group in enumerate(groups):
        next_group=groups[group_index+1][0]['start'] if group_index+1<len(groups) else end-start
        for i,word in enumerate(group):
            stop=min(end-start,next_group, group[i+1]['start'] if i+1<len(group) else word['end']+.10)
            # Keep the phrase visible and turn the spoken word yellow.
            phrase=' '.join((r'{\c&H'+accent+'&}' if j==i and theme!='minimal' else r'{\c&HFFFFFF&}')+(w['text'].upper() if theme in ('punch','bold','spotlight','neon','comic','kinetic') else w['text']) for j,w in enumerate(group))
            motion=r'{\fscx92\fscy92\t(0,100,\fscx100\fscy100)}' if i==0 and theme in ('punch','bold','spotlight','neon','comic','kinetic') else ''
            if theme=='neon':motion=r'{\bord3\shad2}'+motion
            if theme=='kinetic' and i==0:motion=r'{\fscx85\fscy85\frz-4\t(0,150,\fscx100\fscy100\frz0)}'
            if theme=='cinema':motion=r'{\fad(80,80)}'
            if theme=='editorial':motion=r'{\i1}'+motion
            event(word['start'],stop,'Caption',motion+phrase)
            amount=bool(re.search(r'[$£€]\s*\d|\d[\d,]*(?:\.\d+)?[kKmM]?\s*[$£€]',word['text']))
            if amount and theme=='punch' and word['start']-last_accent>=(10 if theme=='podcast' else 3.5):
                event(word['start'],min(end-start,word['start']+1.3),'Amount',r'{\fad(60,180)\fscx80\fscy80\t(0,140,\fscx100\fscy100)}'+word['text'])
            emphasis=amount or bool(re.search(r'\b(never|secret|mistake|craziest|million|thousand|dollars|changed|why)\b',word['text'],re.I))
            if emphasis and word['start']-last_accent>=(10 if theme=='podcast' else 3.5):
                accents.append(dict(time=word['start'],kind='chime' if amount else 'tap'))
                last_accent=word['start']
    from decorations import cues,draw
    decorative=cues(words,decorations,end-start)
    draw(decorative,decorations,width,height,event)
    Path(path).with_suffix('.decorations.json').write_text(__import__('json').dumps(decorative,indent=2),encoding='utf-8')
    accents.extend(dict(time=c['time'],kind='chime' if c['kind']=='money' else 'tap') for c in decorative if all(abs(c['time']-a['time'])>1 for a in accents))
    Path(path).write_text('\n'.join(lines)+'\n',encoding='utf-8-sig')
    return [dict(time=.06,kind='whoosh')]+accents[:max(1,math.ceil((end-start)/(12 if theme=='podcast' else 7)))]

def rounded_mask(path,width,height,radius=44):
    y,x=np.ogrid[:height,:width]
    distance=np.maximum(np.abs(x-width/2)-(width/2-radius),0)**2+np.maximum(np.abs(y-height/2)-(height/2-radius),0)**2
    mask=np.where(distance<=radius**2,255,0).astype(np.uint8)
    Path(path).write_bytes(f'P5\n{width} {height}\n255\n'.encode()+mask.tobytes())

def synth_effects(path, duration, accents, mode='subtle'):
    """Small original waveforms; no external samples, music, or API calls."""
    rate=24000
    audio=np.zeros(math.ceil(duration*rate),dtype=np.float32)
    rng=np.random.default_rng(2026)
    for event in accents:
        kind=event['kind']
        if mode=='cinematic':kind='swell' if kind=='whoosh' else 'bell'
        elif mode=='digital':kind='sweep' if kind=='whoosh' else 'click'
        elif mode=='punchy':kind='impact' if kind!='whoosh' else 'whoosh'
        length=.65 if kind in ('swell','bell','sweep') else .22 if kind=='impact' else .07 if kind=='click' else .32 if kind=='whoosh' else (.28 if kind=='chime' else .09)
        t=np.arange(int(length*rate))/rate
        if kind=='swell':
            signal=np.sin(2*np.pi*(160*t+120*t*t))*np.sin(np.pi*t/length)**2*.045
        elif kind=='bell':
            signal=(np.sin(2*np.pi*660*t)+.25*np.sin(2*np.pi*990*t))*np.exp(-t*9)*.035
        elif kind=='sweep':
            signal=np.sin(2*np.pi*(450*t+900*t*t))*np.sin(np.pi*t/length)**2*.035
        elif kind=='click':
            signal=rng.normal(0,1,len(t))*np.exp(-t*100)*.055
        elif kind=='impact':
            signal=np.sin(2*np.pi*(95*t-110*t*t))*np.exp(-t*22)*.11
        elif kind=='whoosh':
            noise=rng.normal(0,1,len(t))
            smooth=np.convolve(noise,np.ones(9)/9,mode='same')
            signal=smooth*np.sin(np.pi*t/length)**2*.12
        elif kind=='chime':
            signal=(np.sin(2*np.pi*880*t)+.4*np.sin(2*np.pi*1320*t))*np.exp(-t*18)*.045
        else:
            signal=np.sin(2*np.pi*(180*t-500*t*t))*np.exp(-t*65)*.07
        offset=max(0,int(event['time']*rate))
        n=min(len(signal),len(audio)-offset)
        if n>0:audio[offset:offset+n]+=signal[:n]
    with wave.open(str(path),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate)
        out.writeframes((np.clip(audio,-1,1)*32767).astype('<i2').tobytes())
