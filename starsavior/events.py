"""Observed September events; eligibility comes from the selected sweep button."""
import re
import time

from .policy import NeedsReview, roman_value
from .vision import Text, View, norm, BOTTOM

ONSLAUGHT = ("封閉的心象", "異形的攻勢", "虛假的契約")


class EventFlows:
    def event_wait(self, predicate, description, seconds=18):
        deadline = time.monotonic() + seconds
        stable = 0
        while time.monotonic() < deadline:
            v = self.see()
            stable = stable + 1 if predicate(v) else 0
            if stable >= 3:
                return v
            self.task.sleep(.35)
        raise NeedsReview(description)

    @staticmethod
    def event_home(v, kind):
        if kind == "onslaught":
            return all(v.has(name, area=(.04, .4, .36, .76), contains=False) for name in ONSLAUGHT)
        return (v.has("襲擊", area=(.78, .4, .97, .52), contains=False)
                and v.has("環形鏈路", area=(.75, .48, .96, .59))
                and v.has("任務", "任務昌", "任務目", area=(.78, .61, .95, .72), contains=False))

    def open_event(self, kind):
        v = self.see()
        if self.event_home(v, kind):
            return True
        # The four-square Event shortcut keeps the active event subpage.
        # Leave recognized subpages through their observed back hierarchy.
        for _ in range(3):
            state = self.event_navigation_state(v)
            if state not in ("stage", "onslaught", "gray"):
                break
            self.click(Text("返回活動列表上一層", .038, .055, .01, .025))
            v = self.event_wait(lambda page: self.event_navigation_state(page) not in (None, state),
                                "活動子頁返回後尚未穩定，未重複返回")
            if self.event_home(v, kind):
                return True
        if self.event_navigation_state(v) != "list":
            if self.menu("事件") is False:
                return False
        def destination(v):
            return not self.is_menu(v) and (self.event_home(v, kind)
                                           or self.event_navigation_state(v) == "list")
        v = self.event_wait(destination, "事件列表尚未載入")
        if self.event_home(v, kind):
            return True
        v = self.event_wait(lambda page: len(self.event_card_targets(page, kind)) == 1,
                            f"無法確認{'激戰委託' if kind == 'onslaught' else '灰色研究'}活動入口")
        targets = self.event_card_targets(v, kind)
        self.click(targets[0])
        self.event_wait(lambda v: self.event_home(v, kind), "活動首頁尚未載入")
        return True

    def event_card_targets(self, v, kind):
        if self.event_navigation_state(v) != "list":
            return []
        if kind == "onslaught":
            targets = v.find("ONSLAUGHT", "QNSLAUGHT", area=(.35, .2, .95, .8))
        else:
            # This title is split across three lines by OCR. Require both
            # distinct words on the same card, not a guessed card index.
            targets = []
            for t in v.find("AStudy", area=(.35, .2, .95, .8)):
                gray = any(abs(g.cx-t.cx) < .07 and 0 < g.cy-t.cy < .2
                           for g in v.find("Gray", area=(.35, .2, .95, .82)))
                if not gray:
                    area = (max(.35, t.cx-.08), t.cy+.035,
                            min(.95, t.cx+.08), min(.82, t.cy+.16))
                    gray = self.reread_claim_button(v, area, ("Gray",)) is not None
                if gray:
                    targets.append(t)
        return targets

    def event_navigation_state(self, v):
        if self.is_menu(v):
            return None
        if self.event_home(v, "onslaught"):
            return "onslaught"
        if self.event_home(v, "gray"):
            return "gray"
        if (v.has("燭光廣場", area=(.08, 0, .28, .13))
                and v.has("事件", area=(.04, .8, .23, .97), contains=False)):
            return "list"
        if (v.has("事件", area=(.08, 0, .28, .13), contains=False)
                and not v.has("掃蕩次數", area=(.7, .7, .98, .93))
                and v.has("掃蕩戰鬥", "掃蕩戰門", area=(.74, .84, .96, .92), contains=False)
                and any(self.event_rows(v, stage, layout) for stage, layout in
                        [*((name, "column") for name in ONSLAUGHT), ("名偵探消失的世界", "grid")])):
            return "stage"
        return None

    def event_local_text(self, v, area):
        import cv2
        image = cv2.resize(v.crop(area), None, fx=3, fy=3)
        return View(image, self.task.ocr(frame=image, threshold=.8)).items

    def event_tickets(self, v):
        found = v.count(3, area=(.555, .025, .607, .10), required=False)
        if found:
            return found[1][0]
        # Isolate the digits when the ticket icon or neighboring currency
        # merged with the fraction. Never strip an apparent leading digit.
        from .policy import fraction
        values = [fraction(t.text, 3) for t in self.event_local_text(v, (.575, .04, .602, .079))]
        values = [p[0] for p in values if p is not None]
        if len(values) != 1:
            raise NeedsReview("活動免費票券數辨識不明確")
        return values[0]

    @staticmethod
    def event_rows(v, stage, layout):
        area = (.10, .15, .70, .85) if layout == "grid" else (.31, .13, .68, .78)
        rows = [t for t in v.within(area) if EventFlows.stage_label(t, stage)]
        return sorted(rows, key=lambda t: (round(t.cy/.04), t.cx), reverse=True)

    # Access the shared parser without introducing an Engine import cycle.
    @staticmethod
    def stage_label(token, stage):
        from .engine import Engine
        return Engine.stage_label(token, stage)

    @staticmethod
    def event_row_selected(v, row, layout):
        import numpy as np
        x = (.335 if row.cx < .38 else .65) if layout == "grid" else .60
        patch = v.crop((x, row.cy+.032, x+.016, row.cy+.044))
        return bool(patch.size and np.mean(patch.min(axis=2) > 130) > .8)

    def event_selected_level(self, v, stage, row=None, layout=None):
        if row is not None and layout == "column":
            # The header can lose strokes (III -> I). Read the large Arabic
            # number of the highlighted card instead of reporting that guess.
            area = (.276, row.cy-.025, .31, row.cy+.065)
            numbers = [int(t.key) for t in self.event_local_text(v, area) if t.key.isdecimal()]
            return numbers[0] if len(numbers) == 1 and 1 <= numbers[0] <= 99 else None
        headers = [t for t in v.within((.73, .16, .98, .28)) if self.stage_label(t, stage)]
        levels = [roman_value(t.key[len(norm(stage)):]) for t in headers]
        if len(levels) == 1 and levels[0]:
            return levels[0]
        headers = self.event_local_text(v, (.742, .19, .973, .255))
        levels = [roman_value(t.key[len(norm(stage)):]) for t in headers if self.stage_label(t, stage)]
        return levels[0] if len(levels) == 1 and levels[0] else None

    def select_event_stage(self, stage, layout):
        v = self.event_wait(lambda v: len(self.event_rows(v, stage, layout)) > 0,
                            f"未辨識到 {stage} 關卡列表")
        rows = self.event_rows(v, stage, layout)
        for old in rows:
            v = self.see()
            matches = [t for t in self.event_rows(v, stage, layout)
                       if abs(t.cx-old.cx) < .06 and abs(t.cy-old.cy) < .025]
            if len(matches) != 1:
                raise NeedsReview("活動關卡列表已變動，未沿用舊位置")
            row = matches[0]
            self.click(row)
            v = self.event_wait(lambda v: self.event_row_selected(v, row, layout)
                                and self.event_selected_level(v, stage, row, layout) is not None,
                                "未確認活動選中關卡與難度")
            previous, stable = None, 0
            for _ in range(20):
                v = self.see()
                sweep = v.one("掃蕩戰鬥", "掃蕩戰門", area=(.74, .84, .96, .92), required=False)
                state = v.enabled(sweep) if sweep and self.event_row_selected(v, row, layout) else None
                stable = stable+1 if state is not None and state == previous else 0
                previous = state
                if stable >= (3 if state else 5):
                    break
                self.task.sleep(.35)
            else:
                raise NeedsReview("活動掃蕩按鈕狀態未穩定，未選較低關卡")
            # Only a stable disabled button permits trying a lower stage.
            # Missing OCR remains unknown and never means unavailable.
            if state:
                return self.event_selected_level(v, stage, row, layout)
        raise NeedsReview("目前可見活動關卡沒有可用掃蕩")

    def event_sweep(self, stage, layout):
        before = self.event_tickets(self.see())
        if before == 0:
            return "活動免費票券已用完"
        level = self.select_event_stage(stage, layout)
        self.tap("掃蕩戰鬥", area=(.74, .84, .96, .92), enabled=True)
        self.expect("掃蕩次數", area=BOTTOM)
        self.tap("MAX", area=(.89, .82, .95, .91))
        intended = before
        def ready(v):
            if not v.has("掃蕩次數", area=(.8, .78, .9, .85)):
                return False
            button = v.one("開始掃蕩", area=(.76, .91, .9, .98), required=False)
            if button is None or not v.enabled(button):
                return False
            maximum = v.one("MAX", area=(.89, .82, .95, .91), required=False)
            return maximum is not None and v.max_is_gray(maximum)
        v = self.event_wait(ready, "活動掃蕩數量未確認，未提交")
        self.click(v.one("開始掃蕩", area=(.76, .91, .9, .98)))
        self.rewards(require_reward=True, return_when=lambda v: self.sweep_page(v, stage))
        after = self.event_tickets(self.see())
        if before-after != intended:
            raise NeedsReview(f"活動票券變化不符：{before}→{after}，預期使用{intended}；未重試")
        return f"{stage} {level} 掃蕩{intended}次，剩{after}/3"

    def onslaught(self):
        target = self.task.config.get("激戰委託關卡", "略過")
        if target == "略過":
            return "未選激戰委託關卡，略過"
        if target not in ONSLAUGHT:
            raise NeedsReview("未知激戰委託關卡")
        if not self.open_event("onslaught"):
            return "事件未開放，略過激戰委託"
        if self.event_tickets(self.see()) == 0:
            return "激戰委託免費票券已用完"
        self.tap(target, area=(.04, .4, .36, .76))
        return self.event_sweep(target, "column")

    def event_claim_button(self, v):
        # The download icon is often OCR'd as 山 or と. This scoped label is
        # allowed only inside a recognized event mission modal.
        if not v.has("每日任務", "特殊任務", area=(.36, .20, .59, .30), contains=False):
            return None
        hits = [t for t in v.within((.72, .70, .84, .79))
                if t.key in (norm("一鍵領取"), norm("山一鍵領取"), norm("と一鍵領取"))]
        if len(hits) > 1:
            raise NeedsReview("活動一鍵領取有多個候選，未點擊")
        if hits:
            return hits[0]
        # Exclude the download icon; re-read only the four-letter label.
        return self.reread_claim_button(v, (.757, .710, .825, .776))

    def claim_event_missions(self):
        for _ in range(4):
            v, button = self.wait_claim_ready(self.event_claim_button,
                "活動任務尚未載入完整一鍵領取按鈕")
            if not v.enabled(button):
                return
            self.click(button)
            self.wait_claim_change(v, self.event_claim_button)
        raise NeedsReview("活動一鍵領取超過正常次數")

    def gray_assault(self):
        if not self.open_event("gray"):
            return "事件未開放，略過活動襲擊"
        if self.event_tickets(self.see()) == 0:
            return "活動免費票券已用完"
        self.tap("襲擊", area=(.78, .4, .97, .52))
        result = self.event_sweep("名偵探消失的世界", "grid")
        self.click(Text("返回灰色研究", .038, .05, .01, .025))
        self.event_wait(lambda v: self.event_home(v, "gray"), "掃蕩後未回到灰色研究首頁")
        return result

    def gray_missions(self):
        if not self.open_event("gray"):
            return "事件未開放，略過活動任務"
        self.tap("任務", "任務昌", "任務目", area=(.78, .61, .95, .72))
        self.claim_event_missions()
        self.tap("特殊任務", area=(.46, .20, .59, .30))
        self.claim_event_missions()
        self.close((.81, .20, .85, .26))
        self.event_wait(lambda v: self.event_home(v, "gray"), "領獎後未回到灰色研究首頁")
        return "活動每日、點數及特殊任務獎勵已檢查"

    @staticmethod
    def orbital_board(v):
        draw = v.find("全部抽取", area=(.82, .91, .90, .97), contains=False)
        refresh = v.find("更新賓果盤", area=(.83, .91, .96, .97), contains=False)
        return (not v.has("每日任務", area=(.36, .20, .59, .30), contains=False)
                and not v.has("REWARD", "LINK", area=(.30, .30, .66, .62), contains=False)
                and v.has("灰色研究環形鏈路", area=(.04, .10, .24, .19))
                and v.has("活動任務", area=(.58, .20, .66, .29), contains=False)
                and ((len(draw) == 1 and not refresh)
                     or (len(refresh) == 1 and not draw
                         and v.has("賓果盤完成獎勵", area=(.81, .21, .91, .27), contains=False))))

    def orbital_tokens(self, v):
        tokens = [t for t in v.within((.916, .14, .96, .19)) if re.fullmatch(r"[\d,]+", t.key)]
        if not tokens and self.orbital_board(v):
            # The ticket icon can extend the full-frame box outside the counter.
            tokens = [t for t in self.event_local_text(v, (.918, .14, .96, .18))
                      if re.fullmatch(r"[\d,]+", t.key)]
        if len(tokens) != 1:
            raise NeedsReview("環形鏈路票券數不明確")
        return int(tokens[0].key.replace(",", ""))

    @staticmethod
    def orbital_draw_cost(v):
        single = [t for t in v.within((.77, .91, .80, .98)) if t.key.isdecimal()]
        costs = [t for t in v.within((.915, .91, .96, .98)) if re.fullmatch(r"[\d,]+", t.key)]
        if len(single) != 1 or single[0].key != "10" or len(costs) != 1:
            raise NeedsReview("環形鏈路抽取費用未確認，未提交")
        return int(costs[0].key.replace(",", ""))

    def orbital_round(self, v):
        rounds = [re.fullmatch(r"([1-9]\d*)LINK", t.key)
                  for t in v.within((.675, .21, .74, .27))]
        rounds = [int(m[1]) for m in rounds if m]
        if len(rounds) == 1:
            return rounds[0]
        if not rounds and v.has("ILINK", area=(.675, .21, .74, .27), contains=False):
            # First-round 1 LINK is sometimes read as I LINK; re-read pixels.
            digits = [t.key for t in self.event_local_text(v, (.680, .218, .692, .255))
                      if re.fullmatch(r"[1-9]", t.key)]
            if digits == ["1"]:
                return 1
        raise NeedsReview("環形鏈路盤數不明確，未更新盤面")

    def orbital_refresh(self, v):
        button = v.one("更新賓果盤", area=(.83, .91, .96, .97))
        if not self.orbital_board(v) or not v.enabled(button):
            raise NeedsReview("環形鏈路更新按鈕尚未就緒")
        before = self.orbital_tokens(v)
        round_before = self.orbital_round(v)
        self.click(button)
        # Observed: one click, no confirmation and no cost. Never repeat an
        # uncertain refresh; require the next round and unchanged balance.
        def refreshed(page):
            if (not self.orbital_board(page)
                    or page.has("更新賓果盤", area=(.83, .91, .96, .97), contains=False)):
                return False
            try:
                return (self.orbital_round(page) == round_before + 1
                        and self.orbital_tokens(page) == before)
            except NeedsReview:
                return False
        self.event_wait(refreshed, "更新賓果盤後盤數或票券未確認；未重試")
        self.task.log_info(f"環形鏈路已更新：第{round_before}盤→第{round_before + 1}盤；剩餘{before}票")

    def orbital_draw_all(self):
        total = 0
        for _ in range(20):
            v = self.event_wait(self.orbital_board, "環形鏈路盤面尚未穩定")
            # Refresh even when the last draw exhausted all tokens.
            if v.has("更新賓果盤", area=(.83, .91, .96, .97), contains=False):
                self.orbital_refresh(v)
                continue
            before = self.orbital_tokens(v)
            button = v.one("全部抽取", area=(.82, .91, .90, .97))
            if before < 10:
                if v.enabled(button):
                    raise NeedsReview("環形鏈路票券與抽取按鈕狀態不符")
                return total, before
            cost = self.orbital_draw_cost(v)
            if not (10 <= cost <= before and cost % 10 == 0 and v.enabled(button)):
                raise NeedsReview("環形鏈路全部抽取費用或按鈕狀態不符，未提交")
            self.click(button)
            # The observed game submits immediately, shows LINK animation,
            # then REWARD. Never navigate away or resubmit during that gap.
            self.rewards(require_reward=True, return_when=self.orbital_board)
            after = self.orbital_tokens(self.event_wait(self.orbital_board, "抽取後尚未返回盤面"))
            if before-after != cost:
                raise NeedsReview(f"環形鏈路票券變化不符：{before}→{after}，預期{cost}；未重試")
            total += cost
        raise NeedsReview("環形鏈路抽取達到本輪上限，仍有票券待檢查")

    def orbital(self):
        if not self.orbital_board(self.see()):
            if not self.open_event("gray"):
                return "事件未開放，略過環形鏈路"
            self.tap("環形鏈路", area=(.75, .48, .96, .59), contains=True)
        self.event_wait(self.orbital_board, "環形鏈路盤面未載入")
        self.tap("活動任務", area=(.58, .20, .66, .29))
        self.claim_event_missions()
        self.close((.81, .20, .85, .26))
        spent, balance = self.orbital_draw_all()
        self.close()
        self.event_wait(lambda v: self.event_home(v, "gray"), "環形鏈路結束後未回到活動首頁")
        return f"環形鏈路任務已檢查；全部抽取消耗{spent}票，剩餘{balance}票"
