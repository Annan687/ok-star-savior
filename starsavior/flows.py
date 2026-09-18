"""Daily order transcribed from the user's completed demonstration.

Every spending operation requires the expected page, live availability and a
bounded amount. Unknown layouts stop the run and produce a review report.
"""
import re
import time

from .engine import Engine
from .events import EventFlows
from .policy import FARM, TIMED, NeedsReview, is_free, exact_challenge, fraction
from .vision import norm, Text, View, FULL, TOP, BOTTOM, CENTER, RIGHT, LEFT


class DailyFlows(EventFlows, Engine):
    @staticmethod
    def boot_phase(v):
        if DailyFlows.title_start_button(v) is not None:
            return None
        if v.has("STARSAVIOR", "星之救援者", area=(.25, .3, .75, .65), contains=False):
            return "等待遊戲 Logo 結束"
        if (v.has("完整性檢查", area=(.75, 0, .98, .16), contains=False)
                and (v.has("VERSION", area=(0, .88, .3, 1))
                     or v.has("正在下載", "正在載入", area=(.6, .8, 1, 1)))):
            return "等待遊戲載入資料"
        if v.has("STARSAVIOR", "星之救援者", area=(.25, .65, .75, .87), contains=False):
            return "等待 Touch to Start"
        # A newly created game window can be black even with a Steam overlay
        # in its corner. Wait only; never click black frames to advance them.
        patch = v.crop((.2, .2, .8, .8))
        if patch.size and float((patch.max(axis=2) < 20).mean()) > .995:
            return "等待遊戲畫面出現"
        return None

    def prepare_game(self, claim_login=False):
        """Boot readiness is a prerequisite, independent of selected chores."""
        v = self.see()
        if self.is_lobby(v) or self.is_menu(v):
            return
        phase = self.boot_phase(v)
        title = self.title_start_button(v)
        login_popup = v.has("LOGINBONUS", "登入獎勵", "勤紀錄", "簽到簿", "300日紀念")
        if not phase and title is None and not login_popup:
            return  # Existing in-game pages retain their own navigation rules.
        deadline = time.monotonic() + 180
        previous = None
        while title is None and not login_popup:
            if time.monotonic() >= deadline:
                raise NeedsReview(f"遊戲啟動等待逾時（180 秒）：{phase}；未開始日課")
            if phase != previous:
                self.task.info_set("目前項目", phase)
                self.task.log_info(phase)
                previous = phase
            self.task.sleep(.5)
            v = self.see()
            # Ready navigation must win over wallpaper pixels or text.
            if self.is_lobby(v) or self.is_menu(v):
                return
            phase = self.boot_phase(v) or "等待登入入口"
            title = self.title_start_button(v)
            login_popup = v.has("LOGINBONUS", "登入獎勵", "勤紀錄", "簽到簿", "300日紀念")
        self.task.info_set("目前項目", "等待登入並進入大廳")
        self.startup(claim_login=claim_login)

    def startup(self, claim_login=True):
        visited = set()
        unknown_since = None
        entered_title = False
        for _ in range(30):
            self.rewards()
            v = self.see()
            start = self.title_start_button(v)
            if start is not None:
                if entered_title:
                    raise NeedsReview("登入後又回到標題畫面，未重複送出登入")
                self.click(start)
                entered_title = True
                self.wait_for_title_transition()
                unknown_since = None
                continue
            animation_dialog = v.has("跳過動畫", "茶跳過動畫", area=(.12, .12, .5, .45), contains=False)
            if animation_dialog:
                confirm = self.animation_skip_confirmation(v)
                if confirm is not None:
                    self.click(confirm)
                    unknown_since = None
                    continue
            if (v.has("通知", area=CENTER, contains=False)
                    and v.has("30天星光石補給商品", "30天意志力補給商品", area=CENTER)
                    and v.has("是否前往購買商品以更新剩餘期限", area=CENTER)):
                unknown_since = None
                self.tap("取消", area=CENTER)
                continue
            if not animation_dialog and (self.is_lobby(v) or self.is_menu(v)):
                return "已到大廳"
            if v.has("LOGINBONUS", "登入獎勵", "勤紀錄"):
                unknown_since = None
                self.close()
            elif v.has("星穹傳送門") and v.has("全新首領登場"):
                unknown_since = None
                self.close((.86, .15, .96, .30))
            elif v.has("簽到簿", "300日紀念"):
                unknown_since = None
                if not claim_login:
                    self.close()
                    continue
                highlights = v.outline_targets((.3, .22, .95, .90))
                highlights = [t for t in highlights if not v.has("COMPLETE", area=v.around(t, t.w/2, t.h/2))]
                if len(highlights) == 1:
                    self.click(highlights[0])
                    self.expect("REWARD", "點擊以繼續")
                    self.rewards()
                else:
                    # Do not close this calendar if another event remains red.
                    tabs = v.find("簽到", "紀念", area=LEFT, contains=True)
                    red = [t for t in tabs if self.red_mark(v, v.around(t, .10, .05))]
                    unvisited = [t for t in red if t.key not in visited]
                    if unvisited:
                        target = sorted(unvisited, key=lambda t: t.cy)[0]
                        visited.add(target.key)
                        self.click(target)
                    elif red or highlights or not tabs:
                        raise NeedsReview("活動簽到的可領亮框／分頁不明確")
                    else:
                        self.close()
            else:
                # Lobby wallpapers animate on entry. Intermediate frames can
                # contain text while the actual navigation is still hidden.
                now = time.monotonic()
                if unknown_since is None:
                    unknown_since = now
                if now-unknown_since >= 15:
                    raise NeedsReview("等待大廳進場動畫約 15 秒後仍無法確認介面；請檢查是否已進入大廳")
                self.task.sleep(.5)
                continue
        raise NeedsReview("登入領取超過次數上限")

    @staticmethod
    def title_start_button(v):
        if not v.has("STARSAVIOR", "星之救援者", area=(.25, .5, .75, .87), contains=False):
            return None
        return v.one("TOUCHTOSTART", area=(.25, .75, .75, .94), required=False)

    def wait_for_title_transition(self):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            v = self.see()
            if v.items and not v.has("STARSAVIOR", "星之救援者", area=(.25, .5, .75, .87), contains=False):
                return
            self.task.sleep(.5)
        raise NeedsReview("點擊 Touch to Start 後登入等待逾時，請檢查遊戲連線或登入狀態")

    @staticmethod
    def animation_skip_confirmation(v):
        # The star emblem can merge into the title as 茶 in the supplied image.
        if not (v.has("跳過動畫", "茶跳過動畫", area=(.12, .12, .5, .45), contains=False)
                and v.has("確定要跳過動畫嗎？", "確定要跳過動畫嗎",
                          area=CENTER, contains=False)):
            return None
        cancel = v.one("取消", area=(.2, .55, .5, .85), required=False)
        confirm = v.one("確認", area=(.5, .55, .8, .85), required=False)
        if (cancel is None or confirm is None or abs(cancel.cy-confirm.cy) > .04
                or not v.enabled(confirm)):
            return None
        return confirm

    @staticmethod
    def red_mark(v, area):
        import cv2
        patch = v.crop(area)
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        mask = (((hsv[:, :, 0] < 8) | (hsv[:, :, 0] > 172)) &
                (hsv[:, :, 1] > 150) & (hsv[:, :, 2] > 170))
        # A hint for navigation only. Never sufficient to authorize a purchase.
        return mask.mean() > .015

    def open_support(self, v):
        if not self.is_lobby(v):
            raise NeedsReview("支援金需從大廳開始")
        rate = [t for t in v.within((.85, .16, .99, .33)) if re.fullmatch(r"\d+%", t.key)]
        if len(rate) > 1:
            raise NeedsReview("支援金百分比入口有多個候選")
        # Small 0% text can be missed entirely. This fixed lobby card position
        # only opens the panel; its title and free price are checked afterwards.
        self.click(rate[0] if rate else Text("支援金入口", .925, .19, .035, .04))
        self.expect("NOA支援金", "緊急支援")

    def support_location(self):
        # Reward dismissal can return directly to the lobby; wait for transition.
        for _ in range(20):
            v = self.see()
            if v.has("消耗星光石", area=CENTER):
                return "dialog", v
            if v.has("NOA支援金", "緊急支援", area=CENTER):
                return "support", v
            if self.is_lobby(v):
                return "lobby", v
            self.task.sleep(.4)
        raise NeedsReview("支援金獎勵後未返回可辨識的支援金頁或大廳")

    def support(self):
        v = self.see()
        if self.is_menu(v):
            self.click(Text("大廳空白", .32, .5, .01, .01))
            v = self.see()
        self.open_support(v)
        if self.tap("獲得獎勵", area=BOTTOM, optional=True, enabled=True):
            self.expect("點擊以繼續", "點擊以確認", "點擊已確認", "點擊以跳過", area=BOTTOM)
            self.rewards()
        location, v = self.support_location()
        if location == "lobby":
            self.open_support(v)
        elif location != "support":
            raise NeedsReview("領取支援金後出現非預期的緊急支援確認框")
        self.tap("緊急支援", area=BOTTOM)
        v = self.expect("消耗星光石", area=CENTER)
        cost = v.field("消耗星光石")
        claimed = is_free(cost.text)
        if claimed:
            self.tap("緊急支援", area=(.5, .60, .8, .88))
            self.expect("REWARD", "點擊以繼續")
            self.rewards()
        location, _ = self.support_location()
        if location == "dialog":
            self.tap("取消", area=CENTER)
            location, _ = self.support_location()
        if location == "support":
            self.close((.74, .18, .82, .32))
            location, _ = self.support_location()
        if location != "lobby":
            raise NeedsReview("支援金流程結束後未返回大廳")
        return "支援金已檢查；" + ("已領免費緊急支援" if claimed else "緊急支援已非免費，略過")

    def mail(self):
        v = self.see()
        if not self.is_lobby(v):
            raise NeedsReview("郵件入口需從大廳開始")
        # The envelope location was recorded from the demonstrated client area.
        # It only opens mail; the following title check precedes any claim.
        self.click(Text("信封", .915, .041, .01, .025))
        self.expect("信件", "沒有收到的信件")
        n = self.claim_all()
        v = self.see()
        if not v.has("沒有收到的信件"):
            raise NeedsReview("領信後未確認空信箱，請檢查剩餘郵件")
        self.close()
        for _ in range(10):
            if self.is_lobby(self.see()):
                return f"信箱已清空（領取 {n} 輪），已返回大廳"
            self.task.sleep(.4)
        raise NeedsReview("信箱已空，但關閉點擊後未返回大廳，背景輸入可能未生效")

    @staticmethod
    def friend_button(v, label):
        # The leading horizontal stroke can disappear in 900p OCR.
        # Limit the alias to its own footer button on the verified friend page.
        area = ((.65, .85, .79, .97) if label == "一鍵領取"
                else (.79, .85, .93, .97))
        return v.one(label, label[1:], area=area)

    def friend_panel(self):
        v = self.expect("好友列表", area=LEFT)
        if not v.has("好友", area=(.07, .015, .38, .13), contains=False):
            raise NeedsReview("好友列表缺少好友頁標題")
        # Both controls must be present, even when disabled. Missing OCR is
        # not evidence that today's claims or sends have finished.
        for label in ("一鍵領取", "一鍵發送"):
            self.friend_button(v, label)
        return v

    def friends(self):
        v = self.see()
        if not v.has("好友列表", area=LEFT, contains=False):
            self.menu("好友")
        results = []
        for label in ("一鍵領取", "一鍵發送"):
            v = self.friend_panel()
            token = self.friend_button(v, label)
            if not v.enabled(token):
                results.append(f"{label}目前不可用，略過")
                continue
            self.click(token)
            # Claim opens a reward overlay; send becomes disabled directly.
            # Wait for either transition, without submitting the action twice.
            for _ in range(10):
                self.rewards()
                v = self.friend_panel()
                token = self.friend_button(v, label)
                if not v.enabled(token):
                    results.append(f"{label}已完成")
                    break
                self.task.sleep(.4)
            else:
                raise NeedsReview(f"好友{label}後按鈕仍可用，未重複點擊")
        self.close()
        for _ in range(10):
            v = self.see()
            if self.is_lobby(v) or self.is_menu(v):
                return "；".join(results)
            self.task.sleep(.4)
        raise NeedsReview("好友點數處理後未返回大廳或選單")

    def free_card(self, name=None):
        v = self.see()
        hits = (v.find(name, area=(.17, .20, .98, .99), contains=True) if name else
                v.find("免費", "FREE", area=(.49, .20, .98, .99)))
        candidates = []
        for t in hits:
            area = v.around(t, .10, .16)
            if v.has("SOLDOUT", "0/1", area=area):
                continue
            if v.has("免費", "FREE", area=area):
                candidates.append(t)
        if not candidates:
            return False
        if len(candidates) != 1:
            raise NeedsReview(f"免費商品 {name} 不只一個候選")
        self.click(candidates[0])
        self.free_purchase()
        return True

    def open_special_free_tab(self):
        # Limited-time sub-tabs can disappear while the left category remains.
        # Require a loaded shop and a stable alternative tab before skipping.
        area = (.17, .08, .96, .20)
        previous = None
        stable = 0
        for _ in range(12):
            v = self.see()
            shop = (v.has("付費商店", area=TOP, contains=False)
                    and v.has("普通禮包", area=LEFT, contains=False)
                    and v.has("特別販售禮包", area=LEFT, contains=False))
            if shop and v.find("特別販售禮包", area=area, contains=False):
                target = v.one("特別販售禮包", area=area)
                self.click(target)
                self.expect("每個帳號購買", "免費裝備製作禮包", "SOLDOUT",
                            area=(.17, .20, .98, .99))
                return True
            tabs = tuple(t.key for t in v.within(area) if len(t.key) >= 3)
            loaded = shop and tabs and v.has("每個帳號購買", area=(.17, .20, .98, .99))
            stable = stable + 1 if loaded and tabs == previous else (1 if loaded else 0)
            previous = tabs if loaded else None
            self.task.sleep(.4)
        if stable >= 3:
            self.task.log_info("特別販售禮包的限時分頁目前未出現，繼續檢查普通免費禮包")
            return False
        raise NeedsReview("特別禮包分頁或商品尚未辨識完整，未判定為無免費商品")

    def paid_shop(self):
        self.menu("付費商店")
        self.tap("特別販售禮包", area=LEFT)
        special = self.open_special_free_tab()
        n = int(self.free_card("免費裝備製作禮包")) if special else 0
        self.tap("普通禮包", area=LEFT)
        for period in ("每日", "每週", "每月"):
            self.tap(f"{period}禮包", area=(.17, .08, .96, .20))
            self.expect(f"{period}購買", area=(.17, .20, .98, .99))
            n += int(self.free_card(f"{period}免費禮包"))
        detail = "已檢查特別、每日、每週與每月免費禮包" if special else "特別限時分頁未出現；已檢查每日、每週與每月免費禮包"
        return f"{detail}，領取 {n} 個"

    def apocalypse(self):
        self.menu("啟示錄商店")
        self.tap("每日商品", area=LEFT)
        self.expect("每日購買", area=(.49, .20, .98, .99))
        self.free_card()
        self.tap("觀測紀錄", area=LEFT)
        self.tap("觀測報告書", area=(.3, .06, .98, .28))
        self.expect("SALE50%", "SOLDOUT", area=(.49, .20, .98, .99))
        visited = set()
        for _ in range(3):
            v = self.see()
            candidates = []
            for token in v.find("SALE50%", area=(.49, .20, .98, .9)):
                if (round(token.cx, 1), round(token.cy, 1)) in visited:
                    continue
                area = (token.cx-.082, token.cy-.02, token.cx+.027, min(.99, token.cy+.29))
                if not v.has("SOLDOUT", "0/3", area=area):
                    candidates.append(token)
            if not candidates:
                break
            if len(candidates) > 2:
                raise NeedsReview("觀測報告書五折商品超過預期兩項")
            badge = sorted(candidates, key=lambda t: (round(t.cy, 1), t.cx))[0]
            visited.add((round(badge.cx, 1), round(badge.cy, 1)))
            self.click(Text("五折商品", badge.cx-.032, badge.cy+.16, .01, .01))
            v = self.expect("購買商品", area=CENTER)
            remaining = v.count(3, area=CENTER)[1][0]
            if remaining == 0:
                self.close((.74, .20, .80, .29))
                continue
            v.one("1", area=(.45, .56, .55, .66))
            unit_text = v.field("總購買價格").text.replace(",", "").strip()
            if not unit_text.isdigit() or int(unit_text) <= 0:
                raise NeedsReview("五折商品單次價格未辨識")
            unit = int(unit_text)
            self.tap("MAX", area=CENTER)
            v = self.see()
            price = v.field("總購買價格")
            total = re.sub(r"[, ]", "", price.text)
            if total != str(unit*remaining):
                raise NeedsReview("MAX 總價不符五折剩餘限購")
            # Both the exact discounted card and the MAX total were checked.
            self.tap("購買", area=(.3, .60, .8, .9), enabled=True)
            self.expect("REWARD", "點擊以繼續")
            self.rewards()
        return "每日免費商品與兩項五折商品已檢查"

    def exploration_overview(self):
        self.plaza("探索委託")
        v = self.see()
        # Detail pages keep the same title as the three-card overview.
        if (v.has("城市巡邏", "據點調查", "遺跡探索", area=(.07, .50, .28, .80))
                and v.has("掃蕩戰鬥", area=BOTTOM)):
            self.click(Text("返回探索委託列表", .038, .055, .01, .01))
        for name in ("城市巡邏", "據點調查", "遺跡探索"):
            self.expect(name, area=(.54, .25, .85, .86))

    def exploration(self):
        reports = []
        self.exploration_overview()
        stages = ("城市巡邏", "據點調查", "遺跡探索")
        for index, stage in enumerate(stages):
            v = self.expect(stage, area=(.54, .25, .85, .86))
            row = v.one(stage, area=(.54, .25, .85, .86))
            # Each card has its own free-ticket counter; do not use stamina.
            count = v.count(3, area=(.89, row.cy-.03, .98, row.cy+.13), required=False)
            if count is not None and count[1][0] == 0:
                reports.append(f"{stage}：免費券已用完")
                continue
            self.click(row)
            # Tiny counts over card artwork can be missed. The detail header
            # exposes the same free ticket count on a plain background.
            self.expect(stage, area=(.07, .50, .28, .80))
            reports.append(f"{stage}：{self.sweep(stage)}")
            if index < len(stages)-1:
                self.exploration_overview()
        return "；".join(reports)

    def stamina(self):
        target = self.task.config["體力刷關"]
        if target == "不消耗體力":
            return "設定為不消耗體力"
        category, stage = FARM[target]
        self.plaza(category)
        v = self.see()
        if not v.one(stage, area=(.07, .50, .28, .80), required=False):
            v = self.expect(stage, area=(.54, .25, .85, .86))
            self.click(v.one(stage, area=(.54, .25, .85, .86)))
        v = self.expect(stage, area=(.07, .50, .28, .80), seconds=15)
        if category == "探索委託":
            tickets = v.count(3, area=TOP)[1][0]
            if tickets:
                raise NeedsReview("探索免費券尚未用完，請先執行每日探索")
        return self.sweep(stage, resource="stamina")

    def cube(self):
        self.plaza("帕萊斯立方")
        v = self.expect("自動協議")
        remaining = v.count(1, area=TOP)[1][0]
        if not remaining:
            return "權限卡已用完"
        self.tap("自動協議", area=BOTTOM, enabled=True)
        self.confirm("自動協議", "帕萊斯權限卡")
        self.expect("REWARD", "點擊以繼續", seconds=15)
        self.rewards(require_reward=True, return_when=self.cube_settled)
        return "自動協議完成"

    @staticmethod
    def cube_settled(v):
        if (Engine.is_menu(v)
                or not v.has("帕萊斯立方", area=(.07, .015, .38, .13), contains=False)
                or not v.has("自動協議", area=BOTTOM, contains=False)
                or v.has("確認", "取消", "REWARD", area=CENTER, contains=False)):
            return False
        count = v.count(1, area=TOP, required=False)
        return count is not None and count[1][0] == 0

    @staticmethod
    def timed_entrance(v, stage):
        area = (.22, .22, .98, .85)
        matches = v.find(stage, area=area, contains=True)
        if len(matches) == 1:
            return matches[0]
        if matches or stage != "雷塔爾吉亞的魔術師":
            return None
        if not (v.has("限時據點", area=(.07, .015, .38, .13), contains=False)
                and v.has("阿爾克那", area=(.2, .08, .96, .2), contains=False)):
            return None
        # The card title scrolls horizontally: its tail and head can be visible
        # on the same line while the full name never occurs in a single token.
        tails = v.find("魔術師", area=area, contains=False)
        heads = v.find("雷塔爾", "雷塔爾吉亞", area=area, contains=False)
        pairs = [(tail, head) for tail in tails for head in heads
                 if abs(tail.cy-head.cy) < .018
                 and 0 <= head.x-(tail.x+tail.w) < .06
                 and head.x+head.w-tail.x < .17]
        return pairs[0][0] if len(pairs) == 1 else None

    def open_timed_entrance(self, stage):
        for _ in range(20):
            v = self.see()
            token = self.timed_entrance(v, stage)
            if token is not None:
                self.click(token)
                # Card fragments identify only the entrance. The destination
                # must expose the full stage name in its detail header.
                self.expect(stage, area=(.73, .14, .98, .35))
                return
            self.task.sleep(.5)
        raise NeedsReview(f"未能確認限時據點入口：{stage}（名稱可能正在捲動）")

    def timed(self):
        target = self.task.config["限時據點關卡"]
        if target == "略過":
            return "設定為略過"
        category, stage = TIMED[target]
        if category == "晨星綻放石":
            stage = "現成歡樂68號"
        self.plaza("限時據點")
        if self.see().has(stage, area=(.73, .14, .98, .35)):
            return self.sweep(stage, resource="timed")
        self.tap(category, area=(.2, .08, .96, .3))
        v = self.see()
        if not v.count(3, area=TOP, allow_overflow=True)[1][0]:
            return "今日票券已用完"
        if category == "晨星綻放石":
            self.tap("進入", area=(.25, .22, .98, .97), contains=True)
            self.expect(stage)
        else:
            self.open_timed_entrance(stage)
        return self.sweep(stage, resource="timed")

    def corridors(self):
        results = []
        for name in ("太陽迴廊", "月亮迴廊", "星辰迴廊"):
            self.plaza("星際迴廊")
            v = self.corridor_overview()
            row = v.one(name, area=RIGHT)
            area = (.88, row.cy, .98, row.cy+.08)
            if v.has("CLOSED", area=area):
                results.append(f"{name}未開放")
                continue
            remaining = v.count(3, area=area)[1][0]
            if not remaining:
                results.append(f"{name}次數已用完")
                continue
            self.click(row)
            for _ in range(3):
                v = self.see()
                selected = v.one(name, area=RIGHT, required=False)
                if selected and v.enabled(selected):
                    break
                self.task.sleep(.5)
                v = self.corridor_overview()
                self.click(v.one(name, area=RIGHT))
            else:
                raise NeedsReview(f"{name} 未顯示選取高亮，未進入")
            self.tap("進入", area=BOTTOM)
            self.expect(name, area=(.80, .24, .96, .40))
            for _ in range(remaining):
                v = self.see()
                before = v.count(3, area=(.65, .70, .98, 1))[1][0]
                if not before:
                    break
                self.tap("進入", area=BOTTOM, enabled=True)
                won = self.skip_battle()
                if not won:
                    results.append(f"{name}本次失敗，停止該迴廊")
                    break
                after = self.see().count(3, area=(.65, .70, .98, 1))[1][0]
                if after != before-1:
                    raise NeedsReview("迴廊剩餘次數未按預期減少")
            else:
                results.append(f"{name}完成")
        return "；".join(results)

    def corridor_overview(self):
        # The page title appears before the entrance animation finishes.
        # Wait for the actual cards, not just the title at the top left.
        previous = None
        for _ in range(30):
            v = self.see()
            if all(v.one(name, area=RIGHT, required=False) is not None for name in
                   ("太陽迴廊", "月亮迴廊", "星辰迴廊")):
                positions = tuple((round(v.one(name, area=RIGHT).cx, 2),
                                   round(v.one(name, area=RIGHT).cy, 2))
                                  for name in ("太陽迴廊", "月亮迴廊", "星辰迴廊"))
                if positions == previous:
                    return v
                previous = positions
            elif v.has("編制條件", "編制條件：", "編制條件:", "建議戰鬥力", area=(.77, .32, .98, .52)):
                self.click(Text("返回迴廊列表", .038, .055, .01, .01))
                previous = None
            self.task.sleep(.5)
        raise NeedsReview("星際迴廊載入後仍未辨識到完整的太陽／月亮／星辰入口")

    def strategy_keys(self, v):
        count = v.count(6, area=TOP, required=False)
        if count is not None:
            return count[1][0]
        # At 900p the icon and plus button can merge into OCR such as 0%6+.
        # Re-read the isolated digits, never replace '%' with '/' or guess zero.
        if not (v.has("策略戰", area=TOP, contains=False)
                and v.has("對戰列表", area=TOP, contains=False)):
            raise NeedsReview("策略戰鑰匙重讀缺少頁面標題")
        import cv2
        patch = v.crop((.63, .035, .661, .085))
        readings = self.task.ocr(frame=cv2.resize(patch, None, fx=2, fy=2), threshold=.9)
        if len(readings) == 1 and re.fullmatch(r"\d+\s*/\s*6", readings[0].name.strip()):
            value = fraction(readings[0].name, 6)
            if value is not None:
                return value[0]
        raise NeedsReview("策略戰鑰匙放大重讀仍不明確")

    def strategy_screen(self, *labels, area=FULL, seconds=15):
        # Promotion may appear after the battle reward handler has returned.
        for _ in range(3):
            v = self.expect(*labels, "晉級", area=area, seconds=seconds)
            if self.strategy_promotion(v):
                self.rewards(wait_initial=True)
                continue
            if v.has("晉級", area=(.4, .23, .6, .36), contains=False):
                raise NeedsReview("策略戰晉級畫面尚未辨識完整")
            return v
        raise NeedsReview("策略戰晉級後未回到對戰列表")

    def strategy(self):
        v = self.see()
        if self.strategy_promotion(v):
            self.rewards(wait_initial=True)
            v = self.strategy_screen("週聯賽獎勵", "防禦紀錄資訊", "對戰列表")
        if not v.has("週聯賽獎勵", "防禦紀錄資訊", "對戰列表"):
            self.menu("聖鎧")
            v = self.expect("策略戰")
            entry = v.one("策略戰", contains=True)
            if v.has("正在結算中", area=v.around(entry, .12, .12)):
                return "策略戰正在結算，暫無法挑戰；鑰匙未使用"
            # The text footer did not open the card in the live client;
            # anchor to its label and click the illustrated body above it.
            self.click(Text("策略戰卡片", entry.cx-.005, entry.cy-.25, .01, .01))
        refreshes = 0
        for _ in range(35):
            v = self.strategy_screen("週聯賽獎勵", "防禦紀錄資訊", "對戰列表", "重新挑戰", "挑戰")
            if v.has("防禦紀錄資訊", area=CENTER):
                if not (v.has("戰鬥結果現況", area=CENTER)
                        and v.has("勝利次數", area=CENTER)
                        and v.has("戰敗次數", area=CENTER)):
                    raise NeedsReview("防禦紀錄通知內容尚未辨識完整")
                self.tap("確認", area=CENTER)
                continue
            if v.has("週聯賽獎勵"):
                if not v.has("重新配置週聯賽段位"):
                    raise NeedsReview("策略戰結算獎勵內容尚未辨識完整")
                self.tap("確認", area=BOTTOM)
                self.rewards()
                continue
            before = self.strategy_keys(v)
            if before == 0:
                return "鑰匙已用完"
            targets = [t for t in v.within((.5, .22, .97, .98)) if exact_challenge(t.text)]
            targets = sorted([t for t in targets if v.enabled(t)], key=lambda t: t.cy)
            if targets:
                self.click(targets[0])
                self.skip_battle(strategy=True)
                if self.strategy_keys(self.strategy_screen("對戰列表")) != before-1:
                    raise NeedsReview("策略戰後未確認鑰匙扣除")
                continue
            # Check the lower part before deciding every opponent was tried.
            self.task.scroll_relative(.83, .72, -3)
            self.task.sleep(.5)
            v = self.see()
            if any(exact_challenge(t.text) and v.enabled(t) for t in v.within(RIGHT)):
                continue
            if refreshes >= 10:
                return "已達本輪刷新上限，仍有鑰匙待處理"
            # This is navigation to a reviewed confirmation, not a purchase.
            self.click(Text("刷新列表", .887, .138, .012, .025))
            v = self.expect("刷新對戰列表", area=CENTER)
            if v.has("不足", "0/10", area=CENTER):
                self.tap("取消", area=CENTER)
                return "刷新資源／次數不足，仍有鑰匙待處理"
            # User authorized free and gold refresh, even on timer. Verify a
            # paid icon against the actual gold icon in the top resource bar.
            confirm = v.one("確認", area=CENTER)
            if confirm.cy >= .68:
                top_gold = [t for t in v.within((.69, .015, .77, .12))
                            if re.fullmatch(r"[\d.,]+[KMB]?", t.key)]
                costs = [t for t in v.within((.38, .48, .75, .68))
                         if re.fullmatch(r"[\d,]+", t.key)]
                if len(top_gold) != 1 or len(costs) != 1 or not v.same_currency(top_gold[0], costs[0]):
                    raise NeedsReview("刷新費用未確認為黃金，未提交")
            elif v.has("星光石", "消耗", "費用", area=(.27, .45, .77, .65)):
                raise NeedsReview("免費刷新版型出現費用，未提交")
            self.confirm("刷新對戰列表", "連勝")
            refreshes += 1
        raise NeedsReview("策略戰超過處理上限")

    def event(self):
        if self.task.config.get("活動名稱", "灰色研究") == "灰色研究":
            return self.gray_assault()
        if not self.open_legacy_event():
            return "事件入口未開放，略過活動襲擊"
        v = self.expect("襲擊")
        if v.count(3, area=(.54, 0, .64, .15))[1][0] == 0:
            result = "活動票券已用完"
        else:
            self.tap("襲擊", contains=False)
            # Event names change: derive the prefix from the selected header.
            v = self.expect("掃蕩戰鬥")
            rows = [t for t in v.within(RIGHT) if re.search(r"[IVX]+$", t.key)]
            prefixes = {re.sub(r"[IVX]+$", "", t.key).strip() for t in rows}
            if len(prefixes) != 1:
                raise NeedsReview("活動襲擊關卡名稱不明確")
            result = self.sweep(prefixes.pop())
            self.click(Text("返回活動", .032, .043, .015, .03))
        self.expect("襲擊", "任務")
        return result

    def open_legacy_event(self):
        if self.menu("事件") is False:
            return False
        if not self.see().has("襲擊"):
            name = self.task.config["活動名稱"]
            aliases = (name, "TheWitchsVeil", "TheWitch'sVeil") if name == "魔女的帷幕" else (name,)
            self.tap(*aliases, contains=True)
        self.expect("襲擊", "任務")
        return True

    def event_missions(self):
        if self.task.config.get("活動名稱", "灰色研究") == "灰色研究":
            return self.gray_missions()
        if not self.open_legacy_event():
            return "事件入口未開放，略過活動任務"
        self.tap("任務")
        self.claim_all()
        return "活動任務與點數獎勵已檢查"

    def missions(self):
        self.menu("任務")
        for label in ("每日任務", "每週任務"):
            self.tap(label, area=LEFT)
            self.claim_all(require_button=True)
        return "每日及每週的任務／點數獎勵已檢查"

    def dispatch_claim_button(self, v):
        claim = self.claim_button(v)
        if claim is not None and .83 < claim.cx < .96 and claim.cy > .87:
            return claim
        return self.reread_claim_button(v, (.84, .89, .95, .95))

    def dispatch_ready(self):
        previous = None
        stable = 0
        for _ in range(30):
            v = self.see()
            counter = v.count(area=(.4, .86, .57, 1), required=False)
            page_ready = (not self.is_menu(v)
                     and v.has("地區派遣", area=(.07, .015, .38, .13), contains=False)
                     and v.has("地區派遣資訊", area=(.4, .10, .6, .23), contains=False)
                     and (v.has("派遣完成", "派遣中", "領取獎勵", "派遣",
                                area=(.4, .20, .98, .86), contains=False)
                          or any(re.fullmatch(r"派遣中[口〇○◯O0]?", t.key)
                                 for t in v.within((.83, .2, .96, .86))))
                     and counter is not None)
            claim = self.dispatch_claim_button(v) if page_ready else None
            if page_ready and claim is not None:
                state = (counter[1], v.enabled(claim), round(claim.cx, 2), round(claim.cy, 2))
                stable = stable + 1 if state == previous else 1
                previous = state
                if stable >= 3:
                    return v, claim
            else:
                stable = 0
                previous = None
            self.task.sleep(.4)
        missing = "右下角一鍵領取文字仍無法確認" if page_ready and claim is None else "完整頁面、派遣次數或列表狀態尚未穩定"
        raise NeedsReview(f"地區派遣：{missing}；未點擊或判定已領完")

    def dispatch(self):
        self.menu("地區派遣")
        v, claim = self.dispatch_ready()
        if not v.enabled(claim):
            return "目前沒有已完成派遣可領"
        self.click(claim)
        self.expect("派遣完成", "重新派遣")
        self.tap("重新派遣", area=BOTTOM)
        v = self.expect("派遣中")
        if v.one("重新派遣", required=False):
            raise NeedsReview("重新派遣後仍停留獎勵頁")
        return "已領取並沿用原隊伍重新派遣"

    def guild(self):
        self.menu("公會")
        self.expect("REWARD", "公會商店", seconds=15)
        self.rewards()
        # OCR can join all three bottom navigation buttons into one token.
        self.expect("公會商店", area=(.5, .88, .98, 1))
        self.click(Text("公會商店", .798, .939, .01, .01))
        v = self.expect("星光石", "金幣支援箱")
        star = v.one("星光石", area=(.15, .25, .6, .65), contains=True, required=False)
        # Purchased items move to the end. Gold becomes the first card once
        # today's starlight is sold out; don't require its off-screen name.
        if star is None and not v.has("金幣支援箱", area=(.15, .25, .26, .65)):
            raise NeedsReview("公會商品列表未確認，未購買")
        if star and not v.has("SOLDOUT", "0/1", area=v.around(star, .11, .18)):
            self.click(star)
            v = self.expect("購買商品", area=CENTER)
            if not v.has("星光石", area=CENTER):
                raise NeedsReview("公會商品名稱不符")
            price = v.field("總購買價格")
            if price.key != "10":
                raise NeedsReview("公會星光石價格不符已示範的 10 活動證明")
            self.tap("購買", area=(.3, .60, .8, .95), enabled=True)
            self.expect("REWARD", "點擊以繼續")
            self.rewards()
        self.close((.80, .15, .90, .28))
        self.tap("公會捐獻")
        for name in ("黃金", "公會活動證明"):
            for _ in range(3):
                v = self.expect("公會捐獻")
                label = v.one(name, area=(.2, .25, .62, .65), contains=True)
                column = (label.cx-.075, .5, label.cx+.075, .85)
                remaining = v.count(3, area=column)[1][0]
                if remaining == 0:
                    break
                button = self.donation_button(v, column, name)
                if not v.enabled(button):
                    break
                self.click(button)
                self.rewards()
                updated = False
                for _ in range(15):
                    v = self.see()
                    try:
                        updated = v.count(3, area=column)[1][0] == remaining-1
                    except NeedsReview:
                        pass
                    if updated:
                        break
                    self.task.sleep(.3)
                if not updated:
                    raise NeedsReview("捐獻後剩餘次數未減少")
        self.close((.74, .15, .88, .32))
        self.tap("公會任務", area=BOTTOM, contains=True)
        self.claim_all(require_button=True)
        return "公會商店、黃金／活動證明捐獻及任務已檢查"

    @staticmethod
    def donation_button(v, column, name):
        area = (column[0], .70, column[2], .85)
        button = v.one("捐獻", area=area)
        price = v.field("捐獻", area=area)
        # The gold coin icon can be recognized as © or a bullet. The heading and
        # its own footer are already checked; never select the starlight card.
        if not re.fullmatch(r"[^\w,]*\d[\d,]*", price.key):
            raise NeedsReview(f"{name} 捐獻費用按鈕辨識不明確")
        return button

    def passes(self):
        self.menu("通行證")
        self.claim_all(labels=("任務一鍵領取",))
        for name in ("啟示錄支援通行證", "旅程支援通行證", "聖鎧支援通行證"):
            self.claim_pass(name)
        self.tap("突破通行證", area=LEFT)
        self.task.sleep(.5)
        v = self.see()
        names = [t.text for t in v.within((.035, .25, .17, .75))
                 if "通行证" in t.key and "VOL" in t.key]
        if not names:
            raise NeedsReview("未辨識到突破通行證子分頁")
        for name in names:
            self.claim_pass(name)
        return "三種支援通行證與所有可見突破通行證已檢查"

    def claim_pass(self, name):
        self.tap(name, area=LEFT)
        self.expect(name, area=(.27, .14, .79, .35))
        self.task.sleep(.5)
        self.rewards()
        v = self.see()
        area = (.275, .36, .80, .81)
        targets = v.outline_targets(area, color="yellow")
        targets += v.outline_targets(area, color="blue")
        if targets:
            self.click(sorted(targets, key=lambda t: (t.cy, t.cx))[0])
            self.expect("REWARD", "點擊以繼續")
            self.rewards()
            v = self.see()
            if v.outline_targets(area, color="yellow"):
                raise NeedsReview(f"{name} 領取後仍有亮框，需確認是否已領完")
        tab = v.one(name, area=LEFT)
        if self.red_mark(v, (.155, tab.cy-.04, .17, tab.cy+.015)):
            raise NeedsReview(f"{name} 左側仍有紅點，獎勵尚未確認領完")
