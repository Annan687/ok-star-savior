import json
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path

from .policy import NeedsReview, Result, is_free, roman_value
from .vision import View, Text, norm, FULL, TOP, BOTTOM, CENTER, RIGHT, LEFT


class Engine:
    def __init__(self, task):
        self.task = task
        self.clicks = 0
        self.started = time.monotonic()
        self.results = []
        self.current = "啟動"
        self.folder = Path("runs") / time.strftime("%Y%m%d-%H%M%S")
        self.folder.mkdir(parents=True, exist_ok=True)
        driver = getattr(getattr(task, "executor", None), "interaction", None)
        if driver is not None:
            import ok
            window = getattr(driver, "hwnd_window", None)
            (self.folder / "runtime.json").write_text(json.dumps({
                "python": sys.executable, "framework": ok.__file__,
                "driver": type(driver).__name__,
                "game_foreground": window.is_foreground() if window is not None else None,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        if driver is not None and callable(getattr(driver, "begin_trace", None)):
            driver.begin_trace(self.folder)

    def see(self):
        self.task.next_frame()
        frame = self.task.frame.copy()
        if frame.shape[1] < 1280 or not 1.70 < frame.shape[1]/frame.shape[0] < 1.90:
            raise NeedsReview("請使用橫向遊戲視窗，寬度至少 1280；目前擷取比例不符")
        boxes = self.task.ocr(frame=frame, threshold=.65)
        self.view = View(frame, boxes)
        self.view.repair_icon_counts(lambda patch: self.task.ocr(frame=patch, threshold=.9))
        return self.view

    def save(self, detail):
        self.task.screenshot(f"star_savior_{self.current}")
        payload = {"step": self.current, "detail": detail,
                   "ocr": [asdict(t) for t in self.view.items] if hasattr(self, "view") else []}
        (self.folder / "last-screen.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, status, detail):
        self.results.append(Result(self.current, status, detail))
        self.task.info_set(self.current, f"{status}：{detail}")
        (self.folder / "result.json").write_text(json.dumps(
            [asdict(r) for r in self.results], ensure_ascii=False, indent=2), encoding="utf-8")

    def click(self, token):
        if self.clicks >= 450 or time.monotonic()-self.started > 1800:
            raise NeedsReview("已達本輪點擊／時間上限，請檢查是否有重複流程")
        self.clicks += 1
        # Match okww's coordinate-click hold time. Its BaseWWTask.click
        # overrides the framework's 20 ms default with 200 ms.
        self.task.click_relative(token.cx, token.cy, down_time=.2, after_sleep=.8)
        return self.see()

    def tap(self, *labels, area=FULL, contains=False, optional=False, enabled=False):
        end = time.monotonic() + 10
        while True:
            v = self.see()
            if optional or v.find(*labels, area=area, contains=contains) or time.monotonic() >= end:
                break
            self.task.sleep(.35)
        token = v.one(*labels, area=area, contains=contains, required=not optional)
        if token is None:
            return False
        if enabled and not v.enabled(token):
            return False
        self.click(token)
        return True

    def expect(self, *labels, area=FULL, seconds=8):
        end = time.monotonic()+seconds
        while True:
            v = self.see()
            if v.has(*labels, area=area):
                return v
            if time.monotonic() >= end:
                raise NeedsReview(f"畫面未到達：{' / '.join(labels)}")
            self.task.sleep(.4)

    def rewards(self, maximum=18, wait_initial=False):
        seen = 0
        quiet = 0
        pending = 0
        while seen < maximum:
            v = self.see()
            if (v.has("月卡商品", area=CENTER, contains=False)
                    and v.has("REWARD", area=CENTER, contains=False)
                    and v.has("30天星光石補給", "30天意志力補給", area=BOTTOM)):
                # This login reward has no continue prompt. The demonstrated
                # blank area below the supply rows dismisses it.
                self.click(Text("月卡獎勵下方空白", .495, .85, .01, .01))
                seen += 1
                quiet = pending = 0
                continue
            prompt = v.one("點擊以繼續", "點擊以確認", "點擊已確認", "點擊以跳過",
                           area=(.2, .70, .8, 1), required=False)
            level_up = any(re.fullmatch(r"LEVEL.?UP", t.key)
                           for t in v.within((.4, .20, .6, .40)))
            if prompt is None:
                if level_up or v.has("REWARD", "VICTORY", "DEFEAT", "LEVELUP", "升級", area=CENTER, contains=False):
                    pending += 1
                    quiet = 0
                    if pending >= 20:
                        raise NeedsReview("獎勵動畫後仍未出現繼續提示")
                elif seen or wait_initial:
                    quiet += 1
                    if quiet >= 5:
                        return seen
                else:
                    return seen
                self.task.sleep(.35)
                continue
            if not level_up and not v.has("REWARD", "VICTORY", "DEFEAT", "獲得獎勵", "LEVELUP", "升級", "獎勵"):
                raise NeedsReview("看見繼續提示，但未能確認獎勵或戰鬥結果頁")
            self.click(prompt)
            seen += 1
            quiet = pending = 0
        raise NeedsReview("獎勵畫面連續超過 18 張，停止檢查")

    @staticmethod
    def is_menu(v):
        return sum(v.has(s, area=(.50, .18, .95, .9)) for s in
                   ("付費商店", "燭光廣場", "地區派遣", "製作工坊")) >= 3

    @staticmethod
    def is_lobby(v):
        return all(v.has(s, area=LEFT) for s in ("管理", "總部", "觀測")) and not Engine.is_menu(v)

    @staticmethod
    def page_name(v):
        if Engine.is_menu(v):
            return "四格選單"
        if Engine.is_lobby(v):
            return "大廳"
        labels = ("限時據點", "燭光廣場", "探索委託", "討伐委託", "星際迴廊",
                  "策略戰", "信件", "好友", "地區派遣", "啟示錄商店", "付費商店", "公會")
        matches = [s for s in labels if v.has(s, area=(.07, .015, .38, .13), contains=False)]
        return matches[0] if len(matches) == 1 else "其他頁面"

    def close(self, area=(.75, .01, .99, .14)):
        v = self.see()
        self.click(v.close_icon(area))

    def menu(self, destination):
        self.rewards()
        for _ in range(5):
            v = self.see()
            if self.is_menu(v):
                if destination == "好友":
                    # Handshake icon in the verified menu's right-hand rail.
                    token = Text("好友入口", .935, .418, .01, .015)
                elif destination == "通行證":
                    token = v.one("支援通行證", area=(.39, .1, .52, .45), contains=True)
                else:
                    token = v.one(destination, area=(.52, .20, .94, .86))
                self.click(token)
                self.rewards()
                current = self.see()
                if self.is_menu(current) and current.has(destination, area=(.07, .015, .38, .13), contains=False):
                    self.click(Text("關閉已在目的地的選單", .27, .36, .01, .01))
                return
            icon = v.menu_icon()
            if icon:
                self.click(icon)
                continue
            # Nested overlays must be closed, not clicked through.
            if v.has("購買商品", "跳過戰鬥", "刷新對戰列表", "緊急支援", area=CENTER):
                self.tap("取消", area=CENTER)
                continue
            regions = [(.73, .16, .89, .32), (.72, .01, .99, .13)]
            closed = False
            for region in regions:
                try:
                    x = v.close_icon(region)
                except NeedsReview:
                    continue
                self.click(x)
                closed = True
                break
            if not closed:
                raise NeedsReview(f"無法找到前往「{destination}」的四格選單或關閉圖示")
        raise NeedsReview(f"前往「{destination}」的導航超過上限")

    def plaza(self, destination):
        title_area = (.07, .015, .38, .13)
        v = self.see()
        if v.has(destination, area=title_area):
            if self.is_menu(v):
                self.click(Text("關閉四格選單", .27, .36, .01, .01))
                self.expect(destination, area=title_area, seconds=15)
            return
        if not v.has("燭光廣場", area=title_area):
            self.menu("燭光廣場")
        # Navigation may return while the loading animation is still visible.
        end = time.monotonic() + 15
        while True:
            if time.monotonic() >= end:
                raise NeedsReview(f"燭光廣場載入後仍未找到入口：{destination}")
            v = self.see()
            if self.is_menu(v):
                self.click(Text("關閉四格選單", .27, .36, .01, .01))
                continue
            if v.has(destination, area=title_area):
                return
            if v.has("燭光廣場", area=title_area):
                targets = v.find(destination, area=(.35, .18, .98, .95))
                if len(targets) > 1:
                    raise NeedsReview(f"燭光廣場的 {destination} 有多個候選")
                if len(targets) == 1:
                    self.click(targets[0])
                    self.expect(destination, area=title_area, seconds=15)
                    return
            elif v.has("探索委託", "討伐委託", "城市巡邏", "據點調查", "遺跡探索",
                       "扭曲的情感", "酷寒襲擊", "被遺忘的誓言", area=title_area):
                self.click(Text("返回上一層", .038, .055, .01, .025))
            if time.monotonic() >= end:
                raise NeedsReview(f"燭光廣場載入後仍未找到入口：{destination}")
            self.task.sleep(.4)

    def confirm(self, title, body=None):
        v = self.expect(title, area=CENTER)
        if body and not v.has(body, area=CENTER):
            raise NeedsReview(f"{title} 確認框內容不符")
        self.tap("確認", area=CENTER)

    def claim_all(self, labels=("一鍵領取",), max_claims=4):
        count = 0
        for _ in range(max_claims):
            # Task claims briefly remove/disable the button before the points
            # claim appears. Require a quiet interval before declaring done.
            for attempt in range(5):
                self.rewards()
                v = self.see()
                token = v.one(*labels, area=BOTTOM, required=False)
                if token is not None and v.enabled(token):
                    break
                if attempt < 4:
                    self.task.sleep(.4)
            else:
                return count
            before = [(t.key, round(t.cx, 2), round(t.cy, 2)) for t in v.items]
            self.click(token)
            v = self.see()
            if v.has("信件全部領取", area=CENTER):
                self.confirm("信件全部領取", "所有信件")
            self.rewards()
            v = self.see()
            after = [(t.key, round(t.cx, 2), round(t.cy, 2)) for t in v.items]
            if before == after:
                raise NeedsReview("一鍵領取後畫面沒有更新，未重複送出")
            count += 1
        raise NeedsReview("一鍵領取仍可用，超過正常領取次數")

    def select_sweep_stage(self, stage, dark_rows=False):
        # Try visible stage rows from highest downward. The enabled sweep button
        # is the game's own 3-star eligibility check, independent of star color.
        v = self.see()
        prefix = norm(stage)
        rows = []
        row_area = (.28, .14, .72, .95)
        for t in v.within(row_area):
            if t.key.startswith(prefix):
                level = roman_value(t.key[len(prefix):])
                if level is not None and (dark_rows or v.available_stage_row(t)):
                    rows.append((level, t))
        if not rows:
            raise NeedsReview(f"未辨識到 {stage} 的關卡列")
        # Do not claim highest eligibility if the visible list isn't bounded by
        # a higher unavailable stage; the normal game view opens at progression.
        # Roman numerals can lose strokes in OCR (XIII -> XI). Screen order
        # and selected-row highlight are more reliable than sorting that OCR.
        for level, old in sorted(rows, key=lambda p: p[1].cy, reverse=True):
            v = self.see()
            nearby = [t for t in v.within(row_area)
                      if t.key.startswith(prefix) and abs(t.cy-old.cy) < .025]
            if len(nearby) != 1:
                raise NeedsReview("關卡列表位置已變化，未沿用舊座標")
            token = nearby[0]
            self.click(token)
            v = self.see()
            if not v.selected_stage_row(token):
                continue
            sweep = v.one("掃蕩戰鬥", area=BOTTOM, required=False)
            if sweep and v.enabled(sweep):
                headers = [t for t in v.within((.73, .16, .97, .34))
                           if t.key.startswith(prefix)]
                selected = roman_value(headers[0].key[len(prefix):]) if len(headers) == 1 else None
                if selected is None and len(headers) == 1:
                    numbers = [t for t in v.within((.28, token.cy-.045, .34, token.cy+.06))
                               if t.key.isdecimal()]
                    if len(numbers) == 1:
                        selected = int(numbers[0].key)
                if selected is None:
                    raise NeedsReview("未能確認所選可掃蕩關卡的難度")
                return selected
        raise NeedsReview("目前可見關卡沒有可用掃蕩；需檢查更低的滿星關卡")

    def sweep(self, stage, resource="ticket", maximum=3):
        v = self.see()
        count_area = (.4, 0, .96, .16)
        if resource != "stamina":
            top, amount = v.count(maximum, area=count_area, allow_overflow=resource == "timed")
            if amount[0] == 0:
                return "次數已用完"
        if resource == "timed":
            self.select_sweep_stage(stage, dark_rows=True)
        else:
            self.select_sweep_stage(stage)
        self.tap("掃蕩戰鬥", area=BOTTOM, enabled=True)
        self.expect("掃蕩次數", "開始掃蕩", area=BOTTOM)
        self.tap("MAX", area=(.7, .7, .98, 1))
        # The user chooses the game's MAX limit, confirmed by its gray button.
        # Quantity/cost OCR is deliberately not a prerequisite for submission.
        for _ in range(10):
            v = self.see()
            max_button = v.one("MAX", area=(.7, .7, .98, 1), required=False)
            button = v.one("開始掃蕩", area=(.7, .88, .98, 1), required=False)
            if (max_button and button and v.has("掃蕩次數", area=(.7, .7, .98, 1))
                    and v.max_is_gray(max_button)):
                break
            self.task.sleep(.3)
        else:
            raise NeedsReview("點擊 MAX 後未確認按鈕變灰；未開始掃蕩")
        if not v.enabled(button):
            return "資源不足或掃蕩不可用"
        self.click(button)
        self.expect("REWARD", "點擊以繼續", seconds=15)
        self.rewards()
        return "已按 MAX 完成掃蕩並領取獎勵"

    def skip_battle(self, strategy=False):
        self.expect("跳過戰鬥", seconds=12)
        self.tap("跳過戰鬥", area=BOTTOM, enabled=True)
        if strategy:
            v = self.expect("跳過戰鬥", area=CENTER)
            if not (v.has("確定要消耗1個聖鎧鑰匙", area=CENTER)
                    and v.has("跳過該場戰鬥", area=CENTER)):
                raise NeedsReview("策略戰跳過確認未辨識到消耗 1 個聖鎧鑰匙")
            self.tap("確認", area=CENTER)
        else:
            self.confirm("跳過戰鬥", "確定要跳過")
        v = self.expect("VICTORY", "DEFEAT", seconds=30)
        won = v.has("VICTORY")
        self.rewards(wait_initial=True)
        return won

    def free_purchase(self):
        v = self.expect("購買商品", area=(.13, .16, .87, .90))
        price = v.field("總購買價格")
        if not is_free(price.text):
            self.tap("取消", area=CENTER, optional=True)
            raise NeedsReview("商品總價不是免費，已停止購買")
        self.tap("購買", area=(.3, .60, .8, .95), enabled=True)
        self.expect("REWARD", "點擊以繼續", seconds=10)
        self.rewards()
