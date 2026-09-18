"""Framework task adapter for the local 案件檔案 solver."""
from functools import partial
import hashlib
import json
from pathlib import Path
import threading

from ok import BaseTask
from ok.task.exceptions import TaskDisabledException
from qfluentwidgets import FluentIcon

from .case_files.session import Session
from .case_files.solver import Runner, Stopped

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = Path(__file__).resolve().parent / "case_files"


def verify_case_assets():
    manifest = json.loads((PACKAGE / "source.json").read_text(encoding="utf-8-sig"))
    for name, expected in manifest["assets"].items():
        path = PACKAGE / "assets" / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"案件檔案資源缺少或版本不符：{name}，請重新安裝完整版本。")


class FrameworkStopEvent:
    """A latched Event backed by OK's F9 pause, task stop, and app exit.

    No executor.sleep here: its pause waits for resume, which would retain a
    stale timed board (or a held mouse button). Cancellation unwinds instead.
    """
    def __init__(self, task):
        self.task = task
        self.event = threading.Event()

    def set(self):
        self.event.set()

    def is_set(self):
        executor = self.task.executor
        if (not self.task.enabled or self.task.paused or executor.paused
                or executor.exit_event.is_set()):
            self.event.set()
        return self.event.is_set()

    def wait(self, seconds):
        return self.event.wait(seconds)


class CaseFilesTask(BaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "案件檔案"
        self.description = "1600 × 900 視窗 · 自動解盤至結算 · F9 停止"
        self.icon = FluentIcon.GAME
        self._cancel = None
        self.default_config.update({"自動重開": False, "使用舊搜尋器": False})
        self.config_description.update({
            "自動重開": "正常結算後等待 2 秒，再開始下一局；不勾選只執行一局。",
            "使用舊搜尋器": "使用 v1.2 搜尋器比較，保留新版倒數、技能觀測與結果驗證。",
        })
        self.instructions = (
            "遊戲內容需為 1600 × 900 視窗模式。先自行進入案件檔案活動首頁，再按開始。\n\n"
            "勾選自動重開時也可從 RESULT 結算頁開始；每局正常結算後等待 2 秒重開。"
            "不勾選時只玩一局，結算即停止，不自動領獎。\n\n"
            "使用 OK 共用啟停快捷鍵（預設 F9），或任務卡的停止按鈕結束操作。"
            "本任務有即時倒數，暫停也會結束本次操作，不能恢復舊棋盤。"
            "切換視窗、移動或調整遊戲視窗、辨識異常也會停止，不搶回焦點。\n\n"
            "每局紀錄位於 runs/case-files。原 v1.4.1 搜尋策略與操作節奏保留，"
            "快速拖曳在整合版仍待實機驗證。"
        )

    def disable(self):
        if self._cancel is not None:
            self._cancel.set()
        super().disable()

    def pause(self):
        if self._cancel is not None:
            self._cancel.set()
        super().pause()

    def on_report(self, event):
        mapping = {"status": "目前狀態", "round": "目前局數", "points": "已驗證消除得分",
                   "moves": "已完成操作", "final_score": "本局結算分數", "session_best": "本次最高分",
                   "completed_rounds": "已完成局數", "log_directory": "本局紀錄"}
        if event.get("round_started"):
            self.info_set("本局結算分數", "尚未結算")
        for source, label in mapping.items():
            if source in event:
                value = event[source]
                self.info_set(label, "未確認" if value is None else value)

    def run(self):
        self.info_clear()
        self._cancel = FrameworkStopEvent(self)
        try:
            verify_case_assets()
            engine = "baseline" if self.config["使用舊搜尋器"] else "native"
            self.info_set("搜尋器", "v1.2 舊搜尋器" if engine == "baseline" else "新版原生搜尋器")
            self.info_set("執行狀態", "執行中")
            session = Session(self._cancel, self.on_report, engine=engine,
                              auto_restart=self.config["自動重開"],
                              runner_factory=partial(Runner, log_root=ROOT / "runs" / "case-files"))
            result = session.run()
            if result != "result":
                raise RuntimeError("案件檔案未確認正常結算，已停止。")
            self.info_set("執行狀態", "本輪已結束")
        except Stopped as error:
            self.info_set("執行狀態", "已停止")
            self.info_set("目前狀態", str(error))
            self.disable()
            # Keep cancellation out of success/auto-exit handling.
            raise TaskDisabledException() from error
        except Exception as error:
            self.info_set("執行狀態", "需檢查")
            self.info_set("目前狀態", str(error))
            raise
        finally:
            self._cancel = None
