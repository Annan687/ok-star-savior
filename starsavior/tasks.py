from ok import BaseTask
from qfluentwidgets import FluentIcon

from .engine import Engine
from .flows import DailyFlows
from .policy import FARM, TIMED, NeedsReview

STEPS = [
    ("登入彈窗", "startup"), ("支援金與免費緊急支援", "support"), ("郵件", "mail"),
    ("好友點數", "friends"), ("付費商店免費禮包", "paid_shop"), ("啟示錄商店", "apocalypse"),
    ("探索委託免費券", "exploration"), ("體力刷關", "stamina"), ("帕萊斯立方", "cube"),
    ("限時據點", "timed"), ("星際迴廊", "corridors"), ("策略戰", "strategy"),
    ("活動襲擊與任務", "event"), ("每日與每週任務", "missions"),
    ("地區派遣", "dispatch"), ("公會", "guild"), ("通行證", "passes"),
]


class InspectTask(BaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "1. 檢查遊戲畫面（不點擊）"
        self.description = "先確認擷取及中文辨識。截圖和辨識結果只儲存在本機。"
        self.icon = FluentIcon.SEARCH
        self.visible = False

    def run(self):
        engine = Engine(self)
        engine.current = "畫面檢查"
        try:
            v = engine.see()
            engine.save("只讀檢查，未操作遊戲")
            self.info_set("擷取尺寸", f"{v.frame.shape[1]} × {v.frame.shape[0]}")
            self.info_set("辨識文字數", len(v.items))
            self.info_set("四格選單圖示", bool(v.menu_icon()))
            self.info_set("畫面", engine.page_name(v))
            self.log_info(f"檢查完成，結果位於 {engine.folder.resolve()}", notify=True)
        except NeedsReview as error:
            engine.record("需檢查", str(error))
            raise


class DailyTask(BaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "2. Star Savior 日課（測試版）"
        self.description = "可由標題畫面進入大廳，支援計劃任務。遇到未識別畫面會停下並留下原因。"
        self.support_schedule_task = True
        self.icon = FluentIcon.SYNC
        self.visible = False
        self.default_config.update({
            "執行項目": [s for s, _ in STEPS],
            "體力刷關": "不消耗體力",
            "限時據點關卡": "略過",
            "活動名稱": "魔女的帷幕",
            "Exit After Task": False,
        })
        self.config_type.update({
            "執行項目": {"type": "multi_selection", "options": [s for s, _ in STEPS]},
            "體力刷關": {"type": "drop_down", "options": ["不消耗體力", *FARM]},
            "限時據點關卡": {"type": "drop_down", "options": ["略過", *TIMED]},
        })
        self.config_description.update({
            "執行項目": "按示範順序執行勾選項目。今日已做完的項目可取消勾選。",
            "體力刷關": "選一種目標，MAX 使用現有意志力；不購買或使用回體道具。探索目標先耗免費券。",
            "限時據點關卡": "選一關使用當日剩餘票券；只在可掃蕩的滿星關卡執行。",
            "活動名稱": "活動列表中的名稱；換活動時需更新。新活動版型仍需實測。",
            "Exit After Task": "全部勾選項目成功結束後，關閉遊戲與 OKSS；失敗或手動停止時不執行。",
        })

    def run(self):
        engine = DailyFlows(self)
        self.info_clear()
        self.info_set("執行狀態", "執行中")
        selected = self.config["執行項目"]
        if not selected:
            raise NeedsReview("尚未勾選任何日課，未執行完成後關閉")
        unknown = set(selected)-{name for name, _ in STEPS}
        if unknown:
            raise NeedsReview(f"未知設定：{unknown}")
        if self.config["體力刷關"] not in ["不消耗體力", *FARM]:
            raise NeedsReview("未知體力刷關選項")
        if self.config["限時據點關卡"] not in ["略過", *TIMED]:
            raise NeedsReview("未知限時據點選項")
        for index, (name, method) in enumerate(STEPS):
            engine.current = name
            if name not in selected:
                engine.record("略過", "未勾選")
                continue
            self.log_info(f"開始：{name}")
            self.info_set("目前項目", name)
            try:
                detail = getattr(engine, method)()
                engine.record("已執行", detail)
            except NeedsReview as error:
                self.info_set("執行狀態", "需要校正")
                engine.save(str(error))
                engine.record("需校正／尚未完成", str(error))
                for pending, _ in STEPS[index+1:]:
                    if pending in selected:
                        engine.current = pending
                        engine.record("尚未執行", f"前一步 {name} 停止")
                self.log_warning(f"停在 {name}：{error}。紀錄：{engine.folder.resolve()}", notify=True)
                raise
            except Exception as error:
                self.info_set("執行狀態", "執行失敗" if self.enabled else "已停止")
                engine.record("執行失敗", f"{type(error).__name__}: {error}")
                raise
        self.info_set("執行狀態", "本輪已結束")
        self.log_info(f"勾選流程已走完，請查看各項結果：{engine.folder.resolve()}", notify=True)
