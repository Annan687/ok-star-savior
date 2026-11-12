"""Profile-driven event navigation, sharing claims, sweeps and orbital draws."""
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from .activity import ACTIVITIES, CURRENT_ASSAULT_KINDS, CURRENT_EVENT_KIND
from .policy import NeedsReview
from .vision import Text


EVENT_ASSAULT_CLOSED = '事件未開放，略過活動襲擊'


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
        labels = profile.get('home_labels')
        if not v.has('事件', '事件?', area=(.08, 0, .28, .13), contains=False):
            return False
        if 'progress_area' in profile and not v.has(
                '襲擊進度', area=profile['progress_area'], contains=False):
            return False
        if labels is not None:
            ready = all(v.has(label, area=area, contains=False) for label, area in labels.items())
        else:
            ready = sum(v.has(label, area=area, contains=False)
                        for label, area in profile['links'].items()) >= 2
        if not ready:
            return False
        return len(logo_targets(v, profile['home_logo'], profile['home_logo_area'])) == 1

    def tap_activity_home(self, kind, label):
        profile = ACTIVITIES[kind]
        position = profile.get('fixed_links', {}).get(label)
        if position is not None:
            self.event_wait(lambda v: self.resolve_event_home(v, kind), f'活動首頁的{label}入口尚未穩定')
            self.click(Text(label, *position, 0, 0))
            return
        area = profile['links'][label]
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
            return EVENT_ASSAULT_CLOSED
        if (not profile.get('read_tickets_on_stage')
                and not self.task.config.get('襲擊自動推進', False)
                and self.event_tickets(self.see()) == 0):
            return '活動免費票券已用完'
        self.tap_activity_home(kind, profile.get('assault_link', '襲擊'))
        if profile.get('stage_heading'):
            self.event_wait(lambda v: self.assault_stage_page(v, profile['stage'], profile['layout']),
                            f"{profile['name']}的關卡頁尚未載入")
        result = self.event_assault(profile['stage'], profile['layout'])
        self.click(Text('返回活動首頁', .038, .05, .01, .025))
        self.event_wait(lambda v: self.resolve_event_home(v, kind), '襲擊結束後未回到活動首頁')
        return result

    def current_activity_assaults(self):
        results, failures = [], []
        for index, kind in enumerate(CURRENT_ASSAULT_KINDS):
            name = ACTIVITIES[kind]['name']
            try:
                result = self.activity_assault(kind)
                # The global Event menu is disabled; there is no second
                # entry to search. A missing individual card raises instead.
                if index == 0 and result == EVENT_ASSAULT_CLOSED:
                    return result
                results.append(f'{name}：{result}')
            except NeedsReview as exc:
                failures.append(f'{name}：{exc}')
                # Another event has its own tickets. Continue only from a
                # recognized navigation page, never a result or submit modal.
                if index + 1 < len(CURRENT_ASSAULT_KINDS):
                    state = self.event_navigation_state(self.see())
                    if state not in ('list', 'stage', 'onslaught', *ACTIVITIES):
                        failures.append('畫面尚未返回可確認的活動頁，未切換下一個活動')
                        break
        if failures:
            raise NeedsReview('；'.join([*results, *failures]))
        return '；'.join(results)

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
        if ACTIVITIES[kind].get('orbital_enabled') is False:
            return '本期活動不執行環形鏈路'
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
