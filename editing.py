"""Timeline edits and export sidecars. All timestamps are seconds."""
import copy
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

def keep_ranges(segments, start, end, pauses=False, fillers=False, excluded=()):
    cuts=[]
    speech=[]
    for i,s in enumerate(segments):
        if s['end']<=start or s['start']>=end:continue
        if i in excluded:
            cuts.append((max(start,s['start']),min(end,s['end'])))
        words=s.get('words') or [dict(start=s['start'],end=s['end'],word=s['text'])]
        for w in words:
            a,b=max(start,w['start']),min(end,w['end'])
            if b<=a:continue
            speech.append((a,b))
            if fillers and re.fullmatch(r'[\W_]*(um+|uh+|erm+|hmm+)[\W_]*',w['word'],re.I):
                cuts.append((max(start,a-.025),min(end,b+.025)))
    if pauses and speech:
        speech.sort()
        cursor=start
        for a,b in speech:
            if a-cursor>.8:cuts.append((cursor+.12,a-.12))
            cursor=max(cursor,b)
        if end-cursor>.8:cuts.append((cursor+.12,end))
    merged=[]
    for a,b in sorted(cuts):
        if b<=a:continue
        if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
        else:merged.append((a,b))
    keeps=[];cursor=start
    for a,b in merged:
        if a-cursor>.035:keeps.append((cursor,a))
        cursor=max(cursor,b)
    if end-cursor>.035:keeps.append((cursor,end))
    return keeps

def retime(segments,ranges):
    from styles import join_words
    output=[];offset=0
    for a,b in ranges:
        for s in segments:
            x,y=max(a,s['start']),min(b,s['end'])
            if y<=x:continue
            item=copy.deepcopy(s)
            item['start'],item['end']=offset+x-a,offset+y-a
            words=[]
            for w in s.get('words',[]):
                wx,wy=max(a,w['start']),min(b,w['end'])
                if wy>wx:words.append(dict(word=w['word'],start=offset+wx-a,end=offset+wy-a))
            item['words']=words
            if s.get('words'):
                item['text']=join_words(w['word'].strip() for w in words)
            if item['text'].strip():output.append(item)
        offset+=b-a
    return output

def metadata(text):
    text=re.sub(r'\[(?:applause|music|laughter|snorts|laughs|inaudible)\]|>>',' ',text,flags=re.I)
    text=' '.join(re.sub(r'[\u200b-\u200f\ufeff]', '', text).split())
    sentences=re.split(r'(?<=[.!?])\s+',text)
    first=next((s for s in sentences[:12] if '?' in s and 5<=len(s.split())<=22),
               next((s for s in sentences[:12] if len(s.split())>=8),next((s for s in sentences if len(s.split())>=4),text)))
    first=re.sub(r'^(?:yeah|okay|well|right|so|um)[,\s]+','',first,flags=re.I)
    title=first if len(first)<=90 else first[:87].rsplit(' ',1)[0]+'…'
    title=title[:1].upper()+title[1:] if title else 'A moment from this video'
    stop=set('about after again also because before being could doing every first from have here into just like more most much only other really should some that their them then there these they thing think this those very want were what when where which while will with would your you are the and for but not was had has can all how our out'.split())
    stop.update('been time full facts life done now okay yeah going know years number something someone anything everything maybe make sure still back'.split())
    terms=Counter(w for w in re.findall(r'\b[a-zA-Z]{4,}\b',text.lower()) if w not in stop)
    hashtags=['#'+w for w,_ in terms.most_common(3)]+['#Shorts']
    tags=[w for w,_ in terms.most_common(10)]+['shorts']
    start=sentences.index(first) if first in sentences else 0
    description=' '.join(sentences[start:start+3])[:1200].strip()
    return dict(title=title,description=description,hashtags=' '.join(hashtags),tags=tags)

def write_metadata(folder,stem,info):
    folder=Path(folder)
    (folder/f'{stem}.youtube.json').write_text(json.dumps(info,indent=2,ensure_ascii=False),encoding='utf-8')
    sections=[('TITLE',info['title']),('DESCRIPTION',info['description']),('HASHTAGS',info['hashtags']),('TAGS',', '.join(info['tags']))]
    (folder/f'{stem}.post.txt').write_text('\n\n'.join(name+'\n'+value for name,value in sections),encoding='utf-8')

def sidecars(folder,stem,segments,duration):
    from engine import captions,run
    folder=Path(folder)
    text=' '.join(s['text'].strip() for s in segments)
    info=metadata(text)
    write_metadata(folder,stem,info)
    srt=captions(segments,0,duration)
    (folder/f'{stem}.vtt').write_text('WEBVTT\n\n'+re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})',r'\1.\2',srt),encoding='utf-8')
    run(['ffmpeg','-v','error','-y','-ss',min(1,duration/3),'-i',folder/f'{stem}.mp4','-frames:v','1',folder/f'{stem}.jpg'])
    return info

def bundle(folder):
    folder=Path(folder)
    destination=folder/'exports.zip'
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        for f in folder.iterdir():
            if (f.name.startswith('clip-') and not f.name.endswith(('.filter.txt','-filter.txt')) and f.suffix in ('.mp4','.srt','.ass','.vtt','.jpg','.txt','.json')) or f.name in ('transcript.txt','transcript.json','clips.json'):
                archive.write(f,f.name)
    return destination
