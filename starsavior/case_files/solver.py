"""One-round local StarSavior helper. No network or model calls."""
import ctypes
from ctypes import wintypes as W
from datetime import datetime
from pathlib import Path
import json
import queue
import subprocess
import threading
import time

import cv2
import numpy as np
from PIL import Image, ImageGrab
from .observations import HUDReader,serialize,skill_confirmed
from .live_core import LiveSearch,observed_state,revalidate,TIMING
from .starsavior_core.scoring import Terminal,ScoreRules,score_parts
from .starsavior_core.model import Skills,Action

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'
# Seconds requested from the input layer; real game latency is logged separately.
DRAG_PROFILES = {
    'fast': {'before':.02,'hold':.10,'travel':.10,'end':.03,'after':.02,'steps':6,'settle':0},
    'standard': {'before':.04,'hold':.12,'travel':.12,'end':.04,'after':.10,'steps':12,'settle':.30},
    'slow': {'before':.04,'hold':.30,'travel':.75,'end':.12,'after':.10,'steps':12,'settle':.30},
}
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
dwm = ctypes.WinDLL('dwmapi')
# DPI setup belongs to the OKSS/Qt host. Importing a task must not change it.

user32.GetForegroundWindow.restype = W.HWND
user32.IsWindow.argtypes = [W.HWND]
user32.IsWindowVisible.argtypes = [W.HWND]
user32.IsIconic.argtypes = [W.HWND]
user32.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
user32.SetForegroundWindow.argtypes = [W.HWND]
user32.ShowWindow.argtypes = [W.HWND, ctypes.c_int]
kernel32.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
kernel32.OpenProcess.restype = W.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]
kernel32.CloseHandle.argtypes = [W.HANDLE]
dwm.DwmGetWindowAttribute.argtypes = [W.HWND, W.DWORD, ctypes.c_void_p, W.DWORD]

