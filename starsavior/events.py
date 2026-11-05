"""Observed September events; eligibility comes from the selected sweep button."""
import re
import time

from .policy import NeedsReview, roman_value
from .vision import Text, View, norm, BOTTOM
from .snowfield import SnowfieldFlows, SNOWFIELD_STAGE
from .activity import ACTIVITIES
from .activity_flows import ActivityFlows, logo_targets
from .assault import AssaultFlows
from .assault_battle import AssaultBattleFlows

ONSLAUGHT = ("封閉的心象", "異形的攻勢", "虛假的契約")


class EventFlows(AssaultFlows, AssaultBattleFlows, ActivityFlows, SnowfieldFlows):
    def event_wait(self, predicate, description, seconds=18, *, stability_key=None):
        deadline = time.monotonic() + seconds
        stable = 0
        previous = None
        while time.monotonic() < deadline:
            v = self.see()
            ready = predicate(v)
            key = stability_key(v) if ready and stability_key is not None else None
            stable = (stable + 1 if ready and key == previous else int(bool(ready)))
            previous = key
            if stable >= 3:
                return v
            self.task.sleep(.35)
        raise NeedsReview(description)

    @staticmethod
    def event_home(v, kind):
        if kind == "snowfield":
            return SnowfieldFlows.snowfield_home(v)
        if kind == "onslaught":
            return all(v.has(name, area=(.04, .4, .36, .76), contains=False) for name in ONSLAUGHT)
        return (v.has("襲擊", area=(.78, .4, .97, .52), contains=False)
                and v.has("環形鏈路", area=(.75, .48, .96, .59))
                and v.has("任務", "任務昌", "任務目", area=(.78, .61, .95, .72), contains=False))

    def resolve_event_home(self, v, kind):
        if (self.is_menu(v)
                or v.has("每日任務", "特殊任務", area=(.36, .20, .59, .30), contains=False)
                or v.has("REWARD", area=(.3, .2, .7, .6), contains=False)):
            return False
        if kind == "snowfield":
            return self.resolve_snowfield_home(v)
        if kind in ACTIVITIES:
            return self.configured_home(v, kind)
        if self.event_home(v, kind):
            return True
        # Establish the Gray home from its own title, not the activity list.
        # Re-read only the Chinese labels, excluding their English and icons.
        if kind != "gray" or not (
                v.has("事件", area=(.08, 0, .28, .13), contains=False)
                and v.has("AStudy", area=(.05, .55, .35, .72), contains=False)
                and v.has("Gray", area=(.08, .72, .3, .88), contains=False)
                and v.has("故事", area=(.80, .28, .94, .40), contains=False)):
            return False
        for label, area, crop in (
                ("襲擊", (.78, .4, .97, .52), (.862, .449, .902, .493)),
                ("環形鏈路", (.75, .48, .96, .59), (.814, .512, .881, .554)),
                ("任務", (.78, .61, .95, .72), (.838, .642, .872, .678))):
            if not v.has(label, area=area, contains=False):
                token = self.reread_claim_button(v, crop, (label,))
                if token is not None:
                    v.items.append(token)
        return self.event_home(v, kind)

    def tap_gray_home(self, label, area):
        def ready(page):
            if not self.resolve_event_home(page, "gray"):
                return False
            if page.one(label, area=area, required=False) is None:
                crop = {"襲擊": (.862, .449, .902, .493),
                        "環形鏈路": (.814, .512, .881, .554),
                        "任務": (.838, .642, .872, .678)}[label]
                token = self.reread_claim_button(page, crop, (label,))
                if token is not None:
                    page.items.append(token)
            return page.one(label, area=area, required=False) is not None
        v = self.event_wait(ready, f"灰色研究首頁的{label}入口尚未穩定")
        self.click(v.one(label, area=area))

    def open_event(self, kind):
        v = self.see()
        if self.resolve_event_home(v, kind):
            return True
        # The four-square Event shortcut keeps the active event subpage.
        # Leave recognized subpages through their observed back hierarchy.
        for _ in range(3):
            state = self.event_navigation_state(v)
            if state and state.startswith('orbital:'):
                self.close()
                v = self.event_wait(lambda page: self.event_navigation_state(page) not in (None, state),
                                    '環形鏈路返回後尚未穩定，未重複關閉')
                if self.resolve_event_home(v, kind):
                    return True
                continue
            if state not in ("stage", "onslaught", "gray", "snowfield", *ACTIVITIES):
                break
            self.click(Text("返回活動列表上一層", .038, .055, .01, .025))
            v = self.event_wait(lambda page: self.event_navigation_state(page) not in (None, state),
                                "活動子頁返回後尚未穩定，未重複返回")
            if self.resolve_event_home(v, kind):
                return True
        if self.event_navigation_state(v) != "list":
            if self.menu("事件") is False:
                return False
        def destination(v):
            return not self.is_menu(v) and (self.resolve_event_home(v, kind)
                                           or self.event_navigation_state(v) == "list")
        v = self.event_wait(destination, "事件列表尚未載入")
        if self.resolve_event_home(v, kind):
            return True
        v = self.event_wait(lambda page: len(self.event_card_targets(page, kind)) == 1,
                            f"無法確認{dict(onslaught='激戰委託', gray='灰色研究', snowfield='DISCORDANT DUET', **{k: p['name'] for k, p in ACTIVITIES.items()})[kind]}活動入口")
        targets = self.event_card_targets(v, kind)
        self.click(targets[0])
        self.event_wait(lambda v: self.resolve_event_home(v, kind), "活動首頁尚未載入")
        return True

    def event_card_targets(self, v, kind):
        if self.event_navigation_state(v) != "list":
            return []
        if kind in ACTIVITIES:
            return logo_targets(v, ACTIVITIES[kind]['card_logo'], (.35, .55, .95, .82))
        if kind == "snowfield":
            return self.snowfield_card_targets(v)
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
                    # After earlier cards retire this title moves left. At
                    # 900p the decorative "in" can spoil the Gray reread;
                    # retry a tighter top edge relative to the actual title.
                    # Large decorative letters can also disappear from the
                    # detector at 3x; the final 2x pass keeps the same label,
                    # confidence threshold and card-relative bounds.
                    for top, scale in ((.035, 3), (.06, 3), (.06, 2)):
                        area = (max(.35, t.cx-.08), t.cy+top,
                                min(.95, t.cx+.08), min(.82, t.cy+.16))
                        gray = self.reread_claim_button(v, area, ("Gray",), scale=scale) is not None
                        if gray:
                            break
                if not gray:
                    # The detected second title line gives tighter bounds when
                    # the decorative first line's box shifts by a few pixels.
                    # Its OCR text is not an alias: reread the complete Gray.
                    lines = [g for g in v.items if abs(g.cx-t.cx) < .07
                             and .06 < g.cy-t.cy < .17
                             and .04 < g.h < .12 and .04 < g.w < .17]
                    if len(lines) == 1:
                        g = lines[0]
                        area = (max(.35, g.x-.01), max(.2, g.y-.01),
                                min(.95, g.x+g.w+.01), min(.82, g.y+g.h+.01))
                        gray = self.reread_claim_button(v, area, ("Gray",)) is not None
                if gray:
                    targets.append(t)
        return targets

    def event_navigation_state(self, v):
        if self.is_menu(v):
            return None
        for kind in ACTIVITIES:
            if self.resolve_event_home(v, kind):
                return kind
            if self.orbital_board(v, kind=kind):
                return 'orbital:' + kind
        if self.resolve_event_home(v, "snowfield"):
            return "snowfield"
        if self.resolve_event_home(v, "onslaught"):
            return "onslaught"
        if self.resolve_event_home(v, "gray"):
            return "gray"
        if (not v.has("燭光廣場", area=(.08, 0, .28, .13))
                and v.has("事件", area=(.04, .8, .23, .97), contains=False)
                and v.has("一般", area=(.04, .8, .23, .88), contains=False)
                and (v.has("AStudy", "OVERLOAD", "ONSLAUGHT", "DISCORDANT", area=(.35, .2, .95, .8), contains=False)
                     or any(len(logo_targets(v, p['card_logo'], (.35, .55, .95, .82))) == 1
                            for p in ACTIVITIES.values()))):
            # OCR can split the heading into overlapping fragments. The two
            # navigation tabs and a known event card establish where to reread;
            # fragments alone must never authorize list navigation.
            heading = self.reread_claim_button(v, (.123, .035, .195, .095), ("燭光廣場",))
            if heading is not None:
                v.items.append(heading)
        if (v.has("燭光廣場", area=(.08, 0, .28, .13))
                and v.has("事件", area=(.04, .8, .23, .97), contains=False)):
            return "list"
        stages = [(SNOWFIELD_STAGE, "snowfield"),
                  *((p['stage'], p['layout']) for p in ACTIVITIES.values())]
        if (any(self.event_rows(v, stage, layout) for stage, layout in stages)
                and v.has("掃蕩戰鬥", area=(.74, .84, .96, .92), contains=False)
                and not v.has("事件", area=(.08, 0, .28, .13), contains=False)):
            heading = self.reread_claim_button(v, (.128, .04, .164, .082), ("事件",))
            if heading is not None:
                v.items.append(heading)
        if (v.has("事件", area=(.08, 0, .28, .13), contains=False)
                and not v.has("掃蕩次數", area=(.7, .7, .98, .93))
                and v.has("掃蕩戰鬥", "掃蕩戰門", area=(.74, .84, .96, .92), contains=False)
                and any(self.event_rows(v, stage, layout) for stage, layout in
                        [*((name, "column") for name in ONSLAUGHT), ("名偵探消失的世界", "grid"),
                         *stages])):
            return "stage"
        return None

    def event_local_text(self, v, area):
        import cv2
        image = cv2.resize(v.crop(area), None, fx=3, fy=3)
        return View(image, self.task.ocr(frame=image, threshold=.8)).items

    def event_tickets(self, v):
        for attempt in range(8):
            value = self.read_event_tickets(v)
            if value is not None:
                return value
            if attempt < 7:
                self.task.sleep(.4)
                v = self.see()
        raise NeedsReview("活動免費票券數辨識不明確（已局部重讀並等待）；未繼續操作")

    def read_event_tickets(self, v):
        # Only a whole fraction qualifies. A merged currency such as
        # '3/38,050' must be re-read from pixels, never repaired as text.
        from .policy import fraction
        def values(tokens):
            readings = [fraction(t.key, 3) for t in tokens
                        if re.fullmatch(r"\d+/\d+", t.key)]
            return [p[0] for p in readings if p is not None]
        snowfield = (any(self.resolve_event_home(v, kind) for kind in ACTIVITIES)
                     or self.resolve_event_home(v, "snowfield")
                     or bool(self.event_rows(v, SNOWFIELD_STAGE, "snowfield"))
                     or any(p['layout'] == 'snowfield' and bool(self.event_rows(v, p['stage'], p['layout']))
                            for p in ACTIVITIES.values()))
        direct = values(v.within((.575, .025, .642, .10) if snowfield else (.555, .025, .617, .10)))
        if len(direct) == 1:
            return direct[0]
        if len(direct) > 1:
            return None
        # The onslaught home resource bar places the fraction farther right
        # than the previously recorded stage/gray bar. Do not clip its last 3.
        areas = ((.593, .04, .636, .082), (.58, .04, .628, .082)) if snowfield else ((.587, .04, .616, .079),) if self.resolve_event_home(v, "onslaught") else (
            (.575, .04, .602, .079), (.587, .04, .616, .079))
        recovered = []
        for area in areas:
            readings = values(self.event_local_text(v, area))
            if len(readings) > 1:
                return None
            recovered.extend(readings)
        return recovered[0] if recovered and len(set(recovered)) == 1 else None

    @staticmethod
    def event_rows(v, stage, layout):
        area = (.10, .15, .70, .85) if layout in ("grid", "pink_grid") else (.31, .13, .68, .95 if layout == "snowfield" else .78)
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
        x = (.335 if row.cx < .38 else .65) if layout in ("grid", "pink_grid") else .60
        patch = v.crop((x, row.cy+.032, x+.016, row.cy+.044))
        if layout == 'pink_grid':
            # Unselected pink cards are also bright. Only the pale selected
            # background has low saturation; do not infer selection from stars.
            import cv2
            if not patch.size:
                return False
            hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
            return bool(np.mean((hsv[:, :, 1] < 35) & (hsv[:, :, 2] > 215)) > .8)
        return bool(patch.size and np.mean(patch.min(axis=2) > 130) > .8)

    def event_selected_level(self, v, stage, row=None, layout=None):
        if row is not None and layout in ("column", "snowfield"):
            # The header can lose strokes (III -> I). Read the large Arabic
            # number of the highlighted card instead of reporting that guess.
            area = (.276, row.cy-.025, .31, row.cy+.065)
            numbers = [int(t.key) for t in self.event_local_text(v, area) if t.key.isdecimal()]
            if not numbers and layout == "snowfield":
                digit = self.snowfield_selected_digit(v, row)
                if digit is not None:
                    return digit
            if not numbers and layout == "snowfield" and .17 < row.cy < .21:
                # Only the first visible slot: the decorative large 1 often
                # vanishes. Require its complete stage label with Roman I.
                label = self.reread_claim_button(v, (.32, .165, .432, .213), (stage + "I",))
                return 1 if label is not None else None
            if not numbers and layout == "snowfield":
                # The decorative 4 can disappear from digit OCR entirely.
                # Cross-check the highlighted row's complete title against the
                # independent right-hand title; a lone Roman suffix is unsafe.
                names = tuple(stage + suffix for suffix in
                              ("I", "II", "III", "IV", "V", "VI", "VII", "VIII"))
                label = self.reread_claim_button(v, (.32, row.cy-.025, .445, row.cy+.026), names)
                if label is not None:
                    headers = [t for t in v.within((.73, .16, .98, .28))
                               if self.stage_label(t, stage)]
                    if len(headers) == 1 and headers[0].key == label.key:
                        return roman_value(label.key[len(norm(stage)):])
            return numbers[0] if len(numbers) == 1 and 1 <= numbers[0] <= 99 else None
        headers = [t for t in v.within((.73, .16, .98, .28)) if self.stage_label(t, stage)]
        levels = [roman_value(t.key[len(norm(stage)):]) for t in headers]
        if len(levels) == 1 and levels[0]:
            return levels[0]
        headers = self.event_local_text(v, (.742, .19, .973, .255))
        levels = [roman_value(t.key[len(norm(stage)):]) for t in headers if self.stage_label(t, stage)]
        return levels[0] if len(levels) == 1 and levels[0] else None

    def snowfield_selected_digit(self, v, row):
        # On the highlighted card the numeral is dark, the emblem is light.
        # Preserve the numeral's pixels; do not infer a level from row position
        # or reinterpret a damaged Roman suffix. Two masks must agree.
        if not self.event_row_selected(v, row, "snowfield"):
            return None
        import cv2
        crop = v.crop((.282, row.cy-.014, .305, row.cy+.046))
        if not crop.size:
            return None
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        readings = []
        for cutoff in (60, 80):
            _, mask = cv2.threshold(gray, cutoff, 255, cv2.THRESH_BINARY)
            mask = cv2.copyMakeBorder(mask, 12, 12, 12, 12,
                                     cv2.BORDER_CONSTANT, value=255)
            frame = cv2.cvtColor(cv2.resize(mask, None, fx=3, fy=3), cv2.COLOR_GRAY2BGR)
            tokens = View(frame, self.task.ocr(frame=frame, threshold=.9)).items
            if len(tokens) != 1 or tokens[0].key not in tuple("12345678"):
                return None
            readings.append(int(tokens[0].key))
        return readings[0] if readings[0] == readings[1] else None

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
        for attempt in range(5):
            v, button = self.wait_claim_ready(self.event_claim_button,
                "活動任務尚未載入完整一鍵領取按鈕")
            if not v.enabled(button):
                return
            # The fourth submission may have completed the page. Observe its
            # final state before reporting the limit; never send a fifth claim.
            if attempt == 4:
                break
            self.click(button)
            # The foreground game's custom cursor/glow can cover the gray
            # claim text after a task-only claim. Move off the footer before
            # checking the update; do not treat the covered label as disabled.
            self.task.move_relative(.70, .68)
            self.wait_claim_change(v, self.event_claim_button)
        raise NeedsReview("活動一鍵領取超過正常次數")

    def gray_assault(self):
        if not self.open_event("gray"):
            return "事件未開放，略過活動襲擊"
        if (not self.task.config.get('襲擊自動推進', False)
                and self.event_tickets(self.see()) == 0):
            return "活動免費票券已用完"
        self.tap_gray_home("襲擊", area=(.78, .4, .97, .52))
        result = self.event_assault("名偵探消失的世界", "grid")
        self.click(Text("返回灰色研究", .038, .05, .01, .025))
        self.event_wait(lambda v: self.resolve_event_home(v, "gray"), "掃蕩後未回到灰色研究首頁")
        return result

    def gray_missions(self):
        if not self.open_event("gray"):
            return "事件未開放，略過活動任務"
        self.tap_gray_home("任務", area=(.78, .61, .95, .72))
        self.claim_event_missions()
        self.tap("特殊任務", area=(.46, .20, .59, .30))
        self.claim_event_missions()
        self.close((.81, .20, .85, .26))
        self.event_wait(lambda v: self.resolve_event_home(v, "gray"), "領獎後未回到灰色研究首頁")
        return "活動每日、點數及特殊任務獎勵已檢查"

    def orbital_board(self, v, kind=None):
        if ACTIVITIES.get(kind or getattr(self, '_orbital_kind', 'gray'), {}).get('orbital_enabled') is False:
            return False
        if (v.has("每日任務", area=(.36, .20, .59, .30), contains=False)
                or v.has("REWARD", "LINK", area=(.30, .30, .66, .62), contains=False)
                or not v.has("活動任務", area=(.58, .20, .66, .29), contains=False)):
            return False
        kind = kind or getattr(self, '_orbital_kind', 'gray')
        if kind in ACTIVITIES:
            profile = ACTIVITIES[kind]
            # The top-left name scrolls; this subtitle stays fixed.
            area = profile['orbital_title_area']
            title = profile['orbital_title']
            if not v.has(title, area=area, contains=False):
                if self.reread_claim_button(v, area, (title,)) is None:
                    return False
        elif not v.has("灰色研究環形鏈路", area=(.04, .10, .24, .19)):
            return False
        draw = v.find("全部抽取", area=(.82, .91, .90, .97), contains=False)
        refresh = v.find("更新賓果盤", area=(.83, .91, .96, .97), contains=False)
        if len(draw) == 1 and not refresh:
            return True
        # The refresh button replaces draw only when the board is complete.
        return len(refresh) == 1 and not draw

    def orbital_tokens(self, v):
        number = r"\d+(?:,\d{3})*"
        tokens = [t for t in v.within((.90, .14, .96, .19)) if re.fullmatch(number, t.key)]
        if len(tokens) != 1 and self.orbital_board(v):
            # Right-aligned balances grow leftwards. The old .918 crop cut
            # 130 into 30 when full-frame OCR merged the ticket icon with it.
            # The icon can also become a separate digit beside the balance.
            # Re-read the complete area instead of choosing the rightmost
            # number: a split 1 + 0 must not become a false zero balance.
            tokens = [t for t in self.event_local_text(v, (.90, .14, .96, .18))
                      if re.fullmatch(number, t.key)]
            if any(t.x <= .02 or t.x + t.w >= .98 for t in tokens):
                raise NeedsReview("環形鏈路票券數碰到裁切邊界，未採用不完整數字")
        if len(tokens) != 1:
            raise NeedsReview("環形鏈路票券數不明確")
        return int(tokens[0].key.replace(",", ""))

    def orbital_round(self, v):
        rounds = [re.fullmatch(r"([1-9]\d*)LINK", t.key)
                  for t in v.within((.675, .21, .74, .27))]
        rounds = [int(m[1]) for m in rounds if m]
        if len(rounds) == 1:
            return rounds[0]
        if not rounds and getattr(self, '_orbital_kind', None) in ACTIVITIES and self.orbital_board(v):
            # Read the complete badge: cropping only the 1 clips its stroke at
            # 720p. Do not translate the ambiguous full-frame ILINK into 1.
            badges = [re.fullmatch(r'([1-9]\d*)LINK', t.key)
                      for t in self.event_local_text(v, (.675, .21, .74, .27))]
            badges = [int(m[1]) for m in badges if m]
            if len(badges) == 1:
                return badges[0]
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
        round_before = self.orbital_round(v)
        self.click(button)
        # Observed: one click, no confirmation and no cost. Never repeat an
        # uncertain refresh; require the next round and restored draw button.
        def refreshed(page):
            if (not self.orbital_board(page)
                    or page.has("更新賓果盤", area=(.83, .91, .96, .97), contains=False)):
                return False
            try:
                return self.orbital_round(page) == round_before + 1
            except NeedsReview:
                return False
        self.event_wait(refreshed, "更新賓果盤後尚未確認下一盤；未重試")
        self.task.log_info(f"環形鏈路已更新：第{round_before}盤→第{round_before + 1}盤")

    def orbital_draw_ready(self, v):
        v.orbital_action = None
        v.orbital_balance = None
        if not self.orbital_board(v):
            return False
        if v.has("更新賓果盤", area=(.83, .91, .96, .97), contains=False):
            v.orbital_action = "refresh"
            return True
        try:
            balance = self.orbital_tokens(v)
            if balance == 0:
                v.orbital_action = "zero"
            elif v.enabled(v.one("全部抽取", area=(.82, .91, .90, .97))):
                v.orbital_action = "draw"
            v.orbital_balance = balance
            return v.orbital_action is not None
        except NeedsReview:
            return False

    def orbital_draw_all(self):
        draws = 0
        for _ in range(20):
            v = self.event_wait(self.orbital_draw_ready, "環形鏈路盤面、票數或抽取按鈕尚未就緒",
                                stability_key=lambda page: page.orbital_action)
            # Refresh even when the last draw exhausted all tokens.
            if v.has("更新賓果盤", area=(.83, .91, .96, .97), contains=False):
                self.orbital_refresh(v)
                continue
            # Reuse the reading which established this frame's action. Local
            # OCR must not turn the same confirmed frame into another state.
            balance = getattr(v, 'orbital_balance', None)
            if balance is None:
                balance = self.orbital_tokens(v)
            button = v.one("全部抽取", area=(.82, .91, .90, .97))
            if balance == 0:
                return draws, balance
            if not v.enabled(button):
                raise NeedsReview("環形鏈路票券非0，但全部抽取按鈕未開放；未提交")
            self.click(button)
            # The observed game submits immediately, shows LINK animation,
            # then REWARD. Never navigate away or resubmit during that gap.
            self.rewards(require_reward=True, return_when=self.orbital_board)
            # User policy: only zero/nonzero matters, not the exact OCR value
            # or draw cost. The next iteration still waits for a ready board.
            draws += 1
        raise NeedsReview("環形鏈路抽取達到本輪上限，仍有票券待檢查")

    def orbital(self):
        if not self.orbital_board(self.see()):
            if not self.open_event("gray"):
                return "事件未開放，略過環形鏈路"
            self.tap_gray_home("環形鏈路", area=(.75, .48, .96, .59))
        self.event_wait(self.orbital_board, "環形鏈路盤面未載入")
        self.tap("活動任務", area=(.58, .20, .66, .29))
        self.claim_event_missions()
        self.close((.81, .20, .85, .26))
        draws, balance = self.orbital_draw_all()
        self.close()
        self.event_wait(lambda v: self.resolve_event_home(v, "gray"), "環形鏈路結束後未回到活動首頁")
        return f"環形鏈路任務已檢查；完成全部抽取{draws}次，餘額顯示{balance}票"
