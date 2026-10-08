"""Discordant Duet navigation from the October event screenshots."""
from .vision import Text

SNOWFIELD_STAGE = "潛伏於雪原之物"
HOME_LINKS = (("故事", (.53, .86, .61, .95)), ("襲擊", (.62, .86, .70, .95)),
              ("任務", (.80, .86, .88, .95)), ("商店", (.89, .86, .97, .95)))


class SnowfieldFlows:
    @staticmethod
    def snowfield_home(v):
        return (v.has("事件", area=(.08, 0, .28, .13), contains=False)
                and v.has("DISCORDANT", area=(.58, .49, .90, .60), contains=False)
                and v.has("DUET", area=(.63, .57, .85, .68), contains=False)
                and v.has("襲擊進度", area=(.59, .76, .69, .83), contains=False)
                and sum(v.has(label, area=area, contains=False) for label, area in HOME_LINKS) >= 2)

    def resolve_snowfield_home(self, v):
        if self.snowfield_home(v):
            return True
        # Decorative title lettering can be misread; never accept that typo.
        if (v.has("事件", area=(.08, 0, .28, .13), contains=False)
                and v.has("DUET", area=(.63, .57, .85, .68), contains=False)
                and v.has("襲擊進度", area=(.59, .76, .69, .83))
                and sum(v.has(label, area=area, contains=False) for label, area in HOME_LINKS) >= 2):
            for scale in (3, 2):
                token = self.reread_claim_button(v, (.61, .507, .873, .589), ("DISCORDANT",), scale=scale)
                if token is not None:
                    v.items.append(token)
                    break
        return self.snowfield_home(v)

    @staticmethod
    def snowfield_card_targets(v):
        return [t for t in v.find("DISCORDANT", area=(.35, .2, .95, .8), contains=False)
                if len([g for g in v.find("DUET", area=(.35, .2, .95, .8), contains=False)
                        if abs(g.cx-t.cx) < .07 and .015 < g.cy-t.cy < .10]) == 1]

    def tap_snowfield_home(self, label, area):
        def ready(page):
            if not self.resolve_event_home(page, "snowfield"):
                return False
            if page.one(label, area=area, required=False) is None:
                crops = {"襲擊": ((.636,.88,.677,.928),),
                         "任務": ((.818,.88,.861,.928), (.822,.881,.864,.929))}[label]
                for crop in crops:
                    for scale in (3, 2):
                        token = self.reread_claim_button(page, crop, (label,), scale=scale)
                        if token is not None:
                            page.items.append(token)
                            return True
            return page.one(label, area=area, required=False) is not None
        v = self.event_wait(ready, f"新活動首頁的{label}入口尚未穩定")
        self.click(v.one(label, area=area))

    def recover_menu_from_event_home(self, v):
        # Falling snow and the bright background obscure the four-square icon.
        # Leave only a fully identified event home via its known back hierarchy.
        if not self.resolve_event_home(v, "snowfield"):
            return False
        self.event_wait(lambda page: self.resolve_event_home(page, "snowfield"),
                        "活動首頁尚未穩定，未返回列表")
        self.click(Text("返回活動列表", .038, .055, .01, .025))
        self.event_wait(lambda page: self.event_navigation_state(page) == "list",
                        "活動首頁返回列表未確認，未重複返回")
        return True

    def snowfield_assault(self):
        if not self.open_event("snowfield"):
            return "事件未開放，略過活動襲擊"
        if self.event_tickets(self.see()) == 0:
            return "活動免費票券已用完"
        self.tap_snowfield_home("襲擊", (.62, .86, .70, .95))
        result = self.event_sweep(SNOWFIELD_STAGE, "snowfield")
        self.click(Text("返回新活動首頁", .038, .05, .01, .025))
        self.event_wait(lambda v: self.resolve_event_home(v, "snowfield"), "掃蕩後未回到新活動首頁")
        return result

    def snowfield_missions(self):
        if not self.open_event("snowfield"):
            return "事件未開放，略過活動任務"
        self.tap_snowfield_home("任務", (.80, .86, .88, .95))
        # The October mission screenshot confirms the existing modal layout.
        self.claim_event_missions()
        self.tap("特殊任務", area=(.46, .20, .59, .30))
        self.claim_event_missions()
        # At 720p the stylized X loses part of its stroke above threshold 200.
        # Keep the shared shape/uniqueness checks and this modal's corner ROI.
        self.close((.81, .20, .85, .26), light_min=180)
        self.event_wait(lambda v: self.resolve_event_home(v, "snowfield"), "領獎後未回到新活動首頁")
        return "活動每日、點數及特殊任務獎勵已檢查"
