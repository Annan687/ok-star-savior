"""The user's authorized low-power battle warning, scoped to its full dialog."""
import cv2
import numpy as np

from .vision import Text


_TITLE = ('入場警告', (.285, .283, .350, .325))
_BODY = (
    ('目前編制的隊伍戰鬥力不足。', (.415, .435, .580, .470)),
    ('真的要進行戰鬥嗎？', (.440, .471, .560, .504)),
)
_TODAY = ('今日不再顯示', (.472, .599, .540, .635))
_CANCEL = ('取消', (.403, .666, .450, .711))
_CONFIRM = ('確認', (.552, .666, .598, .711))
_CHECKBOX = Text('今日不再顯示勾選框', 733/1600, 545/900, 17/1600, 17/900)


class AssaultWarningFlows:
    def assault_power_warning(self, v):
        """Recognize the entire known low-power warning, never any Confirm UI."""
        v.assault_power_confirm = None
        # Establish the dialog from its title, or both complete body lines
        # before rereading another missing label. A generic white popup alone
        # cannot authorize these reads or a confirmation.
        def known(spec):
            label, area = spec
            return len(v.find(label, area=area, contains=False)) == 1
        if not (known(_TITLE) or all(known(spec) for spec in _BODY)):
            return False
        patch = v.crop((.255, .273, .746, .641))
        if not patch.size:
            return False
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        if np.mean((hsv[:, :, 1] < 40) & (hsv[:, :, 2] > 215)) < .80:
            return False
        found = []
        for label, area in (_TITLE, *_BODY, _TODAY, _CANCEL, _CONFIRM):
            hits = v.find(label, area=area, contains=False)
            if len(hits) > 1:
                return False
            token = hits[0] if hits else self.reread_claim_button(v, area, (label,))
            if token is None:
                return False
            found.append(token)
        if not all(v.enabled(token) for token in found[-2:]):
            return False
        v.assault_power_confirm = found[-1]
        return True

    def assault_power_checkbox_state(self, v):
        """Return checked/unchecked only for the complete dialog and box shape."""
        if not self.assault_power_warning(v):
            return None
        frame = cv2.resize(v.frame, (1600, 900))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        # The bottom/right may be occluded by the cursor immediately after a
        # click. The three independent visible edges still identify this box.
        borders = (gray[545:547, 735:748].min(axis=0),
                   gray[548:560, 733:735].min(axis=1),
                   gray[548:552, 748:750].min(axis=1))
        if any(np.mean(edge < 175) < .80 for edge in borders):
            return None
        blue = ((hsv[:, :, 0] >= 90) & (hsv[:, :, 0] <= 120)
                & (hsv[:, :, 1] > 100) & (hsv[:, :, 2] > 140))
        white = (hsv[:, :, 1] < 40) & (hsv[:, :, 2] > 215)
        fill = float(blue[548:560, 735:748].mean())
        # Require both light arms of the check mark as well as blue fill;
        # a blue hover glow or a solid colored square is not a checked box.
        light = ((frame[:, :, 0] > 210) & (frame[:, :, 1] > 170)
                 & (frame[:, :, 2] > 100))
        check = (light[552:557, 735:740].mean() > .25
                 and light[550:554, 743:747].mean() > .25)
        if fill > .35 and check:
            return 'checked'
        if fill < .03 and white[549:559, 736:747].mean() > .90:
            return 'unchecked'
        return None

    def confirm_assault_power_warning(self):
        """Check today's suppression and confirm once; caller waits for battle."""
        def ready(v):
            v.assault_power_check = self.assault_power_checkbox_state(v)
            return v.assault_power_check is not None
        page = self.event_wait(ready, '襲擊戰力警告或今日不再顯示狀態未確認；未確認出戰',
                               stability_key=lambda v: v.assault_power_check)
        if page.assault_power_check == 'unchecked':
            self.click(_CHECKBOX)
            self.task.move_relative(.60, .77)
        page = self.event_wait(
            lambda v: self.assault_power_checkbox_state(v) == 'checked',
            '襲擊戰力警告的今日不再顯示尚未勾選；未重點或確認出戰')
        self.task.log_info('依使用者設定，已勾選戰力不足警告的今日不再顯示，確認出戰一次')
        self.click(page.assault_power_confirm)
