"""Visible HUD observations. Unknown values remain unknown; no synthetic countdown."""
from dataclasses import dataclass,asdict
from pathlib import Path
import time
import cv2
import numpy as np

HUD_SCORE=(463,162,642,198)
HUD_TIME=(1040,163,1140,198)
RESULT_SCORE=(910,450,1040,494)

@dataclass(frozen=True)
class Reading:
    value: object
    confidence: float
    source: str
    captured_unix_ms: int
    evidence: object=None

def glyphs(image,box):
    x0,y0,x1,y1=box
    gray=cv2.cvtColor(image[y0:y1,x0:x1],cv2.COLOR_RGB2GRAY)
    peak=float(np.percentile(gray,99))
    if peak<12:return []
    mask=(gray>peak*.9).astype(np.uint8)
    n,labels,stats,_=cv2.connectedComponentsWithStats(mask,8)
    components=[]
    for x,y,w,h,area in stats[1:]:
        if h<gray.shape[0]*.55 or w<5 or area<35:continue
        crop=mask[y:y+h,x:x+w]
        # Some real HUD pairs (e.g. 84) touch at their lower edges. Split a wide
        # component at a low vertical projection instead of dropping both digits.
        count=max(1,round(w/(h*.75))) if w>h*1.15 else 1
        cuts=[0]
        for k in range(1,count):
            center=round(w*k/count);radius=max(2,round(h*.14))
            lo=max(cuts[-1]+5,center-radius);hi=min(w-5,center+radius)
            if hi<=lo:continue
            projection=crop[:,lo:hi+1].sum(0)
            cuts.append(lo+int(np.argmin(projection)))
        cuts.append(w)
        for left,right in zip(cuts,cuts[1:]):
            part=crop[:,left:right];ys,xs=np.where(part)
            if not len(xs):continue
            part=part[ys.min():ys.max()+1,xs.min():xs.max()+1]
            components.append((int(x+left),cv2.resize(part,(20,28),interpolation=cv2.INTER_NEAREST).astype(np.float32)))
    return [g for _,g in sorted(components,key=lambda p:p[0])]

class HUDReader:
    def __init__(self,assets):
        with np.load(Path(assets)/'hud_digits.npz') as f:
            self.samples=f['samples'];self.values=f['values']
    def number(self,image,box,source,stamp,maximum):
        pieces=glyphs(image,box)
        if not pieces:return Reading(None,0,source,stamp,'no glyphs')
        digits=[];conf=[];distances=[]
        for piece in pieces:
            distances_by_sample=np.mean(np.abs(self.samples-piece),axis=(1,2))
            distances_by_digit=[float(np.min(distances_by_sample[self.values==i])) for i in range(10)]
            order=np.argsort(distances_by_digit);digit=int(order[0]);best=distances_by_digit[digit]
            margin=distances_by_digit[int(order[1])]-best
            confidence=min(1.0,max(0.0,1-best*2),max(0.0,margin/.09))
            if best>.16 or margin<.025:return Reading(None,confidence,source,stamp,{'distance':best,'margin':margin})
            digits.append(str(digit));conf.append(confidence);distances.append(best)
        value=int(''.join(digits))
        if value>maximum:return Reading(None,0,source,stamp,{'out_of_range':value})
        return Reading(value,min(conf),source,stamp,{'distances':distances})
    def read(self,image,result=False,stamp=None):
        stamp=stamp or int(time.time()*1000)
        time_read=self.number(image,HUD_TIME,'hud.time.template-v1',stamp,130)
        score=self.number(image,RESULT_SCORE if result else HUD_SCORE,'result.score.template-v1' if result else 'hud.score.template-v1',stamp,18000)
        skills={}
        if not result and time_read.value is not None:
            scale=float(np.percentile(image[163:198,1040:1140].max(2),97))
            for key,x in [('q',691),('w',778),('e',864)]:
                ratio=float(np.percentile(image[161:195,x:x+44].max(2),90))/max(1,scale)
                # Require a clear bright/dim state, leaving intermediate animation frames unknown.
                available=True if .80<=ratio<=1.25 else False if ratio<.45 else None
                confidence=.95 if available is not None else 0
                skills[key]=Reading(available,confidence,'hud.skill.brightness-v1',stamp,{'normalized_brightness':ratio})
        else:
            skills={key:Reading(None,0,'unobserved',stamp) for key in 'qwe'}
        return {'timer':time_read,'score':score,'skills':skills,'captured_unix_ms':stamp}

def serialize(observation):
    return {'timer':asdict(observation['timer']),'score':asdict(observation['score']),
            'skills':{k:asdict(v) for k,v in observation['skills'].items()},
            'captured_unix_ms':observation['captured_unix_ms']}

def skill_confirmed(key,before,after,before_board,after_board):
    """W may be the identity permutation, but must consume its visible skill state."""
    if before is None or after is None:return False
    a=before['skills'][key];b=after['skills'][key]
    evidence=a.value is True and b.value is False and min(a.confidence,b.confidence)>=.85
    if not evidence:return False
    if key=='w':return np.array_equal(np.sort(before_board.ravel()),np.sort(after_board.ravel())) and np.array_equal(before_board==0,after_board==0)
    if key=='q':return np.count_nonzero(before_board)-np.count_nonzero(after_board)==min(5,np.count_nonzero(before_board)) and bool(np.all((after_board==0)|(after_board==before_board)))
    if key=='e':
        x=before['timer'].value;y=after['timer'].value
        return x is not None and y is not None and 7<=y-x<=11 and np.array_equal(before_board,after_board)
    return False
