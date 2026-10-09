import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from framing import stable_plan
from editing import metadata,write_metadata
from app import settings
from decorations import cues
from quality import encoder_args
from styles import timed_words,write_punch_ass

class UpgradeTests(unittest.TestCase):
    def test_jitter_does_not_move_camera_or_flash_views(self):
        points=[(i/4,.5+(.015 if i%2 else -.015),.4,i%3!=0,False) for i in range(40)]
        _,shots,trajectory=stable_plan(points,720,1280,2276,1280,10,30)
        self.assertEqual(len(shots),1)
        self.assertTrue(shots[0]['cropped'])
        self.assertEqual(len({(p[1],p[2]) for p in trajectory}),1)

    def test_sustained_move_eases_and_cut_resets(self):
        points=[(i/4,.4 if i<16 else .8,.4,True,i==32) for i in range(48)]
        _,shots,path=stable_plan(points,720,1280,2276,1280,12,30)
        self.assertEqual(len(shots),2)
        self.assertLess(path[4*30+5][1],path[7*30][1])
        moves=[abs(b[1]-a[1]) for a,b in zip(path,path[1:]) if b[0]!=8]
        self.assertLessEqual(max(moves),6)
        self.assertGreater(path[8*30][1],path[8*30-1][1])

    def test_no_faces_stays_wide(self):
        points=[(i/4,.5,.5,False,False) for i in range(16)]
        _,shots,_=stable_plan(points,720,1280,2276,1280,4,30)
        self.assertFalse(shots[0]['cropped'])

    def test_metadata_clean_grounded_and_saved(self):
        info=metadata('>> [applause] Why does a DNA test matter after all these years? We discuss family memories and a father stepping up.')
        self.assertNotIn('applause',str(info))
        self.assertNotIn('>>',str(info))
        self.assertLessEqual(len(info['title']),100)
        self.assertLess(len(', '.join(info['tags'])),500)
        d=Path(__file__).resolve().parent/'_scratch'
        d.mkdir(exist_ok=True)
        write_metadata(d,'clip-01',info)
        self.assertEqual(json.loads((d/'clip-01.youtube.json').read_text()),info)

    def test_decorations_sparse_and_relevant(self):
        words=[dict(text='Why',start=0,end=.5),dict(text='secret',start=1,end=2),dict(text='$50',start=13,end=14)]
        events=cues(words,'auto',40)
        self.assertEqual(len(events),2)
        self.assertGreaterEqual(events[1]['time']-events[0]['time'],12)
        self.assertEqual(cues(words,'off',40),[])

    def test_configuration_validation_and_encoder_routes(self):
        self.assertEqual(settings({})['motion'],'off')
        with self.assertRaises(ValueError):settings({'decorations':'unknown'})
        for name in ('libx264','h264_nvenc','h264_qsv','h264_amf'):
            with patch('hardware.detect',return_value={'encoder':name,'cpu_threads':4}):
                self.assertIn(name,encoder_args()[0])

    def test_platform_caption_overlap_is_clamped(self):
        segments=[dict(start=0,end=3,text='DNA',words=[dict(word='DNA',start=0,end=3)]),
                  dict(start=1,end=4,text='test now?',words=[dict(word='test',start=1,end=2),dict(word='now?',start=2,end=4)])]
        words=timed_words(segments,0,4)
        self.assertTrue(all(a['end']<=b['start'] for a,b in zip(words,words[1:])))
        d=Path(__file__).resolve().parent/'_scratch'
        write_punch_ass(d/'overlap.ass',segments,0,4,theme='comic')
        lines=[line for line in (d/'overlap.ass').read_text(encoding='utf-8-sig').splitlines() if line.startswith('Dialogue:')]
        times=[line.split(',')[1:3] for line in lines]
        self.assertTrue(all(a[1]<=b[0] for a,b in zip(times,times[1:])))

if __name__=='__main__':unittest.main()
