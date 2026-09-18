"""Observed-state adapter and bounded JSON-lines native client. No desktop input."""
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
import hashlib,json,queue,subprocess,threading,time,uuid
from .starsavior_core.model import State,Skills,Action
from .starsavior_core.bounds import numeric_upper_bound,q_now_residue_distribution,optimistic_score_bound
from .starsavior_core.scoring import ScoreRules,Terminal,score_parts

POLICY='v1.2-route+v1.3-observation-guard'
TIMING={'version':'hud-quantized-unmeasured','calibrated':False,'move_ms':None,
        'q_ms':None,'w_ms':None,'e_ms':None,'future_plan_ms':None}

def fingerprint(board):
    return hashlib.sha256(bytes(map(int,board))).hexdigest()

def observed_state(board,observation,version,initial_cells=150):
    flat=tuple(map(int,board.ravel()));timer=observation['timer'];skills=observation['skills']
    if timer.value is None or timer.confidence<.75 or any(v.value is None or v.confidence<.85 for v in skills.values()):
        raise ValueError('倒數或技能狀態無法可靠辨識，已停止。')
    mask=sum(bit for key,bit in [('q',1),('w',2),('e',4)] if skills[key].value)
    # A conservative action-time estimate, not an assertion about HUD rounding.
    remaining=max(0,(int(timer.value)-1)*1000)
    state=State(flat,board.shape[0],board.shape[1],remaining,Skills(mask),initial_cells)
    stamp=observation['captured_unix_ms']
    return {'board':list(flat),'height':state.height,'width':state.width,'initial_cells':initial_cells,
        'remaining_ms':remaining,'skills_mask':mask,'hud_score':observation['score'].value,
        'state_version':version,'board_hash':fingerprint(flat),'policy_version':POLICY,
        'timing_version':TIMING['version'],'cleared_in_time':False,
        'board_observation':{'source':'board.template-v1.2','confidence':.9,'captured_unix_ms':stamp},
        'time_observation':{'source':timer.source,'confidence':timer.confidence,'captured_unix_ms':stamp},
        'skill_observation':{'source':'hud.skill.brightness-v1','confidence':min(v.confidence for v in skills.values()),'captured_unix_ms':stamp}}

def python_analysis(payload):
    s=State(tuple(payload['board']),payload['height'],payload['width'],payload['remaining_ms'],Skills(payload['skills_mask']),payload['initial_cells'])
    rules=ScoreRules('floor_seconds')
    parts=score_parts(Terminal(s.initial_cells,s.occupied,s.skills,s.remaining_ms,payload.get('cleared_in_time',False)),rules)
    return {'score_if_stop':{'cell_points':parts.cell_points,'skill_points':parts.skill_points,'time_points':float(parts.time_points),'total':float(parts.total)},
        'removable_upper_bound':numeric_upper_bound(s.board,bool(s.skills&Skills.Q)),
        'optimistic_score_bound':float(optimistic_score_bound(s,rules)),
        'q_now_residue_probabilities':[{'numerator':p.numerator,'denominator':p.denominator} for p in q_now_residue_distribution(s.board)]}

def revalidate(before,after,rect,minimum_ms=1200):
    if before['board_hash']!=after['board_hash'] or before['skills_mask']!=after['skills_mask']:
        raise ValueError('搜尋後棋盤或技能已改變，棄用舊結果。')
    if after['remaining_ms'] is None or after['remaining_ms']<minimum_ms:
        return False
    a,b,c,d=rect;h,w=after['height'],after['width']
    if not (0<=a<=c<h and 0<=b<=d<w):raise ValueError('無效座標。')
    if sum(after['board'][r*w+j] for r in range(a,c+1) for j in range(b,d+1))!=10:
        raise ValueError('搜尋結果不符合合計 10。')
    # Wall time is used only to reject stale observations, never to invent HUD time.
    if int(time.time()*1000)-after['time_observation']['captured_unix_ms']>700:
        raise ValueError('動作前觀測已過期。')
    return True