class MouseInput(ctypes.Structure):
    _fields_ = [('dx',W.LONG),('dy',W.LONG),('data',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',ctypes.c_size_t)]
class KeyInput(ctypes.Structure):
    _fields_ = [('vk',W.WORD),('scan',W.WORD),('flags',W.DWORD),('time',W.DWORD),('extra',ctypes.c_size_t)]
class HardwareInput(ctypes.Structure):
    _fields_ = [('msg',W.DWORD),('lo',W.WORD),('hi',W.WORD)]
class InputUnion(ctypes.Union):
    _fields_ = [('mi',MouseInput),('ki',KeyInput),('hi',HardwareInput)]
class Input(ctypes.Structure):
    _anonymous_ = ('value',)
    _fields_ = [('type',W.DWORD),('value',InputUnion)]
user32.SendInput.argtypes = [W.UINT, ctypes.POINTER(Input), ctypes.c_int]

class Stopped(Exception):
    pass

class Control:
    def __init__(self, event):
        self.event = event
    def check(self):
        # OKSS supplies a cancellation event linked to its existing hotkey.
        # Do not register/poll a second F8/F9 listener in the embedded solver.
        if self.event.is_set():
            self.event.set()
            raise Stopped('已停止。遊戲畫面保持原狀。')
    def wait(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check()
            self.event.wait(min(.025, max(0, end-time.monotonic())))
        self.check()

def find_game():
    found = []
    callback_type = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    @callback_type
    def visit(hwnd, _):
        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title, 512)
        if title.value != 'StarSavior' or not user32.IsWindowVisible(hwnd):
            return True
        pid = W.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = kernel32.OpenProcess(0x1000, False, pid.value)
        if process:
            try:
                path = ctypes.create_unicode_buffer(32768)
                size = W.DWORD(len(path))
                if kernel32.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(size)):
                    if Path(path.value).name.lower() == 'starsavior.exe':
                        found.append(hwnd)
            finally:
                kernel32.CloseHandle(process)
        return True
    user32.EnumWindows(visit, 0)
    if not found:
        raise RuntimeError('找不到 StarSavior。請先開啟遊戲，再停在案件檔案活動首頁。')
    if len(found) != 1:
        raise RuntimeError('找到多個 StarSavior 視窗，請只保留一個再開始。')
    return found[0]

class Game:
    def __init__(self, control):
        self.control = control
        self.hwnd = find_game()
        self.held = False
        self.rect = self.bounds()
    def bounds(self):
        r = W.RECT()
        if not user32.IsWindow(self.hwnd) or dwm.DwmGetWindowAttribute(self.hwnd,9,ctypes.byref(r),ctypes.sizeof(r)):
            raise RuntimeError('遊戲視窗已關閉或無法讀取。')
        if (r.right-r.left,r.bottom-r.top) != (1602,932):
            raise RuntimeError('目前支援遊戲內容 1600 × 900 的視窗模式。請調整遊戲解析度後再開始。')
        return (r.left,r.top,r.right,r.bottom)
    def activate(self):
        self.control.check()
        if user32.IsIconic(self.hwnd):
            user32.ShowWindow(self.hwnd,9)
        user32.SetForegroundWindow(self.hwnd)
        self.control.wait(.35)
        self.rect = self.bounds()
        self.check()
    def check(self):
        self.control.check()
        if user32.GetForegroundWindow() != self.hwnd:
            raise Stopped('已停止：你切換了視窗。')
        if self.bounds() != self.rect:
            raise Stopped('已停止：遊戲視窗的位置或大小改變了。')
    @staticmethod
    def inject(inp):
        if user32.SendInput(1,ctypes.byref(inp),ctypes.sizeof(inp)) != 1:
            raise RuntimeError('無法操作遊戲滑鼠。請確認工具與遊戲使用相同權限執行。')
    def pos(self,x,y):
        self.check()
        sx=self.rect[0]+round(x);sy=self.rect[1]+round(y)
        vx,vy,vw,vh=[user32.GetSystemMetrics(i) for i in (76,77,78,79)]
        self.inject(Input(type=0,mi=MouseInput(round((sx-vx)*65535/(vw-1)),round((sy-vy)*65535/(vh-1)),0,0xC001,0,0)))
    def down(self):
        self.check()
        self.inject(Input(type=0,mi=MouseInput(0,0,0,2,0,0)))
        self.held=True
    def release(self):
        if self.held:
            try:
                self.inject(Input(type=0,mi=MouseInput(0,0,0,4,0,0)))
            finally:
                self.held=False
    def click_start(self):
        self.pos(1385,844)
        self.control.wait(.06)
        self.down()
        try:
            self.control.wait(.10)
        finally:
            self.release()
        self.control.wait(.12)
        self.pos(1280,470)
    def click_restart(self):
        # Caller has freshly confirmed the RESULT panel in this same window.
        self.pos(941,667)
        self.control.wait(.06);self.down()
        try:self.control.wait(.10)
        finally:self.release()
        self.control.wait(.12);self.pos(1280,470)
    def shot(self):
        self.check()
        return np.array(ImageGrab.grab(bbox=self.rect,all_screens=True))
    def drag(self,move,slow=False,profile=None):
        profile=profile or ('slow' if slow else 'fast')
        pace=DRAG_PROFILES[profile]
        a,b,c,d=move[:4]
        x1,y1=xy(a,b);x2,y2=xy(c,d)
        self.pos(x1,y1);self.control.wait(pace['before'])
        self.down()
        try:
            self.control.wait(pace['hold'])
            start=time.monotonic();steps=pace['steps']
            for i in range(1,steps+1):
                self.pos(x1+(x2-x1)*i/steps,y1+(y2-y1)*i/steps)
                # Avoid accumulating the Windows wait overshoot at every fast step.
                delay=max(0,start+pace['travel']*i/steps-time.monotonic()) if profile=='fast' else pace['travel']/steps
                self.control.wait(delay)
            self.control.wait(pace['end'])
        finally:
            self.release()
        self.control.wait(pace['after'])
        self.pos(1280,470)
    def key(self,key):
        self.check()
        self.inject(Input(type=1,ki=KeyInput(ord(key.upper()),0,0,0,0)))
        try:
            self.control.wait(.09)
        finally:
            self.inject(Input(type=1,ki=KeyInput(ord(key.upper()),0,2,0,0)))

def xy(r,c):
    return 438+51.8*c,276.5+51.8*r

def glyph(im,r,c):
    x,y=map(round,xy(r,c))
    g=cv2.cvtColor(im[y-18:y+19,x-17:x+18],cv2.COLOR_RGB2GRAY)
    rim=np.concatenate([g[:3,:].ravel(),g[-3:,:].ravel(),g[:,:3].ravel(),g[:,-3:].ravel()])
    if np.median(rim)<185:
        return None
    mask=(g[3:-3,3:-3]<115).astype(np.uint8)
    ys,xs=np.where(mask)
    if len(xs)<35:
        return None
    return cv2.resize(mask[ys.min():ys.max()+1,xs.min():xs.max()+1],(20,28),interpolation=cv2.INTER_NEAREST).astype(np.float32)

class Reader:
    def __init__(self):
        with np.load(ASSETS/'digits.npz') as f:
            self.samples=f['samples'];self.values=f['values']
        with np.load(ASSETS/'screens.npz') as f:
            self.templates={k:f[k] for k in f.files}
    def match(self,im,name,box):
        x,y,w,h=box
        patch=cv2.cvtColor(im[y:y+h,x:x+w],cv2.COLOR_RGB2GRAY)
        template=cv2.cvtColor(self.templates[name],cv2.COLOR_RGB2GRAY)
        return float(cv2.matchTemplate(patch,template,cv2.TM_CCOEFF_NORMED)[0,0])
    def is_result(self,im):
        return self.match(im,'result',(735,230,135,35))>.92
    def is_home(self,im):
        return self.match(im,'home',(1280,817,180,58))>.87 and not self.is_result(im)
    def is_play(self,im):
        return self.match(im,'hud',(371,170,79,33))>.90 and not self.is_result(im)
    def board(self,im):
        board=np.zeros((10,15),dtype=np.int16);bad=[]
        for r in range(10):
            for c in range(15):
                g=glyph(im,r,c)
                if g is None:
                    continue
                dist=np.mean(np.abs(self.samples-g),axis=(1,2))
                i=int(np.argmin(dist));board[r,c]=self.values[i]
                if dist[i]>.16:
                    bad.append((r,c))
        return board,bad

RECTS=np.array([(a,b,c,d) for a in range(10) for c in range(a,10) for b in range(15) for d in range(b,15)],dtype=np.int16)
A,B,C,D=RECTS.T
def moves(board):
    p=np.pad(board,((1,0),(1,0))).cumsum(0).cumsum(1)
    q=np.pad(board>0,((1,0),(1,0))).cumsum(0).cumsum(1)
    sums=p[C+1,D+1]-p[A,D+1]-p[C+1,B]+p[A,B]
    counts=q[C+1,D+1]-q[A,D+1]-q[C+1,B]+q[A,B]
    result=[];seen=set()
    for i in np.flatnonzero((sums==10)&(counts>0)):
        a,b,c,d=map(int,RECTS[i])
        cells=tuple(map(tuple,np.argwhere(board[a:c+1,b:d+1]>0)+[a,b]))
        if cells in seen:
            continue
        seen.add(cells)
        rows,cols=zip(*cells)
        result.append((int(min(rows)),int(min(cols)),int(max(rows)),int(max(cols)),int(counts[i]),cells))
    return result

def strategy_moves(board,skills):
    options=moves(board)
    if 'w' not in skills:
        return [m for m in options if m[4]==2]
    return options

class Search:
    def __init__(self,control):
        self.control=control
        self.last_diagnostics={}
        self.proc=subprocess.Popen([str(ASSETS/'RouteSearch-v1.2.exe')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1,creationflags=0x08000000)
        self.answers=queue.Queue()
        def read():
            for line in self.proc.stdout:
                self.answers.put(line.strip())
            self.answers.put('ERROR:closed')
        threading.Thread(target=read,daemon=True).start()
    def request(self,text):
        self.control.check()
        self.proc.stdin.write(text+'\n');self.proc.stdin.flush()
        until=time.monotonic()+8
        while time.monotonic()<until:
            self.control.check()
            try:
                answer=self.answers.get(timeout=.03)
            except queue.Empty:
                continue
            if not answer or answer.startswith('ERROR'):
                raise RuntimeError('解盤程式異常，已停止。')
            return answer
        raise RuntimeError('解盤計算逾時，已停止。')
    def reset(self):
        self.request('RESET')
    def choose(self,board,options,skills):
        budget=900 if np.count_nonzero(board)==150 else 420
        answer=self.request(str(budget)+'|'+str(int('w' not in skills))+'|'+str(int('q' not in skills))+'|'+','.join(map(str,board.ravel())))
        parts=answer.split('|');coords=tuple(map(int,parts[0].split(',')))
        move=next((m for m in options if tuple(m[:4])==coords),None)
        if move is None:
            raise RuntimeError('計算結果與棋盤不符，已停止。')
        self.last_diagnostics={'trials':int(parts[1]),'route_value':float(parts[2]),'planned_moves':int(parts[3]),'q_samples':int(parts[4]) if len(parts)>4 else 0}
        return move,int(parts[1])
    def close(self):
        if self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=.3)
            except (OSError,subprocess.TimeoutExpired):
                self.proc.terminate()
                self.proc.wait(timeout=2)


class Runner:
    def __init__(self,event,report,game_factory=Game,search_factory=None,engine='native',existing_game=None,start_screen='home',log_root=None):
        if start_screen not in ('home','home_or_result','result'):raise ValueError('invalid starting screen')
        self.control=Control(event);self.report=report;self.game_factory=game_factory
        self.search_factory=search_factory;self.engine=engine
        self.reader=Reader();self.hud_reader=HUDReader(ASSETS)
        self.game=existing_game;self.start_screen=start_screen;self.search=None;self.directory=None;self.log=None
        self.points=0;self.count=0;self.skills=set();self.version=0;self.pending=None
        self.last_board=None;self.hud=None;self.last_hud=None;self.started=None
        self.last_image=None
        self.drag_profile='fast'
        self.log_root=Path(log_root) if log_root is not None else ROOT/'紀錄'
    def status(self,text,**more):
        self.report({'status':text,'points':self.points,'moves':self.count,**more})
    def record(self,kind,**values):
        item={'event':kind,'unix_ms':int(time.time()*1000),'version':'1.4.1','engine':self.engine,**values}
        if self.log:self.log.write(json.dumps(item,ensure_ascii=False)+'\n');self.log.flush()
    def observe(self):
        im=self.game.shot();self.last_image=im;stamp=int(time.time()*1000)
        if self.reader.is_result(im):
            self.hud=self.hud_reader.read(im,result=True,stamp=stamp)
            return 'result',im,None,[]
        if not self.reader.is_play(im):return 'other',im,None,[]
        board,bad=self.reader.board(im);self.hud=self.hud_reader.read(im,stamp=stamp)
        if self.hud['timer'].value is None or self.hud['timer'].confidence<.75 or any(v.value is None or v.confidence<.85 for v in self.hud['skills'].values()):
            self.record('observation_rejected',observation=serialize(self.hud))
            if self.directory:Image.fromarray(im).save(self.directory/'觀測拒絕.png')
            return 'uncertain',im,board,bad
        return 'board',im,board,bad
    def state(self,board):
        self.version+=1
        state=observed_state(board,self.hud,self.version)
        # Availability can only decrease within one round. A bright animation cannot restore a spent skill.
        seen={k for k,v in self.hud['skills'].items() if v.value is False}
        if not self.skills.issubset(seen):raise RuntimeError('技能狀態出現矛盾，已停止。')
        self.skills=seen
        return state
    def finish(self,im):
        # Wait for modal score animation to settle; never click Leave or Restart.
        readings=[]
        for _ in range(4):
            self.control.wait(.25);im=self.game.shot()
            if not self.reader.is_result(im):raise RuntimeError('結算畫面不穩定，已停止。')
            readings.append(self.hud_reader.read(im,result=True))
        final=readings[-1]
        score=final['score'].value if readings[-2]['score'].value==final['score'].value and min(readings[-2]['score'].confidence,final['score'].confidence)>=.75 else None
        background_score=self.hud_reader.number(im,(463,162,642,198),'result.background.hud.score',int(time.time()*1000),18000)
        last_count=int(np.count_nonzero(self.last_board)) if self.last_board is not None else None
        pending_confirmed=False;comparison=None;outcomes=[]
        if last_count is not None and final['timer'].value is not None:
            candidates=[('unchanged',last_count,set(self.skills))]
            if self.pending and self.pending['kind'] in ('MOVE','Q'):
                used=set(self.skills)
                if self.pending['kind']=='Q':used.add('q')
                candidates.append(('pending_applied',last_count-self.pending['removed'],used))
            for label,left,used in candidates:
                mask=Skills(sum(bit for key,bit in [('q',1),('w',2),('e',4)] if key not in used))
                parts=score_parts(Terminal(150,left,mask,final['timer'].value*1000,left==0),ScoreRules('floor_seconds'))
                outcomes.append({'label':label,'remaining_cells':left,'used_skills':sorted(used),'predicted_using_displayed_seconds':float(parts.total),
                    'cell_points':parts.cell_points,'skill_points':parts.skill_points,'time_points':float(parts.time_points),'matches_visible_score':score==parts.total})
            matched=[v for v in outcomes if v['matches_visible_score']]
            if len(matched)==1:
                comparison={**matched[0],'rounding_calibrated':False,'note':'Terminal-score consistency, not a subsecond rounding calibration.'}
                pending_confirmed=comparison['label']=='pending_applied'
                last_count=comparison['remaining_cells'];self.skills=set(comparison['used_skills']);self.points=comparison['cell_points']
                if pending_confirmed and self.pending['kind']=='MOVE':self.count+=1
        # The background HUD already includes settlement bonuses; it is NOT base points.
        self.record('result',observation=serialize(final),actual_final_score=score,background_hud_score=background_score.value,base_score=self.points,
            remaining_cells=last_count,pending_action=self.pending,pending_confirmed=pending_confirmed,
            used_skills=sorted(self.skills),score_comparison=comparison,conditional_outcomes=outcomes)
        if self.directory:Image.fromarray(im).save(self.directory/'結算.png')
        self.status('已到結算，自動停止。'+('畫面總分：'+format(score,',') if score is not None else '總分無法可靠讀取，請看遊戲畫面。'),finished=True,remaining=None,final_score=score)
        return 'result'
    def use_skill(self,key,board):
        if self.hud['timer'].value is None or self.hud['timer'].value<=1:
            self.control.wait(.2);return None
        before=self.hud;self.last_board=board.copy()
        if before['skills'][key].value is not True:raise RuntimeError('技能目前不可用。')
        action=Action(key.upper());self.pending={'kind':action.kind,'removed':min(5,int(np.count_nonzero(board))) if key=='q' else 0}
        Image.fromarray(self.game.shot()).save(self.directory/(key+'-before.png'))
        start=time.monotonic();self.game.key(key);self.control.wait(2.1)
        until=time.monotonic()+4
        while time.monotonic()<until:
            kind,im,actual,bad=self.observe()
            if kind=='result':return self.finish(im)
            if kind=='board' and not bad and skill_confirmed(key,before,self.hud,board,actual):
                self.skills.add(key)
                self.points+=self.pending['removed']*100
                self.record('skill',action=self.pending,before=serialize(before),after=serialize(self.hud),
                    board_before=board.tolist(),board_after=actual.tolist(),wall_ms=round((time.monotonic()-start)*1000),
                    hud_seconds_difference=self.hud['timer'].value-before['timer'].value,confirmed=True)
                Image.fromarray(im).save(self.directory/(key+'-after.png'))
                self.pending=None;self.search.reset();return None
            self.control.wait(.15)
        self.record('skill_unconfirmed',action=self.pending,before=serialize(before),after=serialize(self.hud))
        Image.fromarray(im).save(self.directory/(key+'-unconfirmed.png'))
        raise RuntimeError('無法確認 '+key.upper()+' 技能已生效，已停止。')
    def run(self):
        try:
            self.status('尋找 StarSavior…')
            if self.game is None:
                self.game=self.game_factory(self.control);self.game.activate()
            else:
                # Repeated rounds must never steal focus back after a user switch.
                self.game.check()
            self.game.pos(1280,470);self.control.wait(.2);im=self.game.shot()
            restart=self.reader.is_result(im)
            if restart and self.start_screen=='home':raise RuntimeError('目前是結算畫面。請自行按「離開」回到活動首頁，或勾選自動重開。')
            if self.start_screen=='result' and not restart:raise RuntimeError('結算畫面已改變，已停止自動重開。')
            if not restart and not self.reader.is_home(im):raise RuntimeError('請先停在案件檔案活動首頁。')
            self.directory=self.log_root/datetime.now().strftime('%Y%m%d-%H%M%S-%f');self.directory.mkdir(parents=True,exist_ok=True)
            self.log=(self.directory/'過程.jsonl').open('w',encoding='utf-8')
            self.status('準備搜尋器…',log_directory=str(self.directory.resolve()))
            self.record('session',timing=TIMING,input_profiles=DRAG_PROFILES,rounding='floor_seconds-assumed',policy='v1.2 moves; HUD time guard; shadow core',skill_probability_assumption='uniform-unverified',entry='result' if restart else 'home')
            # Warm native process before starting the game clock.
            self.search=self.search_factory(self.control) if self.search_factory else LiveSearch(self.control,ASSETS,Search(self.control) if self.engine=='baseline' else None)
            self.status('點擊重新開始，等待新棋盤…' if restart else '點擊開始遊戲，等待倒數…')
            # A final fresh observation protects against a modal change during native warmup.
            im=self.game.shot()
            if restart:
                if not self.reader.is_result(im):raise RuntimeError('結算畫面已改變，已停止自動重開。')
                self.game.click_restart()
            else:
                if not self.reader.is_home(im):raise RuntimeError('活動首頁已改變，已停止。')
                self.game.click_start()
            until=time.monotonic()+12
            while time.monotonic()<until:
                self.control.wait(.2);kind,im,board,bad=self.observe()
                # The old result may remain during restart animation. A new round
                # must first display its full board before any finish is accepted.
                if kind=='result':continue
                if kind=='board' and not bad and np.count_nonzero(board)==150:break
            else:raise RuntimeError('未看到完整棋盤，已停止。')
            Image.fromarray(im).save(self.directory/'開局.png')
            self.started=time.monotonic();failures=0;unknown_since=None;verified=None
            while time.monotonic()-self.started<165:
                # A just-confirmed board can seed the next search. A separate fresh
                # observation after every search is still mandatory before any input.
                if verified is not None and 0<=int(time.time()*1000)-self.hud['captured_unix_ms']<500:
                    self.game.check();kind,im,board,bad=verified
                else:
                    kind,im,board,bad=self.observe()
                verified=None
                if kind=='result':return self.finish(im)
                if kind!='board' or bad or not np.count_nonzero(board):
                    if unknown_since is None:unknown_since=time.monotonic()
                    if time.monotonic()-unknown_since>5:raise RuntimeError('畫面或數字無法可靠辨識，已停止。')
                    self.control.wait(.2);continue
                unknown_since=None;state=self.state(board);self.last_board=board.copy();self.last_hud=self.hud
                self.record('observation',state=state,observation=serialize(self.hud))
                options=strategy_moves(board,self.skills)
                if not options:
                    key=next((k for k in 'wq' if k not in self.skills),None)
                    if key:
                        self.status('使用 '+key.upper()+' 技能並核對畫面…')
                        if self.use_skill(key,board)=='result':return 'result'
                        continue
                    self.status('已無可消除的組合，等待結算…');self.control.wait(.25);continue
                if self.hud['timer'].value<=20 and 'e' not in self.skills:
                    self.status('使用 E 延長時間並核對倒數…')
                    if self.use_skill('e',board)=='result':return 'result'
                    continue
                if state['remaining_ms']<1200:
                    self.control.wait(.2);continue
                start=time.monotonic();move,trials=self.search.choose(board,options,self.skills,state)
                search_ms=round((time.monotonic()-start)*1000)
                kind,im,fresh,bad=self.observe()
                if kind=='result':return self.finish(im)
                if kind=='uncertain':
                    # No input during a transient unreadable HUD; discard this search and observe again.
                    self.control.wait(.15);continue
                if kind!='board' or bad:raise RuntimeError('搜尋後畫面無法驗證，已停止。')
                refreshed=self.state(fresh)
                if not revalidate(state,refreshed,move[:4],minimum_ms=2200 if self.drag_profile=='slow' else 1200):continue
                self.record('decision',action={'kind':'MOVE','rect':move[:4]},state_version=state['state_version'],
                    refreshed_state=refreshed,search_wall_ms=search_ms,native=getattr(self.search,'last_diagnostics',{}))
                expected=board.copy();a,b,c,d=move[:4];expected[a:c+1,b:d+1]=0
                before=self.hud;start=time.monotonic();self.pending={'kind':'MOVE','rect':move[:4],'removed':move[4]}
                self.game.drag(move,profile=self.drag_profile)
                input_ms=round((time.monotonic()-start)*1000)
                self.control.wait(DRAG_PROFILES[self.drag_profile]['settle'])
                confirm_start=time.monotonic();timeout=confirm_start+3.5;polls=0;matching_frames=0
                while True:
                    kind,im,actual,bad=self.observe();polls+=1
                    if kind=='result':return self.finish(im)
                    matched=kind=='board' and not bad and np.array_equal(expected,actual)
                    matching_frames=matching_frames+1 if matched else 0
                    old_score=before['score'];new_score=self.hud['score']
                    score_confirmed=(old_score.value is not None and new_score.value is not None
                        and min(old_score.confidence,new_score.confidence)>=.75
                        and new_score.value-old_score.value==move[4]*100)
                    # Early animation frames can hide selected digits. In fast mode,
                    # require the correct score delta or two matching board frames.
                    if matched and (self.drag_profile!='fast' or score_confirmed or matching_frames>=2):
                        self.points+=move[4]*100;self.count+=1;failures=0
                        self.record('move',action=self.pending,before=serialize(before),after=serialize(self.hud),
                            wall_ms=round((time.monotonic()-start)*1000),input_ms=input_ms,
                            confirmation_ms=round((time.monotonic()-confirm_start)*1000),confirmation_polls=polls,
                            drag_profile=self.drag_profile,confirmation_evidence='board_and_score' if score_confirmed else 'stable_board' if matching_frames>=2 else 'board',confirmed=True)
                        verified=(kind,im,actual,bad)
                        self.pending=None;self.status('正在解盤 · 已驗證本次消除',remaining=int(np.count_nonzero(actual)),routes=trials);break
                    if time.monotonic()>timeout:
                        Image.fromarray(im).save(self.directory/'動作未確認.png')
                        if kind=='board' and not bad and np.array_equal(board,actual):
                            failures+=1;self.search.reset();self.pending=None
                            if failures>=3:raise RuntimeError('連續三次拖曳未消除，已停止。')
                            previous=self.drag_profile
                            self.drag_profile={'fast':'standard','standard':'slow','slow':'slow'}[previous]
                            self.record('input_fallback',previous=previous,current=self.drag_profile,reason='unchanged_board',failures=failures)
                            self.status('這次未消除，改用較慢速度重試…');break
                        raise RuntimeError('棋盤出現預期外變化，已停止。')
                    self.control.wait(.06 if self.drag_profile=='fast' else .15)
            raise RuntimeError('本局超過預期時間，已停止。')
        except BaseException as exc:
            self.record('stop',reason=str(exc),pending=self.pending)
            if self.directory and self.last_image is not None:Image.fromarray(self.last_image).save(self.directory/'停止.png')
            raise
        finally:
            try:
                if self.game:self.game.release()
            finally:
                try:
                    if self.search:self.search.close()
                finally:
                    if self.log:self.log.close()
