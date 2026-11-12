"""Assault preparation and real battles; submissions are never retried."""
import time

import cv2
import numpy as np

from .policy import NeedsReview
from .assault_vision import auto_battle_state, auto_battle_target
from .assault_warning import AssaultWarningFlows


_START = (.76, .90, .96, .98)
_LEAVE = (.74, .87, .96, .97)
_AUTO_FORMATION = (.55, .91, .67, .97)


class AssaultBattleFlows(AssaultWarningFlows):
    @staticmethod
    def check_assault_interruption(v):
        if (v.has('通知', area=(.25, .30, .38, .38), contains=False)
                and v.has('服务器已更新。', area=(.35, .43, .65, .55), contains=False)):
            raise NeedsReview('伺服器已更新，襲擊流程中斷；未將通知判為戰敗，也未重打或掃蕩')

    def configured_assault_party(self):
        specified = self.task.config.get('襲擊指定隊伍', False)
        if type(specified) is not bool:
            raise NeedsReview('襲擊指定隊伍必須為勾選設定')
        if not specified:
            return None
        choice = self.task.config.get('襲擊出戰隊伍', '隊伍1')
        choices = tuple(f'隊伍{n}' for n in range(1, 7))
        if choice not in choices:
            raise NeedsReview('未知襲擊出戰隊伍；未切換或開始戰鬥')
        return choices.index(choice) + 1

    def assault_formation(self, v, stage, level):
        # Selection was already confirmed before entering preparation. Keep
        # page/control evidence here without rechecking the small stage title.
        if (self.is_menu(v)
                or not v.has('編制', area=(.12, .035, .18, .09), contains=False)
                or not v.has('事件', area=(.74, .16, .81, .20), contains=False)):
            return False
        if (v.one('開始戰鬥', area=_START, required=False) is None
                or not v.has('全部解除', area=(.44, .91, .55, .97), contains=False)):
            return False
        if v.has('自動編制', area=_AUTO_FORMATION, contains=False):
            return True
        return (v.has('自動編', area=_AUTO_FORMATION, contains=False)
                and self.reread_claim_button(v, _AUTO_FORMATION, ('自動編制',)) is not None)

    def assault_party(self, v, number):
        if number not in range(1, 7):
            return None
        area = (.045, .275 + (number-1)*.077, .080, .343 + (number-1)*.077)
        hits = v.find(str(number), area=area, contains=False)
        if len(hits) > 1:
            return None
        return hits[0] if hits else self.reread_claim_button(v, area, (str(number),))

    @staticmethod
    def assault_party_selected(v, token):
        if token is None:
            return False
        # The selected number sits on a white disk; the other five are dark.
        patch = v.crop((token.cx-.012, token.cy-.020, token.cx+.012, token.cy+.020))
        if not patch.size:
            return False
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        return bool(np.mean((hsv[:, :, 1] < 40) & (hsv[:, :, 2] > 215)) > .55)

    def prepare_assault_party(self, stage, level):
        number = self.configured_assault_party()
        def ready(v):
            self.check_assault_interruption(v)
            return (self.assault_formation(v, stage, level)
                    and (number is None or self.assault_party(v, number) is not None))
        v = self.event_wait(ready, '襲擊編制頁／隊伍選項尚未確認；未開始戰鬥', seconds=90)
        if number is not None:
            token = self.assault_party(v, number)
            if not self.assault_party_selected(v, token):
                self.click(token)
        def selected(page):
            self.check_assault_interruption(page)
            if not self.assault_formation(page, stage, level):
                return False
            if number is not None and not self.assault_party_selected(page, self.assault_party(page, number)):
                return False
            button = page.one('開始戰鬥', area=_START, required=False)
            count = self.read_event_tickets(page, formation=True)
            return button is not None and page.enabled(button) and count is not None and count > 0
        return self.event_wait(selected, '未確認所選隊伍、剩餘免費票或開始戰鬥按鈕；未出戰', seconds=30)

    def assault_battle_result(self, v, stage, level):
        # Both observed result screens have a right-hand result and Leave.
        # The user explicitly requested no stage-name/Roman-numeral check:
        # those small glyphs are unreliable and do not determine the outcome.
        won = v.has('VICTORY', area=(.70, .18, .98, .38), contains=False)
        lost = v.has('DEFEAT', area=(.70, .18, .98, .38), contains=False)
        if won == lost:
            return None
        leave = v.one('離開', area=_LEAVE, required=False)
        if leave is None or not v.enabled(leave):
            return None
        return won, leave

    def wait_assault_battle(self, stage, level):
        deadline = time.monotonic() + 600
        auto_deadline = time.monotonic() + 180
        previous = None
        stable = 0
        toggled = False
        auto_verified = False
        warning_handled = False
        warning_deadline = None
        while time.monotonic() < deadline:
            page = self.see()
            self.check_assault_interruption(page)
            warning = self.assault_power_warning(page)
            result = None if warning else self.assault_battle_result(page, stage, level)
            auto = None if warning or auto_verified or result is not None else auto_battle_state(page)
            key = ('warning',) if warning else ('result', result[0]) if result is not None else ('auto', auto) if auto else None
            stable = stable + 1 if key is not None and key == previous else int(key is not None)
            previous = key
            if warning:
                if stable >= 3 and not warning_handled:
                    self.confirm_assault_power_warning()
                    warning_handled = True
                    warning_deadline = time.monotonic() + 60
                    auto_deadline = time.monotonic() + 180
                    previous, stable = None, 0
                elif warning_handled and time.monotonic() >= warning_deadline:
                    raise NeedsReview('襲擊戰力警告已確認，但仍未離開警告畫面；未再次確認或出戰')
                elif not warning_handled and time.monotonic() >= auto_deadline:
                    raise NeedsReview('襲擊戰力警告尚未穩定，未確認出戰')
                self.task.sleep(.4)
                continue
            if result is not None and stable >= 3:
                return result
            if not auto_verified and result is None:
                if auto == 'on' and stable >= 3:
                    auto_verified = True
                    self.task.log_info('襲擊自動戰鬥已確認開啟')
                elif auto == 'off' and stable >= 3 and not toggled:
                    self.click(auto_battle_target(page))
                    # Mouse hover lights the icon blue even when it is off.
                    # Move away without clicking, then inspect the true state.
                    self.task.move_relative(.70, .12)
                    toggled = True
                    previous, stable = None, 0
                    auto_deadline = time.monotonic() + 60
                if not auto_verified and time.monotonic() >= auto_deadline:
                    raise NeedsReview('襲擊已提交，但自動戰鬥開啟狀態未確認；未再次點擊或出戰')
            self.task.sleep(.4)
        raise NeedsReview('襲擊戰鬥等待超過10分鐘，未確認勝敗；未重打或掃蕩')

    def fight_event_stage(self, stage, layout, level):
        # Validate options before navigating away from the stage list.
        party = self.configured_assault_party()
        def ready(page):
            self.check_assault_interruption(page)
            selected = [row for row in self.assault_rows(page, stage, layout)
                        if self.event_row_selected(page, row, layout)]
            if len(selected) != 1 or not self.assault_selected_state(page, stage, layout, selected[0]):
                return False
            return page.assault_selection == (level, 'advance')
        page = self.event_wait(ready, '襲擊關卡或進入狀態已改變；未出戰')
        self.click(page.one('進入', area=(.74, .92, .96, .99)))
        page = self.prepare_assault_party(stage, level)
        choice = f'隊伍{party}' if party is not None else '目前隊伍'
        self.task.log_info(f'襲擊第{level}關：{choice}開始戰鬥（僅提交一次）')
        self.click(page.one('開始戰鬥', area=_START))
        won, leave = self.wait_assault_battle(stage, level)
        self.task.log_info(f'襲擊第{level}關：{"勝利" if won else "失敗"}，離開結算')
        self.click(leave)
        def returned(v):
            self.check_assault_interruption(v)
            return self.assault_stage_page(v, stage, layout)
        self.event_wait(returned,
                        '襲擊結算已離開，但尚未回到關卡列表；未再次出戰或掃蕩', seconds=90)
        return won