class NativeClient:
    def __init__(self,executable,check=lambda:None):
        self.check=check;self.answers=queue.Queue();self.quarantined=[]
        self.proc=subprocess.Popen([str(executable)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            text=True,encoding='utf-8',bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        def read():
            for line in self.proc.stdout:
                try:self.answers.put(json.loads(line))
                except ValueError:self.answers.put({'status':'malformed'})
            self.answers.put({'status':'closed'})
        threading.Thread(target=read,daemon=True).start()
        try:self.request('ping',timeout_ms=1500)
        except BaseException:
            self.close();raise
    def send(self,payload):
        self.proc.stdin.write(json.dumps(payload,separators=(',',':'))+'\n');self.proc.stdin.flush()
    @staticmethod
    def matches(answer,request):
        if answer.get('protocol')!=2 or answer.get('request_id')!=request['request_id']:return False
        s=request.get('state')
        return s is None or (answer.get('state_version')==s['state_version'] and answer.get('board_hash')==s['board_hash'])
    def request(self,kind,state=None,budget_ms=420,timeout_ms=None,**extra):
        request={'protocol':2,'type':kind,'request_id':uuid.uuid4().hex,'budget_ms':budget_ms,
            'deadline_unix_ms':int(time.time()*1000)+budget_ms,**extra}
        if state is not None:request['state']=state
        self.check();self.send(request)
        end=time.monotonic()+(timeout_ms if timeout_ms is not None else budget_ms+200)/1000
        try:
            while time.monotonic()<end:
                self.check()
                try:answer=self.answers.get(timeout=min(.02,max(.001,end-time.monotonic())))
                except queue.Empty:continue
                if answer.get('status') in ('closed','malformed'):raise RuntimeError('原生核心通訊中斷。')
                if not self.matches(answer,request):
                    self.quarantined.append(answer);continue
                if answer['status'] not in ('ok','deadline','cancelled'):raise RuntimeError('原生核心錯誤：'+str(answer.get('error',answer['status'])))
                return answer
            raise TimeoutError('原生搜尋逾時，已取消並停止。')
        except BaseException:
            try:self.send({'protocol':2,'type':'cancel','request_id':request['request_id']})
            except (OSError,ValueError):pass
            self.close()
            raise
    def close(self):
        if self.proc.poll() is None:
            try:self.proc.stdin.close();self.proc.wait(timeout=.15)
            except (OSError,subprocess.TimeoutExpired):self.proc.kill();self.proc.wait(timeout=1)
        for stream in (self.proc.stdin,self.proc.stdout):
            try:stream.close()
            except (OSError,ValueError):pass

class LiveSearch:
    def __init__(self,control,assets,baseline=None):
        self.control=control;self.baseline=baseline;self.last_diagnostics={}
        try:self.client=NativeClient(Path(assets)/'CoreHost.exe',control.check)
        except BaseException:
            if self.baseline:self.baseline.close()
            raise
    def reset(self):
        self.client.request('reset',budget_ms=200)
        if self.baseline:self.baseline.reset()
    def choose(self,board,options,skills,state):
        budget=900 if sum(v!=0 for v in state['board'])==150 else 420
        reply=self.client.request('analyze' if self.baseline else 'choose',state,budget_ms=budget,
            rounding='floor_seconds',timing=TIMING,objective={'mode':'mean_score'})
        py=python_analysis(state);native=reply['analysis']
        if py['score_if_stop']!=native['score_if_stop'] or py['removable_upper_bound']!=native['removable_upper_bound'] or py['optimistic_score_bound']!=native['optimistic_score_bound']['total'] or py['q_now_residue_probabilities']!=native['q_now_residue_probabilities']:
            raise RuntimeError('Python 與 C# 核心交叉驗證不一致，已停止。')
        self.last_diagnostics=reply
        if reply['status']=='cancelled':raise RuntimeError('搜尋已取消，棄用這次結果。')
        if self.baseline:return self.baseline.choose(board,options,skills)
        coords=tuple(reply['action'].get('rect') or ())
        move=next((m for m in options if tuple(m[:4])==coords),None)
        if move is None:raise RuntimeError('搜尋未回傳可驗證的動作，已停止。')
        return move,0
    def close(self):
        try:self.client.close()
        finally:
            if self.baseline:self.baseline.close()
