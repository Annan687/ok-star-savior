"""Profile-driven event navigation, sharing claims, sweeps and orbital draws."""
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from .activity import ACTIVITIES, CURRENT_EVENT_KIND
from .vision import Text


@lru_cache(maxsize=16)
def activity_logo(name):
    path = Path(__file__).resolve().parent.parent / 'assets' / 'activities' / name
    return cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)


def logo_targets(v, name, area):
    """Search the observed region, never a card index. Reject separate matches."""
    template = activity_logo(name)
    frame = cv2.cvtColor(cv2.resize(v.frame, (1600, 900)), cv2.COLOR_BGR2GRAY)
    x, y, r, b = [int(n*s) for n, s in zip(area, (1600, 900, 1600, 900))]
    patch = frame[y:b, x:r]
    h, w = template.shape
    if patch.shape[0] < h or patch.shape[1] < w:
        return []
    scores = cv2.matchTemplate(patch, template, cv2.TM_CCOEFF_NORMED)
    result = []
    for _ in range(3):
        _, score, _, (left, top) = cv2.minMaxLoc(scores)
        if score < .90:
            break
        result.append(Text('活動標誌', (x+left)/1600, (y+top)/900, w/1600, h/900))
        scores[max(0, top-h//2):top+h//2+1, max(0, left-w//2):left+w//2+1] = -1
    return result


class ActivityFlows:
    def configured_home(self, v, kind):
        profile = ACTIVITIES[kind]
        if not (v.has('事件', area=(.08, 0, .28, .13), contains=False)
                and v.has('襲擊進度', area=profile['progress_area'], contains=False)
                and sum(v.has(label, area=area, contains=False)
                        for label, area in profile['links'].items()) >= 2):
            return False
        return len(logo_targets(v, profile['home_logo'], profile['home_logo_area'])) == 1

    def tap_activity_home(self, kind, label):
        area = ACTIVITIES[kind]['links'][label]
        def ready(v):
            if not self.resolve_event_home(v, kind):
                return False
            if not v.find(label, area=area, contains=False):
                token = self.reread_claim_button(v, area, (label,))
                if token is not None:
                    v.items.append(token)
            return v.one(label, area=area, required=False) is not None
        v = self.event_wait(ready, f'活動首頁的{label}入口尚未穩定')
        self.click(v.one(label, area=area))

    def activity_assault(self, kind=CURRENT_EVENT_KIND):
        profile = ACTIVITIES[kind]
        if not self.open_event(kind):
            return '事件未開放，略過活動襲擊'
        if self.event_tickets(self.see()) == 0:
            return '活動免費票券已用完'
        self.tap_activity_home(kind, '襲擊')
        result = self.event_sweep(profile['stage'], profile['layout'])
        self.click(Text('返回活動首頁', .038, .05, .01, .025))
        self.event_wait(lambda v: self.resolve_event_home(v, kind), '掃蕩後未回到活動首頁')
        return result

    def activity_missions(self, kind=CURRENT_EVENT_KIND):
        if not self.open_event(kind):
            return '事件未開放，略過活動任務'
        self.tap_activity_home(kind, '任務')
        self.claim_event_missions()
        self.tap('特殊任務', area=(.46, .20, .59, .30))
        self.claim_event_missions()
        self.close((.81, .20, .85, .26), light_min=ACTIVITIES[kind]['mission_close_light'])
        self.event_wait(lambda v: self.resolve_event_home(v, kind), '領獎後未回到活動首頁')
        return '活動每日、點數及特殊任務獎勵已檢查'

    def activity_orbital(self, kind=CURRENT_EVENT_KIND):
        self._orbital_kind = kind
        try:
            if not self.orbital_board(self.see()):
                if not self.open_event(kind):
                    return '事件未開放，略過環形鏈路'
                self.tap_activity_home(kind, '環形鏈路')
            self.event_wait(self.orbital_board, '環形鏈路盤面未載入')
            self.tap('活動任務', area=(.58, .20, .66, .29))
            self.claim_event_missions()
            self.close((.81, .20, .85, .26), light_min=ACTIVITIES[kind]['mission_close_light'])
            draws, balance = self.orbital_draw_all()
            self.close()
            self.event_wait(lambda v: self.resolve_event_home(v, kind), '環形鏈路結束後未回到活動首頁')
            return f'環形鏈路任務已檢查；完成全部抽取{draws}次，餘額顯示{balance}票'
        finally:
            self.__dict__.pop('_orbital_kind', None)
