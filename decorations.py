"""Transcript-cued ASS bubbles and vector stickers. All artwork is drawn locally."""
import math
import re

def cues(words,mode,duration):
    if mode=='off':return []
    result=[];last=-12
    for w in words:
        text=w['text'];kind=None
        if re.search(r'[$£€]\s*\d|\b(million|money|dollars)\b',text,re.I):kind='money'
        elif re.search(r'\b(why|how|what|question)\b',text,re.I):kind='question'
        elif re.search(r'\b(won|win|success|amazing|great|perfect)\b',text,re.I):kind='star'
        elif re.search(r'\b(secret|mistake|never|important|remember)\b',text,re.I):kind='note'
        if kind and w['start']-last>=12:
            result.append(dict(time=w['start'],end=min(duration,w['start']+1.7),kind=kind,text=text))
            last=w['start']
        if len(result)>=max(1,math.ceil(duration/20)):break
    return result

def draw(events,mode,width,height,event):
    scale=width/720
    for index,cue in enumerate(events):
        a,b=cue['time'],cue['end'];x=round(width*(.76 if index%2==0 else .24));y=round(height*.17)
        animate=rf'{{\an5\pos({x},{y})\fad(90,180)\fscx70\fscy70\t(0,160,\fscx100\fscy100)}}'
        # Keep decorations in upper corners, away from the large lower captions.
        if mode in ('auto','bubbles'):
            label=cue['text'].strip('.,!?')[:16].upper()
            w=round(max(95,len(label)*19+30)*scale);h=round(54*scale);r=round(12*scale)
            path=f'm {r} 0 l {w-r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h-r} b {w} {h} {w} {h} {w-r} {h} l {r} {h} b 0 {h} 0 {h} 0 {h-r} l 0 {r} b 0 0 0 0 {r} 0'
            event(a,b,'Caption',animate+r'{\bord0\shad0\c&H303020&\p1}'+path+r'{\p0}',3)
            event(a,b,'Caption',animate+rf'{{\fs{round(27*scale)}\bord1\3c&H303020&\c&HFFFFFF&}}'+label,4)
            tail=rf'{{\an7\pos({x-round(20*scale)},{y+round(22*scale)})\fad(90,180)\bord0\c&H303020&\p1}}m 0 0 l 24 0 0 24{{\p0}}'
            event(a,b,'Caption',tail,3)
        if mode in ('auto','stickers'):
            sy=y+round(82*scale) if mode=='auto' else y
            base=rf'{{\an5\pos({x},{sy})\fad(90,180)\frz-10\t(0,220,\frz0)\fscx75\fscy75\t(0,160,\fscx100\fscy100)\bord2\3c&H101010&\c&H5CF8C3&}}'
            if cue['kind']=='star':
                coords=[]
                for i in range(10):
                    angle=-math.pi/2+i*math.pi/5;r=(29 if i%2==0 else 13)*scale
                    coords.append(f'{round(32*scale+r*math.cos(angle))} {round(32*scale+r*math.sin(angle))}')
                art=r'{\p1}m '+coords[0]+' l '+' '.join(coords[1:])+r'{\p0}'
            else:
                symbol={'money':'$','question':'?','note':'!'}[cue['kind']]
                art=rf'{{\fs{round(58*scale)}}}'+symbol
            event(a,b,'Caption',base+art,4)
