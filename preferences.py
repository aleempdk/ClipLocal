"""Small, inspectable preference model. Ratings adjust ranking, not model weights."""
import json
import re
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILE = ROOT / 'feedback.json'
LOCK = threading.Lock()

def features(text, duration):
    opening = ' '.join(text.split()[:25]).lower()
    return {
        'question': float('?' in opening or bool(re.match(r'\s*(why|how|what|when|would|can|do)\b', opening))),
        'advice': float(bool(re.search(r'\b(should|need|try|learn|advice|mistake|never)\b', opening))),
        'surprise': float(bool(re.search(r'\b(secret|actually|truth|imagine|surprising|crazy|changed)\b', opening))),
        'story': float(bool(re.search(r'\b(i|my|we)\b', opening))),
        'short': max(0., min(1., (90-duration)/60)),
    }

def read():
    if not FILE.exists(): return {}
    return json.loads(FILE.read_text(encoding='utf-8'))

def save(job, clip, rating):
    if type(rating) is not int or rating not in (-1, 0, 1):
        raise ValueError('Choose keep, pass, or clear')
    key = job + '/' + clip['file']
    with LOCK:
        data = read()
        if rating == 0: data.pop(key, None)
        else: data[key] = dict(rating=rating, features=features(clip.get('text',''), clip.get('duration',clip['end']-clip['start'])))
        temporary = FILE.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
        temporary.replace(FILE)
    return dict(rating=rating, count=len(data))

def weights():
    with LOCK: data = read()
    # Prior of 3 limits overreaction; each clip has one replaceable vote.
    return {key: sum(item['rating']*item['features'].get(key,0) for item in data.values()) /
            (3 + sum(item['features'].get(key,0) for item in data.values())) for key in features('',45)}

def adjustment(text, duration, learned):
    return max(-2., min(2., sum(value*learned.get(key,0) for key,value in features(text,duration).items())))
