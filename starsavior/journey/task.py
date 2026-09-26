"""Read-only framework task. Uses OK capture/OCR and the existing F9 control."""
import time

from ok import BaseTask
from qfluentwidgets import FluentIcon

from .model import STORE, StableAdvice, load_events, match_event, recognize
from .overlay import game_bounds


class JourneyHelperTask(BaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '跑馬小幫手（困難・預覽版）'
        self.description = '僅支援遊戲簡體中文介面 · 半透明選項效果提示 · 不代選選項'
        self.icon = FluentIcon.INFO
        self._session = None
        self.default_config.update({'背景不透明度': '80%', '提示文字': '繁體'})
        self.config_type.update({
            '背景不透明度': {'type': 'drop_down', 'options': ['60%', '80%', '95%']},
            '提示文字': {'type': 'drop_down', 'options': ['繁體', '简体']},
        })
        self.config_description.update({
            '背景不透明度': '只調整提示背景，文字保持清晰。',
            '提示文字': '只控制浮窗文字；遊戲介面僅支援簡體中文。',
        })
        self.instructions = (
            '先在截圖方式連接遊戲，再進入困難旅程並啟用本任務。\n'
            '僅支援遊戲簡體中文介面；浮窗文字可選繁體或簡體。\n'
            '只提示有選擇分支的事件；卡片收錄 42 筆，來源分支矛盾的事件暫不顯示。\n'
            '不會自動選擇、訓練、購買或消耗資源；直接點擊遊戲即可。\n'
            '浮窗只在遊戲前台顯示。換事件、切換視窗、暫停或停止會隱藏提示。\n'
            '使用任務停止鈕關閉；共用 F9 暫停／繼續，不另設快捷鍵。\n'
            '出現兩個以上選項才讀事件名，不辨識選項文字。\n'
            '同名卡片事件並排顯示，頂部以盾凌／力凌、普夏爾／兔夏爾、婚卡蜜／普卡蜜區分。\n'
            '事件未知、辨識不完整或選項數不符時不顯示效果。\n'
            '效果保留原表術語：體力指跑馬體力，生命指體力屬性。\n'
            '請用視窗或無邊框模式；獨佔全螢幕可能無法顯示。'
        )

    def disable(self):
        if self._session is not None:
            STORE.end(self._session)
        super().disable()

    def run(self):
        data = load_events()
        opacity = self.config.get('背景不透明度', '80%')
        language = self.config.get('提示文字', '繁體')
        if opacity not in ('60%', '80%', '95%') or language not in ('繁體', '简体'):
            raise ValueError('跑馬小幫手設定不符，請重設本任務設定')
        session = self._session = STORE.begin()
        stable = StableAdvice()
        self.info_clear()
        self.info_set('收錄範圍', f"旅程 {len(data['events'])} 筆 · 卡片浮窗 {len(data['card_events'])} 筆")
        try:
            while self.enabled and not self.executor.exit_event.is_set():
                window = self.executor.device_manager.hwnd_window
                hwnd = getattr(window, 'hwnd', 0)
                bounds = game_bounds(hwnd)
                if self.paused or self.executor.paused or not bounds:
                    STORE.publish(session, None)
                    stable = StableAdvice()
                    self.info_set('目前狀態', '等待遊戲回到前台')
                    self.sleep(.4)
                    continue
                frame = self.executor.next_frame(time_out=1)
                if frame is None:
                    STORE.publish(session, None)
                    stable = StableAdvice()
                    self.sleep(.3)
                    continue
                height, width = frame.shape[:2]
                if width < 1280 or not 1.70 < width/height < 1.90:
                    raise ValueError('跑馬小幫手需要寬度至少 1280 的 16:9 遊戲畫面')
                result = match_event(recognize(frame, self.ocr, data), data)
                advice = stable.update(result)
                # Capture must still belong to the same client geometry.
                current = game_bounds(hwnd)
                if current != bounds:
                    advice = None
                    stable = StableAdvice()
                STORE.publish(session, {'task': self, 'hwnd': hwnd, 'size': bounds[2:],
                                       'time': time.monotonic(), 'advice': advice,
                                       'opacity': int(opacity[:-1]), 'language': language})
                self.info_set('目前狀態', result.status if result else '等待旅程事件選項')
                self.sleep(.35)
        finally:
            STORE.end(session)
            self._session = None
